from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Sequence

from brains.shared.text import normalize_text

if TYPE_CHECKING:
    from langchain_core.documents import Document


REFERENCES_TITLES = {
    "references",
    "bibliography",
    "literature cited",
    "works cited",
}


def extract_pdf_blocks(documents: Sequence[Document]) -> tuple[list[Document], list[str]]:
    from langchain_core.documents import Document

    if not documents:
        return [], []

    title = _infer_title(documents)
    authors = _infer_authors(documents, title=title)
    year = _infer_year(documents)
    warnings: list[str] = []
    blocks: list[Document] = []
    section_stack: list[dict[str, Any]] = []
    in_references = False
    references_skipped = 0
    block_index = 0

    for page_doc in documents:
        page = int(page_doc.metadata.get("page", 0))
        page_label = str(page_doc.metadata.get("page_label", page))
        parser = str(page_doc.metadata.get("parser", "unknown"))
        source_path = str(page_doc.metadata["source_path"])
        source_file = str(page_doc.metadata["source_file"])
        lines = page_doc.page_content.splitlines()
        paragraph_lines: list[str] = []
        line_index = 0

        while line_index < len(lines):
            raw_line = lines[line_index]
            stripped = raw_line.strip()
            if not stripped:
                block_index = _flush_paragraph_block(
                    paragraph_lines,
                    blocks=blocks,
                    block_index=block_index,
                    source_path=source_path,
                    source_file=source_file,
                    page=page,
                    page_label=page_label,
                    parser=parser,
                    title=title,
                    authors=authors,
                    year=year,
                    section_stack=section_stack,
                )
                paragraph_lines = []
                line_index += 1
                continue

            if in_references:
                references_skipped += 1
                line_index += 1
                continue

            heading = _parse_heading(stripped)
            if heading is not None:
                block_index = _flush_paragraph_block(
                    paragraph_lines,
                    blocks=blocks,
                    block_index=block_index,
                    source_path=source_path,
                    source_file=source_file,
                    page=page,
                    page_label=page_label,
                    parser=parser,
                    title=title,
                    authors=authors,
                    year=year,
                    section_stack=section_stack,
                )
                paragraph_lines = []
                heading_title, level = heading
                normalized_heading = normalize_text(heading_title)
                if normalized_heading.lower() in REFERENCES_TITLES:
                    in_references = True
                else:
                    _update_section_stack(section_stack, normalized_heading, level)
                line_index += 1
                continue

            if _is_figure_caption(stripped):
                block_index = _flush_paragraph_block(
                    paragraph_lines,
                    blocks=blocks,
                    block_index=block_index,
                    source_path=source_path,
                    source_file=source_file,
                    page=page,
                    page_label=page_label,
                    parser=parser,
                    title=title,
                    authors=authors,
                    year=year,
                    section_stack=section_stack,
                )
                paragraph_lines = []
                cleaned_caption = _clean_text_block(stripped)
                if cleaned_caption:
                    blocks.append(
                        Document(
                            page_content=cleaned_caption,
                            metadata=_block_metadata(
                                source_path=source_path,
                                source_file=source_file,
                                page=page,
                                page_label=page_label,
                                parser=parser,
                                title=title,
                                authors=authors,
                                year=year,
                                section_stack=section_stack,
                                block_kind="figure_caption",
                                block_index=block_index,
                            ),
                        )
                    )
                    block_index += 1
                line_index += 1
                continue

            if stripped.startswith("|"):
                block_index = _flush_paragraph_block(
                    paragraph_lines,
                    blocks=blocks,
                    block_index=block_index,
                    source_path=source_path,
                    source_file=source_file,
                    page=page,
                    page_label=page_label,
                    parser=parser,
                    title=title,
                    authors=authors,
                    year=year,
                    section_stack=section_stack,
                )
                paragraph_lines = []
                table_lines: list[str] = []
                while line_index < len(lines) and lines[line_index].strip().startswith("|"):
                    table_lines.append(lines[line_index].strip())
                    line_index += 1
                table_text = normalize_text("\n".join(table_lines))
                if table_text:
                    blocks.append(
                        Document(
                            page_content=table_text,
                            metadata=_block_metadata(
                                source_path=source_path,
                                source_file=source_file,
                                page=page,
                                page_label=page_label,
                                parser=parser,
                                title=title,
                                authors=authors,
                                year=year,
                                section_stack=section_stack,
                                block_kind="table",
                                block_index=block_index,
                            ),
                        )
                    )
                    block_index += 1
                continue

            paragraph_lines.append(stripped)
            line_index += 1

        block_index = _flush_paragraph_block(
            paragraph_lines,
            blocks=blocks,
            block_index=block_index,
            source_path=source_path,
            source_file=source_file,
            page=page,
            page_label=page_label,
            parser=parser,
            title=title,
            authors=authors,
            year=year,
            section_stack=section_stack,
        )

    if references_skipped:
        warnings.append(
            f"Excluded {references_skipped} reference lines after a detected References section."
        )
    return blocks, warnings


def _flush_paragraph_block(
    paragraph_lines: list[str],
    *,
    blocks: list[Document],
    block_index: int,
    source_path: str,
    source_file: str,
    page: int,
    page_label: str,
    parser: str,
    title: str,
    authors: list[str],
    year: int | None,
    section_stack: Sequence[dict[str, Any]],
) -> int:
    if not paragraph_lines:
        return block_index

    from langchain_core.documents import Document

    cleaned = _clean_text_block(" ".join(paragraph_lines))
    paragraph_lines.clear()
    if not cleaned:
        return block_index

    block_kind = "abstract" if _current_section_name(section_stack).lower() == "abstract" else "paragraph"
    blocks.append(
        Document(
            page_content=cleaned,
            metadata=_block_metadata(
                source_path=source_path,
                source_file=source_file,
                page=page,
                page_label=page_label,
                parser=parser,
                title=title,
                authors=authors,
                year=year,
                section_stack=section_stack,
                block_kind=block_kind,
                block_index=block_index,
            ),
        )
    )
    return block_index + 1


