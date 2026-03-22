from __future__ import annotations

from pathlib import Path


def make_document(
    *,
    text: str,
    pdf_path: Path,
    repo_root: Path,
    page: int,
    page_label: str,
    parser: str,
):
    from langchain_core.documents import Document

    source_path = pdf_path.relative_to(repo_root).as_posix()
    return Document(
        page_content=text,
        metadata={
            "source_path": source_path,
            "source_file": pdf_path.name,
            "page": page,
            "page_label": page_label,
            "parser": parser,
        },
    )
