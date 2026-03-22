from __future__ import annotations

import io
import json
from pathlib import Path

from brain.sources.pdf import fetch as pdf_fetch
from brain.sources.pdf.indexing import pointer_manifest_path, write_active_index_pointer
from brain.sources.pdf.models import IndexConfig
from brain.config import BrainPaths


class FakeResponse(io.BytesIO):
    def __init__(self, payload: bytes, *, url: str, headers: dict[str, str] | None = None) -> None:
        super().__init__(payload)
        self._url = url
        self.headers = headers or {}

    def geturl(self) -> str:
        return self._url

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def make_paths(tmp_path: Path) -> BrainPaths:
    repo_root = tmp_path
    brain_root = repo_root / ".brain"
    index_root = brain_root / ".index" / "pdf_search"
    return BrainPaths(
        repo_root=repo_root,
        brain_root=brain_root,
        pdf_dir=repo_root / "PDF",
        index_root=index_root,
        db_uri=index_root / "lancedb",
        manifest_path=index_root / "manifest.json",
        table_name="scientific_pdf_chunks",
    )


def make_index_config(paths: BrainPaths) -> IndexConfig:
    return IndexConfig(
        paths=paths,
        parser="auto",
        grobid_url="http://127.0.0.1:8070",
        marker_command="marker_single",
        embed_model="nomic-embed-text",
        ollama_base_url="http://127.0.0.1:11434",
        chunk_size=1200,
        chunk_overlap=200,
        batch_size=32,
        overwrite=True,
    )


def test_extract_http_urls_handles_markdown_and_bare_links() -> None:
    text = """
See [paper](https://example.org/paper.pdf).
Mirror: https://example.org/paper.pdf
Landing page: https://arxiv.org/abs/2401.00001).
"""

    urls = pdf_fetch.extract_http_urls(text)

    assert urls == [
        "https://example.org/paper.pdf",
        "https://arxiv.org/abs/2401.00001",
    ]


def test_extract_http_urls_keeps_doi_urls_with_parentheses() -> None:
    text = "[doi](https://doi.org/10.1016/0022-2836(70)90057-4)"

    urls = pdf_fetch.extract_http_urls(text)

    assert urls == ["https://doi.org/10.1016/0022-2836(70)90057-4"]


def test_list_source_note_paths_defaults_to_literature_notes(tmp_path: Path) -> None:
    (tmp_path / "EN").mkdir()
    (tmp_path / "UA").mkdir()
    (tmp_path / "EN" / "Literature and Priorities.md").write_text("x", encoding="utf-8")
    (tmp_path / "UA" / "Література та пріоритети.md").write_text("y", encoding="utf-8")

    paths = pdf_fetch.list_source_note_paths(tmp_path)

    assert [path.relative_to(tmp_path).as_posix() for path in paths] == [
        "EN/Literature and Priorities.md",
        "UA/Література та пріоритети.md",
    ]


