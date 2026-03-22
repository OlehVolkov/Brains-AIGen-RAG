from __future__ import annotations

from pathlib import Path

from brains.shared.text import normalize_text
from brains.sources.pdf.backends.factory import make_document


def _table_to_markdown(table: list[list[str | None]]) -> str:
    if not table:
        return ""
    normalized = [
        [normalize_text(str(cell or "")).replace("\n", " ") for cell in row]
        for row in table
        if any(cell not in {None, ""} for cell in row)
    ]
    if not normalized:
        return ""
    header = normalized[0]
    body = normalized[1:] or [[]]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * len(header)) + " |",
    ]
    for row in body:
        padded = row + [""] * max(0, len(header) - len(row))
        lines.append("| " + " | ".join(padded[: len(header)]) + " |")
    return "\n".join(lines)


def load_pdf_with_pdfplumber(pdf_path: Path, repo_root: Path):
    import pdfplumber

    documents = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            text_parts: list[str] = []
            extracted_text = normalize_text(page.extract_text() or "")
            if extracted_text:
                text_parts.append(extracted_text)
            for table in page.extract_tables() or []:
                table_markdown = _table_to_markdown(table)
                if table_markdown:
                    text_parts.append(table_markdown)
            combined = normalize_text("\n\n".join(part for part in text_parts if part))
            if not combined:
                continue
            documents.append(
                make_document(
                    text=combined,
                    pdf_path=pdf_path,
                    repo_root=repo_root,
                    page=page_index,
                    page_label=str(page_index),
                    parser="pdfplumber",
                )
            )
    return documents
