from __future__ import annotations

from brains.shared.langchain import embed_texts, embed_texts_with_model_fallback


def test_embed_texts_uses_primary_embed_endpoint(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_post(url: str, payload: dict[str, object], *, timeout: float = 30.0):
        calls.append((url, payload))
        if url.endswith("/api/embed"):
            return {"embeddings": [[1.0, 2.0], [3.0, 4.0]]}
        raise AssertionError("legacy endpoint should not be used")

    monkeypatch.setattr("brains.shared.langchain._post_json", fake_post)

    vectors = embed_texts(
        ["a", "b"],
        model="nomic-embed-text",
        base_url="http://127.0.0.1:11434",
        batch_size=8,
    )

    assert vectors == [[1.0, 2.0], [3.0, 4.0]]
    assert calls == [
        (
            "http://127.0.0.1:11434/api/embed",
            {"model": "nomic-embed-text", "input": ["a", "b"]},
        )
    ]


def test_embed_texts_falls_back_to_legacy_embeddings_endpoint(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_post(url: str, payload: dict[str, object], *, timeout: float = 30.0):
        calls.append((url, payload))
        if url.endswith("/api/embed"):
            raise TimeoutError("embed endpoint unavailable")
        return {"embedding": [0.5, 0.25]}

    monkeypatch.setattr("brains.shared.langchain._post_json", fake_post)

    vectors = embed_texts(
        ["alpha", "beta"],
        model="nomic-embed-text",
        base_url="http://127.0.0.1:11434",
        batch_size=8,
    )

    assert vectors == [[0.5, 0.25], [0.5, 0.25]]
    assert calls == [
        (
            "http://127.0.0.1:11434/api/embed",
            {"model": "nomic-embed-text", "input": ["alpha", "beta"]},
        ),
        (
            "http://127.0.0.1:11434/api/embed",
            {"model": "nomic-embed-text", "input": ["alpha", "beta"]},
        ),
        (
            "http://127.0.0.1:11434/api/embed",
            {"model": "nomic-embed-text", "input": ["alpha", "beta"]},
        ),
        (
            "http://127.0.0.1:11434/api/embeddings",
            {"model": "nomic-embed-text", "prompt": "alpha"},
        ),
        (
            "http://127.0.0.1:11434/api/embeddings",
            {"model": "nomic-embed-text", "prompt": "beta"},
        ),
    ]


def test_embed_texts_retries_transient_primary_embed_failure(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    attempts = {"count": 0}

    def fake_post(url: str, payload: dict[str, object], *, timeout: float = 30.0):
        calls.append((url, payload))
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise TimeoutError("temporary Ollama failure")
        if url.endswith("/api/embed"):
            return {"embeddings": [[0.1, 0.2]]}
        raise AssertionError("legacy endpoint should not be used after a successful retry")

    monkeypatch.setattr("brains.shared.langchain._post_json", fake_post)

    vectors = embed_texts(
        ["alpha"],
        model="bge-m3:latest",
        base_url="http://127.0.0.1:11434",
        batch_size=1,
    )

    assert vectors == [[0.1, 0.2]]
    assert calls == [
        (
            "http://127.0.0.1:11434/api/embed",
            {"model": "bge-m3:latest", "input": ["alpha"]},
        ),
        (
            "http://127.0.0.1:11434/api/embed",
            {"model": "bge-m3:latest", "input": ["alpha"]},
        ),
    ]


def test_embed_texts_with_model_fallback_uses_second_model(monkeypatch) -> None:
    calls: list[str] = []

    def fake_embed_texts(
        texts,
        *,
        model: str,
        base_url: str,
        batch_size: int,
    ):
        calls.append(model)
        if model == "bge-m3:latest":
            raise RuntimeError("HTTP 500")
        return [[9.0, 1.0]]

    monkeypatch.setattr("brains.shared.langchain.embed_texts", fake_embed_texts)

    vectors, actual_model, warnings = embed_texts_with_model_fallback(
        ["alpha"],
        model="bge-m3:latest",
        fallback_models=["bge-large:latest", "nomic-embed-text:latest"],
        base_url="http://127.0.0.1:11434",
        batch_size=8,
    )

    assert vectors == [[9.0, 1.0]]
    assert actual_model == "bge-large:latest"
    assert calls == ["bge-m3:latest", "bge-large:latest"]
    assert any("fell back from 'bge-m3:latest' to 'bge-large:latest'" in warning for warning in warnings)
