from __future__ import annotations

from pathlib import Path

from brains.config import resolve_vault_paths
from brains.sources.vault import (
    VaultSearchConfig,
    format_vault_search_results,
    list_markdown_paths,
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
    assert "Overview paragraph." in sections[0][2]
    assert sections[1][0] == "Blocks"


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
