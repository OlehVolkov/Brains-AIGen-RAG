from __future__ import annotations

from collections import Counter
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

from brains.shared import logger
from brains.shared.langchain import embed_texts
from brains.shared.text import chunk_id
from brains.config.loader import get_config, resolve_repo_path
from brains.sources.vault.chunking import chunk_markdown_blocks, extract_markdown_blocks
from brains.sources.vault.markdown import list_markdown_paths
from brains.sources.vault.models import VaultIndexConfig
from brains.sources.vault.parsers import parse_markdown_documents

if TYPE_CHECKING:
    from langchain_core.documents import Document


def build_vault_rows(
    documents: Sequence[Document],
    vectors: Sequence[Sequence[float]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for doc, vector in zip(documents, vectors, strict=True):
        source_path = str(doc.metadata["source_path"])
        chunk_index = int(doc.metadata["chunk_index"])
        rows.append(
            {
                "id": chunk_id(
                    source_path=source_path,
                    page=0,
                    chunk_index=chunk_index,
                    text=doc.page_content,
                ),
                "vector": list(vector),
                "text": doc.page_content,
                "source_path": source_path,
                "source_file": str(doc.metadata["source_file"]),
                "title": str(doc.metadata.get("title", "")),
                "section": str(doc.metadata.get("section", "Document")),
                "section_path": str(doc.metadata.get("section_path", "Document")),
                "heading_level": int(doc.metadata.get("heading_level", 0)),
                "language_branch": str(doc.metadata.get("language_branch", "root")),
                "parser": str(doc.metadata.get("parser", "native")),
                "chunk_index": chunk_index,
                "chunk_kind": str(doc.metadata.get("chunk_kind", "paragraph")),
                "block_count": int(doc.metadata.get("block_count", 1)),
                "char_count": int(doc.metadata["char_count"]),
                "word_count": int(doc.metadata.get("word_count", 0)),
            }
        )
    return rows


def write_manifest(
    config: VaultIndexConfig,
    markdown_paths: Sequence[Path],
    *,
    parser_counts: Counter[str],
    block_count: int,
    rows: Sequence[dict[str, Any]],
    warnings: Sequence[str],
) -> dict[str, Any]:
    config.paths.index_root.mkdir(parents=True, exist_ok=True)
    char_counts = [int(row["char_count"]) for row in rows]
    word_counts = [int(row.get("word_count", 0)) for row in rows]
    chunk_kind_counts = Counter(str(row.get("chunk_kind", "paragraph")) for row in rows)
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "table_name": config.paths.table_name,
        "db_uri": config.paths.db_uri.relative_to(config.paths.brains_root).as_posix()
        if config.paths.db_uri.is_relative_to(config.paths.brains_root)
        else str(config.paths.db_uri),
        "embed_model": config.embed_model,
        "ollama_base_url": config.ollama_base_url,
        "parser": config.parser,
        "chunk_size": config.chunk_size,
        "chunk_overlap": config.chunk_overlap,
        "batch_size": config.batch_size,
        "markdown_count": len(markdown_paths),
        "block_count": block_count,
        "chunk_count": len(rows),
        "parser_counts": dict(sorted(parser_counts.items())),
        "chunk_kind_counts": dict(sorted(chunk_kind_counts.items())),
        "chunk_stats": {
            "avg_char_count": round(sum(char_counts) / len(char_counts), 2),
            "min_char_count": min(char_counts),
            "max_char_count": max(char_counts),
            "avg_word_count": round(sum(word_counts) / len(word_counts), 2),
            "min_word_count": min(word_counts),
            "max_word_count": max(word_counts),
        },
        "markdown_files": [
            path.relative_to(config.paths.repo_root).as_posix()
            if path.is_relative_to(config.paths.repo_root)
            else str(path)
            for path in markdown_paths
        ],
        "warnings": list(warnings),
    }
    config.paths.manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def pointer_manifest_path(config: VaultIndexConfig) -> Path:
    default_index_root = resolve_repo_path(
        config.paths.repo_root,
        get_config().vault.index_root,
    )
    return default_index_root / "active_index.json"


def write_active_index_pointer(config: VaultIndexConfig, manifest: dict[str, Any]) -> Path | None:
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
        "markdown_count": manifest.get("markdown_count"),
        "chunk_count": manifest.get("chunk_count"),
    }
    pointer_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return pointer_path


def index_vault(config: VaultIndexConfig) -> dict[str, Any]:
    import lancedb

    logger.info("Collecting markdown files from repository root {}", config.paths.repo_root)
    markdown_paths = list_markdown_paths(config.paths.repo_root)
    if not markdown_paths:
        raise ValueError("No markdown files were found for vault indexing.")

    source_docs: list[Document] = []
    warnings: list[str] = []
    parser_counts: Counter[str] = Counter()
    for markdown_path in markdown_paths:
        parse_result = parse_markdown_documents(
            markdown_path,
            config.paths.repo_root,
            parser=config.parser,
        )
        source_docs.extend(parse_result.documents)
        parser_counts[parse_result.parser] += 1
        warnings.extend(parse_result.warnings)

    block_docs, block_warnings = extract_markdown_blocks(source_docs)
    warnings.extend(block_warnings)

    chunked_docs = chunk_markdown_blocks(
        block_docs,
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
    )
    if not chunked_docs:
        raise ValueError("No markdown content could be prepared for indexing.")

    logger.info("Embedding {} markdown chunks into LanceDB.", len(chunked_docs))
    vectors = embed_texts(
        [doc.page_content for doc in chunked_docs],
        model=config.embed_model,
        base_url=config.ollama_base_url,
        batch_size=config.batch_size,
    )
    rows = build_vault_rows(chunked_docs, vectors)
    config.paths.db_uri.mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(str(config.paths.db_uri))
    table = db.create_table(
        config.paths.table_name,
        data=rows,
        mode="overwrite" if config.overwrite else "create",
    )
    table.create_fts_index("text", replace=True)
    manifest = write_manifest(
        config,
        markdown_paths,
        parser_counts=parser_counts,
        block_count=len(block_docs),
        rows=rows,
        warnings=warnings,
    )
    active_index_pointer = write_active_index_pointer(config, manifest)
    logger.info(
        "Indexed {} markdown files into table {} with {} chunks.",
        len(markdown_paths),
        config.paths.table_name,
        len(rows),
    )
    return {
        "table_name": config.paths.table_name,
        "markdown_count": len(markdown_paths),
        "section_count": len(source_docs),
        "block_count": len(block_docs),
        "chunk_count": len(rows),
        "manifest_path": str(config.paths.manifest_path),
        "db_uri": str(config.paths.db_uri),
        "embed_model": config.embed_model,
        "parser": config.parser,
        "parser_counts": dict(sorted(parser_counts.items())),
        "warnings": warnings,
        "manifest": manifest,
        "active_index_pointer": str(active_index_pointer) if active_index_pointer else None,
    }
