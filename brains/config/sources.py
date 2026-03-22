from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from pydantic.fields import FieldInfo
from pydantic_settings import PydanticBaseSettingsSource


def read_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


class CombinedTomlSource(PydanticBaseSettingsSource):
    def __init__(
        self,
        settings_cls,
        *,
        config_path: Path,
        local_config_path: Path,
    ) -> None:
        super().__init__(settings_cls)
        self.config_path = config_path
        self.local_config_path = local_config_path

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        return deep_merge(read_toml(self.config_path), read_toml(self.local_config_path))
