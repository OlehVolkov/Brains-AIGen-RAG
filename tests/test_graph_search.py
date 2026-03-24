from __future__ import annotations

from pathlib import Path

from brains.config import GraphPaths
from brains.sources.graph.indexing import index_graph
from brains.sources.graph.models import GraphIndexConfig, GraphPathConfig, GraphSearchConfig
from brains.sources.graph.search import explain_graph_path, search_graph


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
    (tmp_path / "EN/1. AlphaFold3/1.2. Architecture/1.2.2. Pairformer.md").write_text(
        "---\ncssclasses: [note]\ntags: [architecture, pairformer]\n---\n\n"
        "# Pairformer\n\n"
        "## What is the Pairformer?\n\n"
        "See [[EN/1. AlphaFold3/1.2. Architecture/1.2.3. Diffusion Module]].\n",
        encoding="utf-8",
    )
    (tmp_path / "UA/1. AlphaFold3/1.2. Архітектура/1.2.2. Pairformer.md").write_text(
        "---\ncssclasses: [note]\ntags: [architecture, pairformer]\n---\n\n"
        "# Pairformer\n\n"
        "## Що таке Pairformer?\n",
        encoding="utf-8",
    )
    (tmp_path / "EN/1. AlphaFold3/1.2. Architecture/1.2.3. Diffusion Module.md").write_text(
        "---\ncssclasses: [note]\ntags: [architecture, diffusion]\n---\n\n"
        "# Diffusion Module\n\n"
        "## Module\n\nConnected to Pairformer.\n",
        encoding="utf-8",
    )


def test_search_graph_returns_pairformer_note_first(tmp_path: Path) -> None:
    write_sample_repo(tmp_path)
    paths = make_graph_paths(tmp_path)
    index_graph(GraphIndexConfig(paths=paths))

    payload = search_graph(
        GraphSearchConfig(
            paths=paths,
            query="pairformer",
            k=3,
            max_hops=1,
        )
    )

    assert payload["results"]
    assert payload["results"][0]["source_path"] == "EN/1. AlphaFold3/1.2. Architecture/1.2.2. Pairformer.md"
    assert any("matched note" in evidence for evidence in payload["results"][0]["evidence"])


def test_search_graph_expands_to_linked_notes(tmp_path: Path) -> None:
    write_sample_repo(tmp_path)
    paths = make_graph_paths(tmp_path)
    index_graph(GraphIndexConfig(paths=paths))

    payload = search_graph(
        GraphSearchConfig(
            paths=paths,
            query="pairformer",
            k=5,
            max_hops=1,
        )
    )

    result_paths = [row["source_path"] for row in payload["results"]]
    assert "EN/1. AlphaFold3/1.2. Architecture/1.2.3. Diffusion Module.md" in result_paths


def test_explain_graph_path_returns_direct_note_link(tmp_path: Path) -> None:
    write_sample_repo(tmp_path)
    paths = make_graph_paths(tmp_path)
    index_graph(GraphIndexConfig(paths=paths))

    payload = explain_graph_path(
        GraphPathConfig(
            paths=paths,
            source="EN/1. AlphaFold3/1.2. Architecture/1.2.2. Pairformer.md",
            target="EN/1. AlphaFold3/1.2. Architecture/1.2.3. Diffusion Module.md",
            max_hops=2,
        )
    )

    assert payload["path_found"] is True
    assert payload["hops"] == 1
    assert payload["resolved_source_path"] == "EN/1. AlphaFold3/1.2. Architecture/1.2.2. Pairformer.md"
    assert payload["resolved_target_path"] == "EN/1. AlphaFold3/1.2. Architecture/1.2.3. Diffusion Module.md"
    assert payload["edges"][0]["edge_types"] == ["links_to"]


def test_explain_graph_path_can_use_entity_bridge(tmp_path: Path) -> None:
    write_sample_repo(tmp_path)
    (tmp_path / "EN/1. AlphaFold3/1.2. Architecture/1.2.4. Recycling.md").write_text(
        "# Recycling\n\n## Module\n\nUses Pairformer representations.\n",
        encoding="utf-8",
    )
    paths = make_graph_paths(tmp_path)
    index_graph(GraphIndexConfig(paths=paths))

    payload = explain_graph_path(
        GraphPathConfig(
            paths=paths,
            source="EN/1. AlphaFold3/1.2. Architecture/1.2.4. Recycling.md",
            target="EN/1. AlphaFold3/1.2. Architecture/1.2.2. Pairformer.md",
            max_hops=2,
        )
    )

    assert payload["path_found"] is True
    assert payload["hops"] == 2
    assert any(node["node_type"] == "entity" for node in payload["nodes"])
    assert payload["edges"][0]["edge_types"] == ["mentions_entity"]
    assert payload["edges"][1]["edge_types"] == ["defines_entity"]
