from __future__ import annotations

from pathlib import Path

from brains.shared.text import normalize_text
from brains.sources.pdf.backends.factory import make_document


def load_pdf_with_pymupdf(pdf_path: Path, repo_root: Path):
    import fitz

    documents = []
    pdf = fitz.open(pdf_path)
    try:
        for page_index, page in enumerate(pdf, start=1):
            text = normalize_text(page.get_text("text"))
            if not text:
                continue
            documents.append(
                make_document(
                    text=text,
                    pdf_path=pdf_path,
                    repo_root=repo_root,
                    page=page_index,
                    page_label=str(page_index),
                    parser="pymupdf",
                )
            )
    finally:
        pdf.close()
    return documents
