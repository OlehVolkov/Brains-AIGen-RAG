from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from brain.config import ResearchPaths, get_config


class ResearchRunConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    paths: ResearchPaths
    query: str
    model: str = Field(default_factory=lambda: get_config().research.model)
    ollama_base_url: str = Field(default_factory=lambda: get_config().ollama.base_url)
    vault_k: int = Field(default_factory=lambda: get_config().research.vault_k)
    pdf_k: int = Field(default_factory=lambda: get_config().research.pdf_k)
    memory_k: int = Field(default_factory=lambda: get_config().research.memory_k)
    reflection_rounds: int = Field(
        default_factory=lambda: get_config().research.reflection_rounds
    )
    session_id: str | None = None
    save_memory: bool = True

    @classmethod
    def from_settings(
        cls,
        *,
        paths: ResearchPaths,
        query: str,
        model: str | None = None,
        ollama_base_url: str | None = None,
        vault_k: int | None = None,
        pdf_k: int | None = None,
        memory_k: int | None = None,
        reflection_rounds: int | None = None,
        session_id: str | None = None,
        save_memory: bool = True,
    ) -> "ResearchRunConfig":
        config = get_config()
        return cls(
            paths=paths,
            query=query,
            model=config.research.model if model is None else model,
            ollama_base_url=config.ollama.base_url if ollama_base_url is None else ollama_base_url,
            vault_k=config.research.vault_k if vault_k is None else vault_k,
            pdf_k=config.research.pdf_k if pdf_k is None else pdf_k,
            memory_k=config.research.memory_k if memory_k is None else memory_k,
            reflection_rounds=reflection_rounds
            if reflection_rounds is not None
            else config.research.reflection_rounds,
            session_id=session_id,
            save_memory=save_memory,
        )
