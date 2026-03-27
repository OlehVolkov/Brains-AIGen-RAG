from __future__ import annotations

import os
import subprocess
import sys
from typing import Annotated

import typer

from brains.background import enqueue_cli_job, get_job_output, list_job_records, load_job_record
from brains.config import resolve_background_paths
from brains.shared import print_json, print_text


tasks_app = typer.Typer(
    help="Queue heavy brains CLI commands for background execution with Huey.",
    no_args_is_help=True,
)


def _emit(payload: dict | list[dict], *, json_output: bool) -> None:
    if json_output:
        if isinstance(payload, list):
            print_json({"jobs": payload})
        else:
            print_json(payload)
        return

    if isinstance(payload, list):
        if not payload:
            print_text("No background jobs found.")
            return
        lines = []
        for item in payload:
            label = f" | label={item['label']}" if item.get("label") else ""
            lines.append(f"{item['job_id']} | {item['status']}{label} | {' '.join(item.get('command', []))}")
        print_text("\n".join(lines))
        return

    lines = [
        f"job_id: {payload['job_id']}",
        f"status: {payload['status']}",
        f"command: {' '.join(payload.get('command', []))}",
    ]
    if payload.get("label"):
        lines.append(f"label: {payload['label']}")
    if payload.get("returncode") is not None:
        lines.append(f"returncode: {payload['returncode']}")
    if payload.get("stdout_path"):
        lines.append(f"stdout: {payload['stdout_path']}")
    if payload.get("stderr_path"):
        lines.append(f"stderr: {payload['stderr_path']}")
    if payload.get("error"):
        lines.append(f"error: {payload['error']}")
    print_text("\n".join(lines))


def register_task_commands(app: typer.Typer) -> None:
    app.add_typer(tasks_app, name="tasks")


@tasks_app.command(
    "enqueue",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def enqueue_command(
    ctx: typer.Context,
    label: Annotated[str | None, typer.Option(help="Optional human-readable label for the background job.")] = None,
    json_output: Annotated[bool, typer.Option(help="Emit JSON output.")] = False,
) -> None:
    command = list(ctx.args)
    if not command:
        raise typer.BadParameter("Provide a brains CLI command after `tasks enqueue`.")
    payload = enqueue_cli_job(command, label=label)
    _emit(payload, json_output=json_output)


@tasks_app.command("status")
def status_command(
    job_id: Annotated[str, typer.Argument(help="Background job id.")],
    json_output: Annotated[bool, typer.Option(help="Emit JSON output.")] = False,
) -> None:
    payload = load_job_record(job_id)
    _emit(payload, json_output=json_output)


@tasks_app.command("list")
def list_command(
    limit: Annotated[int, typer.Option(help="Maximum number of recent jobs to display.")] = 20,
    json_output: Annotated[bool, typer.Option(help="Emit JSON output.")] = False,
) -> None:
    payload = list_job_records(limit=limit)
    _emit(payload, json_output=json_output)


@tasks_app.command("output")
def output_command(
    job_id: Annotated[str, typer.Argument(help="Background job id.")],
    stream: Annotated[str, typer.Option(help="Which output stream to print: stdout or stderr.")] = "stdout",
) -> None:
    if stream not in {"stdout", "stderr"}:
        raise typer.BadParameter("Stream must be either `stdout` or `stderr`.")
    print_text(get_job_output(job_id, stream=stream))


@tasks_app.command("worker")
def worker_command() -> None:
    paths = resolve_background_paths()
    env = os.environ.copy()
    env["BRAINS_REPO_ROOT"] = str(paths.repo_root)
    env["BRAINS_ROOT"] = str(paths.brains_root)
    raise SystemExit(
        subprocess.run(
            [sys.executable, "-m", "huey.bin.huey_consumer", "brains.background.app.huey"],
            cwd=paths.brains_root,
            env=env,
            check=False,
        ).returncode
    )
