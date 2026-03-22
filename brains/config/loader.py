from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
)

from brains.config.models import BrainsConfig, BrainsPaths, ResearchPaths
from brains.config.sources import CombinedTomlSource


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def repo_root() -> Path:
    return project_root()


def brains_root() -> Path:
    return project_root() / ".brains"


def config_path() -> Path:
    return project_root() / "config" / "brains.toml"


def local_config_path() -> Path:
    return project_root() / "config" / "local.toml"


def dotenv_path() -> Path:
    return project_root() / ".env"


def resolve_repo_path(base_repo_root: Path, raw_path: str | Path) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    return base_repo_root / candidate


class DefaultBrainsConfig(BrainsConfig):
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            EnvSettingsSource(
                settings_cls,
                env_prefix="BRAINS_",
                env_nested_delimiter="__",
            ),
            DotEnvSettingsSource(
                settings_cls,
                env_file=dotenv_path(),
                env_prefix="BRAINS_",
                env_nested_delimiter="__",
            ),
            CombinedTomlSource(
                settings_cls,
                config_path=config_path(),
                local_config_path=local_config_path(),
            ),
            file_secret_settings,
        )


def load_config(
    *,
    config_path: str | Path | None = None,
    local_config_path: str | Path | None = None,
) -> BrainsConfig:
    if config_path is None and local_config_path is None:
        return DefaultBrainsConfig()

    resolved_config_path = Path(config_path) if config_path else globals()["config_path"]()
    resolved_local_path = (
        Path(local_config_path)
        if local_config_path
        else globals()["local_config_path"]()
    )

    class CustomBrainsConfig(BrainsConfig):
        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            return (
                init_settings,
                EnvSettingsSource(
                    settings_cls,
                    env_prefix="BRAINS_",
                    env_nested_delimiter="__",
                ),
                DotEnvSettingsSource(
                    settings_cls,
                    env_file=dotenv_path(),
                    env_prefix="BRAINS_",
                    env_nested_delimiter="__",
                ),
                CombinedTomlSource(
                    settings_cls,
                    config_path=resolved_config_path,
                    local_config_path=resolved_local_path,
                ),
                file_secret_settings,
            )

    return CustomBrainsConfig()


@lru_cache(maxsize=1)
def get_config() -> BrainsConfig:
    return load_config()


def resolve_pdf_paths(
    *,
    pdf_dir: str | Path | None = None,
    index_root: str | Path | None = None,
    table_name: str | None = None,
) -> BrainsPaths:
    config = get_config()
    current_repo_root = repo_root()
    resolved_index_root = resolve_repo_path(
        current_repo_root,
        index_root or config.pdf.index_root,
    )
    return BrainsPaths(
        repo_root=current_repo_root,
        brains_root=brains_root(),
        pdf_dir=resolve_repo_path(current_repo_root, pdf_dir or config.pdf.pdf_dir),
        index_root=resolved_index_root,
        db_uri=resolved_index_root / "lancedb",
        manifest_path=resolved_index_root / "manifest.json",
        table_name=table_name or config.pdf.table_name,
    )


def resolve_vault_paths(
    *,
    index_root: str | Path | None = None,
    table_name: str | None = None,
) -> BrainsPaths:
    config = get_config()
    current_repo_root = repo_root()
    resolved_index_root = resolve_repo_path(
        current_repo_root,
        index_root or config.vault.index_root,
    )
    return BrainsPaths(
        repo_root=current_repo_root,
        brains_root=brains_root(),
        pdf_dir=resolve_repo_path(current_repo_root, config.pdf.pdf_dir),
        index_root=resolved_index_root,
        db_uri=resolved_index_root / "lancedb",
        manifest_path=resolved_index_root / "manifest.json",
        table_name=table_name or config.vault.table_name,
    )


def resolve_research_paths(
    *,
    index_root: str | Path | None = None,
) -> ResearchPaths:
    config = get_config()
    current_repo_root = repo_root()
    resolved_index_root = resolve_repo_path(
        current_repo_root,
        index_root or config.research.index_root,
    )
    return ResearchPaths(
        repo_root=current_repo_root,
        brains_root=brains_root(),
        index_root=resolved_index_root,
        memory_path=resolved_index_root / "memory.jsonl",
        sessions_dir=resolved_index_root / "sessions",
    )
