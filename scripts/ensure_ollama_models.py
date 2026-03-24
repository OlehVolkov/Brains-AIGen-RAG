#!/usr/bin/env python3
"""
Reusable Ollama model bootstrapper for local retrieval stacks.

Purpose:
- check whether the repository's recommended Ollama models are present;
- pull missing embedding/reranker models through the Ollama HTTP API;
- provide a portable helper that other agents can adapt to a different repository structure.

Adapt first when reusing in another repository:
- `config/brains.toml` and `config/local.toml` if the target project uses another model roster;
- `brains_root()` / `repo_root()` if the nested Python project is not under `/.brains`;
- the selected default profiles if another repository does not need all model families.
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


def iter_pull_ollama_model_statuses(model: str, *, base_url: str) -> list[dict[str, object]]:
    payload = {"name": canonical_model_name(model), "stream": True}
    req = request.Request(
        base_url.rstrip("/") + "/api/pull",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    events: list[dict[str, object]] = []
    with request.urlopen(req, timeout=600.0) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if not line:
                continue
            item = json.loads(line)
            if isinstance(item, dict):
                events.append(item)
    return events


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
    parser = argparse.ArgumentParser(description="Ensure the repository's Ollama models are installed.")
    parser.add_argument(
        "--base-url",
        default=None,
        help="Override the Ollama base URL. Defaults to the configured `/.brains` value.",
    )
    parser.add_argument(
        "--profile",
        action="append",
        choices=["embeddings", "reranker", "lightweight", "multilingual", "all"],
        help="Restrict installation to one or more model profiles. Defaults to all.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report which models are missing, without pulling them.",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Emit JSON instead of human-readable text.",
    )
    return parser.parse_args()


def _selected_models(profiles: list[str] | None) -> list[str]:
    config = load_ollama_config()
    configured_profiles = {
        name: (
            str(profile["preferred_model"]),
            *list(profile.get("fallback_models", [])),
        )
        for name, profile in dict(config["profiles"]).items()
        if isinstance(profile, dict)
    }
    chosen_profiles = profiles or ["all"]
    if "all" in chosen_profiles:
        chosen_profiles = list(configured_profiles)
    models: list[str] = []
    for profile in chosen_profiles:
        models.extend(configured_profiles[profile])
    return unique_model_names(models)


def main() -> int:
    args = parse_args()
    config = load_ollama_config()
    base_url = args.base_url or str(config["base_url"])
    target_models = _selected_models(args.profile)
    try:
        installed_before = list_installed_ollama_models(base_url)
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

    installed_normalized = {normalize_model_name(name) for name in installed_before}
    missing = [name for name in target_models if normalize_model_name(name) not in installed_normalized]
    pulled: list[dict[str, object]] = []
    if not args.dry_run:
        for model in missing:
            events = iter_pull_ollama_model_statuses(model, base_url=base_url)
            status = ""
            digest = ""
            for event in events:
                value = event.get("status")
                if isinstance(value, str) and value:
                    status = value
                value = event.get("digest")
                if isinstance(value, str) and value:
                    digest = value
            pulled.append(
                {
                    "model": model,
                    "status": status or "completed",
                    "digest": digest or None,
                    "events": len(events),
                }
            )

    installed_after = list_installed_ollama_models(base_url)
    installed_after_normalized = {normalize_model_name(name) for name in installed_after}
    remaining_missing = [
        name for name in target_models if normalize_model_name(name) not in installed_after_normalized
    ]
    payload = {
        "status": "ok" if not remaining_missing else "partial",
        "base_url": base_url,
        "target_models": target_models,
        "installed_before": installed_before,
        "missing_before": missing,
        "dry_run": args.dry_run,
        "pulled": pulled,
        "installed_after": installed_after,
        "missing_after": remaining_missing,
    }
    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Ollama base URL: {base_url}")
        if not missing:
            print("All requested models are already installed.")
        elif args.dry_run:
            print("Missing models:")
            for model in missing:
                print(f"- {model}")
        else:
            print("Pull results:")
            for item in pulled:
                print(f"- {item['model']}: {item['status']}")
            if remaining_missing:
                print("Still missing:")
                for model in remaining_missing:
                    print(f"- {model}")
    return 0 if not remaining_missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
