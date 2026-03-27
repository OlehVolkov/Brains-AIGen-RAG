from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import uuid

from brains.config import BackgroundPaths, resolve_background_paths


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def ensure_background_dirs(paths: BackgroundPaths) -> None:
    paths.queue_path.parent.mkdir(parents=True, exist_ok=True)
    paths.jobs_root.mkdir(parents=True, exist_ok=True)


def _job_dir(paths: BackgroundPaths, job_id: str) -> Path:
    return paths.jobs_root / job_id


def job_record_path(paths: BackgroundPaths, job_id: str) -> Path:
    return _job_dir(paths, job_id) / "job.json"


def stdout_path(paths: BackgroundPaths, job_id: str) -> Path:
    return _job_dir(paths, job_id) / "stdout.txt"


def stderr_path(paths: BackgroundPaths, job_id: str) -> Path:
    return _job_dir(paths, job_id) / "stderr.txt"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _safe_relative(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def create_job_record(
    paths: BackgroundPaths,
    *,
    job_id: str,
    command: list[str],
    label: str | None = None,
) -> dict:
    ensure_background_dirs(paths)
    record = {
        "job_id": job_id,
        "status": "queued",
        "label": label,
        "command": list(command),
        "created_at": _now_iso(),
        "started_at": None,
        "finished_at": None,
        "returncode": None,
        "error": None,
        "stdout_path": _safe_relative(stdout_path(paths, job_id), paths.repo_root),
        "stderr_path": _safe_relative(stderr_path(paths, job_id), paths.repo_root),
    }
    _write_json(job_record_path(paths, job_id), record)
    return record


def load_job_record(job_id: str, *, paths: BackgroundPaths | None = None) -> dict:
    current_paths = paths or resolve_background_paths()
    record_path = job_record_path(current_paths, job_id)
    if not record_path.exists():
        raise FileNotFoundError(f"Unknown background job: {job_id}")
    return json.loads(record_path.read_text(encoding="utf-8"))


def update_job_record(
    job_id: str,
    *,
    paths: BackgroundPaths | None = None,
    **updates,
) -> dict:
    current_paths = paths or resolve_background_paths()
    record_path = job_record_path(current_paths, job_id)
    if record_path.exists():
        record = load_job_record(job_id, paths=current_paths)
    else:
        record = {
            "job_id": job_id,
            "status": "queued",
            "label": None,
            "command": [],
            "created_at": _now_iso(),
            "started_at": None,
            "finished_at": None,
            "returncode": None,
            "error": None,
            "stdout_path": _safe_relative(stdout_path(current_paths, job_id), current_paths.repo_root),
            "stderr_path": _safe_relative(stderr_path(current_paths, job_id), current_paths.repo_root),
        }
    record.update(updates)
    _write_json(record_path, record)
    return record


def list_job_records(
    *,
    paths: BackgroundPaths | None = None,
    limit: int = 20,
) -> list[dict]:
    current_paths = paths or resolve_background_paths()
    ensure_background_dirs(current_paths)
    records: list[dict] = []
    for job_path in current_paths.jobs_root.glob("*/job.json"):
        try:
            payload = json.loads(job_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        records.append(payload)
    records.sort(
        key=lambda item: item.get("created_at") or "",
        reverse=True,
    )
    return records[:limit]


def enqueue_cli_job(command: list[str], *, label: str | None = None) -> dict:
    from brains.background.tasks import run_cli_command_task

    paths = resolve_background_paths()
    job_id = uuid.uuid4().hex
    create_job_record(paths, job_id=job_id, command=command, label=label)
    run_cli_command_task(job_id, command)
    return load_job_record(job_id, paths=paths)


def get_job_output(
    job_id: str,
    *,
    stream: str = "stdout",
    paths: BackgroundPaths | None = None,
) -> str:
    current_paths = paths or resolve_background_paths()
    artifact_path = stdout_path(current_paths, job_id) if stream == "stdout" else stderr_path(current_paths, job_id)
    if not artifact_path.exists():
        return ""
    return artifact_path.read_text(encoding="utf-8")
