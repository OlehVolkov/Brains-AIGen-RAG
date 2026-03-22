from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

import typer

from brains.shared import logger
from brains.mcp import build_mcp_server

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class McpTransport(StrEnum):
    STDIO = "stdio"
    SSE = "sse"
    STREAMABLE_HTTP = "streamable-http"


def register_mcp_commands(app: typer.Typer) -> None:
    @app.command("mcp")
    def mcp_command(
        transport: Annotated[McpTransport, typer.Option(help="MCP transport mode.")] = McpTransport.STDIO,
        host: Annotated[str, typer.Option(help="Bind host for HTTP-based transports.")] = "127.0.0.1",
        port: Annotated[int, typer.Option(help="Bind port for HTTP-based transports.")] = 8000,
        debug: Annotated[bool, typer.Option(help="Enable debug mode for the MCP server.")] = False,
        log_level: Annotated[LogLevel, typer.Option(help="Log level for the MCP server.")] = "INFO",
    ) -> None:
        logger.info("Starting MCP server over transport {}", transport.value)
        server = build_mcp_server(host=host, port=port, debug=debug, log_level=log_level)
        server.run(transport=transport.value)
