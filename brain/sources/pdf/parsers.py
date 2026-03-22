from __future__ import annotations

from pathlib import Path

from brain.sources.pdf.backends import (
    _table_to_markdown,
    load_pdf_with_grobid,
    load_pdf_with_marker,
    load_pdf_with_pdfplumber,
    load_pdf_with_pymupdf,
    make_document,
)


PARSER_CHOICES = ["auto", "pymupdf", "pdfplumber", "grobid", "marker"]
__all__ = ["PARSER_CHOICES", "_table_to_markdown", "list_pdf_paths", "load_pdf_documents", "make_document"]


def list_pdf_paths(pdf_dir: Path) -> list[Path]:
    if not pdf_dir.exists():
        raise FileNotFoundError(f"PDF directory does not exist: {pdf_dir}")
    return sorted(path for path in pdf_dir.rglob("*.pdf") if path.is_file())


def load_pdf_documents(
    pdf_path: Path,
    repo_root: Path,
    *,
    parser: str,
    grobid_url: str,
    marker_command: str,
):
    warnings: list[str] = []
    parser_order = {
        "auto": ["pymupdf", "pdfplumber"],
        "pymupdf": ["pymupdf"],
        "pdfplumber": ["pdfplumber"],
        "grobid": ["grobid"],
        "marker": ["marker"],
    }
    if parser not in parser_order:
        raise ValueError(f"Unsupported parser: {parser}")

    rel_path = pdf_path.relative_to(repo_root).as_posix()
    last_error: Exception | None = None
    for parser_name in parser_order[parser]:
        try:
            if parser_name == "pymupdf":
                documents = load_pdf_with_pymupdf(pdf_path, repo_root)
            elif parser_name == "pdfplumber":
                documents = load_pdf_with_pdfplumber(pdf_path, repo_root)
            elif parser_name == "grobid":
                documents = load_pdf_with_grobid(pdf_path, repo_root, grobid_url)
            else:
                documents = load_pdf_with_marker(pdf_path, repo_root, marker_command)
            if documents:
                if parser == "auto" and parser_name != "pymupdf":
                    warnings.append(f"{rel_path}: auto parser fell back to {parser_name}.")
                return documents, warnings
        except Exception as exc:
            last_error = exc
            warnings.append(
                f"{rel_path}: parser {parser_name} failed "
                f"({type(exc).__name__}: {exc})."
            )

    if last_error is not None:
        raise ValueError(
            f"No configured parser could extract text from {rel_path}: "
            f"{type(last_error).__name__}: {last_error}"
        ) from last_error
    return [], warnings
