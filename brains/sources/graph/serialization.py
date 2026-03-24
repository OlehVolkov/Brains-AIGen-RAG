from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
from networkx.readwrite import json_graph


def save_graph(graph: nx.MultiDiGraph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json_graph.node_link_data(graph)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_graph(path: Path) -> nx.MultiDiGraph:
    payload = json.loads(path.read_text(encoding="utf-8"))
    graph = json_graph.node_link_graph(payload, directed=True, multigraph=True)
    if not isinstance(graph, nx.MultiDiGraph):
        graph = nx.MultiDiGraph(graph)
    return graph
