#!/usr/bin/env bash
set -euo pipefail

UV_BIN="${UV_BIN:-/home/oleh/.local/bin/uv}"
UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"

export UV_CACHE_DIR

exec "$UV_BIN" run --project .brain brain fetch-pdfs --reindex "$@"