def _block_metadata(
    *,
    source_path: str,
    source_file: str,
    page: int,
    page_label: str,
    parser: str,
    title: str,
    authors: list[str],
    year: int | None,
    section_stack: Sequence[dict[str, Any]],
    block_kind: str,
    block_index: int,
) -> dict[str, Any]:
    section_titles = [str(item["title"]) for item in section_stack]
    section = section_titles[-1] if section_titles else "Document"
    section_level = int(section_stack[-1]["level"]) if section_stack else 0
    return {
        "source_path": source_path,
        "source_file": source_file,
        "page": page,
        "page_label": page_label,
        "parser": parser,
        "title": title,
        "authors": list(authors),
        "year": year,
        "section": section,
        "section_level": section_level,
        "section_path": " > ".join(section_titles) if section_titles else "Document",
        "block_kind": block_kind,
        "block_index": block_index,
    }


def _update_section_stack(section_stack: list[dict[str, Any]], title: str, level: int) -> None:
    while section_stack and int(section_stack[-1]["level"]) >= level:
        section_stack.pop()
    section_stack.append({"title": title, "level": level})


def _parse_heading(line: str) -> tuple[str, int] | None:
    markdown_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
    if markdown_match:
        return normalize_text(markdown_match.group(2)), len(markdown_match.group(1))

    numbered_match = re.match(r"^(\d+(?:\.\d+)*)\s+(.+?)\s*$", line)
    if numbered_match and len(line) <= 120:
        level = numbered_match.group(1).count(".") + 1
        return normalize_text(numbered_match.group(2)), level

    lowered = normalize_text(line).lower()
    if lowered in REFERENCES_TITLES:
        return normalize_text(line), 1
    if lowered == "abstract":
        return "Abstract", 1
    if _looks_like_heading(line):
        return normalize_text(line), 1
    return None


def _looks_like_heading(line: str) -> bool:
    if len(line) > 100:
        return False
    if line.endswith((".", "?", "!", ";", ":")):
        return False
    words = line.split()
    if not words or len(words) > 12:
        return False
    if sum(1 for char in line if char.isupper()) >= max(4, len(line) // 3):
        return True
    return all(word[:1].isupper() for word in words[: min(5, len(words))])


def _is_figure_caption(line: str) -> bool:
    return bool(re.match(r"^(?:figure|fig\.)\s*\d+[A-Za-z0-9.-]*[:.]?\s+", line, re.IGNORECASE))


def _clean_text_block(text: str) -> str:
    cleaned = normalize_text(text.replace("- ", "-"))
    cleaned = re.sub(r"\[(?:\d+(?:\s*,\s*\d+)*(?:\s*-\s*\d+)?)\]", "", cleaned)
    cleaned = re.sub(
        r"\(([A-Z][A-Za-z'`-]+(?: et al\.)?,?\s+\d{4}[a-z]?(?:;\s*[A-Z][A-Za-z'`-]+(?: et al\.)?,?\s+\d{4}[a-z]?)*)\)",
        "",
        cleaned,
    )
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    if _looks_like_formula(cleaned):
        return "[FORMULA]"
    return cleaned.strip(" ,;")


def _looks_like_formula(text: str) -> bool:
    if len(text) < 6:
        return False
    if not any(symbol in text for symbol in ("=", "+", "-", "/", "^", "∇", "∂")):
        return False
    alpha_chars = sum(1 for char in text if char.isalpha())
    symbol_chars = sum(1 for char in text if not char.isalnum() and not char.isspace())
    return symbol_chars > alpha_chars and alpha_chars < max(12, len(text) // 3)


def _infer_title(documents: Sequence[Document]) -> str:
    first_page_lines = _nonempty_lines(documents[0].page_content)
    for line in first_page_lines[:8]:
        if _parse_heading(line) is not None:
            continue
        if len(line) > 160:
            continue
        if len(line.split()) < 3:
            continue
        return normalize_text(line)
    source_file = str(documents[0].metadata.get("source_file", "document"))
    return normalize_text(source_file.rsplit(".", 1)[0].replace("_", " ").replace("-", " "))


def _infer_authors(documents: Sequence[Document], *, title: str) -> list[str]:
    first_page_lines = _nonempty_lines(documents[0].page_content)
    try:
        title_index = first_page_lines.index(title)
    except ValueError:
        title_index = -1
    candidate_lines = first_page_lines[title_index + 1 : title_index + 4]
    authors: list[str] = []
    for line in candidate_lines:
        if _parse_heading(line) is not None:
            break
        if any(char.isdigit() for char in line):
            continue
        if len(line) > 120:
            continue
        if len(line.split()) > 20:
            continue
        if "," in line or " and " in line.lower():
            authors.extend(
                normalize_text(part)
                for part in re.split(r",| and ", line)
                if normalize_text(part)
            )
            break
    return authors


def _infer_year(documents: Sequence[Document]) -> int | None:
    match = re.search(r"\b(19|20)\d{2}\b", documents[0].page_content)
    if match:
        return int(match.group(0))
    return None


def _current_section_name(section_stack: Sequence[dict[str, Any]]) -> str:
    if not section_stack:
        return "Document"
    return str(section_stack[-1]["title"])


def _nonempty_lines(text: str) -> list[str]:
    return [normalize_text(line) for line in text.splitlines() if normalize_text(line)]
