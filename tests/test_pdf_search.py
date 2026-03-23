from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document

from brains.shared.preprocessing import clean_pdf_documents
from brains.shared import normalize_text
from brains.sources.pdf import (
    SearchConfig,
    _table_to_markdown,
    format_search_results,
    load_pdf_documents,
    search_pdfs,
)
from brains.sources.pdf.chunking import chunk_pdf_blocks
from brains.sources.pdf.structured import extract_pdf_blocks
from brains.config import resolve_pdf_paths


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

    monkeypatch.setattr("brains.sources.pdf.parsers.load_pdf_with_pymupdf", fail_pymupdf)
    monkeypatch.setattr("brains.sources.pdf.parsers.load_pdf_with_pdfplumber", ok_pdfplumber)

    docs, warnings = load_pdf_documents(
        pdf_path,
        tmp_path,
        parser="auto",
        grobid_url="http://127.0.0.1:8070",
        marker_command="marker_single",
    )

    assert docs == [{"page_content": "dummy"}]
    assert any("fell back to pdfplumber" in warning for warning in warnings)


def test_load_pdf_documents_supports_docling_parser(monkeypatch, tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    monkeypatch.setattr(
        "brains.sources.pdf.parsers.load_pdf_with_docling",
        lambda pdf_path_arg, repo_root_arg: [{"page_content": "# Title\n\nBody"}],
    )

    docs, warnings = load_pdf_documents(
        pdf_path,
        tmp_path,
        parser="docling",
        grobid_url="http://127.0.0.1:8070",
        marker_command="marker_single",
    )

    assert docs == [{"page_content": "# Title\n\nBody"}]
    assert warnings == []


def test_clean_pdf_documents_removes_repeated_header_and_footer_lines() -> None:
    documents = [
        Document(
            page_content="Conference 2026\nPaper Title\nBody page one\n1",
            metadata={"page": 1, "page_label": "1"},
        ),
        Document(
            page_content="Conference 2026\nPaper Title\nBody page two\n2",
            metadata={"page": 2, "page_label": "2"},
        ),
    ]

    cleaned, warnings = clean_pdf_documents(documents)

    assert [doc.page_content for doc in cleaned] == ["Body page one", "Body page two"]
    assert any("Removed 6 repeated PDF boilerplate lines" in warning for warning in warnings)


def test_extract_pdf_blocks_excludes_references_and_keeps_section_hierarchy() -> None:
    documents = [
        Document(
            page_content=(
                "Great Paper Title\n"
                "Alice Smith, Bob Jones\n"
                "Published 2023\n\n"
                "Abstract\n"
                "We study retrieval (Smith et al., 2020) and chunking [1].\n\n"
                "1 Introduction\n"
                "Intro paragraph.\n\n"
                "1.1 Methods\n"
                "Method paragraph.\n\n"
                "References\n"
                "[1] Hidden reference text."
            ),
            metadata={
                "source_path": "PDF/paper.pdf",
                "source_file": "paper.pdf",
                "page": 1,
                "page_label": "1",
                "parser": "pymupdf",
            },
        )
    ]

    blocks, warnings = extract_pdf_blocks(documents)

    assert [block.metadata["block_kind"] for block in blocks] == ["abstract", "paragraph", "paragraph"]
    assert blocks[0].metadata["title"] == "Great Paper Title"
    assert blocks[0].metadata["authors"] == ["Alice Smith", "Bob Jones"]
    assert blocks[0].metadata["year"] == 2023
    assert blocks[1].metadata["section_path"] == "Introduction"
    assert blocks[2].metadata["section_path"] == "Introduction > Methods"
    assert "Smith et al., 2020" not in blocks[0].page_content
    assert "[1]" not in blocks[0].page_content
    assert all("Hidden reference text" not in block.page_content for block in blocks)
    assert any("Excluded" in warning for warning in warnings)


def test_chunk_pdf_blocks_preserves_table_block_and_context_metadata() -> None:
    blocks = [
        Document(
            page_content="Intro paragraph.",
            metadata={
                "source_path": "PDF/paper.pdf",
                "source_file": "paper.pdf",
                "page": 1,
                "page_label": "1",
                "parser": "pymupdf",
                "title": "Great Paper Title",
                "authors": ["Alice Smith"],
                "year": 2023,
                "section": "Methods",
                "section_level": 1,
                "section_path": "Methods",
                "block_kind": "paragraph",
                "block_index": 0,
            },
        ),
        Document(
            page_content="| col1 | col2 |\n| --- | --- |\n| a | b |",
            metadata={
                "source_path": "PDF/paper.pdf",
                "source_file": "paper.pdf",
                "page": 1,
                "page_label": "1",
                "parser": "pdfplumber",
                "title": "Great Paper Title",
                "authors": ["Alice Smith"],
                "year": 2023,
                "section": "Methods",
                "section_level": 1,
                "section_path": "Methods",
                "block_kind": "table",
                "block_index": 1,
            },
        ),
    ]

    chunks = chunk_pdf_blocks(blocks, chunk_size=500, chunk_overlap=80)

    assert len(chunks) == 1
    assert chunks[0].metadata["section_path"] == "Methods"
    assert chunks[0].metadata["chunk_kind"] == "mixed"
    assert "Great Paper Title | Methods" in chunks[0].page_content
    assert "Table" in chunks[0].page_content
    assert "| col1 | col2 |" in chunks[0].page_content


def test_search_pdfs_falls_back_to_fts_when_embeddings_fail(monkeypatch, tmp_path: Path) -> None:
    paths = resolve_pdf_paths(pdf_dir=tmp_path / "PDF", index_root=tmp_path / "index")

    monkeypatch.setattr("brains.sources.pdf.search.open_table", lambda paths_arg: object())

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

    monkeypatch.setattr("brains.sources.pdf.search.embed_query_text", fail_embed)
    monkeypatch.setattr(
        "brains.sources.pdf.search.run_fts_search",
        lambda table, **kwargs: fake_fts_search(**kwargs),
    )

    payload = search_pdfs(
        SearchConfig(
            paths=paths,
            query="knowledge retrieval",
            mode="hybrid",
            reranker="none",
        )
    )

    assert payload["effective_mode"] == "fts"
    assert payload["results"][0]["rank"] == 1
    assert any("falling back to FTS search" in warning for warning in payload["warnings"])


def test_search_pdfs_falls_back_when_cross_encoder_fails(monkeypatch, tmp_path: Path) -> None:
    paths = resolve_pdf_paths(pdf_dir=tmp_path / "PDF", index_root=tmp_path / "index")

    monkeypatch.setattr("brains.sources.pdf.search.open_table", lambda paths_arg: object())
    monkeypatch.setattr(
        "brains.sources.pdf.search.embed_query_text",
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

    monkeypatch.setattr("brains.sources.pdf.search.run_hybrid_search", fake_hybrid_search)

    payload = search_pdfs(
        SearchConfig(
            paths=paths,
            query="knowledge retrieval",
            mode="hybrid",
            reranker="cross-encoder",
        )
    )

    assert calls == ["cross-encoder", "rrf"]
    assert payload["effective_reranker"] == "rrf"
    assert any("Cross-encoder reranking failed" in warning for warning in payload["warnings"])


def test_search_pdfs_uses_fetch_k_for_hybrid_rrf_candidates(monkeypatch, tmp_path: Path) -> None:
    paths = resolve_pdf_paths(pdf_dir=tmp_path / "PDF", index_root=tmp_path / "index")

    monkeypatch.setattr("brains.sources.pdf.search.open_table", lambda paths_arg: object())
    monkeypatch.setattr(
        "brains.sources.pdf.search.embed_query_text",
        lambda *args, **kwargs: [0.1, 0.2],
    )

    captured: dict[str, int] = {}

    def fake_hybrid_search(table, **kwargs):
        captured["fetch_limit"] = kwargs["fetch_limit"]
        return [
            {
                "text": "paper snippet",
                "source_path": "PDF/paper.pdf",
                "page_label": "1",
                "chunk_index": 0,
            }
        ]

    monkeypatch.setattr("brains.sources.pdf.search.run_hybrid_search", fake_hybrid_search)

    payload = search_pdfs(
        SearchConfig(
            paths=paths,
            query="knowledge retrieval",
            mode="hybrid",
            reranker="none",
            k=3,
            fetch_k=11,
        )
    )

    assert payload["effective_reranker"] == "rrf"
    assert captured["fetch_limit"] == 11


def test_search_pdfs_auto_mode_routes_exact_match_queries_to_fts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths = resolve_pdf_paths(pdf_dir=tmp_path / "PDF", index_root=tmp_path / "index")
    captured: dict[str, object] = {}

    monkeypatch.setattr("brains.sources.pdf.search.open_table", lambda paths_arg: object())

    def fail_embed(*args, **kwargs):
        raise AssertionError("auto-routed FTS search should not embed the query")

    def fake_fts_search(**kwargs):
        captured["fetch_limit"] = kwargs["fetch_limit"]
        return [
            {
                "text": "paper snippet",
                "source_path": "PDF/paper.pdf",
                "page_label": "1",
                "chunk_index": 0,
            }
        ]

    monkeypatch.setattr("brains.sources.pdf.search.embed_query_text", fail_embed)
    monkeypatch.setattr(
        "brains.sources.pdf.search.run_fts_search",
        lambda table, **kwargs: fake_fts_search(**kwargs),
    )

    payload = search_pdfs(
        SearchConfig(
            paths=paths,
            query='"GraphRAG.pdf"',
            mode="auto",
            reranker="none",
        )
    )

    assert payload["effective_mode"] == "fts"
    assert captured["fetch_limit"] == 5
    assert any("Auto mode chose FTS" in warning for warning in payload["warnings"])


def test_search_pdfs_applies_distance_threshold(monkeypatch, tmp_path: Path) -> None:
    paths = resolve_pdf_paths(pdf_dir=tmp_path / "PDF", index_root=tmp_path / "index")

    monkeypatch.setattr("brains.sources.pdf.search.open_table", lambda paths_arg: object())
    monkeypatch.setattr(
        "brains.sources.pdf.search.embed_query_text",
        lambda *args, **kwargs: [0.1, 0.2],
    )
    monkeypatch.setattr(
        "brains.sources.pdf.search.run_vector_search",
        lambda table, **kwargs: [
            {
                "text": "strong hit",
                "source_path": "PDF/good.pdf",
                "page_label": "1",
                "chunk_index": 0,
                "_distance": 0.12,
            },
            {
                "text": "weak hit",
                "source_path": "PDF/weak.pdf",
                "page_label": "2",
                "chunk_index": 1,
                "_distance": 0.91,
            },
        ],
    )

    payload = search_pdfs(
        SearchConfig(
            paths=paths,
            query="knowledge retrieval",
            mode="vector",
            reranker="none",
            max_distance=0.5,
        )
    )

    assert [row["source_path"] for row in payload["results"]] == ["PDF/good.pdf"]
    assert any("Filtered 1 distant hits" in warning for warning in payload["warnings"])


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
