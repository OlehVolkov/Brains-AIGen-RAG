from __future__ import annotations

from typing import Annotated

import typer

from brains.shared import logger, print_json, print_text
from brains.shared.formatting import format_index_summary
from brains.config import get_config, resolve_graph_paths
from brains.sources.graph import (
    GraphIndexConfig,
    GraphPathConfig,
    GraphSearchConfig,
    explain_graph_path,
    format_graph_path_results,
    format_graph_search_results,
    index_graph,
    search_graph,
)


def emit(payload: dict, *, json_output: bool, formatter) -> None:
    if json_output:
        print_json(payload)
    else:
        print_text(formatter(payload))


def register_graph_commands(app: typer.Typer) -> None:
    @app.command("index-graph")
    def index_graph_command(
        index_root: Annotated[
            str | None,
            typer.Option(help="Directory under /.brains/.index for graph artifacts."),
        ] = None,
        graph_file: Annotated[
            str | None,
            typer.Option(help="Graph artifact filename under the graph index root."),
        ] = None,
        json_output: Annotated[bool, typer.Option(help="Emit JSON output.")] = False,
    ) -> None:
        logger.info("Starting graph indexing command.")
        paths = resolve_graph_paths(index_root=index_root, graph_file=graph_file)
        summary = index_graph(GraphIndexConfig.from_settings(paths=paths))
        logger.info("Finished graph indexing command.")
        emit(summary, json_output=json_output, formatter=format_index_summary)

    @app.command("search-graph")
    def search_graph_command(
        query: Annotated[str, typer.Argument(help="Graph search query.")],
        index_root: Annotated[
            str | None,
            typer.Option(help="Directory under /.brains/.index for graph artifacts."),
        ] = None,
        graph_file: Annotated[
            str | None,
            typer.Option(help="Graph artifact filename under the graph index root."),
        ] = None,
        k: Annotated[int | None, typer.Option(help="Maximum number of note hits.")] = None,
        max_hops: Annotated[
            int | None,
            typer.Option(help="Maximum graph expansion hops from seed nodes."),
        ] = None,
        json_output: Annotated[bool, typer.Option(help="Emit JSON output.")] = False,
    ) -> None:
        logger.info("Starting graph search command for query: {}", query)
        settings = get_config()
        paths = resolve_graph_paths(index_root=index_root, graph_file=graph_file)
        payload = search_graph(
            GraphSearchConfig.from_settings(
                paths=paths,
                query=query,
                k=settings.graph.k if k is None else k,
                max_hops=settings.graph.max_hops if max_hops is None else max_hops,
            )
        )
        logger.info("Finished graph search command for query: {}", query)
        emit(payload, json_output=json_output, formatter=format_graph_search_results)

    @app.command("explain-path")
    def explain_path_command(
        source: Annotated[str, typer.Argument(help="Source note path or note title/query.")],
        target: Annotated[str, typer.Argument(help="Target note path or note title/query.")],
        index_root: Annotated[
            str | None,
            typer.Option(help="Directory under /.brains/.index for graph artifacts."),
        ] = None,
        graph_file: Annotated[
            str | None,
            typer.Option(help="Graph artifact filename under the graph index root."),
        ] = None,
        max_hops: Annotated[
            int | None,
            typer.Option(help="Maximum number of edges allowed in the explanation path."),
        ] = None,
        json_output: Annotated[bool, typer.Option(help="Emit JSON output.")] = False,
    ) -> None:
        logger.info("Starting graph path explanation from {} to {}", source, target)
        settings = get_config()
        paths = resolve_graph_paths(index_root=index_root, graph_file=graph_file)
        payload = explain_graph_path(
            GraphPathConfig.from_settings(
                paths=paths,
                source=source,
                target=target,
                max_hops=settings.graph.max_hops if max_hops is None else max_hops,
            )
        )
        logger.info("Finished graph path explanation from {} to {}", source, target)
        emit(payload, json_output=json_output, formatter=format_graph_path_results)
