from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

from brains.shared import logger
from brains.shared.langchain import embed_texts, split_documents
from brains.shared.text import chunk_id
from brains.sources.pdf.models import IndexConfig
from brains.sources.pdf.parsers import list_pdf_paths, load_pdf_documents
from brains.config.loader import get_config, resolve_repo_path

if TYPE_CHECKING:
    from langchain_core.documents import Document


def build_rows(
    documents: Sequence[Document],
    vectors: Sequence[Sequence[float]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for doc, vector in zip(documents, vectors, strict=True):
        source_path = str(doc.metadata["source_path"])
        page = int(doc.metadata.get("page", 0))
        chunk_index = int(doc.metadata["chunk_index"])
        rows.append(
            {
                "id": chunk_id(
                    source_path=source_path,
                    page=page,
                    chunk_index=chunk_index,
                    text=doc.page_content,
                ),
                "vector": list(vector),
                "text": doc.page_content,
                "source_path": source_path,
                "source_file": str(doc.metadata["source_file"]),
                "page": page,
                "page_label": str(doc.metadata.get("page_label", page)),
                "parser": str(doc.metadata.get("parser", "unknown")),
                "chunk_index": chunk_index,
                "char_count": int(doc.metadata["char_count"]),
            }
        )
    return rows


def write_manifest(
    config: IndexConfig,
    pdf_paths: Sequence[Path],
    chunk_count: int,
) -> dict[str, Any]:
    config.paths.index_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "table_name": config.paths.table_name,
        "db_uri": config.paths.db_uri.relative_to(config.paths.brains_root).as_posix()
        if config.paths.db_uri.is_relative_to(config.paths.brains_root)
        else str(config.paths.db_uri),
        "parser": config.parser,
        "grobid_url": config.grobid_url,
        "marker_command": config.marker_command,
        "embed_model": config.embed_model,
        "ollama_base_url": config.ollama_base_url,
        "chunk_size": config.chunk_size,
        "chunk_overlap": config.chunk_overlap,
        "batch_size": config.batch_size,
        "pdf_count": len(pdf_paths),
        "chunk_count": chunk_count,
        "pdf_files": [
            path.relative_to(config.paths.repo_root).as_posix()
            if path.is_relative_to(config.paths.repo_root)
            else str(path)
            for path in pdf_paths
        ],
    }
    config.paths.manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def pointer_manifest_path(config: IndexConfig) -> Path:
    default_index_root = resolve_repo_path(
        config.paths.repo_root,
        get_config().pdf.index_root,
    )
    return default_index_root / "active_index.json"


def write_active_index_pointer(config: IndexConfig, manifest: dict[str, Any]) -> Path | None:
    pointer_path = pointer_manifest_path(config)
    default_index_root = pointer_path.parent
    if config.paths.index_root == default_index_root:
        if pointer_path.exists():
            pointer_path.unlink()
        return None

    default_index_root.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": datetime.now(UTC).isoformat(),
        "reason": "fallback_index_root",
        "table_name": config.paths.table_name,
        "index_root": str(config.paths.index_root),
        "manifest_path": str(config.paths.manifest_path),
        "db_uri": str(config.paths.db_uri),
        "pdf_count": manifest.get("pdf_count"),
        "chunk_count": manifest.get("chunk_count"),
    }
    pointer_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return pointer_path


def index_pdfs(config: IndexConfig) -> dict[str, Any]:
    import lancedb

    logger.info("Collecting PDF files from {}", config.paths.pdf_dir)
    pdf_paths = list_pdf_paths(config.paths.pdf_dir)
    if not pdf_paths:
        raise ValueError(f"No PDF files were found in {config.paths.pdf_dir}.")

    source_docs: list[Document] = []
    warnings: list[str] = []
    for pdf_path in pdf_paths:
        logger.debug("Loading PDF: {}", pdf_path)
        docs, parser_warnings = load_pdf_documents(
            pdf_path,
            config.paths.repo_root,
            parser=config.parser,
            grobid_url=config.grobid_url,
            marker_command=config.marker_command,
        )
        warnings.extend(parser_warnings)
        source_docs.extend(docs)

    chunked_docs = split_documents(
        source_docs,
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
    )
    if not chunked_docs:
        raise ValueError("No PDF content could be prepared for indexing.")

    logger.info("Embedding {} PDF chunks into LanceDB.", len(chunked_docs))
    vectors = embed_texts(
        [doc.page_content for doc in chunked_docs],
        model=config.embed_model,
        base_url=config.ollama_base_url,
        batch_size=config.batch_size,
    )
    rows = build_rows(chunked_docs, vectors)
    config.paths.db_uri.mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(str(config.paths.db_uri))
    table = db.create_table(
        config.paths.table_name,
        data=rows,
        mode="overwrite" if config.overwrite else "create",
    )
    table.create_fts_index("text", replace=True)
    manifest = write_manifest(config, pdf_paths, len(rows))
    active_index_pointer = write_active_index_pointer(config, manifest)
    logger.info(
        "Indexed {} PDFs into table {} with {} chunks.",
        len(pdf_paths),
        config.paths.table_name,
        len(rows),
    )
    return {
        "table_name": config.paths.table_name,
        "pdf_count": len(pdf_paths),
        "page_count": len(source_docs),
        "chunk_count": len(rows),
        "manifest_path": str(config.paths.manifest_path),
        "db_uri": str(config.paths.db_uri),
        "embed_model": config.embed_model,
        "warnings": warnings,
        "manifest": manifest,
        "active_index_pointer": str(active_index_pointer) if active_index_pointer else None,
    }
