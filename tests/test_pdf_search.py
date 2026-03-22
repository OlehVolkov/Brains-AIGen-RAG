from __future__ import annotations

from pathlib import Path

from brain.shared import normalize_text
from brain.sources.pdf import (
    SearchConfig,
    _table_to_markdown,
    format_search_results,
    load_pdf_documents,
    search_pdfs,
)
from brain.config import resolve_pdf_paths


def test_normalize_text_collapses_whitespace() -> None:
    raw = "A   line \n\n\n with\t\tspaces"
    assert normalize_text(raw) == "A line\n with spaces"


def test_table_to_markdown_renders_header_and_rows() -> None:
    table = [["col1", "col2"], ["a", "b"]]
    markdown = _table_to_markdown(table)
    assert "| col1 | col2 |" in markdown
    assert "| a | b |" in markdown


def test_load_pdf_documents_auto_falls_back_to_pdfplumber(monkeypatch, tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    def fail_pymupdf(*args, **kwargs):
        raise RuntimeError("boom")

    def ok_pdfplumber(pdf_path_arg, repo_root_arg):
        return [
            {
                "page_content": "dummy"
            }
        ]

    monkeypatch.setattr("brain.sources.pdf.parsers.load_pdf_with_pymupdf", fail_pymupdf)
    monkeypatch.setattr("brain.sources.pdf.parsers.load_pdf_with_pdfplumber", ok_pdfplumber)

    docs, warnings = load_pdf_documents(
        pdf_path,
        tmp_path,
        parser="auto",
        grobid_url="http://127.0.0.1:8070",
        marker_command="marker_single",
    )

    assert docs == [{"page_content": "dummy"}]
    assert any("fell back to pdfplumber" in warning for warning in warnings)


def test_search_pdfs_falls_back_to_fts_when_embeddings_fail(monkeypatch, tmp_path: Path) -> None:
    paths = resolve_pdf_paths(pdf_dir=tmp_path / "PDF", index_root=tmp_path / "index")

    monkeypatch.setattr("brain.sources.pdf.search.open_table", lambda paths_arg: object())

    def fail_embed(*args, **kwargs):
        raise RuntimeError("ollama unavailable")

    def fake_fts_search(**kwargs):
        return [
            {
                "text": "paper snippet",
                "source_path": "PDF/paper.pdf",
                "page_label": "1",
                "chunk_index": 0,
            }
        ]

    monkeypatch.setattr("brain.sources.pdf.search.embed_query_text", fail_embed)
    monkeypatch.setattr(
        "brain.sources.pdf.search.run_fts_search",
        lambda table, **kwargs: fake_fts_search(**kwargs),
    )

    payload = search_pdfs(
        SearchConfig(
            paths=paths,
            query="alphafold",
            mode="hybrid",
            reranker="none",
        )
    )

    assert payload["effective_mode"] == "fts"
    assert payload["results"][0]["rank"] == 1
    assert any("falling back to FTS search" in warning for warning in payload["warnings"])


def test_search_pdfs_falls_back_when_cross_encoder_fails(monkeypatch, tmp_path: Path) -> None:
    paths = resolve_pdf_paths(pdf_dir=tmp_path / "PDF", index_root=tmp_path / "index")

    monkeypatch.setattr("brain.sources.pdf.search.open_table", lambda paths_arg: object())
    monkeypatch.setattr(
        "brain.sources.pdf.search.embed_query_text",
        lambda *args, **kwargs: [0.1, 0.2],
    )

    calls: list[str] = []

    def fake_hybrid_search(table, **kwargs):
        calls.append(kwargs["reranker"])
        if kwargs["reranker"] == "cross-encoder":
            raise RuntimeError("cpu model load failed")
        return [
            {
                "text": "paper snippet",
                "source_path": "PDF/paper.pdf",
                "page_label": "1",
                "chunk_index": 0,
            }
        ]

    monkeypatch.setattr("brain.sources.pdf.search.run_hybrid_search", fake_hybrid_search)

    payload = search_pdfs(
        SearchConfig(
            paths=paths,
            query="alphafold",
            mode="hybrid",
            reranker="cross-encoder",
        )
    )

    assert calls == ["cross-encoder", "rrf"]
    assert payload["effective_reranker"] == "rrf"
    assert any("Cross-encoder reranking failed" in warning for warning in payload["warnings"])


def test_format_search_results_renders_warnings_and_hits() -> None:
    rendered = format_search_results(
        {
            "warnings": ["fallback used"],
            "results": [
                {
                    "rank": 1,
                    "source_path": "PDF/paper.pdf",
                    "page_label": "3",
                    "chunk_index": 2,
                    "snippet": "protein folding",
                }
            ],
        }
    )
    assert "Fallbacks:" in rendered
    assert "PDF/paper.pdf" in rendered
    assert "protein folding" in rendered
