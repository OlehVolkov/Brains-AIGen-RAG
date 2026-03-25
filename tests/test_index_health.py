from __future__ import annotations

import json
from pathlib import Path

from brains.shared import health
from brains.shared.health import check_index_health, resolve_active_index_paths
from brains.config import BrainsPaths


def make_paths(tmp_path: Path) -> BrainsPaths:
    repo_root = tmp_path
    brains_root = repo_root / ".brains"
    index_root = brains_root / ".index" / "pdf_search"
    return BrainsPaths(
        repo_root=repo_root,
        brains_root=brains_root,
        pdf_dir=repo_root / "PDF",
        index_root=index_root,
        db_uri=index_root / "lancedb",
        manifest_path=index_root / "manifest.json",
        table_name="scientific_pdf_chunks",
    )


def test_resolve_active_index_paths_uses_pointer_payload(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    paths.index_root.mkdir(parents=True, exist_ok=True)
    pointer_path = paths.index_root / "active_index.json"
    payload = {
        "index_root": str(tmp_path / "fallback-index"),
        "db_uri": str(tmp_path / "fallback-index" / "lancedb"),
        "manifest_path": str(tmp_path / "fallback-index" / "manifest.json"),
        "table_name": "fallback_table",
    }
    pointer_path.write_text(json.dumps(payload), encoding="utf-8")

    effective_paths, resolved_pointer = resolve_active_index_paths(paths)

    assert resolved_pointer == pointer_path
    assert effective_paths.index_root == tmp_path / "fallback-index"
    assert effective_paths.db_uri == tmp_path / "fallback-index" / "lancedb"
    assert effective_paths.manifest_path == tmp_path / "fallback-index" / "manifest.json"
    assert effective_paths.table_name == "fallback_table"


def test_check_index_health_reports_missing_artifacts(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)

    payload = check_index_health(paths, probe_query="pairformer", timeout_seconds=1)

    assert payload["status"] == "missing"
    assert payload["artifacts"]["db_uri_exists"] is False
    assert payload["artifacts"]["table_exists"] is False


def test_check_index_health_retries_once_after_timeout(tmp_path: Path, monkeypatch) -> None:
    paths = make_paths(tmp_path)
    table_path = paths.db_uri / f"{paths.table_name}.lance"
    table_path.mkdir(parents=True, exist_ok=True)
    paths.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    paths.manifest_path.write_text("{}", encoding="utf-8")

    attempts = iter(
        [
            {"status": "timeout", "elapsed_seconds": 10.0},
            {"status": "ok", "elapsed_seconds": 0.5, "row_count": 123, "probe_results": []},
        ]
    )

    monkeypatch.setattr(health, "_run_probe_attempt", lambda **_: next(attempts))

    payload = check_index_health(
        paths,
        probe_query="pairformer",
        timeout_seconds=10,
        retry_on_timeout=1,
    )

    assert payload["status"] == "ok"
    assert payload["attempts"] == 2
    assert payload["retried_after_timeout"] is True
    assert payload["row_count"] == 123


def test_check_index_health_reports_timeout_after_retries_exhausted(tmp_path: Path, monkeypatch) -> None:
    paths = make_paths(tmp_path)
    table_path = paths.db_uri / f"{paths.table_name}.lance"
    table_path.mkdir(parents=True, exist_ok=True)
    paths.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    paths.manifest_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        health,
        "_run_probe_attempt",
        lambda **_: {"status": "timeout", "elapsed_seconds": 10.0},
    )

    payload = check_index_health(
        paths,
        probe_query="pairformer",
        timeout_seconds=10,
        retry_on_timeout=1,
    )

    assert payload["status"] == "timeout"
    assert payload["attempts"] == 2
    assert payload["retried_after_timeout"] is True
