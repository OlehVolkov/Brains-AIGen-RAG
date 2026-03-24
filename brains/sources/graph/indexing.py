from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime
from itertools import combinations
import json
import re
from pathlib import Path
from typing import TypedDict, cast

import networkx as nx

from brains.config import get_config
from brains.shared import logger
from brains.sources.graph.models import GraphIndexConfig
from brains.sources.graph.serialization import save_graph
from brains.sources.vault.markdown import (
    _infer_note_title,
    detect_language_branch,
    list_markdown_paths,
    split_markdown_sections,
)


LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)
NUMERIC_PREFIX_RE = re.compile(r"^((\d+)(?:\.\d+)*)\.")
FENCE_RE = re.compile(r"```.*?```", re.S)
TITLE_NUMERIC_PREFIX_RE = re.compile(r"^\d+(?:\.\d+)*\.\s*")


def _note_node_id(path: str) -> str:
    return f"note::{path}"


def _section_node_id(path: str, section_path: str) -> str:
    return f"section::{path}::{section_path}"


def _tag_node_id(tag: str) -> str:
    return f"tag::{tag}"


def _doi_node_id(doi: str) -> str:
    return f"doi::{doi.lower()}"


def _entity_node_id(numeric_id: str) -> str:
    return f"entity::{numeric_id}"


def _strip_fences(text: str) -> str:
    return FENCE_RE.sub("", text)


