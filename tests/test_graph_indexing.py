from __future__ import annotations

import json
from pathlib import Path

from brains.config import GraphPaths
from brains.sources.graph.indexing import build_repository_graph, index_graph
from brains.sources.graph.models import GraphIndexConfig
from brains.sources.graph.serialization import load_graph


def make_graph_paths(tmp_path: Path) -> GraphPaths:
    return GraphPaths(
        repo_root=tmp_path,
        brains_root=tmp_path / ".brains",
        index_root=tmp_path / ".brains" / ".index" / "graph_search",
        graph_path=tmp_path / ".brains" / ".index" / "graph_search" / "graph.json",
        manifest_path=tmp_path / ".brains" / ".index" / "graph_search" / "manifest.json",
    )


def write_sample_repo(tmp_path: Path) -> None:
    (tmp_path / "EN/1. AlphaFold3/1.2. Architecture").mkdir(parents=True, exist_ok=True)
    (tmp_path / "UA/1. AlphaFold3/1.2. Архітектура").mkdir(parents=True, exist_ok=True)
    (tmp_path / "Home.md").write_text("# Home\n\n[[EN/1. AlphaFold3/1.2. Architecture/1.2.2. Pairformer]]\n", encoding="utf-8")
    (tmp_path / "UA/Головна.md").write_text("# Головна\n\n[[UA/1. AlphaFold3/1.2. Архітектура/1.2.2. Pairformer]]\n", encoding="utf-8")
    (tmp_path / "EN/1. AlphaFold3/1.2. Architecture/1.2.2. Pairformer.md").write_text(
        "---\ncssclasses: [note]\ntags: [architecture, pairformer]\n---\n\n"
        "# Pairformer\n\n"
        "🇺🇦 [[UA/1. AlphaFold3/1.2. Архітектура/1.2.2. Pairformer|Українська]]\n\n"
        "## What is the Pairformer?\n\n"
        "See [[EN/1. AlphaFold3/1.2. Architecture/1.2.3. Diffusion Module]].\n\n"
        "## Sources\n\n> DOI: 10.1038/s41586-024-07487-w\n",
        encoding="utf-8",
    )
    (tmp_path / "UA/1. AlphaFold3/1.2. Архітектура/1.2.2. Pairformer.md").write_text(
        "---\ncssclasses: [note]\ntags: [architecture, pairformer]\n---\n\n"
        "# Pairformer\n\n"
        "🇬🇧 [[EN/1. AlphaFold3/1.2. Architecture/1.2.2. Pairformer|English]]\n\n"
        "## Що таке Pairformer?\n\n"
        "Див. [[UA/1. AlphaFold3/1.2. Архітектура/1.2.3. Дифузійний модуль]].\n",
        encoding="utf-8",
    )
    (tmp_path / "EN/1. AlphaFold3/1.2. Architecture/1.2.3. Diffusion Module.md").write_text(
        "# Diffusion Module\n\n## Module\n\nRelated to Pairformer.\n",
        encoding="utf-8",
    )
    (tmp_path / "UA/1. AlphaFold3/1.2. Архітектура/1.2.3. Дифузійний модуль.md").write_text(
        "# Дифузійний модуль\n\n## Модуль\n\nПов'язаний з Pairformer.\n",
        encoding="utf-8",
    )


def test_build_repository_graph_captures_note_structure(tmp_path: Path) -> None:
    write_sample_repo(tmp_path)

    graph, summary = build_repository_graph(tmp_path)

    assert summary["node_type_counts"]["note"] >= 6
    assert summary["node_type_counts"]["entity"] >= 2
    assert summary["edge_type_counts"]["has_section"] >= 4
    assert summary["edge_type_counts"]["defines_entity"] >= 4
    assert summary["edge_type_counts"]["mentions_entity"] >= 2
    assert any(data.get("edge_type") == "mirror_of" for *_rest, data in graph.edges(data=True))
    assert any(data.get("edge_type") == "links_to" for *_rest, data in graph.edges(data=True))
    assert "entity::1.2.2" in graph


def test_index_graph_writes_graph_and_manifest(tmp_path: Path) -> None:
    write_sample_repo(tmp_path)
    paths = make_graph_paths(tmp_path)

    payload = index_graph(GraphIndexConfig(paths=paths))

    assert paths.graph_path.exists()
    assert paths.manifest_path.exists()
    manifest = json.loads(paths.manifest_path.read_text(encoding="utf-8"))
    assert manifest["markdown_count"] >= 6
    assert payload["node_count"] >= 6
    graph = load_graph(paths.graph_path)
    assert "note::EN/1. AlphaFold3/1.2. Architecture/1.2.2. Pairformer.md" in graph
    assert "entity::1.2.2" in graph
