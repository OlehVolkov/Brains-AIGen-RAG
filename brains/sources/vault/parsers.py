from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from brains.sources.vault.backends import load_markdown_with_docling
from brains.sources.vault.markdown import load_markdown_with_native

MARKDOWN_PARSER_CHOICES = ["native", "docling", "auto"]

_TABLE_RE = re.compile(r"(?m)^\|.+\|\s*$\n^\|[\s:|-]+\|\s*$")
_DISPLAY_MATH_RE = re.compile(r"\$\$|\\begin\{(?:equation|align|gather|multline)")
_RICH_FENCE_RE = re.compile(r"(?m)^```(?:mermaid|math|latex|tex|tikz|dot|graphviz|plantuml|puml)\b")
_IMAGE_RE = re.compile(r"!\[\[[^\]]+\]\]|!\[[^\]]*\]\([^)]+\)")
_FORMULA_RE = re.compile(r"\\(?:frac|sum|int|alpha|beta|gamma|nabla|partial)\b")


@dataclass(frozen=True)
class MarkdownParseResult:
    documents: list
    parser: str
    warnings: list[str]


def resolve_markdown_parser(markdown_text: str, *, requested_parser: str) -> tuple[str, str | None]:
    if requested_parser not in MARKDOWN_PARSER_CHOICES:
        raise ValueError(
            f"Unsupported vault parser {requested_parser!r}. "
            f"Choose one of {', '.join(MARKDOWN_PARSER_CHOICES)}."
        )
    if requested_parser != "auto":
        return requested_parser, None
    if _looks_like_rich_scientific_markdown(markdown_text):
        return "docling", "Auto parser chose Docling for rich markdown structure."
    return "native", None


def parse_markdown_documents(
    markdown_path: Path,
    repo_root: Path,
    *,
    parser: str = "native",
) -> MarkdownParseResult:
    raw_text = markdown_path.read_text(encoding="utf-8")
    effective_parser, route_warning = resolve_markdown_parser(raw_text, requested_parser=parser)
    warnings = [route_warning] if route_warning else []

    if effective_parser == "docling":
        try:
            documents = load_markdown_with_docling(markdown_path, repo_root)
            return MarkdownParseResult(documents=documents, parser="docling", warnings=warnings)
        except Exception as exc:
            warnings.append(
                "Docling markdown parsing failed; falling back to native parsing "
                f"({type(exc).__name__}: {exc})."
            )
            effective_parser = "native"

    documents = load_markdown_with_native(markdown_path, repo_root)
    return MarkdownParseResult(documents=documents, parser=effective_parser, warnings=warnings)


def load_markdown_documents(
    markdown_path: Path,
    repo_root: Path,
    *,
    parser: str = "native",
):
    return parse_markdown_documents(
        markdown_path,
        repo_root,
        parser=parser,
    ).documents


def _looks_like_rich_scientific_markdown(markdown_text: str) -> bool:
    return any(
        pattern.search(markdown_text)
        for pattern in (
            _TABLE_RE,
            _DISPLAY_MATH_RE,
            _RICH_FENCE_RE,
            _IMAGE_RE,
            _FORMULA_RE,
        )
    )
