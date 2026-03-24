from __future__ import annotations

from typing import Any, Sequence
from pathlib import Path

from brains.config import get_config
from brains.shared import logger
from brains.config.loader import resolve_graph_paths
from brains.sources.graph.search import expand_seed_note_paths
from brains.shared.retrieval import (
    apply_result_thresholds,
    apply_ollama_rerank,
    embed_query_text,
    open_table,
    resolve_fetch_limit,
    resolve_query_mode,
    run_fts_search,
    run_hybrid_search,
    run_vector_search,
    validate_search_config,
)
from brains.shared.text import _with_warnings, snippet
from brains.sources.vault.models import VaultSearchConfig
from brains.config.loader import resolve_vault_paths


VAULT_SEARCH_COLUMNS = [
    "id",
    "text",
    "source_path",
    "source_file",
    "title",
    "section",
    "section_path",
    "heading_level",
    "language_branch",
    "parser",
    "block_kind",
    "chunk_index",
    "chunk_kind",
    "block_count",
    "char_count",
    "word_count",
]
def search_vault_knowledge(
    *,
    query: str,
    mode: str = "hybrid",
    reranker: str = "none",
    k: int = 5,
    fetch_k: int = 20,
    graph_max_hops: int | None = None,
    snippet_chars: int = 320,
    min_score: float | None = None,
    max_distance: float | None = None,
    index_root: str | None = None,
) -> dict[str, Any]:
    paths = resolve_vault_paths(index_root=index_root)
    return search_vault(
        VaultSearchConfig.from_settings(
            paths=paths,
            query=query,
            mode=mode,
            reranker=reranker,
            k=k,
            fetch_k=fetch_k,
            graph_max_hops=graph_max_hops,
            snippet_chars=snippet_chars,
            min_score=min_score,
            max_distance=max_distance,
        )
    )


