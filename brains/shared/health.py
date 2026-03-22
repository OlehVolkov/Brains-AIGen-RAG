from __future__ import annotations

import json
import multiprocessing
import traceback
from pathlib import Path
from queue import Empty
from time import monotonic
from typing import Any

from brains.config import BrainsPaths


def resolve_active_index_paths(paths: BrainsPaths) -> tuple[BrainsPaths, Path | None]:
    pointer_path = paths.index_root / "active_index.json"
    if not pointer_path.exists():
        return paths, None

    payload = json.loads(pointer_path.read_text(encoding="utf-8"))
    index_root = Path(payload["index_root"])
    db_uri = Path(payload.get("db_uri", index_root / "lancedb"))
    manifest_path = Path(payload.get("manifest_path", index_root / "manifest.json"))
    table_name = payload.get("table_name", paths.table_name)
    return (
        BrainsPaths(
            repo_root=paths.repo_root,
            brains_root=paths.brains_root,
            pdf_dir=paths.pdf_dir,
            index_root=index_root,
            db_uri=db_uri,
            manifest_path=manifest_path,
            table_name=table_name,
        ),
        pointer_path,
    )


def _probe_index_worker(
    queue: multiprocessing.queues.Queue,
    *,
    db_uri: str,
    table_name: str,
    probe_query: str | None,
) -> None:
    try:
        import lancedb

        db = lancedb.connect(db_uri)
        table = db.open_table(table_name)
        payload: dict[str, Any] = {
            "status": "ok",
            "row_count": table.count_rows(),
        }
        if probe_query:
            payload["probe_query"] = probe_query
            raw_rows = table.search(
                probe_query,
                query_type="fts",
                fts_columns="text",
            ).limit(3).to_list()
            payload["probe_results"] = [
                {
                    key: row[key]
                    for key in ("source_path", "section", "chunk_index", "_score")
                    if key in row
                }
                for row in raw_rows
            ]
        queue.put(payload)
    except BaseException as exc:  # pragma: no cover - exercised via subprocess boundary
        queue.put(
            {
                "status": "error",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        )


def check_index_health(
    paths: BrainsPaths,
    *,
    probe_query: str | None = None,
    timeout_seconds: int = 10,
) -> dict[str, Any]:
    effective_paths, pointer_path = resolve_active_index_paths(paths)
    table_path = effective_paths.db_uri / f"{effective_paths.table_name}.lance"
    payload: dict[str, Any] = {
        "status": "unknown",
        "table_name": effective_paths.table_name,
        "index_root": str(effective_paths.index_root),
        "db_uri": str(effective_paths.db_uri),
        "manifest_path": str(effective_paths.manifest_path),
        "table_path": str(table_path),
        "pointer_path": str(pointer_path) if pointer_path else None,
        "pointer_used": pointer_path is not None,
        "probe_query": probe_query,
        "timeout_seconds": timeout_seconds,
        "artifacts": {
            "db_uri_exists": effective_paths.db_uri.exists(),
            "manifest_exists": effective_paths.manifest_path.exists(),
            "table_exists": table_path.exists(),
        },
    }

    if not payload["artifacts"]["db_uri_exists"] or not payload["artifacts"]["table_exists"]:
        payload["status"] = "missing"
        payload["error"] = "Index artifacts are missing on disk."
        return payload

    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    process = ctx.Process(
        target=_probe_index_worker,
        kwargs={
            "queue": queue,
            "db_uri": str(effective_paths.db_uri),
            "table_name": effective_paths.table_name,
            "probe_query": probe_query,
        },
    )

    started_at = monotonic()
    process.start()
    process.join(timeout_seconds)
    payload["elapsed_seconds"] = round(monotonic() - started_at, 3)

    if process.is_alive():
        process.terminate()
        process.join(2)
        payload["status"] = "timeout"
        payload["error"] = (
            "Timed out while opening or querying the LanceDB table. "
            "Under WSL or restricted sandbox environments, this often indicates a runtime "
            "environment issue rather than a corrupted index."
        )
        payload["suggestion"] = (
            "Retry the health-check outside the sandbox. If the repository is on /mnt/c, "
            "keep the active index under a Linux-native path such as /tmp."
        )
        return payload

    try:
        child_payload = queue.get_nowait()
    except Empty:
        child_payload = {
            "status": "error",
            "error": "The health-check worker exited without returning a result.",
            "exit_code": process.exitcode,
        }

    payload.update(child_payload)
    return payload