def _extract_frontmatter(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return None
    return parts[0].removeprefix("---\n")


def _strip_frontmatter_block(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return text
    return parts[1]


def _extract_tags(text: str) -> list[str]:
    frontmatter = _extract_frontmatter(text)
    if not frontmatter:
        return []
    match = re.search(r"(?m)^tags:\s*\[(.*?)\]\s*$", frontmatter)
    if not match:
        return []
    tags = []
    for raw in match.group(1).split(","):
        cleaned = raw.strip().strip("'\"")
        if cleaned:
            tags.append(cleaned)
    return sorted(set(tags))


def _extract_links(text: str, existing_targets: set[str]) -> list[str]:
    links: list[str] = []
    for target in LINK_RE.findall(_strip_fences(text)):
        cleaned = target.strip().replace("\\", "/")
        if cleaned in existing_targets:
            links.append(cleaned)
        elif f"{cleaned}.md" in existing_targets:
            links.append(f"{cleaned}.md")
    return sorted(set(links))


def _extract_dois(text: str) -> list[str]:
    return sorted({match.rstrip(").,;") for match in DOI_RE.findall(text)})


def _numeric_note_id(source_path: str) -> str | None:
    match = NUMERIC_PREFIX_RE.match(Path(source_path).name)
    if not match:
        return None
    return match.group(1)


def _top_level_domain(source_path: str) -> str | None:
    note_id = _numeric_note_id(source_path)
    if note_id is None:
        return None
    return note_id.split(".")[0]


def _is_governance_page(source_path: str, governance_files: set[str]) -> bool:
    return Path(source_path).name in governance_files


def _normalized_title_aliases(title: str) -> list[str]:
    normalized = TITLE_NUMERIC_PREFIX_RE.sub("", title).strip()
    if not normalized:
        return []
    aliases = {normalized}
    if " — " in normalized:
        aliases.update(part.strip() for part in normalized.split(" — ") if part.strip())
    if " - " in normalized:
        aliases.update(part.strip() for part in normalized.split(" - ") if part.strip())
    if ":" in normalized:
        aliases.update(part.strip() for part in normalized.split(":") if part.strip())
    aliases = {alias for alias in aliases if len(alias) >= 3}
    return sorted(aliases)


def _text_mentions_alias(text: str, alias: str) -> bool:
    pattern = re.compile(rf"(?<!\w){re.escape(alias)}(?!\w)", re.I)
    return bool(pattern.search(text))


def _graph_edge(
    graph: nx.MultiDiGraph,
    source: str,
    target: str,
    edge_type: str,
    **attrs: object,
) -> None:
    graph.add_edge(source, target, edge_type=edge_type, **attrs)


class EntitySpec(TypedDict):
    entity_id: str
    aliases: list[str]


def build_repository_graph(repo_root: Path) -> tuple[nx.MultiDiGraph, dict[str, object]]:
    graph_settings = get_config().graph
    governance_files = set(graph_settings.governance_files)
    special_page_pairs = list(graph_settings.special_page_pairs)
    markdown_paths = list_markdown_paths(repo_root)
    known_targets = {path.relative_to(repo_root).as_posix() for path in markdown_paths}

    graph = nx.MultiDiGraph()
    note_records: list[dict[str, object]] = []
    note_ids_by_numeric: dict[str, list[str]] = defaultdict(list)
    note_ids_by_domain: dict[str, list[str]] = defaultdict(list)
    entity_aliases_by_numeric: dict[str, set[str]] = defaultdict(set)
    entity_labels_by_numeric: dict[str, str] = {}
    note_lookup: dict[str, str] = {}
    edge_counts: Counter[str] = Counter()

    for markdown_path in markdown_paths:
        source_path = markdown_path.relative_to(repo_root).as_posix()
        raw_text = markdown_path.read_text(encoding="utf-8")
        sections = split_markdown_sections(raw_text)
        title = _infer_note_title(markdown_path, sections)
        tags = _extract_tags(raw_text)
        dois = _extract_dois(raw_text)
        links = _extract_links(raw_text, known_targets)
        note_id = _note_node_id(source_path)
        note_lookup[source_path] = note_id
        numeric_id = _numeric_note_id(source_path)
        top_level_domain = _top_level_domain(source_path)
        language_branch = detect_language_branch(source_path)
        note_records.append(
            {
                "source_path": source_path,
                "raw_text": raw_text,
                "sections": sections,
                "title": title,
                "tags": tags,
                "dois": dois,
                "links": links,
                "note_id": note_id,
                "numeric_id": numeric_id,
                "top_level_domain": top_level_domain,
                "language_branch": language_branch,
            }
        )

        graph.add_node(
            note_id,
            node_type="note",
            source_path=source_path,
            title=title,
            language_branch=language_branch,
            numeric_id=numeric_id,
            top_level_domain=top_level_domain,
            tags=tags,
            doi_count=len(dois),
            search_text=" ".join([source_path, title, *tags]).lower(),
        )
        if numeric_id:
            note_ids_by_numeric[numeric_id].append(note_id)
            if not _is_governance_page(source_path, governance_files):
                aliases = _normalized_title_aliases(title)
                entity_aliases_by_numeric[numeric_id].update(aliases)
                if language_branch == "EN" and aliases:
                    entity_labels_by_numeric[numeric_id] = aliases[0]
                elif numeric_id not in entity_labels_by_numeric and aliases:
                    entity_labels_by_numeric[numeric_id] = aliases[0]
        if top_level_domain:
            note_ids_by_domain[top_level_domain].append(note_id)

        for section_title, heading_level, section_path, _section_text in sections:
            section_id = _section_node_id(source_path, section_path)
            graph.add_node(
                section_id,
                node_type="section",
                source_path=source_path,
                title=title,
                section=section_title,
                section_path=section_path,
                heading_level=heading_level,
                note_id=note_id,
                search_text=" ".join([source_path, title, section_title, section_path]).lower(),
            )
            _graph_edge(graph, note_id, section_id, "has_section")
            edge_counts["has_section"] += 1

        for tag in tags:
            tag_id = _tag_node_id(tag)
            graph.add_node(
                tag_id,
                node_type="tag",
                tag=tag,
                search_text=tag.lower(),
            )
            _graph_edge(graph, note_id, tag_id, "has_tag")
            _graph_edge(graph, tag_id, note_id, "has_tag")
            edge_counts["has_tag"] += 2

        for doi in dois:
            doi_id = _doi_node_id(doi)
            graph.add_node(
                doi_id,
                node_type="doi",
                doi=doi,
                search_text=doi.lower(),
            )
            _graph_edge(graph, note_id, doi_id, "cites_doi")
            _graph_edge(graph, doi_id, note_id, "cites_doi")
            edge_counts["cites_doi"] += 2

        for target in links:
            if target not in note_lookup and target not in known_targets:
                continue
            target_id = _note_node_id(target)
            _graph_edge(graph, note_id, target_id, "links_to")
            edge_counts["links_to"] += 1

    entity_specs: dict[str, EntitySpec] = {}
    for numeric_id, entity_aliases in sorted(entity_aliases_by_numeric.items()):
        cleaned_aliases = sorted(alias for alias in entity_aliases if len(alias) >= 3)
        if not cleaned_aliases:
            continue
        entity_id = _entity_node_id(numeric_id)
        label = entity_labels_by_numeric.get(numeric_id, cleaned_aliases[0])
        graph.add_node(
            entity_id,
            node_type="entity",
            entity=label,
            aliases=cleaned_aliases,
            numeric_id=numeric_id,
            search_text=" ".join(cleaned_aliases).lower(),
        )
        entity_specs[numeric_id] = {
            "entity_id": entity_id,
            "aliases": cleaned_aliases,
        }

    for record in note_records:
        note_id = str(record["note_id"])
        raw_text = str(record["raw_text"])
        numeric_id = cast(str | None, record["numeric_id"])
        if numeric_id and numeric_id in entity_specs:
            entity_id = str(entity_specs[numeric_id]["entity_id"])
            _graph_edge(graph, note_id, entity_id, "defines_entity", numeric_id=numeric_id)
            _graph_edge(graph, entity_id, note_id, "defines_entity", numeric_id=numeric_id)
            edge_counts["defines_entity"] += 2

        text_for_entities = _strip_fences(_strip_frontmatter_block(raw_text))
        for entity_numeric_id, spec in entity_specs.items():
            if entity_numeric_id == numeric_id:
                continue
            aliases = spec["aliases"]
            matched_alias = next((alias for alias in aliases if _text_mentions_alias(text_for_entities, alias)), None)
            if matched_alias is None:
                continue
            entity_id = str(spec["entity_id"])
            _graph_edge(graph, note_id, entity_id, "mentions_entity", matched_alias=matched_alias)
            _graph_edge(graph, entity_id, note_id, "mentions_entity", matched_alias=matched_alias)
            edge_counts["mentions_entity"] += 2

    for numeric_id, note_ids in sorted(note_ids_by_numeric.items()):
        if len(note_ids) != 2:
            continue
        left, right = note_ids
        _graph_edge(graph, left, right, "mirror_of", numeric_id=numeric_id)
        _graph_edge(graph, right, left, "mirror_of", numeric_id=numeric_id)
        edge_counts["mirror_of"] += 2

    for left_path, right_path in special_page_pairs:
        if left_path not in note_lookup or right_path not in note_lookup:
            continue
        left = note_lookup[left_path]
        right = note_lookup[right_path]
        _graph_edge(graph, left, right, "mirror_of", numeric_id=None)
        _graph_edge(graph, right, left, "mirror_of", numeric_id=None)
        edge_counts["mirror_of"] += 2

    for domain, note_ids in sorted(note_ids_by_domain.items()):
        for left, right in combinations(sorted(note_ids), 2):
            _graph_edge(graph, left, right, "same_top_level_domain", domain=domain)
            _graph_edge(graph, right, left, "same_top_level_domain", domain=domain)
            edge_counts["same_top_level_domain"] += 2

    node_type_counts = Counter(str(attrs.get("node_type", "unknown")) for _node, attrs in graph.nodes(data=True))
    summary = {
        "markdown_count": len(markdown_paths),
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "node_type_counts": dict(sorted(node_type_counts.items())),
        "edge_type_counts": dict(sorted(edge_counts.items())),
    }
    return graph, summary


def write_manifest(
    config: GraphIndexConfig,
    *,
    summary: dict[str, object],
) -> dict[str, object]:
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "graph_path": config.paths.graph_path.relative_to(config.paths.brains_root).as_posix()
        if config.paths.graph_path.is_relative_to(config.paths.brains_root)
        else str(config.paths.graph_path),
        **summary,
    }
    config.paths.index_root.mkdir(parents=True, exist_ok=True)
    config.paths.manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def index_graph(config: GraphIndexConfig) -> dict[str, object]:
    logger.info("Collecting markdown files for graph indexing from {}", config.paths.repo_root)
    graph, summary = build_repository_graph(config.paths.repo_root)
    save_graph(graph, config.paths.graph_path)
    manifest = write_manifest(config, summary=summary)
    logger.info(
        "Indexed repository graph with {} nodes and {} edges.",
        graph.number_of_nodes(),
        graph.number_of_edges(),
    )
    return {
        **summary,
        "graph_path": str(config.paths.graph_path),
        "manifest_path": str(config.paths.manifest_path),
        "manifest": manifest,
    }
