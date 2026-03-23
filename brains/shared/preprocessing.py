from __future__ import annotations

import re
from collections import Counter
from math import ceil
from typing import TYPE_CHECKING, Any, Sequence

from brains.shared.text import normalize_text

if TYPE_CHECKING:
    from langchain_core.documents import Document


_WIKI_LINK_RE = r"\[\[[^\]]+\]\]"
_MARKDOWN_LINK_RE = r"\[[^\]]+\]\([^)]+\)"
_LINK_TOKEN_RE = rf"(?:{_WIKI_LINK_RE}|{_MARKDOWN_LINK_RE})"
_NAV_SEPARATOR_RE = r"(?:\||/|>|->|→|::|·|•)"
_NAV_LINE_RE = re.compile(
    rf"^\s*{_LINK_TOKEN_RE}(?:\s*{_NAV_SEPARATOR_RE}\s*{_LINK_TOKEN_RE})+\s*$"
)
_RELATED_SECTION_TITLES = {
    "related notes",
    "see also",
    "links",
    "пов'язані нотатки",
    "див. також",
    "посилання",
}


def clean_markdown_text(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    cleaned_lines: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", stripped)
        if heading_match:
            title = normalize_text(heading_match.group(2)).lower()
            if title in _RELATED_SECTION_TITLES:
                next_index = index + 1
                section_lines: list[str] = []
                while next_index < len(lines) and not re.match(r"^\s*#{1,6}\s+", lines[next_index]):
                    section_lines.append(lines[next_index])
                    next_index += 1
                if _is_navigation_only_block(section_lines):
                    index = next_index
                    continue
        if not _is_navigation_only_line(stripped):
            cleaned_lines.append(line)
        index += 1

    return "\n".join(cleaned_lines)


def clean_pdf_documents(documents: Sequence[Any]) -> tuple[list[Any], list[str]]:
    if not documents or not _is_document_like(documents[0]):
        return list(documents), []

    top_candidates, bottom_candidates = _collect_repeated_edge_lines(documents)
    cleaned_docs: list[Document] = []
    removed_docs = 0
    removed_lines = 0

    from langchain_core.documents import Document

    for document in documents:
        lines = _nonempty_lines(document.page_content)
        page_label = str(document.metadata.get("page_label", document.metadata.get("page", "")))
        trimmed_lines, removed_count = _trim_pdf_edge_furniture(
            lines,
            top_candidates=top_candidates,
            bottom_candidates=bottom_candidates,
            page_label=page_label,
        )
        cleaned_text = normalize_text("\n".join(trimmed_lines))
        if not cleaned_text:
            continue
        metadata = dict(document.metadata)
        metadata["preclean_removed_lines"] = int(metadata.get("preclean_removed_lines", 0))
        metadata["preclean_removed_lines"] += removed_count
        cleaned_docs.append(Document(page_content=cleaned_text, metadata=metadata))
        if removed_count:
            removed_docs += 1
            removed_lines += removed_count

    warnings: list[str] = []
    if removed_lines:
        warnings.append(
            "Removed "
            f"{removed_lines} repeated PDF boilerplate lines across {removed_docs} pages "
            "before chunking."
        )
    return cleaned_docs, warnings


def _collect_repeated_edge_lines(
    documents: Sequence[Document],
) -> tuple[set[str], set[str]]:
    page_count = len(documents)
    threshold = page_count if page_count <= 3 else ceil(page_count / 2)
    top_counts: Counter[str] = Counter()
    bottom_counts: Counter[str] = Counter()

    for document in documents:
        lines = _nonempty_lines(document.page_content)
        top_counts.update(_normalize_match_line(line) for line in lines[:3])
        bottom_counts.update(_normalize_match_line(line) for line in lines[-3:])

    top_candidates = {
        line
        for line, count in top_counts.items()
        if line and count >= threshold
    }
    bottom_candidates = {
        line
        for line, count in bottom_counts.items()
        if line and count >= threshold
    }
    return top_candidates, bottom_candidates


def _trim_pdf_edge_furniture(
    lines: list[str],
    *,
    top_candidates: set[str],
    bottom_candidates: set[str],
    page_label: str,
) -> tuple[list[str], int]:
    trimmed = list(lines)
    removed = 0

    while trimmed:
        first = _normalize_match_line(trimmed[0])
        if first in top_candidates or _is_page_furniture_line(first, page_label=page_label):
            trimmed.pop(0)
            removed += 1
            continue
        break

    while trimmed:
        last = _normalize_match_line(trimmed[-1])
        if last in bottom_candidates or _is_page_furniture_line(last, page_label=page_label):
            trimmed.pop()
            removed += 1
            continue
        break

    return trimmed, removed


def _is_navigation_only_block(lines: Sequence[str]) -> bool:
    meaningful = [line.strip() for line in lines if line.strip()]
    if not meaningful:
        return True
    return all(_is_navigation_list_item(line) for line in meaningful)


def _is_navigation_list_item(line: str) -> bool:
    bullet_stripped = re.sub(r"^\s*[-*+]\s+", "", line).strip()
    return _is_navigation_only_line(bullet_stripped) or _is_link_only_line(bullet_stripped)


def _is_navigation_only_line(line: str) -> bool:
    if not line:
        return False
    return bool(_NAV_LINE_RE.fullmatch(line))


def _is_link_only_line(line: str) -> bool:
    if not line:
        return False
    return bool(re.fullmatch(_LINK_TOKEN_RE, line))


def _is_page_furniture_line(line: str, *, page_label: str) -> bool:
    if not line:
        return False
    lowered = line.lower()
    if re.fullmatch(r"\d{1,4}", line):
        return True
    if page_label and line == page_label:
        return True
    if re.fullmatch(rf"(?:page|p\.)\s*{re.escape(page_label)}", lowered):
        return True
    return False


def _nonempty_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _normalize_match_line(line: str) -> str:
    return normalize_text(line).lower()


def _is_document_like(value: Any) -> bool:
    return hasattr(value, "page_content") and hasattr(value, "metadata")
