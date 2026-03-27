from __future__ import annotations

from pathlib import Path

from brains.background import jobs as background_jobs
from brains.background import runner as background_runner
from brains.background.app import huey
from brains.background.jobs import (
    create_job_record,
    enqueue_cli_job,
    get_job_output,
    list_job_records,
    load_job_record,
    stderr_path,
    stdout_path,
    update_job_record,
)
from brains.config import BackgroundPaths
from brains.config.loader import brains_root as actual_brains_root
from brains.config.loader import repo_root as actual_repo_root


def make_background_paths(tmp_path: Path) -> BackgroundPaths:
    repo_root = tmp_path / "repo"
    brains_root = repo_root / ".brains"
    jobs_root = brains_root / ".cache" / "huey" / "jobs"
    return BackgroundPaths(
        repo_root=repo_root,
        brains_root=brains_root,
        queue_path=brains_root / ".cache" / "huey" / "queue.db",
        jobs_root=jobs_root,
    )


def test_create_and_load_job_record(tmp_path: Path) -> None:
    paths = make_background_paths(tmp_path)
    payload = create_job_record(
        paths,
        job_id="demo-job",
        command=["index-vault", "--parser", "auto"],
        label="vault",
    )

    assert payload["status"] == "queued"
    loaded = load_job_record("demo-job", paths=paths)
    assert loaded["job_id"] == "demo-job"
    assert loaded["command"] == ["index-vault", "--parser", "auto"]


def test_update_job_record_preserves_existing_payload(tmp_path: Path) -> None:
    paths = make_background_paths(tmp_path)
    create_job_record(paths, job_id="demo-job", command=["index"], label=None)

    updated = update_job_record(
        "demo-job",
        paths=paths,
        status="running",
        started_at="2026-03-26T00:00:00Z",
    )

    assert updated["status"] == "running"
    assert updated["started_at"] == "2026-03-26T00:00:00Z"
    assert updated["command"] == ["index"]


def test_list_job_records_returns_most_recent_first(tmp_path: Path) -> None:
    paths = make_background_paths(tmp_path)
    create_job_record(paths, job_id="job-a", command=["index"], label=None)
    create_job_record(paths, job_id="job-b", command=["index-vault"], label=None)

    records = list_job_records(paths=paths, limit=10)

    assert [record["job_id"] for record in records] == ["job-b", "job-a"]


def test_get_job_output_reads_requested_stream(tmp_path: Path) -> None:
    paths = make_background_paths(tmp_path)
    create_job_record(paths, job_id="demo-job", command=["index-graph"], label=None)
    stdout_path(paths, "demo-job").write_text("stdout text", encoding="utf-8")
    stderr_path(paths, "demo-job").write_text("stderr text", encoding="utf-8")

    assert get_job_output("demo-job", stream="stdout", paths=paths) == "stdout text"
    assert get_job_output("demo-job", stream="stderr", paths=paths) == "stderr text"


def test_enqueue_cli_job_smoke_runs_background_help(monkeypatch, tmp_path: Path) -> None:
    paths = BackgroundPaths(
        repo_root=actual_repo_root(),
        brains_root=actual_brains_root(),
        queue_path=tmp_path / "queue.db",
        jobs_root=tmp_path / "jobs",
    )
    monkeypatch.setattr(background_jobs, "resolve_background_paths", lambda: paths)
    monkeypatch.setattr(background_runner, "resolve_background_paths", lambda: paths)

    original_immediate = huey.immediate
    huey.immediate = True
    try:
        payload = enqueue_cli_job(["--help"], label="smoke-help")
    finally:
        huey.immediate = original_immediate

    assert payload["status"] == "succeeded"
    assert payload["returncode"] == 0
    assert payload["label"] == "smoke-help"

    stdout = get_job_output(payload["job_id"], stream="stdout", paths=paths)
    stderr = get_job_output(payload["job_id"], stream="stderr", paths=paths)

    assert "Usage: python -m brains" in stdout
    assert "tasks" in stdout
    assert stderr == ""