def test_fetch_pdf_url_uses_arxiv_pdf_candidate_and_downloads_file(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths = make_paths(tmp_path)
    requested_urls: list[str] = []

    def fake_urlopen(request_obj, timeout: int):
        requested_urls.append(request_obj.full_url)
        assert timeout == 9
        if request_obj.full_url == "https://arxiv.org/abs/2401.00001":
            return FakeResponse(
                b"<html><head></head><body>landing</body></html>",
                url=request_obj.full_url,
                headers={"Content-Type": "text/html; charset=utf-8"},
            )
        return FakeResponse(
            b"%PDF-1.7 demo",
            url="https://arxiv.org/pdf/2401.00001.pdf",
            headers={
                "Content-Type": "application/pdf",
                "Content-Disposition": 'attachment; filename="af3-paper.pdf"',
            },
        )

    monkeypatch.setattr(pdf_fetch.request, "urlopen", fake_urlopen)

    result = pdf_fetch.fetch_pdf_url(
        source_url="https://arxiv.org/abs/2401.00001",
        source_notes=["EN/Literature and Priorities.md"],
        paths=paths,
        timeout=9,
    )

    assert requested_urls == [
        "https://arxiv.org/abs/2401.00001",
        "https://arxiv.org/pdf/2401.00001.pdf",
    ]
    assert result["status"] == "downloaded"
    assert result["saved_path"] == "PDF/af3-paper.pdf"
    assert (tmp_path / "PDF" / "af3-paper.pdf").read_bytes() == b"%PDF-1.7 demo"


def test_candidate_pdf_urls_expands_arxiv_doi() -> None:
    urls = pdf_fetch.candidate_pdf_urls("https://doi.org/10.48550/arXiv.2006.11239")

    assert "https://arxiv.org/abs/2006.11239" in urls
    assert "https://arxiv.org/pdf/2006.11239.pdf" in urls


def test_extract_pdf_urls_from_html_reads_meta_and_relative_links() -> None:
    html = """
    <html>
      <head>
        <meta name="citation_pdf_url" content="/content/pdf/main.pdf">
      </head>
      <body>
        <a href="/downloads/supplement.pdf">PDF</a>
      </body>
    </html>
    """

    urls = pdf_fetch.extract_pdf_urls_from_html(html, base_url="https://example.org/article")

    assert urls == [
        "https://example.org/content/pdf/main.pdf",
        "https://example.org/downloads/supplement.pdf",
    ]


def test_fetch_pdf_url_follows_html_landing_page_to_pdf(monkeypatch, tmp_path: Path) -> None:
    paths = make_paths(tmp_path)

    def fake_urlopen(request_obj, timeout: int):
        url = request_obj.full_url
        if url == "https://doi.org/10.1234/example":
            return FakeResponse(
                b'<html><meta name="citation_pdf_url" content="https://publisher.org/paper.pdf"></html>',
                url="https://publisher.org/article",
                headers={"Content-Type": "text/html; charset=utf-8"},
            )
        if url == "https://publisher.org/paper.pdf":
            return FakeResponse(
                b"%PDF-1.7 full",
                url=url,
                headers={"Content-Type": "application/pdf"},
            )
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(pdf_fetch.request, "urlopen", fake_urlopen)

    result = pdf_fetch.fetch_pdf_url(
        source_url="https://doi.org/10.1234/example",
        source_notes=["EN/Literature and Priorities.md"],
        paths=paths,
    )

    assert result["status"] == "downloaded"
    assert result["resolved_url"] == "https://publisher.org/paper.pdf"
    assert result["attempts"][0]["status"] == "not_pdf"


def test_fetch_pdfs_from_notes_writes_manifest_and_supports_dry_run(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths = make_paths(tmp_path)
    note_path = tmp_path / "EN" / "Literature and Priorities.md"
    note_path.parent.mkdir(parents=True)
    note_path.write_text(
        "[pdf](https://example.org/paper.pdf)\nhttps://example.org/landing-page\n",
        encoding="utf-8",
    )

    def fake_urlopen(request_obj, timeout: int):
        url = request_obj.full_url
        if url.endswith("paper.pdf"):
            return FakeResponse(
                b"",
                url=url,
                headers={"Content-Type": "application/pdf"},
            )
        return FakeResponse(
            b"<html></html>",
            url=url,
            headers={"Content-Type": "text/html"},
        )

    monkeypatch.setattr(pdf_fetch.request, "urlopen", fake_urlopen)

    result = pdf_fetch.fetch_pdfs_from_notes(
        paths,
        note_globs=["EN/Literature and Priorities.md"],
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["downloadable_count"] == 1
    assert result["failed_count"] == 1
    manifest = json.loads((paths.index_root / "fetch_manifest.json").read_text(encoding="utf-8"))
    assert manifest["requested_url_count"] == 2
    assert manifest["results"][0]["status"] == "downloadable"
    assert manifest["results"][1]["status"] == "failed"


def test_write_active_index_pointer_for_fallback_index(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    fallback_root = tmp_path / "tmp-index"
    fallback_paths = BrainPaths(
        repo_root=paths.repo_root,
        brain_root=paths.brain_root,
        pdf_dir=paths.pdf_dir,
        index_root=fallback_root,
        db_uri=fallback_root / "lancedb",
        manifest_path=fallback_root / "manifest.json",
        table_name=paths.table_name,
    )
    config = make_index_config(fallback_paths)

    pointer_path = write_active_index_pointer(
        config,
        {
            "pdf_count": 11,
            "chunk_count": 855,
        },
    )

    assert pointer_path == tmp_path / ".brain" / ".index" / "pdf_search" / "active_index.json"
    payload = json.loads(pointer_path.read_text(encoding="utf-8"))
    assert payload["index_root"] == str(fallback_root)
    assert payload["db_uri"] == str(fallback_root / "lancedb")
    assert payload["manifest_path"] == str(fallback_root / "manifest.json")


def test_write_active_index_pointer_removed_for_default_index(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    config = make_index_config(paths)
    default_pointer = pointer_manifest_path(config)
    default_pointer.parent.mkdir(parents=True, exist_ok=True)
    default_pointer.write_text("stale\n", encoding="utf-8")

    pointer_path = write_active_index_pointer(
        config,
        {
            "pdf_count": 1,
            "chunk_count": 2,
        },
    )

    assert pointer_path is None
    assert not default_pointer.exists()
