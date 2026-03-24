from __future__ import annotations

from collections import defaultdict
from itertools import islice
import re
from typing import Any

import networkx as nx

from brains.config.loader import resolve_graph_paths
from brains.shared import snippet
from brains.sources.graph.models import GraphPathConfig, GraphSearchConfig
from brains.sources.graph.serialization import load_graph


TOKEN_RE = re.compile(r"[\w.-]+", re.U)
EDGE_BONUS = {
    "mirror_of": 1.5,
    "links_to": 1.2,
    "defines_entity": 1.15,
    "mentions_entity": 1.0,
    "has_section": 1.0,
    "has_tag": 0.9,
    "cites_doi": 0.9,
    "same_top_level_domain": 0.4,
}
SEED_EXPANSION_EDGE_BONUS = {
    "mirror_of": 1.4,
    "links_to": 1.1,
    "defines_entity": 1.05,
    "mentions_entity": 0.95,
    "has_tag": 0.8,
    "cites_doi": 0.8,
    "has_section": 0.5,
    "same_top_level_domain": 0.25,
}
PATH_EDGE_WEIGHT = {
    "mirror_of": 0.8,
    "links_to": 1.0,
    "defines_entity": 0.7,
    "mentions_entity": 0.9,
    "has_tag": 1.2,
    "cites_doi": 1.3,
    "same_top_level_domain": 2.6,
    "has_section": 4.0,
}


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text.lower()) if len(token) >= 2]


def _node_match_score(query: str, tokens: list[str], attrs: dict[str, Any]) -> float:
    searchable = str(attrs.get("search_text", "")).lower()
    if not searchable:
        return 0.0
    score = 0.0
    title = str(attrs.get("title", "")).lower()
    source_path = str(attrs.get("source_path", "")).lower()
    exact_query = query.lower().strip()

    if exact_query and exact_query in {title, source_path, searchable}:
        score += 6.0
    if exact_query and exact_query in searchable:
        score += 2.0

    for token in tokens:
        if token in searchable:
            score += 1.0
            if token in title or token in source_path:
                score += 0.5
    return score


def _node_label(graph: nx.MultiDiGraph, node_id: str) -> str:
    attrs = dict(graph.nodes[node_id])
    node_type = str(attrs.get("node_type", "unknown"))
    if node_type == "note":
        return str(attrs.get("title", attrs.get("source_path", node_id)))
    if node_type == "section":
        return str(attrs.get("section_path", attrs.get("section", node_id)))
    if node_type == "tag":
        return f"tag:{attrs.get('tag', node_id)}"
    if node_type == "doi":
        return f"doi:{attrs.get('doi', node_id)}"
    if node_type == "entity":
        return str(attrs.get("entity", node_id))
    return node_id


def _note_candidates(graph: nx.MultiDiGraph) -> list[tuple[str, dict[str, Any]]]:
    return [
        (str(node_id), dict(attrs))
        for node_id, attrs in graph.nodes(data=True)
        if attrs.get("node_type") == "note"
    ]


def _resolve_note_node(graph: nx.MultiDiGraph, query: str) -> tuple[str, list[str]]:
    raw = query.strip()
    normalized = raw.lower()
    warnings: list[str] = []

    for node_id, attrs in _note_candidates(graph):
        source_path = str(attrs.get("source_path", "")).lower()
        title = str(attrs.get("title", "")).lower()
        if normalized in {node_id.lower(), source_path, title}:
            return node_id, warnings

    tokens = _tokenize(raw)
    scored: list[tuple[float, str, dict[str, Any]]] = []
    for node_id, attrs in _note_candidates(graph):
        score = _node_match_score(raw, tokens, attrs)
        if score > 0:
            scored.append((score, node_id, attrs))

    if not scored:
        raise ValueError(f"No note node matched `{query}`.")

    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best_node_id, best_attrs = scored[0]
    if len(scored) > 1 and scored[1][0] == best_score:
        warnings.append(
            f"Resolved `{query}` to `{best_attrs.get('source_path', best_node_id)}` by tie-broken fuzzy note match."
        )
    elif str(best_attrs.get("source_path", "")).lower() != normalized:
        warnings.append(
            f"Resolved `{query}` to `{best_attrs.get('source_path', best_node_id)}` by fuzzy note match."
        )
    return best_node_id, warnings


