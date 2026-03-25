from __future__ import annotations

from pathlib import Path

from brains.config import (
    BrainsPaths,
    GraphPaths,
    load_config,
    resolve_graph_paths,
    resolve_pdf_paths,
    resolve_research_paths,
    resolve_vault_paths,
)
from brains.sources.graph.models import GraphIndexConfig, GraphSearchConfig
from brains.sources.pdf.models import IndexConfig, SearchConfig
from brains.research.models import ResearchRunConfig
from brains.sources.vault.models import VaultIndexConfig, VaultSearchConfig


def test_load_config_merges_base_local_and_env(monkeypatch, tmp_path: Path) -> None:
    base = tmp_path / "brains.toml"
    local = tmp_path / "local.toml"
    base.write_text(
        """
[ollama]
base_url = "http://base:11434"

[ollama.profiles.embeddings]
preferred_model = "base-embed"
fallback_models = ["fallback-a", "fallback-b"]

[pdf]
pdf_dir = "PDF"
index_root = ".brains/.index/pdf_search"
table_name = "base_pdf"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    local.write_text(
        """
[vault]
table_name = "local_vault"
index_root = ".brains/.index/custom_vault"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("BRAINS_OLLAMA__PROFILES__EMBEDDINGS__PREFERRED_MODEL", "env-embed")

    config = load_config(config_path=base, local_config_path=local)

    assert config.ollama.embed_model == "env-embed"
    assert config.ollama.embed_fallback_models == ["fallback-a", "fallback-b"]
    assert config.ollama.base_url == "http://base:11434"
    assert config.pdf.table_name == "base_pdf"
    assert config.vault.table_name == "local_vault"


def test_resolve_pdf_paths_uses_default_config_layout() -> None:
    paths = resolve_pdf_paths()

    assert paths.pdf_dir.name == "PDF"
    assert paths.index_root.as_posix().endswith("/.brains/.index/pdf_search")
    assert paths.table_name == "scientific_pdf_chunks"


def test_resolve_vault_paths_uses_default_config_layout() -> None:
    paths = resolve_vault_paths()

    assert paths.index_root.as_posix().endswith("/.brains/.index/vault_search")
    assert paths.table_name == "vault_markdown_chunks"


def test_resolve_research_paths_uses_default_config_layout() -> None:
    paths = resolve_research_paths()

    assert paths.index_root.as_posix().endswith("/.brains/.index/research")
    assert paths.memory_path.as_posix().endswith("/.brains/.index/research/memory.jsonl")


def test_resolve_graph_paths_uses_default_config_layout() -> None:
    paths = resolve_graph_paths()

    assert paths.index_root.as_posix().endswith("/.brains/.index/graph_search")
    assert paths.graph_path.as_posix().endswith("/.brains/.index/graph_search/graph.json")


def test_default_config_exposes_graph_and_health_settings() -> None:
    config = load_config()

    assert "AGENTS.md" in config.graph.governance_files
    assert ("Home.md", "UA/Головна.md") in config.graph.special_page_pairs
    assert config.health.pdf_probe_query == "pairformer"
    assert config.health.vault_probe_query == "pairformer"


def test_from_settings_preserves_explicit_zero_values() -> None:
    pdf_paths = resolve_pdf_paths()
    vault_paths = resolve_vault_paths()
    graph_paths = resolve_graph_paths()
    research_paths = resolve_research_paths()

    pdf_config = IndexConfig.from_settings(
        paths=pdf_paths,
        chunk_size=0,
        chunk_overlap=0,
        batch_size=0,
    )
    vault_config = VaultIndexConfig.from_settings(
        paths=vault_paths,
        chunk_size=0,
        chunk_overlap=0,
        batch_size=0,
    )
    research_config = ResearchRunConfig.from_settings(
        paths=research_paths,
        query="pairformer",
        vault_k=0,
        pdf_k=0,
        memory_k=0,
    )
    graph_search_config = GraphSearchConfig.from_settings(
        paths=graph_paths,
        query="pairformer",
        k=0,
        max_hops=0,
    )

    assert pdf_config.chunk_size == 0
    assert pdf_config.chunk_overlap == 0
    assert pdf_config.batch_size == 0
    assert vault_config.chunk_size == 0
    assert vault_config.chunk_overlap == 0
    assert vault_config.batch_size == 0
    assert graph_search_config.k == 0
    assert graph_search_config.max_hops == 0
    assert research_config.vault_k == 0
    assert research_config.pdf_k == 0
    assert research_config.memory_k == 0


def test_graph_index_config_from_settings_preserves_paths(tmp_path: Path) -> None:
    paths = GraphPaths(
        repo_root=tmp_path,
        brains_root=tmp_path / ".brains",
        index_root=tmp_path / ".brains" / ".index" / "graph_search",
        graph_path=tmp_path / ".brains" / ".index" / "graph_search" / "graph.json",
        manifest_path=tmp_path / ".brains" / ".index" / "graph_search" / "manifest.json",
    )

    config = GraphIndexConfig.from_settings(paths=paths)

    assert config.paths == paths


def test_vault_search_config_uses_manifest_embed_model_when_present(tmp_path: Path) -> None:
    paths = BrainsPaths(
        repo_root=tmp_path,
        brains_root=tmp_path / ".brains",
        pdf_dir=tmp_path / "PDF",
        index_root=tmp_path / ".brains" / ".index" / "vault_search",
        db_uri=tmp_path / ".brains" / ".index" / "vault_search" / "lancedb",
        manifest_path=tmp_path / ".brains" / ".index" / "vault_search" / "manifest.json",
        table_name="vault_markdown_chunks",
    )
    paths.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    paths.manifest_path.write_text('{"embed_model":"bge-m3:latest"}\n', encoding="utf-8")

    config = VaultSearchConfig.from_settings(paths=paths, query="pairformer")

    assert config.embed_model == "bge-m3:latest"


def test_pdf_search_config_uses_manifest_embed_model_when_present(tmp_path: Path) -> None:
    paths = BrainsPaths(
        repo_root=tmp_path,
        brains_root=tmp_path / ".brains",
        pdf_dir=tmp_path / "PDF",
        index_root=tmp_path / ".brains" / ".index" / "pdf_search",
        db_uri=tmp_path / ".brains" / ".index" / "pdf_search" / "lancedb",
        manifest_path=tmp_path / ".brains" / ".index" / "pdf_search" / "manifest.json",
        table_name="scientific_pdf_chunks",
    )
    paths.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    paths.manifest_path.write_text('{"embed_model":"nomic-embed-text"}\n', encoding="utf-8")

    config = SearchConfig.from_settings(paths=paths, query="pairformer")

    assert config.embed_model == "nomic-embed-text"
