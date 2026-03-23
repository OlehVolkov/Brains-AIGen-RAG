from __future__ import annotations

from pathlib import Path

from brains.shared.text import normalize_text
from brains.sources.vault.markdown import build_markdown_documents


def load_markdown_with_docling(markdown_path: Path, repo_root: Path):
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    result = converter.convert(str(markdown_path))
    markdown_text = normalize_text(result.document.export_to_markdown())
    if not markdown_text:
        return []
    return build_markdown_documents(
        markdown_text,
        markdown_path=markdown_path,
        repo_root=repo_root,
        parser_label="docling",
    )
