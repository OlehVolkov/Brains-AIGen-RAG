from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Sequence

from brains.shared.text import normalize_text

if TYPE_CHECKING:
    from langchain_core.documents import Document


_DIAGRAM_LANGS = {"mermaid", "plantuml", "puml", "dot", "graphviz"}
_FORMULA_LANGS = {"math", "latex", "tex", "katex"}
_IMAGE_RE = re.compile(r"^!\[\[[^\]]+\]\]$|^!\[[^\]]*\]\([^)]+\)$")
_TABLE_DIVIDER_RE = re.compile(r"^\|[\s:|-]+\|\s*$")
_FIGURE_CAPTION_RE = re.compile(
    r"^(?:figure|fig\.)\s*\d+[A-Za-z0-9.-]*[:.]?\s+",
    re.IGNORECASE,
)
_ABSTRACT_TITLES = {"abstract", "summary", "overview"}
_REFERENCES_TITLES = {
    "references",
    "bibliography",
    "works cited",
    "literature cited",
    "sources",
    "джерела",
    "література",
    "references and links",
}
_SPECIAL_BLOCK_KINDS = {"table", "figure_caption", "formula", "diagram", "image", "code_block"}


def extract_markdown_blocks(documents: Sequence[Document]) -> tuple[list[Document], list[str]]:
    from langchain_core.documents import Document

    blocks: list[Document] = []
    block_index = 0
    skipped_reference_sections = 0

    for document in documents:
        if _is_reference_section(document.metadata):
            skipped_reference_sections += 1
            continue

        text = normalize_text(document.page_content)
        if not text:
            continue
        default_kind = _default_paragraph_kind(document.metadata)
        parsed_blocks = _parse_markdown_blocks(text)
        if parsed_blocks and _should_drop_leading_heading(parsed_blocks[0][1], document.metadata):
            parsed_blocks = parsed_blocks[1:]
        if not parsed_blocks:
            parsed_blocks = [(default_kind, text)]

        for kind, block_text in parsed_blocks:
            cleaned = normalize_text(block_text)
            if not cleaned:
                continue
            if kind == "paragraph":
                kind = default_kind
            metadata = dict(document.metadata)
            metadata["block_kind"] = kind
            metadata["block_index"] = block_index
            blocks.append(Document(page_content=cleaned, metadata=metadata))
            block_index += 1

    warnings: list[str] = []
    if skipped_reference_sections:
        warnings.append(
            f"Excluded {skipped_reference_sections} markdown reference sections before chunking."
        )
    return blocks, warnings