def search_vault(config: VaultSearchConfig) -> dict[str, Any]:
    logger.info("Running vault search for query: {}", config.query)
    validate_search_config(config)
    warnings: list[str] = []
    effective_mode, route_reason = resolve_query_mode(
        query=config.query,
        requested_mode=config.mode,
    )
    if route_reason:
        warnings.append(route_reason)
    graph_enabled = effective_mode == "hybrid-graph"
    base_mode = "hybrid" if graph_enabled else effective_mode
    effective_reranker = (
        "rrf" if base_mode in {"hybrid", "hybrid-graph"} and config.reranker == "none" else config.reranker
    )
    if base_mode != "hybrid" and effective_reranker == "rrf":
        effective_reranker = "none"
        warnings.append(
            "RRF reranking requires hybrid retrieval; falling back to base ranking."
        )

    table = open_table(config.paths)
    query_vector: list[float] | None = None

    if base_mode in {"vector", "hybrid"}:
        try:
            query_vector = embed_query_text(
                config.query,
                model=config.embed_model,
                base_url=config.ollama_base_url,
            )
        except Exception as exc:
            logger.warning("Vault vector embeddings unavailable; falling back to FTS.")
            base_mode = "fts"
            warnings.append(
                "Vector embeddings unavailable; falling back to FTS search "
                f"({type(exc).__name__}: {exc})."
            )
            if effective_reranker == "rrf":
                effective_reranker = "none"
                warnings.append(
                    "RRF reranking requires hybrid retrieval; falling back to plain FTS ranking."
                )

    fetch_limit = resolve_fetch_limit(
        k=config.k,
        fetch_k=config.fetch_k,
        reranker=effective_reranker,
    )

    try:
        if base_mode == "vector":
            rows = run_vector_search(
                table,
                select_columns=VAULT_SEARCH_COLUMNS,
                query_vector=query_vector or [],
                query_text=config.query,
                fetch_limit=fetch_limit,
                reranker=effective_reranker,
                cross_encoder_model=config.cross_encoder_model,
            )
        elif base_mode == "fts":
            rows = run_fts_search(
                table,
                select_columns=VAULT_SEARCH_COLUMNS,
                query_text=config.query,
                fetch_limit=fetch_limit,
                reranker=effective_reranker,
                cross_encoder_model=config.cross_encoder_model,
            )
        else:
            rows = run_hybrid_search(
                table,
                select_columns=VAULT_SEARCH_COLUMNS,
                query_vector=query_vector or [],
                query_text=config.query,
                fetch_limit=fetch_limit,
                reranker=effective_reranker,
                cross_encoder_model=config.cross_encoder_model,
            )
    except Exception as exc:
        if effective_reranker == "cross-encoder":
            logger.warning("Vault cross-encoder reranking failed; applying fallback.")
            fallback_reranker = "rrf" if effective_mode == "hybrid" else "none"
            warnings.append(
                "Cross-encoder reranking failed on CPU; falling back to "
                f"{fallback_reranker} ({type(exc).__name__}: {exc})."
            )
            effective_reranker = fallback_reranker
            fetch_limit = resolve_fetch_limit(
                k=config.k,
                fetch_k=config.fetch_k,
                reranker=effective_reranker,
            )
            if base_mode == "vector":
                rows = run_vector_search(
                    table,
                    select_columns=VAULT_SEARCH_COLUMNS,
                    query_vector=query_vector or [],
                    query_text=config.query,
                    fetch_limit=fetch_limit,
                    reranker=effective_reranker,
                    cross_encoder_model=config.cross_encoder_model,
                )
            elif base_mode == "fts":
                rows = run_fts_search(
                    table,
                    select_columns=VAULT_SEARCH_COLUMNS,
                    query_text=config.query,
                    fetch_limit=fetch_limit,
                    reranker=effective_reranker,
                    cross_encoder_model=config.cross_encoder_model,
                )
            else:
                rows = run_hybrid_search(
                    table,
                    select_columns=VAULT_SEARCH_COLUMNS,
                    query_vector=query_vector or [],
                    query_text=config.query,
                    fetch_limit=fetch_limit,
                    reranker=effective_reranker,
                    cross_encoder_model=config.cross_encoder_model,
                )
        else:
            raise

    if effective_reranker == "ollama":
        try:
            rows = apply_ollama_rerank(
                rows,
                query=config.query,
                model=config.ollama_rerank_model,
                base_url=config.ollama_base_url,
                top_k=config.k,
            )
        except Exception as exc:
            logger.warning("Vault Ollama reranking unavailable; keeping base order.")
            warnings.append(
                "Ollama reranking unavailable; using base retrieval order "
                f"({type(exc).__name__}: {exc})."
            )

    rows, threshold_warnings = apply_result_thresholds(
        rows,
        min_score=config.min_score,
        max_distance=config.max_distance,
    )
    warnings.extend(threshold_warnings)

    prepared: list[dict[str, Any]] = []
    for rank, row in enumerate(rows[: config.k], start=1):
        payload = dict(row)
        payload["rank"] = rank
        payload["snippet"] = snippet(str(payload.get("text", "")), config.snippet_chars)
        prepared.append(payload)

    if graph_enabled:
        prepared, graph_warnings = _merge_graph_expansion(config, prepared)
        warnings.extend(graph_warnings)

    prepared = _with_warnings(prepared, warnings)
    reported_mode = effective_mode if graph_enabled else base_mode
    logger.info("Vault search produced {} hits.", len(prepared))
    return {
        "results": prepared,
        "warnings": warnings,
        "effective_mode": reported_mode,
        "effective_reranker": effective_reranker,
    }


def _base_row_score(row: dict[str, Any], *, total_rows: int) -> float:
    score = row.get("_relevance_score")
    if isinstance(score, (int, float)):
        return float(score)
    score = row.get("_score")
    if isinstance(score, (int, float)):
        return float(score)
    distance = row.get("_distance")
    if isinstance(distance, (int, float)):
        return 1.0 / (1.0 + float(distance))
    rank = int(row.get("rank", total_rows))
    return max(total_rows - rank + 1, 1) / max(total_rows, 1)


