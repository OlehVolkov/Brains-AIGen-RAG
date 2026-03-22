from __future__ import annotations

import json
import os
import sys
from typing import Any

from loguru import logger
from rich.console import Console
from rich.text import Text

_LOGGING_CONFIGURED = False


def get_console(*, stderr: bool = False) -> Console:
    return Console(
        file=sys.stderr if stderr else sys.stdout,
        soft_wrap=True,
        stderr=stderr,
    )


def _rich_log_sink(message) -> None:
    get_console(stderr=True).print(Text.from_ansi(str(message)), end="")


def configure_logging() -> None:
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return
    logger.add(
        _rich_log_sink,
        level=os.getenv("BRAINS_LOG_LEVEL", "WARNING").upper(),
        colorize=True,
        backtrace=False,
        diagnose=False,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
    )
    _LOGGING_CONFIGURED = True


def print_json(payload: dict[str, Any]) -> None:
    get_console().print_json(json=json.dumps(payload, ensure_ascii=False, indent=2))


def print_text(text: str) -> None:
    get_console().print(text)
