from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from brains.shared.preprocessing import clean_markdown_text
from brains.shared.text import normalize_text

if TYPE_CHECKING:
    from langchain_core.documents import Document


SectionRecord = tuple[str, int, str, str]


def list_markdown_paths(repo_root: Path) -> list[Path]:
    excluded_roots = {".brains", ".git", ".obsidian", ".smart-env", "PDF"}
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


def split_markdown_sections(markdown_text: str) -> list[SectionRecord]:
    cleaned = normalize_text(clean_markdown_text(strip_frontmatter(markdown_text)))
    if not cleaned:
        return []

    matches = list(re.finditer(r"(?m)^(#{1,6})\s+(.+?)\s*$", cleaned))
    if not matches:
        return [("Document", 0, "Document", cleaned)]

    sections: list[SectionRecord] = []
    if matches[0].start() > 0:
        preamble = normalize_text(cleaned[: matches[0].start()])
        if preamble:
            sections.append(("Preamble", 0, "Preamble", preamble))

    section_stack: list[tuple[int, str]] = []
    for index, match in enumerate(matches):
        heading_level = len(match.group(1))
        section_title = normalize_text(match.group(2))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(cleaned)
        body = normalize_text(cleaned[start:end])
        combined = normalize_text(f"{section_title}\n\n{body}" if body else section_title)
        if not combined:
            continue
        while section_stack and section_stack[-1][0] >= heading_level:
            section_stack.pop()
        section_stack.append((heading_level, section_title))
        section_path = " > ".join(title for _, title in section_stack)
        sections.append((section_title, heading_level, section_path, combined))
    return sections


def make_markdown_document(
    *,
    text: str,
    markdown_path: Path,
    repo_root: Path,
    title: str,
    section: str,
    section_path: str,
    heading_level: int,
    parser: str,
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
            "title": title,
            "section": section,
            "section_path": section_path,
            "heading_level": heading_level,
            "language_branch": detect_language_branch(source_path),
            "parser": parser,
        },
    )


def build_markdown_documents(
    markdown_text: str,
    *,
    markdown_path: Path,
    repo_root: Path,
    parser_label: str,
) -> list[Document]:
    sections = split_markdown_sections(markdown_text)
    title = _infer_note_title(markdown_path, sections)
    return [
        make_markdown_document(
            text=text,
            markdown_path=markdown_path,
            repo_root=repo_root,
            title=title,
            section=section,
            section_path=section_path,
            heading_level=heading_level,
            parser=parser_label,
        )
        for section, heading_level, section_path, text in sections
        if text
    ]


def load_markdown_with_native(markdown_path: Path, repo_root: Path) -> list[Document]:
    raw_text = markdown_path.read_text(encoding="utf-8")
    return build_markdown_documents(
        raw_text,
        markdown_path=markdown_path,
        repo_root=repo_root,
        parser_label="native",
    )


def _infer_note_title(markdown_path: Path, sections: list[SectionRecord]) -> str:
    for section_title, heading_level, _section_path, _text in sections:
        if heading_level == 1 and section_title:
            return section_title
    return markdown_path.stem
