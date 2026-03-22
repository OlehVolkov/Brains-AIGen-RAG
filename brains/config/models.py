from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OllamaConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    embed_model: str = "nomic-embed-text"
    base_url: str = "http://127.0.0.1:11434"
    rerank_model: str = "llama3.2:3b"


class RerankerConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    cross_encoder_model: str = "cross-encoder/ms-marco-TinyBERT-L-6"


class PdfConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    table_name: str = "scientific_pdf_chunks"
    pdf_dir: str = "PDF"
    index_root: str = ".brains/.index/pdf_search"
    parser: str = "auto"
    grobid_url: str = "http://127.0.0.1:8070"
    marker_command: str = "marker_single"
    chunk_size: int = 1200
    chunk_overlap: int = 200
    batch_size: int = 32


class VaultConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    table_name: str = "vault_markdown_chunks"
    index_root: str = ".brains/.index/vault_search"
    chunk_size: int = 1200
    chunk_overlap: int = 200
    batch_size: int = 32


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