def _graph_row_payload(hit: dict[str, Any], *, snippet_chars: int) -> dict[str, Any]:
    evidence = hit.get("evidence", [])
    evidence_text = "; ".join(str(item) for item in evidence[:3])
    text = f"{hit['title']}\n{evidence_text}".strip()
    return {
        "id": f"graph::{hit['source_path']}",
        "text": text,
        "source_path": hit["source_path"],
        "source_file": hit["source_path"].split("/")[-1],
        "title": hit["title"],
        "section": "Graph note",
        "section_path": hit["title"],
        "heading_level": 1,
        "language_branch": hit.get("language_branch", "root"),
        "parser": "graph",
        "block_kind": "graph",
        "chunk_index": -1,
        "chunk_kind": "graph_note",
        "block_count": 1,
        "char_count": len(text),
        "word_count": len(text.split()),
        "graph_evidence": list(evidence),
        "snippet": snippet(text, snippet_chars),
    }


def _merge_graph_expansion(
    config: VaultSearchConfig,
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    if not rows:
        return rows, []

    try:
        excluded_files = set(get_config().graph.governance_files)
        seed_paths: list[str] = []
        for row in rows:
            source_path = str(row["source_path"])
            if Path(source_path).name in excluded_files:
                continue
            if source_path in seed_paths:
                continue
            seed_paths.append(source_path)
            if len(seed_paths) >= min(config.k, 3):
                break
        if not seed_paths:
            seed_paths = list(dict.fromkeys(str(row["source_path"]) for row in rows[: min(config.k, 2)]))
        graph_paths = resolve_graph_paths()
        graph_hits = expand_seed_note_paths(
            graph_path=graph_paths.graph_path,
            seed_paths=seed_paths,
            max_hops=config.graph_max_hops,
            limit=max(config.fetch_k, config.k),
        )
    except FileNotFoundError:
        return rows, ["Graph artifacts not found; skipping graph expansion."]
    except Exception as exc:
        return rows, [f"Graph expansion unavailable ({type(exc).__name__}: {exc})."]

    if not graph_hits:
        return rows, []

    graph_scores = {str(hit["source_path"]): float(hit["score"]) for hit in graph_hits}
    existing_paths = {str(row["source_path"]) for row in rows}
    total_rows = len(rows)
    merged: list[dict[str, Any]] = []

    for row in rows:
        payload = dict(row)
        payload["_graph_boost"] = graph_scores.get(str(payload["source_path"]), 0.0)
        payload["_combined_score"] = _base_row_score(payload, total_rows=total_rows) + float(payload["_graph_boost"])
        merged.append(payload)

    for hit in graph_hits:
        source_path = str(hit["source_path"])
        if source_path in existing_paths:
            continue
        payload = _graph_row_payload(hit, snippet_chars=config.snippet_chars)
        payload["_graph_boost"] = float(hit["score"])
        payload["_combined_score"] = float(hit["score"]) * 0.6
        merged.append(payload)

    merged.sort(key=lambda item: float(item.get("_combined_score", 0.0)), reverse=True)
    for rank, row in enumerate(merged[: config.k], start=1):
        row["rank"] = rank
    return merged[: config.k], []


def format_vault_search_results(payload: dict[str, Any]) -> str:
    results: Sequence[dict[str, Any]] = payload.get("results", [])
    warnings: Sequence[str] = payload.get("warnings", [])
    lines: list[str] = []
    if warnings:
        lines.append("Fallbacks:")
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")
    for row in results:
        score = row.get("_relevance_score") or row.get("_score") or row.get("_distance") or ""
        score_text = f" | score={score}" if score != "" else ""
        section = row.get("section") or "Document"
        branch = row.get("language_branch") or "root"
        lines.append(
            f"[{row['rank']}] {row['source_path']} | branch={branch} | "
            f"section={section} | chunk={row['chunk_index']}{score_text}"
        )
        lines.append(row["snippet"])
        for evidence in row.get("graph_evidence", [])[:3]:
            lines.append(f"- {evidence}")
        lines.append("")
    return "\n".join(lines).rstrip()
