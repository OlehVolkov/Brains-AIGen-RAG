#!/usr/bin/env python3
"""
Reusable Ollama model presence checker for local retrieval stacks.

Purpose:
- report whether the repository's recommended Ollama models are already installed;
- show which embedding/reranker defaults `/.brains` will prefer at runtime;
- act as a small adaptation template for similar repositories with a different model roster.

Adapt first when reusing in another repository:
- `config/brains.toml` and `config/local.toml` if the target project needs different model families;
- `brains_root()` / `repo_root()` if the Python project is not under `/.brains`;
- CLI defaults if the target environment exposes Ollama at a different base URL.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import tomllib
from urllib import error
from urllib import request


def brains_root() -> Path:
    return Path(__file__).resolve().parent.parent


def repo_root() -> Path:
    return brains_root().parent


def canonical_model_name(name: str) -> str:
    model = name.strip()
    if not model:
        raise ValueError("Ollama model name must not be empty.")
    return model


def normalize_model_name(name: str) -> str:
    model = canonical_model_name(name)
    return model[:-7] if model.endswith(":latest") else model


def unique_model_names(names: list[str] | tuple[str, ...]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for raw_name in names:
        name = canonical_model_name(raw_name)
        normalized = normalize_model_name(name)
        if normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(name)
    return ordered


def list_installed_ollama_models(base_url: str) -> list[str]:
    with request.urlopen(base_url.rstrip("/") + "/api/tags", timeout=15.0) as response:
        payload = json.loads(response.read().decode("utf-8"))
    models = payload.get("models", [])
    installed: list[str] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        for key in ("name", "model"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                installed.append(value.strip())
                break
    return unique_model_names(installed)


def resolve_installed_ollama_model(
    preferred: str,
    *,
    base_url: str,
    fallback_models: list[str],
) -> tuple[str, bool, str | None]:
    requested = canonical_model_name(preferred)
    try:
        installed = list_installed_ollama_models(base_url)
    except (error.URLError, TimeoutError, OSError, ValueError) as exc:
        return requested, False, (
            "Ollama tags probe unavailable; using configured model without a preflight "
            f"check ({type(exc).__name__}: {exc})."
        )

    for model in installed:
        if normalize_model_name(model) == normalize_model_name(requested):
            return model, False, None
    for candidate in unique_model_names(fallback_models):
        for model in installed:
            if normalize_model_name(model) == normalize_model_name(candidate):
                return model, True, (
                    f"Preferred Ollama model '{requested}' is not installed; using fallback '{model}'."
                )
    return requested, False, (
        f"Ollama model '{requested}' is not installed locally. "
        "Run the ensure_ollama_models helper before indexing or search."
    )


def load_ollama_config() -> dict[str, object]:
    base_path = brains_root() / "config" / "brains.toml"
    if not base_path.exists():
        raise FileNotFoundError(f"Missing required config file: {base_path}")

    payload = tomllib.loads(base_path.read_text(encoding="utf-8"))
    ollama = payload.get("ollama")
    if not isinstance(ollama, dict):
        raise ValueError("`[ollama]` must exist in `.brains/config/brains.toml`.")

    config = dict(ollama)
    profiles = ollama.get("profiles")
    if not isinstance(profiles, dict):
        raise ValueError("`[ollama.profiles.*]` must exist in `.brains/config/brains.toml`.")
    config["profiles"] = {key: dict(value) for key, value in profiles.items() if isinstance(value, dict)}

    local_path = brains_root() / "config" / "local.toml"
    if local_path.exists():
        local_payload = tomllib.loads(local_path.read_text(encoding="utf-8"))
        local_ollama = local_payload.get("ollama")
        if isinstance(local_ollama, dict):
            local_profiles = local_ollama.get("profiles")
            if isinstance(local_profiles, dict):
                merged_profiles = dict(config["profiles"])
                for key, value in local_profiles.items():
                    if not isinstance(value, dict):
                        continue
                    merged_profiles[key] = {
                        **merged_profiles.get(key, {}),
                        **value,
                    }
                config["profiles"] = merged_profiles
            for key, value in local_ollama.items():
                if key == "profiles":
                    continue
                config[key] = value

    if "base_url" not in config:
        raise ValueError("`ollama.base_url` must be configured in `.brains/config/brains.toml`.")
    return config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check which recommended Ollama models are installed.")
    parser.add_argument(
        "--base-url",
        default=None,
        help="Override the Ollama base URL. Defaults to the configured `/.brains` value.",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Emit JSON instead of human-readable text.",
    )
    return parser.parse_args()


def _profile_summary(installed: list[str], base_url: str) -> dict[str, object]:
    config = load_ollama_config()
    profiles = dict(config["profiles"])
    configured_profiles = {
        name: (
            canonical_model_name(str(profile["preferred_model"])),
            *list(profile.get("fallback_models", [])),
        )
        for name, profile in profiles.items()
        if isinstance(profile, dict)
    }
    installed_normalized = {normalize_model_name(name) for name in installed}
    summary: dict[str, object] = {}
    for label, models in configured_profiles.items():
        preferred, *fallbacks = models
        resolved, fallback_used, warning = resolve_installed_ollama_model(
            preferred,
            base_url=base_url,
            fallback_models=fallbacks,
        )
        required = unique_model_names(models)
        summary[label] = {
            "preferred": preferred,
            "fallbacks": list(fallbacks),
            "resolved": resolved,
            "fallback_used": fallback_used,
            "warning": warning,
            "installed": [name for name in required if normalize_model_name(name) in installed_normalized],
            "missing": [name for name in required if normalize_model_name(name) not in installed_normalized],
        }
    return summary


def main() -> int:
    args = parse_args()
    config = load_ollama_config()
    base_url = args.base_url or str(config["base_url"])
    try:
        installed = list_installed_ollama_models(base_url)
    except (error.URLError, TimeoutError, OSError, ValueError) as exc:
        payload = {
            "status": "error",
            "base_url": base_url,
            "error": f"{type(exc).__name__}: {exc}",
        }
        if args.json_output:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"Ollama probe failed at {base_url}: {payload['error']}")
        return 1

    payload = {
        "status": "ok",
        "base_url": base_url,
        "installed_models": installed,
        "profiles": _profile_summary(installed, base_url),
    }
    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"Ollama base URL: {base_url}")
    print("")
    print("Installed models:")
    if installed:
        for model in installed:
            print(f"- {model}")
    else:
        print("- none")
    print("")
    print("Configured profiles:")
    for profile, data in payload["profiles"].items():
        print(f"- {profile}:")
        print(f"  preferred: {data['preferred']}")
        print(f"  resolved: {data['resolved']}")
        if data["fallbacks"]:
            print(f"  fallbacks: {', '.join(data['fallbacks'])}")
        if data["missing"]:
            print(f"  missing: {', '.join(data['missing'])}")
        if data["warning"]:
            print(f"  note: {data['warning']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
