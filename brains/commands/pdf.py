from __future__ import annotations

from enum import StrEnum
from typing import Annotated

import typer

from brains.shared import logger, print_json, print_text
from brains.shared.formatting import format_index_summary
from brains.sources.pdf import (
    PARSER_CHOICES,
    fetch_pdfs_from_notes,
    format_search_results,
    index_pdfs,
    search_pdfs,
)
from brains.sources.pdf.models import IndexConfig, SearchConfig
from brains.config import get_config, resolve_pdf_paths


class ParserChoice(StrEnum):
    AUTO = "auto"
    PYMUPDF = "pymupdf"
    PDFPLUMBER = "pdfplumber"
    DOCLING = "docling"
    GROBID = "grobid"
    MARKER = "marker"


class SearchMode(StrEnum):
    AUTO = "auto"
    VECTOR = "vector"
    FTS = "fts"
    HYBRID = "hybrid"


class RerankerChoice(StrEnum):
    NONE = "none"
    RRF = "rrf"
    CROSS_ENCODER = "cross-encoder"
    OLLAMA = "ollama"


def emit(payload: dict, *, json_output: bool, formatter) -> None:
    if json_output:
        print_json(payload)
    else:
        print_text(formatter(payload))


def register_pdf_commands(app: typer.Typer) -> None:
    @app.command("index")
    def index_command(
        pdf_dir: Annotated[str | None, typer.Option(help="Directory with PDF files.")] = None,
        index_root: Annotated[
            str | None,
            typer.Option(help="Directory under /.brains/.index for search artifacts."),
        ] = None,
        table_name: Annotated[str | None, typer.Option(help="LanceDB table name.")] = None,
        parser: Annotated[
            ParserChoice | None,
            typer.Option(help=f"PDF parser backend. Choices: {', '.join(PARSER_CHOICES)}."),
        ] = None,
        grobid_url: Annotated[
            str | None,
            typer.Option(help="Base URL for a local Grobid service when --parser grobid is used."),
        ] = None,
        marker_command: Annotated[
            str | None,
            typer.Option(help="Command used for marker-pdf parsing when --parser marker is used."),
        ] = None,
        embed_model: Annotated[str | None, typer.Option(help="Ollama embedding model name.")] = None,
        ollama_base_url: Annotated[
            str | None,
            typer.Option(help="Base URL for the local Ollama server."),
        ] = None,
        chunk_size: Annotated[int | None, typer.Option(help="Chunk size in characters.")] = None,
        chunk_overlap: Annotated[int | None, typer.Option(help="Chunk overlap in characters.")] = None,
        batch_size: Annotated[int | None, typer.Option(help="Embedding batch size.")] = None,
        no_overwrite: Annotated[
            bool,
            typer.Option(
                help="Fail if the table already exists instead of rebuilding it.",
            ),
        ] = False,
        json_output: Annotated[bool, typer.Option(help="Emit JSON output.")] = False,
    ) -> None:
        logger.info("Starting PDF indexing command.")
        settings = get_config()
        paths = resolve_pdf_paths(
            pdf_dir=pdf_dir,
            index_root=index_root,
            table_name=table_name or settings.pdf.table_name,
        )
        summary = index_pdfs(
            IndexConfig.from_settings(
                paths=paths,
                parser=parser.value if parser else None,
                grobid_url=grobid_url,
                marker_command=marker_command,
                embed_model=embed_model,
                ollama_base_url=ollama_base_url,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                batch_size=batch_size,
                overwrite=not no_overwrite,
            )
        )
        logger.info("Finished PDF indexing command.")
        emit(summary, json_output=json_output, formatter=format_index_summary)

    @app.command("search")
    def search_command(
        query: Annotated[str, typer.Argument(help="Search query.")],
        pdf_dir: Annotated[str | None, typer.Option(help="Optional PDF directory override.")] = None,
        index_root: Annotated[
            str | None,
            typer.Option(help="Directory under /.brains/.index for search artifacts."),
        ] = None,
        table_name: Annotated[str | None, typer.Option(help="LanceDB table name.")] = None,
        mode: Annotated[SearchMode, typer.Option(help="Retrieval mode.")] = SearchMode.HYBRID,
        reranker: Annotated[RerankerChoice, typer.Option(help="Reranking mode.")] = RerankerChoice.NONE,
        embed_model: Annotated[str | None, typer.Option(help="Ollama embedding model name.")] = None,
        ollama_base_url: Annotated[str | None, typer.Option(help="Base URL for the local Ollama server.")] = None,
        cross_encoder_model: Annotated[
            str | None,
            typer.Option(help="Sentence-transformers cross-encoder model used for reranking."),
        ] = None,
        ollama_rerank_model: Annotated[
            str | None,
            typer.Option(help="Ollama chat model used for LLM-based reranking."),
        ] = None,
        k: Annotated[int, typer.Option(help="Final number of hits.")] = 5,
        fetch_k: Annotated[int, typer.Option(help="Number of candidates fetched before reranking.")] = 20,
        min_score: Annotated[
            float | None,
            typer.Option(help="Optional minimum score threshold for score-based results (0.0-1.0)."),
        ] = None,
        max_distance: Annotated[
            float | None,
            typer.Option(help="Optional maximum vector distance threshold for distance-based results."),
        ] = None,
        snippet_chars: Annotated[int, typer.Option(help="Snippet length in characters.")] = 320,
        json_output: Annotated[bool, typer.Option(help="Emit JSON output.")] = False,
    ) -> None:
        logger.info("Starting PDF search command for query: {}", query)
        settings = get_config()
        paths = resolve_pdf_paths(
            pdf_dir=pdf_dir,
            index_root=index_root,
            table_name=table_name or settings.pdf.table_name,
        )
        results = search_pdfs(
            SearchConfig.from_settings(
                paths=paths,
                query=query,
                mode=mode.value,
                reranker=reranker.value,
                embed_model=embed_model,
                ollama_base_url=ollama_base_url,
                cross_encoder_model=cross_encoder_model,
                ollama_rerank_model=ollama_rerank_model,
                k=k,
                fetch_k=fetch_k,
                min_score=min_score,
                max_distance=max_distance,
                snippet_chars=snippet_chars,
            )
        )
        logger.info("Finished PDF search command for query: {}", query)
        emit(results, json_output=json_output, formatter=format_search_results)

    @app.command("fetch-pdfs")
    def fetch_pdfs_command(
        pdf_dir: Annotated[
            str | None,
            typer.Option(help="Directory where downloaded PDF files will be stored."),
        ] = None,
        index_root: Annotated[
            str | None,
            typer.Option(help="Directory under /.brains/.index for fetch manifests and search artifacts."),
        ] = None,
        table_name: Annotated[
            str | None,
            typer.Option(help="LanceDB table name used when --reindex is enabled."),
        ] = None,
        notes_glob: Annotated[
            list[str] | None,
            typer.Option(
                "--notes-glob",
                help="Markdown path or glob pattern for notes to scan. Uses `pdf.fetch_note_globs` from config when omitted.",
            ),
        ] = None,
        limit: Annotated[int | None, typer.Option(help="Maximum number of unique URLs to attempt.")] = None,
        timeout: Annotated[int, typer.Option(help="HTTP timeout in seconds per URL attempt.")] = 20,
        dry_run: Annotated[bool, typer.Option(help="Scan and probe links without writing PDF files.")] = False,
        reindex: Annotated[
            bool,
            typer.Option(help="Rebuild the PDF search index after new PDFs are downloaded."),
        ] = False,
        json_output: Annotated[bool, typer.Option(help="Emit JSON output.")] = False,
    ) -> None:
        logger.info("Starting PDF fetch command.")
        settings = get_config()
        paths = resolve_pdf_paths(
            pdf_dir=pdf_dir,
            index_root=index_root,
            table_name=table_name or settings.pdf.table_name,
        )
        payload = fetch_pdfs_from_notes(
            paths,
            note_globs=notes_glob,
            limit=limit,
            dry_run=dry_run,
            timeout=timeout,
        )
        if reindex and not dry_run and payload.get("downloaded_count", 0):
            payload["reindex"] = index_pdfs(
                IndexConfig.from_settings(
                    paths=paths,
                )
            )
        logger.info("Finished PDF fetch command.")
        emit(payload, json_output=json_output, formatter=format_index_summary)
