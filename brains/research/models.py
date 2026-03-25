from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from brains.config import ResearchPaths, get_config


class ResearchRunConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    paths: ResearchPaths
    query: str
    vault_k: int = Field(default_factory=lambda: get_config().research.vault_k)
    pdf_k: int = Field(default_factory=lambda: get_config().research.pdf_k)
    memory_k: int = Field(default_factory=lambda: get_config().research.memory_k)
    session_id: str | None = None
    save_memory: bool = True

    @classmethod
    def from_settings(
        cls,
        *,
        paths: ResearchPaths,
        query: str,
        vault_k: int | None = None,
        pdf_k: int | None = None,
        memory_k: int | None = None,
        session_id: str | None = None,
        save_memory: bool = True,
    ) -> "ResearchRunConfig":
        config = get_config()
        return cls(
            paths=paths,
            query=query,
            vault_k=config.research.vault_k if vault_k is None else vault_k,
            pdf_k=config.research.pdf_k if pdf_k is None else pdf_k,
            memory_k=config.research.memory_k if memory_k is None else memory_k,
            session_id=session_id,
            save_memory=save_memory,
        )
