from __future__ import annotations

from typing import Any, Sequence

from brains.shared import logger
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
from brains.sources.pdf.models import SearchConfig
from brains.config.loader import resolve_pdf_paths


SEARCH_COLUMNS = [
    "id",
    "text",
    "source_path",
    "source_file",
    "page",
    "page_label",
    "title",
    "authors",
    "year",
    "section",
    "section_level",
    "section_path",
    "block_kind",
    "chunk_kind",
    "block_count",
    "chunk_index",
    "char_count",
    "word_count",
]


def search_pdf_corpus(
    *,
    query: str,
    mode: str = "hybrid",
    reranker: str = "none",
    k: int = 5,
    fetch_k: int = 20,
    snippet_chars: int = 320,
    min_score: float | None = None,
    max_distance: float | None = None,
    index_root: str | None = None,
) -> dict[str, Any]:
    paths = resolve_pdf_paths(index_root=index_root)
    return search_pdfs(
        SearchConfig.from_settings(
            paths=paths,
            query=query,
            mode=mode,
            reranker=reranker,
            k=k,
            fetch_k=fetch_k,
            snippet_chars=snippet_chars,
            min_score=min_score,
            max_distance=max_distance,
        )
    )


def search_pdfs(config: SearchConfig) -> dict[str, Any]:
    logger.info("Running PDF search for query: {}", config.query)
    validate_search_config(config)
    warnings: list[str] = []
    effective_mode, route_reason = resolve_query_mode(
        query=config.query,
        requested_mode=config.mode,
    )
    if route_reason:
        warnings.append(route_reason)
    effective_reranker = (
        "rrf" if effective_mode == "hybrid" and config.reranker == "none" else config.reranker
    )
    if effective_mode != "hybrid" and effective_reranker == "rrf":
        effective_reranker = "none"
        warnings.append(
            "RRF reranking requires hybrid retrieval; falling back to base ranking."
        )

    table = open_table(config.paths)
    query_vector: list[float] | None = None

    if config.mode in {"vector", "hybrid"}:
        try:
            query_vector = embed_query_text(
                config.query,
                model=config.embed_model,
                base_url=config.ollama_base_url,
            )
        except Exception as exc:
            logger.warning("PDF vector embeddings unavailable; falling back to FTS.")
            effective_mode = "fts"
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
        if effective_mode == "vector":
            rows = run_vector_search(
                table,
                select_columns=SEARCH_COLUMNS,
                query_vector=query_vector or [],
                query_text=config.query,
                fetch_limit=fetch_limit,
                reranker=effective_reranker,
                cross_encoder_model=config.cross_encoder_model,
            )
        elif effective_mode == "fts":
            rows = run_fts_search(
                table,
                select_columns=SEARCH_COLUMNS,
                query_text=config.query,
                fetch_limit=fetch_limit,
                reranker=effective_reranker,
                cross_encoder_model=config.cross_encoder_model,
            )
        else:
            rows = run_hybrid_search(
                table,
                select_columns=SEARCH_COLUMNS,
                query_vector=query_vector or [],
                query_text=config.query,
                fetch_limit=fetch_limit,
                reranker=effective_reranker,
                cross_encoder_model=config.cross_encoder_model,
            )
    except Exception as exc:
        if effective_reranker == "cross-encoder":
            logger.warning("PDF cross-encoder reranking failed; applying fallback.")
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
            if effective_mode == "vector":
                rows = run_vector_search(
                    table,
                    select_columns=SEARCH_COLUMNS,
                    query_vector=query_vector or [],
                    query_text=config.query,
                    fetch_limit=fetch_limit,
                    reranker=effective_reranker,
                    cross_encoder_model=config.cross_encoder_model,
                )
            elif effective_mode == "fts":
                rows = run_fts_search(
                    table,
                    select_columns=SEARCH_COLUMNS,
                    query_text=config.query,
                    fetch_limit=fetch_limit,
                    reranker=effective_reranker,
                    cross_encoder_model=config.cross_encoder_model,
                )
            else:
                rows = run_hybrid_search(
                    table,
                    select_columns=SEARCH_COLUMNS,
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
            logger.warning("PDF Ollama reranking unavailable; keeping base order.")
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

    prepared = _with_warnings(prepared, warnings)
    logger.info("PDF search produced {} hits.", len(prepared))
    return {
        "results": prepared,
        "warnings": warnings,
        "effective_mode": effective_mode,
        "effective_reranker": effective_reranker,
    }


def format_search_results(payload: dict[str, Any]) -> str:
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
        page_label = row.get("page_label") or row.get("page") or "?"
        section = row.get("section") or "Document"
        lines.append(
            f"[{row['rank']}] {row['source_path']} | page={page_label} | "
            f"section={section} | chunk={row['chunk_index']}{score_text}"
        )
        lines.append(row["snippet"])
        lines.append("")
    return "\n".join(lines).rstrip()