def chunk_markdown_blocks(
    documents: Sequence[Document],
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[Document]:
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
            if block.metadata.get("block_kind") in _SPECIAL_BLOCK_KINDS and seed_blocks:
                break
            seed_blocks.insert(0, block)
            seed_chars += len(_block_payload(block))
            if seed_chars >= overlap_target:
                break
        current_blocks = seed_blocks
        current_chars = sum(len(_block_payload(block)) for block in current_blocks)

    for document in documents:
        payload_chars = len(_block_payload(document))
        if document.metadata.get("block_kind") in _SPECIAL_BLOCK_KINDS:
            if current_blocks and not _is_compatible_chunk(current_blocks[-1], document, chunk_size, current_chars):
                flush_current(preserve_overlap=False)
            if payload_chars >= chunk_size and not current_blocks:
                if payload_chars > chunk_size:
                    for split_doc in _split_large_block(
                        document,
                        chunk_size=chunk_size,
                        chunk_overlap=chunk_overlap,
                        start_chunk_index=chunk_index,
                    ):
                        prepared.append(split_doc)
                        chunk_index += 1
                else:
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
    block_kinds = {str(block.metadata.get("block_kind", "paragraph")) for block in blocks}
    metadata["chunk_kind"] = "mixed" if len(block_kinds) > 1 else next(iter(block_kinds))
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
        separators=["\n\n", "\n", ". ", "; ", " ", ""],
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


def _parse_markdown_blocks(text: str) -> list[tuple[str, str]]:
    lines = text.splitlines()
    blocks: list[tuple[str, str]] = []
    paragraph_lines: list[str] = []
    index = 0

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        paragraph_text = normalize_text("\n".join(paragraph_lines))
        if paragraph_text:
            blocks.append(("paragraph", paragraph_text))
        paragraph_lines = []

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            index += 1
            continue

        if stripped.startswith(("```", "~~~")):
            flush_paragraph()
            fence = stripped[:3]
            info = stripped[3:].strip().lower()
            block_lines = [line]
            index += 1
            while index < len(lines):
                block_lines.append(lines[index])
                if lines[index].strip().startswith(fence):
                    index += 1
                    break
                index += 1
            blocks.append((_fenced_block_kind(info), "\n".join(block_lines)))
            continue

        if stripped == "$$":
            flush_paragraph()
            block_lines = [line]
            index += 1
            while index < len(lines):
                block_lines.append(lines[index])
                if lines[index].strip() == "$$":
                    index += 1
                    break
                index += 1
            blocks.append(("formula", "\n".join(block_lines)))
            continue

        if _IMAGE_RE.fullmatch(stripped):
            flush_paragraph()
            blocks.append(("image", stripped))
            index += 1
            continue

        if _FIGURE_CAPTION_RE.match(stripped):
            flush_paragraph()
            blocks.append(("figure_caption", stripped))
            index += 1
            continue

        if stripped.startswith("|"):
            flush_paragraph()
            table_lines = [stripped]
            index += 1
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index].strip())
                index += 1
            if len(table_lines) >= 2 and any(_TABLE_DIVIDER_RE.fullmatch(line) for line in table_lines[1:2]):
                blocks.append(("table", "\n".join(table_lines)))
            else:
                paragraph_lines.extend(table_lines)
            continue

        paragraph_lines.append(line)
        index += 1

    flush_paragraph()
    return blocks


def _fenced_block_kind(info: str) -> str:
    language = info.split(maxsplit=1)[0] if info.strip() else ""
    if language in _DIAGRAM_LANGS:
        return "diagram"
    if language in _FORMULA_LANGS:
        return "formula"
    return "code_block"


def _should_drop_leading_heading(text: str, metadata: dict[str, Any]) -> bool:
    section = normalize_text(str(metadata.get("section", "")))
    section_path = normalize_text(str(metadata.get("section_path", ""))).split(" > ")[-1]
    normalized = normalize_text(text)
    return normalized != "" and normalized in {section, section_path}


def _default_paragraph_kind(metadata: dict[str, Any]) -> str:
    section = _normalized_section_name(metadata)
    if section in _ABSTRACT_TITLES:
        return "abstract"
    return "paragraph"


def _normalized_section_name(metadata: dict[str, Any]) -> str:
    section = normalize_text(str(metadata.get("section", ""))).lower()
    if section:
        return section
    section_path = normalize_text(str(metadata.get("section_path", "")))
    if not section_path:
        return ""
    return section_path.split(" > ")[-1].strip().lower()


def _is_reference_section(metadata: dict[str, Any]) -> bool:
    return _normalized_section_name(metadata) in _REFERENCES_TITLES


def _context_prefix(metadata: dict[str, Any]) -> str:
    title = normalize_text(str(metadata.get("title", "")).strip())
    section_path = normalize_text(str(metadata.get("section_path", "")).strip())
    parts: list[str] = []
    for part in (title, section_path):
        if part and part not in parts and part != "Document":
            parts.append(part)
    return " | ".join(parts)


def _block_text_for_chunk(document: Document) -> str:
    kind = str(document.metadata.get("block_kind", "paragraph"))
    labels = {
        "table": "Table",
        "figure_caption": "Figure Caption",
        "abstract": "Abstract",
        "formula": "Formula",
        "diagram": "Diagram",
        "image": "Image",
        "code_block": "Code Block",
    }
    label = labels.get(kind)
    if label:
        return f"{label}\n{document.page_content}"
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
