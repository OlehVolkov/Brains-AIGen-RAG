from __future__ import annotations

from brains.shared.langchain import embed_texts


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
            "http://127.0.0.1:11434/api/embeddings",
            {"model": "nomic-embed-text", "prompt": "alpha"},
        ),
        (
            "http://127.0.0.1:11434/api/embeddings",
            {"model": "nomic-embed-text", "prompt": "beta"},
        ),
    ]
