from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from brains.shared.text import normalize_text

if TYPE_CHECKING:
    from langchain_core.documents import Document


def chunk_pdf_blocks(
    documents: Sequence[Document],
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[Document]:
    from langchain_core.documents import Document

    if not documents:
        return []

    overlap_target = max(0, chunk_overlap)
    prepared: list[Document] = []
    current_blocks: list[Document] = []
    current_chars = 0
    chunk_index = 0

    def flush_current(*, preserve_overlap: bool) -> None:
        nonlocal current_blocks, current_chars, chunk_index
        if not current_blocks:
            return
        prepared.append(_make_chunk_document(current_blocks, chunk_index=chunk_index))
        chunk_index += 1
        if not preserve_overlap or overlap_target <= 0 or len(current_blocks) <= 1:
            current_blocks = []
            current_chars = 0
            return
        seed_blocks: list[Document] = []
        seed_chars = 0
        for block in reversed(current_blocks):
            if block.metadata.get("block_kind") in {"table"} and seed_blocks:
                break
            seed_blocks.insert(0, block)
            seed_chars += len(_block_payload(block))
            if seed_chars >= overlap_target:
                break
        current_blocks = seed_blocks
        current_chars = sum(len(_block_payload(block)) for block in current_blocks)

    for document in documents:
        payload_chars = len(_block_payload(document))
        if document.metadata.get("block_kind") in {"table", "figure_caption"}:
            if current_blocks and not _is_compatible_chunk(current_blocks[-1], document, chunk_size, current_chars):
                flush_current(preserve_overlap=False)
            if payload_chars >= chunk_size and not current_blocks:
                prepared.append(_make_chunk_document([document], chunk_index=chunk_index))
                chunk_index += 1
                continue

        if current_blocks and not _same_context(current_blocks[-1], document):
            flush_current(preserve_overlap=False)
        elif current_blocks and current_chars + payload_chars > chunk_size:
            flush_current(preserve_overlap=True)

        if payload_chars > chunk_size and document.metadata.get("block_kind") == "paragraph":
            for split_doc in _split_large_block(
                document,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                start_chunk_index=chunk_index,
            ):
                prepared.append(split_doc)
                chunk_index += 1
            current_blocks = []
            current_chars = 0
            continue

        current_blocks.append(document)
        current_chars += payload_chars

    flush_current(preserve_overlap=False)
    return prepared


def _make_chunk_document(blocks: Sequence[Document], *, chunk_index: int):
    from langchain_core.documents import Document

    first = blocks[0]
    context_prefix = _context_prefix(first.metadata)
    text_parts = [_block_text_for_chunk(block) for block in blocks]
    payload = normalize_text("\n\n".join(part for part in [context_prefix, *text_parts] if part))
    metadata = dict(first.metadata)
    metadata["chunk_index"] = chunk_index
    metadata["char_count"] = len(payload)
    metadata["word_count"] = len(payload.split())
    metadata["block_count"] = len(blocks)
    metadata["chunk_kind"] = "mixed" if len({block.metadata.get("block_kind") for block in blocks}) > 1 else str(
        first.metadata.get("block_kind", "paragraph")
    )
    return Document(page_content=payload, metadata=metadata)


def _split_large_block(
    document: Document,
    *,
    chunk_size: int,
    chunk_overlap: int,
    start_chunk_index: int,
) -> list[Document]:
    from langchain_core.documents import Document
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=[". ", "; ", ", ", " ", ""],
    )
    context_prefix = _context_prefix(document.metadata)
    split_texts = splitter.split_text(document.page_content)
    prepared: list[Document] = []
    for offset, text in enumerate(split_texts):
        payload = normalize_text("\n\n".join([context_prefix, text]))
        metadata = dict(document.metadata)
        metadata["chunk_index"] = start_chunk_index + offset
        metadata["char_count"] = len(payload)
        metadata["word_count"] = len(payload.split())
        metadata["block_count"] = 1
        metadata["chunk_kind"] = str(document.metadata.get("block_kind", "paragraph"))
        prepared.append(Document(page_content=payload, metadata=metadata))
    return prepared


def _context_prefix(metadata: dict[str, Any]) -> str:
    title = normalize_text(str(metadata.get("title", "")).strip())
    section_path = normalize_text(str(metadata.get("section_path", "")).strip())
    parts = [part for part in [title, section_path] if part and part != "Document"]
    return " | ".join(parts)


def _block_text_for_chunk(document: Document) -> str:
    kind = str(document.metadata.get("block_kind", "paragraph"))
    if kind == "table":
        return "Table\n" + document.page_content
    if kind == "figure_caption":
        return "Figure Caption\n" + document.page_content
    return document.page_content


def _same_context(left: Document, right: Document) -> bool:
    keys = ("source_path", "title", "section_path")
    return all(left.metadata.get(key) == right.metadata.get(key) for key in keys)


def _is_compatible_chunk(
    current: Document,
    candidate: Document,
    chunk_size: int,
    current_chars: int,
) -> bool:
    return _same_context(current, candidate) and current_chars < chunk_size


def _block_payload(document: Document) -> str:
    return normalize_text("\n\n".join([_context_prefix(document.metadata), _block_text_for_chunk(document)]))
