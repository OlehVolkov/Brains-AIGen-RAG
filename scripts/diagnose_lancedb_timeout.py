#!/usr/bin/env python3
"""
Diagnose LanceDB open/query time on the local Windows-path index layout.

What this script does:
- resolves the active `vault` or `pdf` index paths from the checked-in config
- measures direct LanceDB operations: connect, open_table, count_rows, FTS search
- optionally repeats the same probe inside a spawned child process to isolate
  multiprocessing startup overhead from pure LanceDB I/O/runtime cost

What to review first when adapting to another repository:
- target resolution depends on this repository's `brains.config` path helpers
- the default probe query assumes an indexed `text` column and repository search
  conventions similar to this vault
- Windows-oriented diagnosis is most useful when the canonical environment is a
  Windows `.venv` and indexes live on a Windows path rather than `/tmp/...`
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import lancedb  # noqa: E402

from brains.config import get_config, resolve_pdf_paths, resolve_vault_paths  # noqa: E402
from brains.shared.health import resolve_active_index_paths  # noqa: E402


def _resolve_paths(target: str):
    settings = get_config()
    if target == "vault":
        return resolve_active_index_paths(resolve_vault_paths(table_name=settings.vault.table_name))[0]
    if target == "pdf":
        return resolve_active_index_paths(resolve_pdf_paths(table_name=settings.pdf.table_name))[0]
    raise ValueError(f"Unsupported target: {target}")


def _probe(db_uri: str, table_name: str, query: str) -> dict[str, Any]:
    metrics: dict[str, Any] = {}

    t0 = time.perf_counter()
    db = lancedb.connect(db_uri)
    metrics["connect_seconds"] = round(time.perf_counter() - t0, 3)

    t0 = time.perf_counter()
    table = db.open_table(table_name)
    metrics["open_table_seconds"] = round(time.perf_counter() - t0, 3)

    t0 = time.perf_counter()
    metrics["row_count"] = table.count_rows()
    metrics["count_rows_seconds"] = round(time.perf_counter() - t0, 3)

    t0 = time.perf_counter()
    hits = table.search(query, query_type="fts", fts_columns="text").limit(3).to_list()
    metrics["search_seconds"] = round(time.perf_counter() - t0, 3)
    metrics["search_hits"] = [
        {key: row.get(key) for key in ("source_path", "section", "chunk_index", "_score")}
        for row in hits
    ]
    metrics["total_seconds"] = round(
        metrics["connect_seconds"]
        + metrics["open_table_seconds"]
        + metrics["count_rows_seconds"]
        + metrics["search_seconds"],
        3,
    )
    return metrics


def _worker(queue: mp.Queue, db_uri: str, table_name: str, query: str) -> None:
    started = time.perf_counter()
    try:
        payload = _probe(db_uri, table_name, query)
        payload["status"] = "ok"
    except BaseException as exc:  # pragma: no cover
        payload = {
            "status": "error",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    payload["worker_elapsed_seconds"] = round(time.perf_counter() - started, 3)
    queue.put(payload)


def _run_spawn_probe(db_uri: str, table_name: str, query: str, timeout_seconds: int) -> dict[str, Any]:
    ctx = mp.get_context("spawn")
    queue: mp.Queue = ctx.Queue()
    proc = ctx.Process(target=_worker, args=(queue, db_uri, table_name, query))
    started = time.perf_counter()
    proc.start()
    proc.join(timeout_seconds)

    result: dict[str, Any] = {
        "spawn_total_wait_seconds": round(time.perf_counter() - started, 3),
        "spawn_exitcode": proc.exitcode,
    }
    if proc.is_alive():
        proc.terminate()
        proc.join(2)
        result["status"] = "timeout"
        return result

    if queue.empty():
        result["status"] = "no_result"
        return result

    result.update(queue.get())
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose LanceDB timeout behavior on local indexes.")
    parser.add_argument("--target", choices=("vault", "pdf"), required=True)
    parser.add_argument("--query", default="pairformer")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--skip-spawn", action="store_true")
    args = parser.parse_args()

    paths = _resolve_paths(args.target)
    payload: dict[str, Any] = {
        "target": args.target,
        "python_executable": sys.executable,
        "platform": sys.platform,
        "cwd": str(Path.cwd()),
        "index_root": str(paths.index_root),
        "db_uri": str(paths.db_uri),
        "manifest_path": str(paths.manifest_path),
        "table_name": paths.table_name,
        "probe_query": args.query,
        "artifacts": {
            "index_root_exists": paths.index_root.exists(),
            "db_uri_exists": paths.db_uri.exists(),
            "manifest_exists": paths.manifest_path.exists(),
            "table_exists": (paths.db_uri / f"{paths.table_name}.lance").exists(),
        },
    }

    direct_started = time.perf_counter()
    try:
        payload["direct_probe"] = {"status": "ok", **_probe(str(paths.db_uri), paths.table_name, args.query)}
    except BaseException as exc:
        payload["direct_probe"] = {
            "status": "error",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    payload["direct_wall_seconds"] = round(time.perf_counter() - direct_started, 3)

    if not args.skip_spawn:
        payload["spawn_probe"] = _run_spawn_probe(
            str(paths.db_uri),
            paths.table_name,
            args.query,
            args.timeout_seconds,
        )

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