def _build_path_graph(graph: nx.MultiDiGraph) -> nx.Graph:
    path_graph = nx.Graph()
    for source, target, attrs in graph.edges(data=True):
        edge_type = str(attrs.get("edge_type", "related"))
        weight = PATH_EDGE_WEIGHT.get(edge_type, 3.0)
        if path_graph.has_edge(source, target):
            existing = path_graph[source][target]
            existing_weight = float(existing["weight"])
            if weight < existing_weight:
                existing["weight"] = weight
                existing["edge_types"] = {edge_type}
            elif weight == existing_weight:
                edge_types = set(existing.get("edge_types", set()))
                edge_types.add(edge_type)
                existing["edge_types"] = edge_types
        else:
            path_graph.add_edge(source, target, weight=weight, edge_types={edge_type})
    return path_graph


def _path_nodes_payload(graph: nx.MultiDiGraph, node_ids: list[str]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for index, node_id in enumerate(node_ids, start=1):
        attrs = dict(graph.nodes[node_id])
        payload.append(
            {
                "index": index,
                "node_id": node_id,
                "node_type": str(attrs.get("node_type", "unknown")),
                "label": _node_label(graph, node_id),
                "source_path": str(attrs.get("source_path", "")) or None,
            }
        )
    return payload


def search_graph_knowledge(
    *,
    query: str,
    k: int = 5,
    max_hops: int = 1,
    index_root: str | None = None,
    graph_file: str | None = None,
) -> dict[str, Any]:
    paths = resolve_graph_paths(index_root=index_root, graph_file=graph_file)
    return search_graph(
        GraphSearchConfig.from_settings(
            paths=paths,
            query=query,
            k=k,
            max_hops=max_hops,
        )
    )


def _edge_payload(graph: nx.MultiDiGraph, source: str, target: str) -> list[dict[str, Any]]:
    payload = graph.get_edge_data(source, target, default={})
    if isinstance(payload, dict):
        return [value for value in payload.values() if isinstance(value, dict)]
    return []


def _note_result(graph: nx.MultiDiGraph, note_id: str, score: float, evidences: list[str]) -> dict[str, Any]:
    attrs = dict(graph.nodes[note_id])
    title = str(attrs.get("title", note_id))
    source_path = str(attrs.get("source_path", ""))
    tags = attrs.get("tags", [])
    tags_text = ", ".join(tags[:4]) if isinstance(tags, list) else ""
    parts = [title]
    if tags_text:
        parts.append(f"tags: {tags_text}")
    section_names = [
        str(section_attrs.get("section"))
        for _source, section_id, edge_attrs in graph.out_edges(note_id, data=True)
        if edge_attrs.get("edge_type") == "has_section"
        for section_attrs in [graph.nodes[section_id]]
        if section_attrs.get("node_type") == "section"
    ]
    if section_names:
        parts.append(f"sections: {', '.join(section_names[:3])}")
    unique_evidences = list(dict.fromkeys(evidences))
    return {
        "source_path": source_path,
        "title": title,
        "language_branch": attrs.get("language_branch", "root"),
        "score": round(score, 3),
        "rank": 0,
        "snippet": snippet(" | ".join(parts), 220),
        "evidence": unique_evidences[:5],
    }


def search_graph(config: GraphSearchConfig) -> dict[str, Any]:
    if config.k <= 0:
        raise ValueError("k must be greater than 0.")
    if config.max_hops < 0:
        raise ValueError("max_hops must be greater than or equal to 0.")

    graph = load_graph(config.paths.graph_path)
    query = config.query.strip()
    tokens = _tokenize(query)
    note_scores: dict[str, float] = defaultdict(float)
    note_evidence: dict[str, list[str]] = defaultdict(list)
    warnings: list[str] = []

    matched_nodes: list[tuple[str, float]] = []
    for node_id, attrs in graph.nodes(data=True):
        score = _node_match_score(query, tokens, dict(attrs))
        if score > 0:
            matched_nodes.append((str(node_id), score))

    if not matched_nodes:
        warnings.append("Graph search found no matching seed nodes for the query.")
        return {"results": [], "warnings": warnings}

    for node_id, seed_score in matched_nodes:
        attrs = dict(graph.nodes[node_id])
        node_type = str(attrs.get("node_type", "unknown"))

        candidate_notes: list[tuple[str, float, str]] = []
        if node_type == "note":
            candidate_notes.append((node_id, seed_score + 3.0, f"matched note `{attrs.get('source_path', node_id)}`"))
        elif node_type == "section":
            note_id = str(attrs.get("note_id", ""))
            if note_id:
                candidate_notes.append((note_id, seed_score + 2.0, f"matched section `{attrs.get('section_path', node_id)}`"))
        else:
            for neighbor in graph.successors(node_id):
                neighbor_attrs = graph.nodes[neighbor]
                if neighbor_attrs.get("node_type") == "note":
                    label = attrs.get("entity") or attrs.get("tag") or attrs.get("doi") or node_id
                    candidate_notes.append((str(neighbor), seed_score + 1.5, f"matched `{label}`"))

        for note_id, base_score, evidence in candidate_notes:
            note_scores[note_id] += base_score
            note_evidence[note_id].append(evidence)

            if config.max_hops <= 0:
                continue

            frontier = [(note_id, 0)]
            seen = {note_id}
            while frontier:
                current, hops = frontier.pop(0)
                if hops >= config.max_hops:
                    continue
                for neighbor in graph.successors(current):
                    neighbor_id = str(neighbor)
                    if neighbor_id in seen:
                        continue
                    seen.add(neighbor_id)
                    if graph.nodes[neighbor_id].get("node_type") != "note":
                        continue
                    edge_bonus = 0.0
                    edge_types: list[str] = []
                    for payload in _edge_payload(graph, current, neighbor_id):
                        edge_type = str(payload.get("edge_type", "related"))
                        edge_types.append(edge_type)
                        edge_bonus = max(edge_bonus, EDGE_BONUS.get(edge_type, 0.3))
                    if not edge_types:
                        continue
                    hop_penalty = 1.0 / (hops + 1)
                    bonus = base_score * edge_bonus * hop_penalty
                    note_scores[neighbor_id] += bonus
                    note_evidence[neighbor_id].append(
                        f"expanded via {', '.join(sorted(set(edge_types)))} from `{graph.nodes[current].get('source_path', current)}`"
                    )
                    frontier.append((neighbor_id, hops + 1))

    ranked = sorted(note_scores.items(), key=lambda item: item[1], reverse=True)
    results = [
        _note_result(graph, note_id, score, note_evidence[note_id])
        for note_id, score in ranked[: config.k]
    ]
    for rank, row in enumerate(results, start=1):
        row["rank"] = rank
    return {"results": results, "warnings": warnings}


def explain_graph_path_knowledge(
    *,
    source: str,
    target: str,
    max_hops: int = 3,
    index_root: str | None = None,
    graph_file: str | None = None,
) -> dict[str, Any]:
    paths = resolve_graph_paths(index_root=index_root, graph_file=graph_file)
    return explain_graph_path(
        GraphPathConfig.from_settings(
            paths=paths,
            source=source,
            target=target,
            max_hops=max_hops,
        )
    )


def explain_graph_path(config: GraphPathConfig) -> dict[str, Any]:
    if config.max_hops <= 0:
        raise ValueError("max_hops must be greater than 0.")

    graph = load_graph(config.paths.graph_path)
    warnings: list[str] = []
    source_id, source_warnings = _resolve_note_node(graph, config.source)
    target_id, target_warnings = _resolve_note_node(graph, config.target)
    warnings.extend(source_warnings)
    warnings.extend(target_warnings)

    source_attrs = dict(graph.nodes[source_id])
    target_attrs = dict(graph.nodes[target_id])

    if source_id == target_id:
        return {
            "source_query": config.source,
            "target_query": config.target,
            "resolved_source_path": str(source_attrs.get("source_path", "")),
            "resolved_target_path": str(target_attrs.get("source_path", "")),
            "path_found": True,
            "hops": 0,
            "total_weight": 0.0,
            "nodes": _path_nodes_payload(graph, [source_id]),
            "edges": [],
            "summary": [f"{_node_label(graph, source_id)} (same note)"],
            "warnings": warnings,
        }

    path_graph = _build_path_graph(graph)
    path_nodes: list[str] | None = None
    try:
        candidates = nx.shortest_simple_paths(path_graph, source_id, target_id, weight="weight")
        for candidate in islice(candidates, 20):
            if len(candidate) - 1 <= config.max_hops:
                path_nodes = [str(node_id) for node_id in candidate]
                break
    except nx.NetworkXNoPath:
        path_nodes = None

    if path_nodes is None:
        warnings.append(
            f"No graph path found between `{source_attrs.get('source_path', source_id)}` and "
            f"`{target_attrs.get('source_path', target_id)}` within {config.max_hops} hops."
        )
        return {
            "source_query": config.source,
            "target_query": config.target,
            "resolved_source_path": str(source_attrs.get("source_path", "")),
            "resolved_target_path": str(target_attrs.get("source_path", "")),
            "path_found": False,
            "hops": None,
            "total_weight": None,
            "nodes": [],
            "edges": [],
            "summary": [],
            "warnings": warnings,
        }

    edges: list[dict[str, Any]] = []
    summary: list[str] = []
    total_weight = 0.0
    for left, right in zip(path_nodes, path_nodes[1:]):
        edge_data = path_graph[left][right]
        edge_types = sorted(str(edge_type) for edge_type in edge_data.get("edge_types", set()))
        weight = float(edge_data.get("weight", 0.0))
        total_weight += weight
        description = f"{_node_label(graph, left)} --{', '.join(edge_types)}--> {_node_label(graph, right)}"
        summary.append(description)
        edges.append(
            {
                "source_node_id": left,
                "target_node_id": right,
                "source_label": _node_label(graph, left),
                "target_label": _node_label(graph, right),
                "edge_types": edge_types,
                "weight": round(weight, 3),
                "description": description,
            }
        )

    return {
        "source_query": config.source,
        "target_query": config.target,
        "resolved_source_path": str(source_attrs.get("source_path", "")),
        "resolved_target_path": str(target_attrs.get("source_path", "")),
        "path_found": True,
        "hops": len(path_nodes) - 1,
        "total_weight": round(total_weight, 3),
        "nodes": _path_nodes_payload(graph, path_nodes),
        "edges": edges,
        "summary": summary,
        "warnings": warnings,
    }


def expand_seed_note_paths(
    *,
    graph_path,
    seed_paths: list[str],
    max_hops: int,
    limit: int,
) -> list[dict[str, Any]]:
    if max_hops <= 0 or limit <= 0:
        return []

    graph = load_graph(graph_path)
    seed_note_ids = [f"note::{path}" for path in seed_paths if f"note::{path}" in graph]
    if not seed_note_ids:
        return []

    note_scores: dict[str, float] = defaultdict(float)
    note_evidence: dict[str, list[str]] = defaultdict(list)

    for seed_note_id in seed_note_ids:
        seed_path = str(graph.nodes[seed_note_id].get("source_path", seed_note_id))
        frontier: list[tuple[str, int, float]] = [(seed_note_id, 0, 1.0)]
        seen: set[tuple[str, int]] = {(seed_note_id, 0)}

        while frontier:
            current, hops, weight = frontier.pop(0)
            if hops >= max_hops:
                continue

            for neighbor in graph.successors(current):
                neighbor_id = str(neighbor)
                state = (neighbor_id, hops + 1)
                if state in seen:
                    continue
                seen.add(state)

                edge_payloads = _edge_payload(graph, current, neighbor_id)
                if not edge_payloads:
                    continue
                edge_types = sorted({str(payload.get("edge_type", "related")) for payload in edge_payloads})
                edge_bonus = max(SEED_EXPANSION_EDGE_BONUS.get(edge_type, 0.3) for edge_type in edge_types)
                next_weight = weight * edge_bonus

                if graph.nodes[neighbor_id].get("node_type") == "note" and neighbor_id != seed_note_id:
                    note_scores[neighbor_id] += next_weight
                    note_evidence[neighbor_id].append(
                        f"expanded via {', '.join(edge_types)} from `{seed_path}`"
                    )

                frontier.append((neighbor_id, hops + 1, next_weight * 0.7))

    ranked = sorted(note_scores.items(), key=lambda item: item[1], reverse=True)
    results = []
    for note_id, score in ranked[:limit]:
        attrs = dict(graph.nodes[note_id])
        results.append(
            {
                "source_path": str(attrs.get("source_path", "")),
                "title": str(attrs.get("title", note_id)),
                "language_branch": str(attrs.get("language_branch", "root")),
                "score": round(score, 3),
                "evidence": list(dict.fromkeys(note_evidence[note_id]))[:5],
            }
        )
    return results


def format_graph_search_results(payload: dict[str, Any]) -> str:
    warnings = payload.get("warnings", [])
    results = payload.get("results", [])
    lines: list[str] = []
    if warnings:
        lines.append("Warnings:")
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")
    for row in results:
        lines.append(
            f"[{row['rank']}] {row['source_path']} | branch={row['language_branch']} | score={row['score']}"
        )
        lines.append(row["snippet"])
        for evidence in row.get("evidence", []):
            lines.append(f"- {evidence}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_graph_path_results(payload: dict[str, Any]) -> str:
    warnings = payload.get("warnings", [])
    lines: list[str] = []
    if warnings:
        lines.append("Warnings:")
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")
    if not payload.get("path_found"):
        lines.append("No path found.")
        return "\n".join(lines).rstrip()

    lines.append(
        "Path: "
        f"{payload.get('resolved_source_path')} -> {payload.get('resolved_target_path')} "
        f"| hops={payload.get('hops')} | weight={payload.get('total_weight')}"
    )
    lines.append("")
    for step in payload.get("summary", []):
        lines.append(f"- {step}")
    return "\n".join(lines).rstrip()
