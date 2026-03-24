from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Sequence
from urllib import error, request

@dataclass(frozen=True)
class ResolvedOllamaModel:
    requested: str
    resolved: str
    fallback_used: bool
    warning: str | None = None


def canonical_model_name(name: str) -> str:
    model = name.strip()
    if not model:
        raise ValueError("Ollama model name must not be empty.")
    return model


def normalize_model_name(name: str) -> str:
    model = canonical_model_name(name)
    return model[:-7] if model.endswith(":latest") else model


def model_aliases(name: str) -> tuple[str, ...]:
    model = canonical_model_name(name)
    aliases: list[str] = [model]
    normalized = normalize_model_name(model)
    if normalized != model:
        aliases.append(normalized)
    else:
        aliases.append(f"{model}:latest")
    return tuple(dict.fromkeys(aliases))


def unique_model_names(names: Sequence[str]) -> list[str]:
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
    url = base_url.rstrip("/") + "/api/tags"
    with request.urlopen(url, timeout=15.0) as response:
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


def match_installed_model(requested: str, installed_models: Sequence[str]) -> str | None:
    normalized_requested = normalize_model_name(requested)
    for candidate in installed_models:
        if normalize_model_name(candidate) == normalized_requested:
            return candidate
    return None


def resolve_installed_ollama_model(
    preferred: str,
    *,
    base_url: str,
    fallback_models: Sequence[str] = (),
    allow_fallback: bool = True,
) -> ResolvedOllamaModel:
    requested = canonical_model_name(preferred)
    try:
        installed = list_installed_ollama_models(base_url)
    except (error.URLError, TimeoutError, OSError, ValueError) as exc:
        return ResolvedOllamaModel(
            requested=requested,
            resolved=requested,
            fallback_used=False,
            warning=(
                "Ollama tags probe unavailable; using configured model without a preflight "
                f"check ({type(exc).__name__}: {exc})."
            ),
        )

    matched = match_installed_model(requested, installed)
    if matched is not None:
        return ResolvedOllamaModel(
            requested=requested,
            resolved=matched,
            fallback_used=False,
        )

    if allow_fallback:
        for candidate in unique_model_names(fallback_models):
            matched = match_installed_model(candidate, installed)
            if matched is None:
                continue
            return ResolvedOllamaModel(
                requested=requested,
                resolved=matched,
                fallback_used=True,
                warning=(
                    f"Preferred Ollama model '{requested}' is not installed; "
                    f"using fallback '{matched}'."
                ),
            )

    return ResolvedOllamaModel(
        requested=requested,
        resolved=requested,
        fallback_used=False,
        warning=(
            f"Ollama model '{requested}' is not installed locally. "
            "Run the ensure_ollama_models helper before indexing or search."
        ),
    )


def iter_pull_ollama_model_statuses(model: str, *, base_url: str) -> list[dict[str, Any]]:
    payload = {"name": canonical_model_name(model), "stream": True}
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        base_url.rstrip("/") + "/api/pull",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    events: list[dict[str, Any]] = []
    with request.urlopen(req, timeout=600.0) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if not line:
                continue
            data = json.loads(line)
            if isinstance(data, dict):
                events.append(data)
    return events
