#!/usr/bin/env python3
"""
Reusable mypy hang/localization helper for repositories that keep Python tooling
in a nested project directory such as `/.brains`.

Purpose:
- run `mypy` against packages/files with a per-target timeout;
- detect which package, subpackage, or file is hanging instead of finishing;
- help agents narrow a type-check stall before changing code blindly.

Adapt first when reusing in another repository:
- `brains_root()` / `repo_root()` if the Python project is not under `/.brains`;
- `--project-dir` if the Python project root is not the current `/.brains` directory;
- `--package-root` if the source package is not under `<project-dir>/brains`;
- `--python-cmd` if the canonical interpreter is not the Windows `.venv` run via `cmd.exe`;
- `--follow-imports` if you need to distinguish local file checking from deep import traversal;
- timeout/depth values if the target project is much larger or smaller.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class ProbeResult:
    target: str
    kind: str
    status: str
    elapsed_seconds: float
    returncode: int | None
    stdout: str
    stderr: str


def brains_root() -> Path:
    return Path(__file__).resolve().parent.parent


def repo_root() -> Path:
    return brains_root().parent


def run_mypy_probe(
    *,
    cwd: Path,
    project_dir: Path,
    python_cmd: str,
    target: Path,
    timeout_seconds: int,
    follow_imports: str,
) -> ProbeResult:
    rel_target = target.relative_to(project_dir).as_posix()
    command = (
        f'cd /d %CD%\\{project_dir.name} && set "UV_PROJECT_ENVIRONMENT=.venv" && '
        f"{python_cmd} -m mypy --no-incremental --follow-imports {follow_imports} {rel_target}"
    )
    started = time.monotonic()
    try:
        completed = subprocess.run(
            ["cmd.exe", "/c", command],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed = time.monotonic() - started
        return ProbeResult(
            target=rel_target,
            kind="dir" if target.is_dir() else "file",
            status="timeout",
            elapsed_seconds=round(elapsed, 3),
            returncode=None,
            stdout=(exc.stdout or "").strip(),
            stderr=(exc.stderr or "").strip(),
        )

    elapsed = time.monotonic() - started
    status = "ok" if completed.returncode == 0 else "error"
    return ProbeResult(
        target=rel_target,
        kind="dir" if target.is_dir() else "file",
        status=status,
        elapsed_seconds=round(elapsed, 3),
        returncode=completed.returncode,
        stdout=(completed.stdout or "").strip(),
        stderr=(completed.stderr or "").strip(),
    )


def child_targets(target: Path) -> list[Path]:
    children = []
    for path in sorted(target.iterdir()):
        if path.name.startswith("__pycache__"):
            continue
        if path.is_dir():
            children.append(path)
        elif path.suffix == ".py":
            children.append(path)
    return children


def probe_tree(
    *,
    cwd: Path,
    project_dir: Path,
    python_cmd: str,
    target: Path,
    timeout_seconds: int,
    max_depth: int,
    follow_imports: str,
    depth: int = 0,
) -> list[ProbeResult]:
    results = [
        run_mypy_probe(
            cwd=cwd,
            project_dir=project_dir,
            python_cmd=python_cmd,
            target=target,
            timeout_seconds=timeout_seconds,
            follow_imports=follow_imports,
        )
    ]
    current = results[-1]
    if current.status != "timeout" or not target.is_dir() or depth >= max_depth:
        return results
    for child in child_targets(target):
        results.extend(
            probe_tree(
                cwd=cwd,
                project_dir=project_dir,
                python_cmd=python_cmd,
                target=child,
                timeout_seconds=timeout_seconds,
                max_depth=max_depth,
                follow_imports=follow_imports,
                depth=depth + 1,
            )
        )
    return results


def default_targets(package_root: Path) -> list[Path]:
    targets: list[Path] = []
    for path in sorted(package_root.iterdir()):
        if path.name.startswith("__pycache__"):
            continue
        if path.is_dir():
            targets.append(path)
    return targets


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose which mypy target is hanging.")
    parser.add_argument(
        "--project-dir",
        default=".",
        help="Python project directory relative to `/.brains`.",
    )
    parser.add_argument(
        "--package-root",
        default="brains",
        help="Source package root relative to the project directory.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=20,
        help="Per-target timeout in seconds.",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=2,
        help="How deep to recursively split timed-out directories.",
    )
    parser.add_argument(
        "--python-cmd",
        default=r".venv\Scripts\python.exe",
        help="Interpreter command to run inside the nested project.",
    )
    parser.add_argument(
        "--follow-imports",
        default="normal",
        choices=["normal", "silent", "skip", "error"],
        help="Value forwarded to mypy --follow-imports.",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Emit JSON instead of text.",
    )
    parser.add_argument(
        "targets",
        nargs="*",
        help="Optional paths relative to --project-dir. Defaults to top-level packages under --package-root.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = repo_root()
    brains_dir = brains_root()
    project_dir = (brains_dir / args.project_dir).resolve()
    package_root = (project_dir / args.package_root).resolve()

    if args.targets:
        targets = [(project_dir / raw).resolve() for raw in args.targets]
    else:
        targets = default_targets(package_root)

    all_results: list[ProbeResult] = []
    for target in targets:
        all_results.extend(
            probe_tree(
                cwd=root,
                project_dir=project_dir,
                python_cmd=args.python_cmd,
                target=target,
                timeout_seconds=args.timeout_seconds,
                max_depth=args.max_depth,
                follow_imports=args.follow_imports,
            )
        )

    if args.json_output:
        payload = {
            "project_dir": str(project_dir),
            "package_root": str(package_root),
            "results": [asdict(result) for result in all_results],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    for result in all_results:
        print(
            f"{result.status:7} {result.elapsed_seconds:7.3f}s "
            f"{result.kind:4} {result.target}"
        , flush=True)
        if result.status == "error":
            detail = result.stderr or result.stdout
            if detail:
                print(detail.strip(), flush=True)
        if result.status == "timeout":
            print("  timed out before mypy completed", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
