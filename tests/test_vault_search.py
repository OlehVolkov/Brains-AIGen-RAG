from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document

from brains.config import resolve_vault_paths
from brains.shared.preprocessing import clean_markdown_text
from brains.sources.vault import (
    VaultSearchConfig,
    chunk_markdown_blocks,
    extract_markdown_blocks,
    format_vault_search_results,
    list_markdown_paths,
    parse_markdown_documents,
    resolve_markdown_parser,
    search_vault,
    split_markdown_sections,
)


def test_list_markdown_paths_skips_tooling_and_pdf_dirs(tmp_path: Path) -> None:
    (tmp_path / "Home.md").write_text("# Home\n", encoding="utf-8")
    (tmp_path / "UA").mkdir()
    (tmp_path / "UA" / "Індекс.md").write_text("# Індекс\n", encoding="utf-8")
    (tmp_path / "EN").mkdir()
    (tmp_path / "EN" / "Index.md").write_text("# Index\n", encoding="utf-8")
    (tmp_path / ".brains").mkdir()
    (tmp_path / ".brains" / "README.md").write_text("# Hidden\n", encoding="utf-8")
    (tmp_path / "PDF").mkdir()
    (tmp_path / "PDF" / "paper.md").write_text("# Not for vault search\n", encoding="utf-8")

    paths = [path.relative_to(tmp_path).as_posix() for path in list_markdown_paths(tmp_path)]

    assert paths == ["EN/Index.md", "Home.md", "UA/Індекс.md"]


def test_split_markdown_sections_strips_frontmatter_and_extracts_headings() -> None:
    markdown = """---
cssclasses: [note]
---

# Pairformer

Overview paragraph.

## Blocks

Details here.
"""
    sections = split_markdown_sections(markdown)

    assert sections[0][0] == "Pairformer"
    assert sections[0][1] == 1
    assert sections[1][2] == "Pairformer > Blocks"
    assert "Overview paragraph." in sections[0][3]
    assert sections[1][0] == "Blocks"


def test_clean_markdown_text_removes_navigation_lines_and_related_links_section() -> None:
    markdown = """[[Home]] > [[Research]] > [[Pairformer]]

# Pairformer

Overview paragraph.

## Related Notes

- [[Alpha]]
- [[Beta]]

## Blocks

Details here.
"""
    cleaned = clean_markdown_text(markdown)

    assert "[[Home]] > [[Research]] > [[Pairformer]]" not in cleaned
    assert "## Related Notes" not in cleaned
    assert "[[Alpha]]" not in cleaned
    assert "# Pairformer" in cleaned
    assert "## Blocks" in cleaned


def test_resolve_markdown_parser_auto_prefers_docling_for_rich_scientific_notes() -> None:
    parser, warning = resolve_markdown_parser(
        """# Pairformer

| Metric | Value |
| --- | --- |
| Score | 0.8 |

```mermaid
graph TD
  A --> B
```
""",
        requested_parser="auto",
    )

    assert parser == "docling"
    assert warning is not None


def test_parse_markdown_documents_supports_docling_parser(monkeypatch, tmp_path: Path) -> None:
    note_path = tmp_path / "EN" / "Pairformer.md"
    note_path.parent.mkdir(parents=True)
    note_path.write_text("# Pairformer\n\nBody.\n", encoding="utf-8")

    monkeypatch.setattr(
        "brains.sources.vault.parsers.load_markdown_with_docling",
        lambda markdown_path, repo_root: [
            Document(
                page_content="Pairformer\n\nDocling body.",
                metadata={
                    "source_path": "EN/Pairformer.md",
                    "source_file": "Pairformer.md",
                    "page": 0,
                    "page_label": "md",
                    "title": "Pairformer",
                    "section": "Pairformer",
                    "section_path": "Pairformer",
                    "heading_level": 1,
                    "language_branch": "EN",
                    "parser": "docling",
                },
            )
        ],
    )

    result = parse_markdown_documents(note_path, tmp_path, parser="docling")

    assert result.parser == "docling"
    assert result.documents[0].metadata["parser"] == "docling"


def test_chunk_markdown_blocks_preserves_formula_and_table_context() -> None:
    blocks, _warnings = extract_markdown_blocks(
        [
            Document(
                page_content=(
                    "Pairformer\n\n"
                    "Overview paragraph.\n\n"
                    "$$\n"
                    "x = y + z\n"
                    "$$\n\n"
                    "| Metric | Value |\n"
                    "| --- | --- |\n"
                    "| Score | 0.8 |"
                ),
                metadata={
                    "source_path": "EN/Pairformer.md",
                    "source_file": "Pairformer.md",
                    "page": 0,
                    "page_label": "md",
                    "title": "Pairformer",
                    "section": "Methods",
                    "section_path": "Pairformer > Methods",
                    "heading_level": 2,
                    "language_branch": "EN",
                    "parser": "docling",
                },
            )
        ]
    )

    chunked = chunk_markdown_blocks(blocks, chunk_size=500, chunk_overlap=50)

    assert len(chunked) == 1
    assert chunked[0].metadata["chunk_kind"] == "mixed"
    assert "Formula" in chunked[0].page_content
    assert "Table" in chunked[0].page_content
    assert "Pairformer | Pairformer > Methods" in chunked[0].page_content


