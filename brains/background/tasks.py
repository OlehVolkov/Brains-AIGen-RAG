from __future__ import annotations

from brains.background.app import huey
from brains.background.runner import run_cli_job


@huey.task()
def run_cli_command_task(job_id: str, command: list[str]) -> dict:
    return run_cli_job(job_id, command)
