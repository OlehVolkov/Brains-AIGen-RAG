from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from brain.shared.text import chunked, normalize_text

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
        prepared.append(Document(page_content=text, metadata=metadata))
    return prepared


def embed_texts(
    texts: Sequence[str],
    *,
    model: str,
    base_url: str,
    batch_size: int,
) -> list[list[float]]:
    from langchain_ollama import OllamaEmbeddings

    embeddings = OllamaEmbeddings(
        model=model,
        base_url=base_url,
        validate_model_on_init=False,
    )
    vectors: list[list[float]] = []
    for batch in chunked(list(texts), batch_size):
        vectors.extend(embeddings.embed_documents(list(batch)))
    return vectors
