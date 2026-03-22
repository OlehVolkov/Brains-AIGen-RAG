from __future__ import annotations

from typing import Annotated

import typer

from brain.shared import logger, print_json, print_text
from brain.research.formatting import format_think_report
from brain.research.models import ResearchRunConfig
from brain.research.orchestration import run_think_loop
from brain.config import resolve_research_paths


def _emit(payload: dict, *, json_output: bool) -> None:
    if json_output:
        print_json(payload)
    else:
        print_text(format_think_report(payload))


def register_research_commands(app: typer.Typer) -> None:
    @app.command("think")
    def think_command(
        query: Annotated[str, typer.Argument(help="Research query or task.")],
        index_root: Annotated[
            str | None,
            typer.Option(help="Directory under /.brain/.index for research memory."),
        ] = None,
        model: Annotated[str | None, typer.Option(help="Ollama chat model name.")] = None,
        ollama_base_url: Annotated[
            str | None,
            typer.Option(help="Base URL for the local Ollama server."),
        ] = None,
        vault_k: Annotated[int | None, typer.Option(help="Number of vault hits to retrieve.")] = None,
        pdf_k: Annotated[int | None, typer.Option(help="Number of PDF hits to retrieve.")] = None,
        memory_k: Annotated[int | None, typer.Option(help="Number of memory hits to recall.")] = None,
        reflection_rounds: Annotated[
            int | None,
            typer.Option(help="Number of self-reflection rounds."),
        ] = None,
        session_id: Annotated[str | None, typer.Option(help="Optional explicit session id.")] = None,
        save_memory: Annotated[
            bool,
            typer.Option(
                "--save-memory/--no-save-memory",
                help="Persist or skip memory/session artifacts.",
            ),
        ] = True,
        json_output: Annotated[bool, typer.Option(help="Emit JSON output.")] = False,
    ) -> None:
        logger.info("Starting research think loop for query: {}", query)
        payload = run_think_loop(
            ResearchRunConfig.from_settings(
                paths=resolve_research_paths(index_root=index_root),
                query=query,
                model=model,
                ollama_base_url=ollama_base_url,
                vault_k=vault_k,
                pdf_k=pdf_k,
                memory_k=memory_k,
                reflection_rounds=reflection_rounds,
                session_id=session_id,
                save_memory=save_memory,
            )
        )
        logger.info("Finished research think loop for query: {}", query)
        _emit(payload, json_output=json_output)
