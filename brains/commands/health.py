from __future__ import annotations

import json
from enum import StrEnum
from typing import Annotated

import typer

from brains.shared import check_index_health, logger, print_json, print_text
from brains.config import get_config, resolve_pdf_paths, resolve_vault_paths


class IndexTarget(StrEnum):
    PDF = "pdf"
    VAULT = "vault"


def register_health_commands(app: typer.Typer) -> None:
    @app.command("check-index")
    def check_index_command(
        target: Annotated[IndexTarget, typer.Option(help="Index family to validate.")] = IndexTarget.PDF,
        pdf_dir: Annotated[str | None, typer.Option(help="Optional PDF directory override for PDF checks.")] = None,
        index_root: Annotated[str | None, typer.Option(help="Optional index root override.")] = None,
        table_name: Annotated[str | None, typer.Option(help="Optional LanceDB table name override.")] = None,
        query: Annotated[str | None, typer.Option(help="Optional FTS probe query.")] = None,
        timeout_seconds: Annotated[int, typer.Option(help="Maximum seconds to wait before reporting a hang.")] = 10,
        json_output: Annotated[bool, typer.Option(help="Emit JSON output.")] = False,
    ) -> None:
        logger.info("Starting index health-check for target: {}", target.value)
        settings = get_config()
        if target is IndexTarget.PDF:
            paths = resolve_pdf_paths(
                pdf_dir=pdf_dir,
                index_root=index_root,
                table_name=table_name or settings.pdf.table_name,
            )
            probe_query = settings.health.pdf_probe_query if query is None else query
        else:
            paths = resolve_vault_paths(
                index_root=index_root,
                table_name=table_name or settings.vault.table_name,
            )
            probe_query = settings.health.vault_probe_query if query is None else query

        payload = check_index_health(
            paths,
            probe_query=probe_query,
            timeout_seconds=timeout_seconds,
        )
        logger.info("Finished index health-check for target: {}", target.value)
        if json_output:
            print_json(payload)
        else:
            print_text(json.dumps(payload, ensure_ascii=False, indent=2))
