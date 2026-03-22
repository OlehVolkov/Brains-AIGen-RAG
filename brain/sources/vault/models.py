from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from brain.config import BrainPaths, get_config


class VaultIndexConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    paths: BrainPaths
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
        paths: BrainPaths,
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
            embed_model=config.ollama.embed_model if embed_model is None else embed_model,
            ollama_base_url=config.ollama.base_url if ollama_base_url is None else ollama_base_url,
            chunk_size=config.vault.chunk_size if chunk_size is None else chunk_size,
            chunk_overlap=config.vault.chunk_overlap if chunk_overlap is None else chunk_overlap,
            batch_size=config.vault.batch_size if batch_size is None else batch_size,
            overwrite=overwrite,
        )


class VaultSearchConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    paths: BrainPaths
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
    snippet_chars: int = 320

    @classmethod
    def from_settings(
        cls,
        *,
        paths: BrainPaths,
        query: str,
        mode: str = "hybrid",
        reranker: str = "none",
        embed_model: str | None = None,
        ollama_base_url: str | None = None,
        cross_encoder_model: str | None = None,
        ollama_rerank_model: str | None = None,
        k: int = 5,
        fetch_k: int = 20,
        snippet_chars: int = 320,
    ) -> "VaultSearchConfig":
        config = get_config()
        return cls(
            paths=paths,
            query=query,
            mode=mode,
            reranker=reranker,
            embed_model=config.ollama.embed_model if embed_model is None else embed_model,
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
            snippet_chars=snippet_chars,
        )
