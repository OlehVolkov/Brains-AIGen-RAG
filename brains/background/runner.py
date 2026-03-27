from __future__ import annotations

from datetime import UTC, datetime
import os
from pathlib import Path
import subprocess
import sys
import traceback

from brains.background.jobs import stderr_path, stdout_path, update_job_record
from brains.config import resolve_background_paths


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _base_env(repo_root: Path, brains_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["BRAINS_REPO_ROOT"] = str(repo_root)
    env["BRAINS_ROOT"] = str(brains_root)
    return env


def run_cli_job(job_id: str, command: list[str]) -> dict:
    paths = resolve_background_paths()
    update_job_record(
        job_id,
        paths=paths,
        status="running",
        started_at=_now_iso(),
        worker_pid=os.getpid(),
        command=list(command),
    )

    stdout_file = stdout_path(paths, job_id)
    stderr_file = stderr_path(paths, job_id)

    try:
        completed = subprocess.run(
            [sys.executable, "-m", "brains", *command],
            cwd=paths.brains_root,
            env=_base_env(paths.repo_root, paths.brains_root),
            capture_output=True,
            text=True,
            check=False,
        )
        stdout_file.write_text(completed.stdout or "", encoding="utf-8")
        stderr_file.write_text(completed.stderr or "", encoding="utf-8")

        status = "succeeded" if completed.returncode == 0 else "failed"
        record = update_job_record(
            job_id,
            paths=paths,
            status=status,
            finished_at=_now_iso(),
            returncode=completed.returncode,
            error=None if completed.returncode == 0 else "Background command failed.",
        )
        return {
            "job_id": job_id,
            "status": status,
            "returncode": completed.returncode,
            "stdout_path": record["stdout_path"],
            "stderr_path": record["stderr_path"],
        }
    except Exception as exc:
        stderr_file.write_text(traceback.format_exc(), encoding="utf-8")
        update_job_record(
            job_id,
            paths=paths,
            status="failed",
            finished_at=_now_iso(),
            returncode=-1,
            error=str(exc),
        )
        raise