def test_chunk_markdown_blocks_splits_oversized_code_block() -> None:
    code_lines = "\n".join(f"print({index})" for index in range(80))
    blocks, _warnings = extract_markdown_blocks(
        [
            Document(
                page_content=(
                    "```python\n"
                    f"{code_lines}\n"
                    "```"
                ),
                metadata={
                    "source_path": "EN/Pairformer.md",
                    "source_file": "Pairformer.md",
                    "page": 0,
                    "page_label": "md",
                    "title": "Pairformer",
                    "section": "Implementation",
                    "section_path": "Pairformer > Implementation",
                    "heading_level": 2,
                    "language_branch": "EN",
                    "parser": "native",
                },
            )
        ]
    )

    chunked = chunk_markdown_blocks(blocks, chunk_size=220, chunk_overlap=40)

    assert len(chunked) > 1
    assert all(doc.metadata["chunk_kind"] == "code_block" for doc in chunked)
    assert all("Pairformer | Pairformer > Implementation" in doc.page_content for doc in chunked)
    assert max(doc.metadata["char_count"] for doc in chunked) < 320


def test_extract_markdown_blocks_excludes_references_and_marks_abstract() -> None:
    blocks, warnings = extract_markdown_blocks(
        [
            Document(
                page_content="Abstract\n\nThis note summarizes the paper.",
                metadata={
                    "source_path": "EN/Pairformer.md",
                    "source_file": "Pairformer.md",
                    "page": 0,
                    "page_label": "md",
                    "title": "Pairformer",
                    "section": "Abstract",
                    "section_path": "Pairformer > Abstract",
                    "heading_level": 1,
                    "language_branch": "EN",
                    "parser": "native",
                },
            ),
            Document(
                page_content="References\n\n- Smith et al. 2024",
                metadata={
                    "source_path": "EN/Pairformer.md",
                    "source_file": "Pairformer.md",
                    "page": 0,
                    "page_label": "md",
                    "title": "Pairformer",
                    "section": "References",
                    "section_path": "Pairformer > References",
                    "heading_level": 1,
                    "language_branch": "EN",
                    "parser": "native",
                },
            ),
        ]
    )

    assert [block.metadata["block_kind"] for block in blocks] == ["abstract"]
    assert any("Excluded 1 markdown reference sections" in warning for warning in warnings)


def test_extract_markdown_blocks_detects_figure_caption() -> None:
    blocks, _warnings = extract_markdown_blocks(
        [
            Document(
                page_content="Figure 1: Pair update mechanism",
                metadata={
                    "source_path": "EN/Pairformer.md",
                    "source_file": "Pairformer.md",
                    "page": 0,
                    "page_label": "md",
                    "title": "Pairformer",
                    "section": "Methods",
                    "section_path": "Pairformer > Methods",
                    "heading_level": 2,
                    "language_branch": "EN",
                    "parser": "native",
                },
            )
        ]
    )

    assert [block.metadata["block_kind"] for block in blocks] == ["figure_caption"]


def test_extract_markdown_blocks_handles_untyped_fenced_code_block() -> None:
    blocks, _warnings = extract_markdown_blocks(
        [
            Document(
                page_content=(
                    "Methods\n\n"
                    "```\n"
                    "plain code block\n"
                    "```\n"
                ),
                metadata={
                    "source_path": "EN/Pairformer.md",
                    "source_file": "Pairformer.md",
                    "page": 0,
                    "page_label": "md",
                    "title": "Pairformer",
                    "section": "Methods",
                    "section_path": "Pairformer > Methods",
                    "heading_level": 2,
                    "language_branch": "EN",
                    "parser": "native",
                },
            )
        ]
    )

    assert [block.metadata["block_kind"] for block in blocks] == ["code_block"]
    assert "plain code block" in blocks[0].page_content


def test_search_vault_falls_back_to_fts_when_embeddings_fail(monkeypatch, tmp_path: Path) -> None:
    paths = resolve_vault_paths(index_root=tmp_path / "index")

    monkeypatch.setattr("brains.sources.vault.search.open_table", lambda paths_arg: object())

    def fail_embed(*args, **kwargs):
        raise RuntimeError("ollama unavailable")

    def fake_fts_search(**kwargs):
        return [
            {
                "text": "knowledge snippet",
                "source_path": "EN/Research/Architecture/Pairformer.md",
                "section": "Pairformer",
                "language_branch": "EN",
                "chunk_index": 0,
            }
        ]

    monkeypatch.setattr("brains.sources.vault.search.embed_query_text", fail_embed)
    monkeypatch.setattr(
        "brains.sources.vault.search.run_fts_search",
        lambda table, **kwargs: fake_fts_search(**kwargs),
    )

    payload = search_vault(
        VaultSearchConfig(
            paths=paths,
            query="pairformer",
            mode="hybrid",
            reranker="none",
        )
    )

    assert payload["effective_mode"] == "fts"
    assert payload["results"][0]["rank"] == 1
    assert any("falling back to FTS search" in warning for warning in payload["warnings"])


