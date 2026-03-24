from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OllamaModelProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    preferred_model: str
    fallback_models: list[str] = Field(default_factory=list)


class OllamaProfilesConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    embeddings: OllamaModelProfile = Field(
        default_factory=lambda: OllamaModelProfile(
            preferred_model="bge-m3:latest",
            fallback_models=[
                "bge-large:latest",
                "nomic-embed-text:latest",
                "e5-small:latest",
                "bge-small:latest",
            ],
        )
    )
    lightweight: OllamaModelProfile = Field(
        default_factory=lambda: OllamaModelProfile(
            preferred_model="e5-small:latest",
            fallback_models=[
                "nomic-embed-text:latest",
                "bge-small:latest",
                "bge-large:latest",
                "bge-m3:latest",
            ],
        )
    )
    multilingual: OllamaModelProfile = Field(
        default_factory=lambda: OllamaModelProfile(
            preferred_model="bge-m3:latest",
            fallback_models=[
                "bge-large:latest",
                "e5-small:latest",
                "bge-small:latest",
            ],
        )
    )
    reranker: OllamaModelProfile = Field(
        default_factory=lambda: OllamaModelProfile(
            preferred_model="qllama/bge-reranker-large:q8_0",
            fallback_models=[],
        )
    )


class OllamaConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    base_url: str = "http://127.0.0.1:11434"
    profiles: OllamaProfilesConfig = Field(default_factory=OllamaProfilesConfig)

    @property
    def embed_model(self) -> str:
        return self.profiles.embeddings.preferred_model

    @property
    def embed_fallback_models(self) -> list[str]:
        return list(self.profiles.embeddings.fallback_models)

    @property
    def lightweight_embed_model(self) -> str:
        return self.profiles.lightweight.preferred_model

    @property
    def lightweight_embed_fallback_models(self) -> list[str]:
        return list(self.profiles.lightweight.fallback_models)

    @property
    def multilingual_embed_model(self) -> str:
        return self.profiles.multilingual.preferred_model

    @property
    def multilingual_embed_fallback_models(self) -> list[str]:
        return list(self.profiles.multilingual.fallback_models)

    @property
    def rerank_model(self) -> str:
        return self.profiles.reranker.preferred_model

    @property
    def rerank_fallback_models(self) -> list[str]:
        return list(self.profiles.reranker.fallback_models)


class RerankerConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    cross_encoder_model: str = "BAAI/bge-reranker-large"


class PdfConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    table_name: str = "scientific_pdf_chunks"
    pdf_dir: str = "PDF"
    fetch_note_globs: list[str] = Field(default_factory=list)
    index_root: str = ".brains/.index/pdf_search"
    parser: str = "auto"
    grobid_url: str = "http://127.0.0.1:8070"
    marker_command: str = "marker_single"
    chunk_size: int = 1200
    chunk_overlap: int = 200
    batch_size: int = 32
    min_score: float | None = None
    max_distance: float | None = None


class VaultConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    table_name: str = "vault_markdown_chunks"
    index_root: str = ".brains/.index/vault_search"
    parser: str = "native"
    chunk_size: int = 1200
    chunk_overlap: int = 200
    batch_size: int = 32
    min_score: float | None = None
    max_distance: float | None = None


class GraphConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    index_root: str = ".brains/.index/graph_search"
    graph_file: str = "graph.json"
    governance_files: list[str] = Field(default_factory=list)
    special_page_pairs: list[tuple[str, str]] = Field(default_factory=list)
    max_hops: int = 1
    k: int = 5


class HealthConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    pdf_probe_query: str | None = None
    vault_probe_query: str | None = None


class ResearchConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    index_root: str = ".brains/.index/research"
    model: str = "llama3.2:3b"
    vault_k: int = 5
    pdf_k: int = 5
    memory_k: int = 3
    reflection_rounds: int = 1


class BrainsConfig(BaseSettings):
    model_config = SettingsConfigDict(
        frozen=True,
        extra="ignore",
        env_prefix="BRAINS_",
        env_nested_delimiter="__",
        env_file_encoding="utf-8",
    )

    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    reranker: RerankerConfig = Field(default_factory=RerankerConfig)
    pdf: PdfConfig = Field(default_factory=PdfConfig)
    vault: VaultConfig = Field(default_factory=VaultConfig)
    graph: GraphConfig = Field(default_factory=GraphConfig)
    health: HealthConfig = Field(default_factory=HealthConfig)
    research: ResearchConfig = Field(default_factory=ResearchConfig)


class BrainsPaths(BaseModel):
    model_config = ConfigDict(frozen=True)

    repo_root: Path
    brains_root: Path
    pdf_dir: Path
    index_root: Path
    db_uri: Path
    manifest_path: Path
    table_name: str


class ResearchPaths(BaseModel):
    model_config = ConfigDict(frozen=True)

    repo_root: Path
    brains_root: Path
    index_root: Path
    memory_path: Path
    sessions_dir: Path


class GraphPaths(BaseModel):
    model_config = ConfigDict(frozen=True)

    repo_root: Path
    brains_root: Path
    index_root: Path
    graph_path: Path
    manifest_path: Path
