from __future__ import annotations

from urllib import error

from brains.shared import ollama as ollama_shared


def test_resolve_installed_ollama_model_prefers_exact_or_alias(monkeypatch) -> None:
    monkeypatch.setattr(
        ollama_shared,
        "list_installed_ollama_models",
        lambda base_url: ["bge-m3"],
    )

    resolved = ollama_shared.resolve_installed_ollama_model(
        "bge-m3:latest",
        base_url="http://127.0.0.1:11434",
    )

    assert resolved.resolved == "bge-m3"
    assert resolved.fallback_used is False
    assert resolved.warning is None


def test_resolve_installed_ollama_model_uses_fallback_when_available(monkeypatch) -> None:
    monkeypatch.setattr(
        ollama_shared,
        "list_installed_ollama_models",
        lambda base_url: ["e5-small:latest"],
    )

    resolved = ollama_shared.resolve_installed_ollama_model(
        "bge-m3:latest",
        base_url="http://127.0.0.1:11434",
        fallback_models=["e5-small:latest", "bge-small:latest"],
    )

    assert resolved.resolved == "e5-small:latest"
    assert resolved.fallback_used is True
    assert resolved.warning is not None


def test_resolve_installed_ollama_model_returns_requested_on_probe_error(monkeypatch) -> None:
    def fake_list_models(base_url: str) -> list[str]:
        raise error.URLError("offline")

    monkeypatch.setattr(ollama_shared, "list_installed_ollama_models", fake_list_models)

    resolved = ollama_shared.resolve_installed_ollama_model(
        "bge-m3:latest",
        base_url="http://127.0.0.1:11434",
        fallback_models=["e5-small:latest"],
    )

    assert resolved.resolved == "bge-m3:latest"
    assert resolved.fallback_used is False
    assert resolved.warning is not None
