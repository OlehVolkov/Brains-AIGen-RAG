from __future__ import annotations

import mimetypes
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING
from urllib import request
from xml.etree import ElementTree

from brain.shared.text import normalize_text
from brain.sources.pdf.backends.factory import make_document

if TYPE_CHECKING:
    from langchain_core.documents import Document


def load_pdf_with_grobid(pdf_path: Path, repo_root: Path, grobid_url: str):
    endpoint = grobid_url.rstrip("/") + "/api/processFulltextDocument"
    boundary = "brain-grobid-boundary"
    content_type = mimetypes.guess_type(pdf_path.name)[0] or "application/pdf"
    pdf_bytes = pdf_path.read_bytes()
    request_body = BytesIO()
    request_body.write(f"--{boundary}\r\n".encode("utf-8"))
    request_body.write(
        (
            f'Content-Disposition: form-data; name="input"; filename="{pdf_path.name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8")
    )
    request_body.write(pdf_bytes)
    request_body.write(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    req = request.Request(
        endpoint,
        data=request_body.getvalue(),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with request.urlopen(req, timeout=120) as response:
        response_text = response.read().decode("utf-8")

    root = ElementTree.fromstring(response_text)
    ns = {"tei": "http://www.tei-c.org/ns/1.0"}
    documents: list[Document] = []
    body_element = root.find(".//tei:text/tei:body", ns)
    if body_element is None:
        return documents

    page_index = 1
    for div in body_element.findall(".//tei:div", ns):
        chunks: list[str] = []
        head = div.find("tei:head", ns)
        if head is not None and head.text:
            chunks.append(head.text)
        for paragraph in div.findall(".//tei:p", ns):
            text = "".join(paragraph.itertext())
            text = normalize_text(text)
            if text:
                chunks.append(text)
        combined = normalize_text("\n\n".join(chunks))
        if not combined:
            continue
        documents.append(
            make_document(
                text=combined,
                pdf_path=pdf_path,
                repo_root=repo_root,
                page=page_index,
                page_label=str(page_index),
                parser="grobid",
            )
        )
        page_index += 1
    return documents
