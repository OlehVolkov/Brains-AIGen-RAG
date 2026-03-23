from __future__ import annotations

import json
import time
from typing import Any
from typing import TYPE_CHECKING, Sequence
from urllib import error, request

from brains.shared.text import chunked, normalize_text

if TYPE_CHECKING:
    from langchain_core.documents import Document


def split_documents(
    documents: list[Document],
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[Document]:
    from langchain_core.documents import Document
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    split_docs = splitter.split_documents(documents)
    prepared: list[Document] = []
    for index, doc in enumerate(split_docs):
        text = normalize_text(doc.page_content)
        if not text:
            continue
        metadata = dict(doc.metadata)
        metadata["chunk_index"] = index
        metadata["char_count"] = len(text)
        metadata["word_count"] = len(text.split())
        prepared.append(Document(page_content=text, metadata=metadata))
    return prepared


def embed_texts(
    texts: Sequence[str],
    *,
    model: str,
    base_url: str,
    batch_size: int,
) -> list[list[float]]:
    vectors: list[list[float]] = []
    for batch in chunked(list(texts), batch_size):
        vectors.extend(
            _embed_batch_with_fallback(
                list(batch),
                model=model,
                base_url=base_url,
            )
        )
    return vectors


def _post_json(url: str, payload: dict[str, Any], *, timeout: float = 30.0) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw)


def _post_json_with_retries(
    url: str,
    payload: dict[str, Any],
    *,
    timeout: float = 30.0,
    attempts: int = 3,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return _post_json(url, payload, timeout=timeout)
        except (error.URLError, TimeoutError, OSError, ValueError) as exc:
            last_error = exc
            if attempt >= attempts:
                raise
            time.sleep(0.5 * attempt)
    if last_error is not None:
        raise last_error
    raise RuntimeError("Embedding request failed without a captured exception.")


def _embed_batch_with_fallback(
    texts: list[str],
    *,
    model: str,
    base_url: str,
) -> list[list[float]]:
    primary_url = base_url.rstrip("/") + "/api/embed"
    try:
        response = _post_json_with_retries(primary_url, {"model": model, "input": texts})
        vectors = response.get("embeddings")
        if not isinstance(vectors, list) or not vectors:
            raise RuntimeError("Ollama /api/embed returned no embeddings.")
        return [list(vector) for vector in vectors]
    except (error.URLError, TimeoutError, OSError, ValueError, RuntimeError):
        legacy_url = base_url.rstrip("/") + "/api/embeddings"
        legacy_vectors: list[list[float]] = []
        for text in texts:
            response = _post_json_with_retries(legacy_url, {"model": model, "prompt": text})
            vector = response.get("embedding")
            if not isinstance(vector, list) or not vector:
                raise RuntimeError("Ollama /api/embeddings returned no embedding.")
            legacy_vectors.append(list(vector))
        return legacy_vectors
