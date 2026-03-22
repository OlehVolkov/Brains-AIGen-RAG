from __future__ import annotations

import typer

from brain.shared import configure_logging
from brain.commands import (
    register_health_commands,
    register_mcp_commands,
    register_pdf_commands,
    register_research_commands,
    register_vault_commands,
)


app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Index and search PDFs and markdown knowledge-base content with LangChain, LanceDB, and Ollama.",
)
main = app

configure_logging()

register_health_commands(app)
register_mcp_commands(app)
register_pdf_commands(app)
register_research_commands(app)
register_vault_commands(app)


if __name__ == "__main__":
    app()
