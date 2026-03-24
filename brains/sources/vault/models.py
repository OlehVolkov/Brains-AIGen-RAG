from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict, Field

from brains.config import BrainsPaths, get_config
from brains.shared.health import resolve_active_index_paths


def _resolve_search_embed_model(paths: BrainsPaths, explicit_model: str | None) -> str:
    if explicit_model is not None:
        return explicit_model
    effective_paths, _pointer_path = resolve_active_index_paths(paths)
    if effective_paths.manifest_path.exists():
        payload = json.loads(effective_paths.manifest_path.read_text(encoding="utf-8"))
        manifest_model = payload.get("embed_model")
        if isinstance(manifest_model, str) and manifest_model:
            return manifest_model
    return get_config().ollama.embed_model


class VaultIndexConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    paths: BrainsPaths
    parser: str = Field(default_factory=lambda: get_config().vault.parser)
    embed_model: str = Field(default_factory=lambda: get_config().ollama.embed_model)
    ollama_base_url: str = Field(default_factory=lambda: get_config().ollama.base_url)
    chunk_size: int = Field(default_factory=lambda: get_config().vault.chunk_size)
    chunk_overlap: int = Field(default_factory=lambda: get_config().vault.chunk_overlap)
    batch_size: int = Field(default_factory=lambda: get_config().vault.batch_size)
    overwrite: bool = True

    @classmethod
    def from_settings(
        cls,
        *,
        paths: BrainsPaths,
        parser: str | None = None,
        embed_model: str | None = None,
        ollama_base_url: str | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        batch_size: int | None = None,
        overwrite: bool = True,
    ) -> "VaultIndexConfig":
        config = get_config()
        return cls(
            paths=paths,
            parser=config.vault.parser if parser is None else parser,
            embed_model=config.ollama.embed_model if embed_model is None else embed_model,
            ollama_base_url=config.ollama.base_url if ollama_base_url is None else ollama_base_url,
            chunk_size=config.vault.chunk_size if chunk_size is None else chunk_size,
            chunk_overlap=config.vault.chunk_overlap if chunk_overlap is None else chunk_overlap,
            batch_size=config.vault.batch_size if batch_size is None else batch_size,
            overwrite=overwrite,
        )


class VaultSearchConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    paths: BrainsPaths
    query: str
    mode: str = "hybrid"
    reranker: str = "none"
    embed_model: str = Field(default_factory=lambda: get_config().ollama.embed_model)
    ollama_base_url: str = Field(default_factory=lambda: get_config().ollama.base_url)
    cross_encoder_model: str = Field(
        default_factory=lambda: get_config().reranker.cross_encoder_model
    )
    ollama_rerank_model: str = Field(
        default_factory=lambda: get_config().ollama.rerank_model
    )
    k: int = 5
    fetch_k: int = 20
    graph_max_hops: int = Field(default_factory=lambda: get_config().graph.max_hops)
    snippet_chars: int = 320
    min_score: float | None = Field(default_factory=lambda: get_config().vault.min_score)
    max_distance: float | None = Field(default_factory=lambda: get_config().vault.max_distance)

    @classmethod
    def from_settings(
        cls,
        *,
        paths: BrainsPaths,
        query: str,
        mode: str = "hybrid",
        reranker: str = "none",
        embed_model: str | None = None,
        ollama_base_url: str | None = None,
        cross_encoder_model: str | None = None,
        ollama_rerank_model: str | None = None,
        k: int = 5,
        fetch_k: int = 20,
        graph_max_hops: int | None = None,
        snippet_chars: int = 320,
        min_score: float | None = None,
        max_distance: float | None = None,
    ) -> "VaultSearchConfig":
        config = get_config()
        return cls(
            paths=paths,
            query=query,
            mode=mode,
            reranker=reranker,
            embed_model=_resolve_search_embed_model(paths, embed_model),
            ollama_base_url=config.ollama.base_url if ollama_base_url is None else ollama_base_url,
            cross_encoder_model=(
                config.reranker.cross_encoder_model
                if cross_encoder_model is None
                else cross_encoder_model
            ),
            ollama_rerank_model=(
                config.ollama.rerank_model
                if ollama_rerank_model is None
                else ollama_rerank_model
            ),
            k=k,
            fetch_k=fetch_k,
            graph_max_hops=(
                config.graph.max_hops if graph_max_hops is None else graph_max_hops
            ),
            snippet_chars=snippet_chars,
            min_score=config.vault.min_score if min_score is None else min_score,
            max_distance=config.vault.max_distance if max_distance is None else max_distance,
        )
