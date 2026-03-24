from __future__ import annotations

import re
from typing import Any, Sequence

from brains.config import BrainsPaths


def open_table(paths: BrainsPaths):
    import lancedb

    db = lancedb.connect(str(paths.db_uri))
    return db.open_table(paths.table_name)


def validate_search_config(config) -> None:
    if config.k <= 0:
        raise ValueError("k must be greater than 0.")
    if config.fetch_k < config.k:
        raise ValueError("fetch_k must be greater than or equal to k.")
    if config.mode not in {"auto", "vector", "fts", "hybrid", "hybrid-graph"}:
        raise ValueError("mode must be one of: auto, vector, fts, hybrid, hybrid-graph.")
    if config.reranker not in {"none", "rrf", "cross-encoder", "ollama"}:
        raise ValueError("reranker must be one of: none, rrf, cross-encoder, ollama.")
    if config.mode not in {"auto", "hybrid", "hybrid-graph"} and config.reranker == "rrf":
        raise ValueError("rrf reranking is only supported for hybrid search.")
    if config.min_score is not None and not 0.0 <= config.min_score <= 1.0:
        raise ValueError("min_score must be between 0.0 and 1.0.")
    if config.max_distance is not None and config.max_distance < 0.0:
        raise ValueError("max_distance must be greater than or equal to 0.0.")


def resolve_fetch_limit(*, k: int, fetch_k: int, reranker: str) -> int:
    if reranker in {"rrf", "cross-encoder", "ollama"}:
        return fetch_k
    return k


def resolve_query_mode(*, query: str, requested_mode: str) -> tuple[str, str | None]:
    if requested_mode != "auto":
        return requested_mode, None

    normalized = query.strip()
    if not normalized:
        return "hybrid", "Auto mode chose hybrid retrieval for an empty query."

    exact_patterns = (
        r"\[\[[^\]]+\]\]",
        r"\b[^\s/]+\.(?:md|pdf)\b",
        r"(?:^|[\s(])(?:UA|EN)/[^\s]+",
        r'"[^"]+"',
        r"'[^']+'",
        r"`[^`]+`",
    )
    if any(re.search(pattern, normalized) for pattern in exact_patterns):
        return "fts", "Auto mode chose FTS for an exact-match or path-like query."

    relation_patterns = (
        r"\brelated\b",
        r"\brelationship\b",
        r"\bconnect(?:ed|ion)?\b",
        r"\bpath\b",
        r"\bdepends?\b",
        r"\bcompare\b",
        r"\bversus\b",
        r"\bvs\b",
        r"\bbetween\b.+\band\b",
        r"\bshared\b",
        r"\bcommon\b",
        r"\bbridge\b",
        r"\bdifference between\b",
        r"\bhow .* relate",
    )
    if any(re.search(pattern, normalized, re.I) for pattern in relation_patterns):
        return "hybrid-graph", "Auto mode chose hybrid-graph retrieval for a relation-oriented query."

    if re.search(r"\b[A-Z0-9_-]{4,}\b", normalized) and len(normalized.split()) <= 3:
        return "fts", "Auto mode chose FTS for a short exact-term query."

    return "hybrid", "Auto mode chose hybrid retrieval for a semantic lookup."


