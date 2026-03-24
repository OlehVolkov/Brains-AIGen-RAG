#!/usr/bin/env python3
"""
Portable wrapper for fetching literature PDFs through the local `brains` CLI.

Purpose:
- run `brains fetch-pdfs --reindex` from `/.brains` without a shell-only wrapper;
- keep the invocation portable by resolving `uv` from `PATH` or `UV_BIN`;
- provide a small adaptation template for similar repositories with another layout.

Adapt first when reusing in another repository:
- `brains_root()` if the Python project is not nested under `/.brains`;
- the default delegated CLI command if the target repository uses another fetch entrypoint;
- optional environment defaults if the target environment needs a custom `UV_CACHE_DIR`.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


def brains_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_uv_executable() -> str:
    configured = os.environ.get("UV_BIN")
    if configured:
        return configured
    resolved = shutil.which("uv")
    if resolved:
        return resolved
    raise FileNotFoundError(
        "Could not find `uv` in PATH. Install uv or set UV_BIN to the executable path."
    )


def build_command(extra_args: list[str]) -> list[str]:
    return [
        resolve_uv_executable(),
        "run",
        "--project",
        str(brains_root()),
        "python",
        "-m",
        "brains",
        "fetch-pdfs",
        "--reindex",
        *extra_args,
    ]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    env = os.environ.copy()
    subprocess.run(
        build_command(args),
        cwd=brains_root(),
        env=env,
        check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
