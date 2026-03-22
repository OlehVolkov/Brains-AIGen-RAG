from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from brain.shared.text import normalize_text

if TYPE_CHECKING:
    from langchain_core.documents import Document


def list_markdown_paths(repo_root: Path) -> list[Path]:
    excluded_roots = {".brain", ".git", ".obsidian", ".smart-env", "PDF"}
    paths: list[Path] = []
    for path in repo_root.rglob("*.md"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(repo_root).parts
        if any(part in excluded_roots for part in rel_parts):
            continue
        paths.append(path)
    return sorted(paths)


def detect_language_branch(source_path: str) -> str:
    if source_path.startswith("UA/"):
        return "UA"
    if source_path.startswith("EN/"):
        return "EN"
    return "root"


def strip_frontmatter(markdown_text: str) -> str:
    if not markdown_text.startswith("---\n"):
        return markdown_text
    parts = markdown_text.split("\n---\n", 1)
    if len(parts) != 2:
        return markdown_text
    return parts[1]


def split_markdown_sections(markdown_text: str) -> list[tuple[str, int, str]]:
    cleaned = normalize_text(strip_frontmatter(markdown_text))
    if not cleaned:
        return []

    matches = list(re.finditer(r"(?m)^(#{1,6})\s+(.+?)\s*$", cleaned))
    if not matches:
        return [("Document", 0, cleaned)]

    sections: list[tuple[str, int, str]] = []
    if matches[0].start() > 0:
        preamble = normalize_text(cleaned[: matches[0].start()])
        if preamble:
            sections.append(("Preamble", 0, preamble))

    for index, match in enumerate(matches):
        heading_level = len(match.group(1))
        section_title = normalize_text(match.group(2))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(cleaned)
        body = normalize_text(cleaned[start:end])
        combined = normalize_text(f"{section_title}\n\n{body}" if body else section_title)
        if combined:
            sections.append((section_title, heading_level, combined))
    return sections


def make_markdown_document(
    *,
    text: str,
    markdown_path: Path,
    repo_root: Path,
    section: str,
    heading_level: int,
):
    from langchain_core.documents import Document

    source_path = markdown_path.relative_to(repo_root).as_posix()
    return Document(
        page_content=text,
        metadata={
            "source_path": source_path,
            "source_file": markdown_path.name,
            "page": 0,
            "page_label": "md",
            "section": section,
            "heading_level": heading_level,
            "language_branch": detect_language_branch(source_path),
            "parser": "markdown",
        },
    )


def load_markdown_documents(markdown_path: Path, repo_root: Path) -> list[Document]:
    raw_text = markdown_path.read_text(encoding="utf-8")
    sections = split_markdown_sections(raw_text)
    return [
        make_markdown_document(
            text=text,
            markdown_path=markdown_path,
            repo_root=repo_root,
            section=section,
            heading_level=heading_level,
        )
        for section, heading_level, text in sections
        if text
    ]