def apply_result_thresholds(
    rows: Sequence[dict[str, Any]],
    *,
    min_score: float | None,
    max_distance: float | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    filtered: list[dict[str, Any]] = []
    dropped_for_score = 0
    dropped_for_distance = 0

    for row in rows:
        score = _coerce_float(row.get("_relevance_score"))
        if score is None:
            score = _coerce_float(row.get("_score"))
        distance = _coerce_float(row.get("_distance"))

        if min_score is not None and score is not None and score < min_score:
            dropped_for_score += 1
            continue
        if max_distance is not None and distance is not None and distance > max_distance:
            dropped_for_distance += 1
            continue
        filtered.append(dict(row))

    warnings: list[str] = []
    if dropped_for_score:
        warnings.append(
            f"Filtered {dropped_for_score} low-score hits below min_score={min_score:.3f}."
        )
    if dropped_for_distance:
        warnings.append(
            f"Filtered {dropped_for_distance} distant hits above max_distance={max_distance:.3f}."
        )
    return filtered, warnings


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def embed_query_text(
    query: str,
    *,
    model: str,
    base_url: str,
) -> list[float]:
    from langchain_ollama import OllamaEmbeddings

    embedder = OllamaEmbeddings(
        model=model,
        base_url=base_url,
        validate_model_on_init=False,
    )
    return embedder.embed_query(query)


def make_cross_encoder_reranker(model_name: str):
    from lancedb.rerankers import CrossEncoderReranker

    return CrossEncoderReranker(
        model_name=model_name,
        column="text",
        device="cpu",
    )


def run_vector_search(
    table,
    *,
    select_columns: Sequence[str],
    query_vector: list[float],
    query_text: str,
    fetch_limit: int,
    reranker: str,
    cross_encoder_model: str,
) -> list[dict[str, Any]]:
    builder = (
        table.search(
            query_vector,
            query_type="vector",
            vector_column_name="vector",
        )
        .select(list(select_columns))
    )
    if reranker == "cross-encoder":
        builder = builder.rerank(
            make_cross_encoder_reranker(cross_encoder_model),
            query_string=query_text,
        )
    return builder.limit(fetch_limit).to_list()


def run_fts_search(
    table,
    *,
    select_columns: Sequence[str],
    query_text: str,
    fetch_limit: int,
    reranker: str,
    cross_encoder_model: str,
) -> list[dict[str, Any]]:
    builder = (
        table.search(
            query_text,
            query_type="fts",
            fts_columns="text",
        )
        .select(list(select_columns))
    )
    if reranker == "cross-encoder":
        builder = builder.rerank(make_cross_encoder_reranker(cross_encoder_model))
    return builder.limit(fetch_limit).to_list()


def run_hybrid_search(
    table,
    *,
    select_columns: Sequence[str],
    query_vector: list[float],
    query_text: str,
    fetch_limit: int,
    reranker: str,
    cross_encoder_model: str,
) -> list[dict[str, Any]]:
    from lancedb.rerankers import RRFReranker

    builder = (
        table.search(
            query_type="hybrid",
            vector_column_name="vector",
            fts_columns="text",
        )
        .vector(query_vector)
        .text(query_text)
        .select(list(select_columns))
    )
    if reranker == "cross-encoder":
        builder = builder.rerank(make_cross_encoder_reranker(cross_encoder_model))
    else:
        builder = builder.rerank(RRFReranker())
    return builder.limit(fetch_limit).to_list()


def apply_ollama_rerank(
    rows: Sequence[dict[str, Any]],
    *,
    query: str,
    model: str,
    base_url: str,
    top_k: int,
) -> list[dict[str, Any]]:
    from langchain_ollama import ChatOllama

    llm = ChatOllama(
        model=model,
        base_url=base_url,
        temperature=0,
        num_predict=16,
        validate_model_on_init=False,
    )
    reranked: list[dict[str, Any]] = []
    for row in rows:
        prompt = (
            "You are reranking scientific PDF passages for retrieval.\n"
            "Score the passage relevance to the query from 0 to 100.\n"
            "Return only the integer score.\n\n"
            f"Query:\n{query}\n\n"
            f"Passage:\n{row['text']}"
        )
        response = llm.invoke(prompt)
        raw = response.content if isinstance(response.content, str) else str(response.content)
        match = re.search(r"-?\d+", raw)
        score = int(match.group(0)) if match else 0
        score = max(0, min(100, score))
        enriched = dict(row)
        enriched["_relevance_score"] = score / 100.0
        enriched["_ollama_rerank_raw"] = raw
        reranked.append(enriched)
    reranked.sort(key=lambda item: item.get("_relevance_score", 0.0), reverse=True)
    return reranked[:top_k]