def test_format_vault_search_results_renders_sections_and_hits() -> None:
    rendered = format_vault_search_results(
        {
            "warnings": ["fallback used"],
            "results": [
                {
                    "rank": 1,
                    "source_path": "UA/Research/Architecture/Pairformer.md",
                    "language_branch": "UA",
                    "section": "Pairformer",
                    "chunk_index": 2,
                    "snippet": "protein pair update",
                }
            ],
        }
    )
    assert "Fallbacks:" in rendered
    assert "section=Pairformer" in rendered
    assert "protein pair update" in rendered


def test_search_vault_uses_fetch_k_for_cross_encoder_candidates(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths = resolve_vault_paths(index_root=tmp_path / "index")

    monkeypatch.setattr("brains.sources.vault.search.open_table", lambda paths_arg: object())
    monkeypatch.setattr(
        "brains.sources.vault.search.embed_query_text",
        lambda *args, **kwargs: [0.1, 0.2],
    )

    captured: dict[str, int] = {}

    def fake_vector_search(table, **kwargs):
        captured["fetch_limit"] = kwargs["fetch_limit"]
        return [
            {
                "text": "knowledge snippet",
                "source_path": "EN/Research/Architecture/Pairformer.md",
                "section": "Pairformer",
                "language_branch": "EN",
                "chunk_index": 0,
            }
        ]

    monkeypatch.setattr("brains.sources.vault.search.run_vector_search", fake_vector_search)

    payload = search_vault(
        VaultSearchConfig(
            paths=paths,
            query="pairformer",
            mode="vector",
            reranker="cross-encoder",
            k=2,
            fetch_k=9,
        )
    )

    assert payload["effective_reranker"] == "cross-encoder"
    assert captured["fetch_limit"] == 9


def test_search_vault_auto_mode_routes_path_queries_to_fts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths = resolve_vault_paths(index_root=tmp_path / "index")

    monkeypatch.setattr("brains.sources.vault.search.open_table", lambda paths_arg: object())

    def fail_embed(*args, **kwargs):
        raise AssertionError("auto-routed FTS search should not embed the query")

    def fake_fts_search(**kwargs):
        return [
            {
                "text": "knowledge snippet",
                "source_path": "EN/Research/Architecture/Pairformer.md",
                "section": "Pairformer",
                "language_branch": "EN",
                "chunk_index": 0,
            }
        ]

    monkeypatch.setattr("brains.sources.vault.search.embed_query_text", fail_embed)
    monkeypatch.setattr(
        "brains.sources.vault.search.run_fts_search",
        lambda table, **kwargs: fake_fts_search(**kwargs),
    )

    payload = search_vault(
        VaultSearchConfig(
            paths=paths,
            query="EN/Research/Architecture/Pairformer.md",
            mode="auto",
            reranker="none",
        )
    )

    assert payload["effective_mode"] == "fts"
    assert any("Auto mode chose FTS" in warning for warning in payload["warnings"])


def test_search_vault_applies_min_score_threshold(monkeypatch, tmp_path: Path) -> None:
    paths = resolve_vault_paths(index_root=tmp_path / "index")

    monkeypatch.setattr("brains.sources.vault.search.open_table", lambda paths_arg: object())
    monkeypatch.setattr(
        "brains.sources.vault.search.embed_query_text",
        lambda *args, **kwargs: [0.1, 0.2],
    )
    monkeypatch.setattr(
        "brains.sources.vault.search.run_hybrid_search",
        lambda table, **kwargs: [
            {
                "text": "strong hit",
                "source_path": "EN/Research/Architecture/Pairformer.md",
                "section": "Pairformer",
                "language_branch": "EN",
                "chunk_index": 0,
                "_score": 0.82,
            },
            {
                "text": "weak hit",
                "source_path": "EN/Research/Architecture/Weak.md",
                "section": "Weak",
                "language_branch": "EN",
                "chunk_index": 1,
                "_score": 0.22,
            },
        ],
    )

    payload = search_vault(
        VaultSearchConfig(
            paths=paths,
            query="pairformer",
            mode="hybrid",
            reranker="none",
            min_score=0.5,
        )
    )

    assert [row["source_path"] for row in payload["results"]] == [
        "EN/Research/Architecture/Pairformer.md"
    ]
    assert any("Filtered 1 low-score hits" in warning for warning in payload["warnings"])
