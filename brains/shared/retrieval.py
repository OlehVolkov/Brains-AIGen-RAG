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
    if config.mode not in {"vector", "fts", "hybrid"}:
        raise ValueError("mode must be one of: vector, fts, hybrid.")
    if config.reranker not in {"none", "rrf", "cross-encoder", "ollama"}:
        raise ValueError("reranker must be one of: none, rrf, cross-encoder, ollama.")
    if config.mode != "hybrid" and config.reranker == "rrf":
        raise ValueError("rrf reranking is only supported for hybrid search.")


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
