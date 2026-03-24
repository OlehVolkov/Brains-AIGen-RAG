from __future__ import annotations

from enum import StrEnum
from typing import Annotated

import typer

from brains.shared import logger, print_json, print_text
from brains.shared.formatting import format_index_summary
from brains.config import get_config, resolve_vault_paths
from brains.sources.vault import format_vault_search_results, index_vault, search_vault
from brains.sources.vault.models import VaultIndexConfig, VaultSearchConfig


class SearchMode(StrEnum):
    AUTO = "auto"
    VECTOR = "vector"
    FTS = "fts"
    HYBRID = "hybrid"
    HYBRID_GRAPH = "hybrid-graph"


class RerankerChoice(StrEnum):
    NONE = "none"
    RRF = "rrf"
    CROSS_ENCODER = "cross-encoder"
    OLLAMA = "ollama"


class VaultParserChoice(StrEnum):
    NATIVE = "native"
    DOCLING = "docling"
    AUTO = "auto"


def emit(payload: dict, *, json_output: bool, formatter) -> None:
    if json_output:
        print_json(payload)
    else:
        print_text(formatter(payload))


def register_vault_commands(app: typer.Typer) -> None:
    @app.command("index-vault")
    def index_vault_command(
        index_root: Annotated[
            str | None,
            typer.Option(help="Directory under /.brains/.index for search artifacts."),
        ] = None,
        table_name: Annotated[str | None, typer.Option(help="LanceDB table name.")] = None,
        parser: Annotated[
            VaultParserChoice,
            typer.Option(help="Markdown parsing backend."),
        ] = VaultParserChoice.NATIVE,
        embed_model: Annotated[str | None, typer.Option(help="Ollama embedding model name.")] = None,
        ollama_base_url: Annotated[str | None, typer.Option(help="Base URL for the local Ollama server.")] = None,
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
        logger.info("Starting vault indexing command.")
        settings = get_config()
        paths = resolve_vault_paths(
            index_root=index_root,
            table_name=table_name or settings.vault.table_name,
        )
        summary = index_vault(
            VaultIndexConfig.from_settings(
                paths=paths,
                parser=parser.value,
                embed_model=embed_model,
                ollama_base_url=ollama_base_url,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                batch_size=batch_size,
                overwrite=not no_overwrite,
            )
        )
        logger.info("Finished vault indexing command.")
        emit(summary, json_output=json_output, formatter=format_index_summary)

    @app.command("search-vault")
    def search_vault_command(
        query: Annotated[str, typer.Argument(help="Search query.")],
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
            typer.Option(
                help="Sentence-transformers cross-encoder model used for reranking.",
            ),
        ] = None,
        ollama_rerank_model: Annotated[
            str | None,
            typer.Option(help="Ollama chat model used for LLM-based reranking."),
        ] = None,
        k: Annotated[int, typer.Option(help="Final number of hits.")] = 5,
        fetch_k: Annotated[int, typer.Option(help="Number of candidates fetched before reranking.")] = 20,
        graph_max_hops: Annotated[
            int | None,
            typer.Option(help="Maximum graph expansion hops when mode=hybrid-graph."),
        ] = None,
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
        logger.info("Starting vault search command for query: {}", query)
        settings = get_config()
        paths = resolve_vault_paths(
            index_root=index_root,
            table_name=table_name or settings.vault.table_name,
        )
        results = search_vault(
            VaultSearchConfig.from_settings(
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
                graph_max_hops=graph_max_hops,
                min_score=min_score,
                max_distance=max_distance,
                snippet_chars=snippet_chars,
            )
        )
        logger.info("Finished vault search command for query: {}", query)
        emit(results, json_output=json_output, formatter=format_vault_search_results)
