from __future__ import annotations

from pathlib import Path

from brains.shared.text import normalize_text
from brains.sources.pdf.backends.factory import make_document


def load_pdf_with_docling(pdf_path: Path, repo_root: Path):
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))
    markdown_text = normalize_text(result.document.export_to_markdown())
    if not markdown_text:
        return []
    return [
        make_document(
            text=markdown_text,
            pdf_path=pdf_path,
            repo_root=repo_root,
            page=1,
            page_label="1",
            parser="docling",
        )
    ]
