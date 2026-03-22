from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from brains.config.loader import repo_root as default_repo_root
from brains.sources.vault.markdown import detect_language_branch, list_markdown_paths, strip_frontmatter


EXCLUDED_ROOTS = {".brains", ".git", ".obsidian", ".smart-env", "PDF"}
WRITE_MODES = {"overwrite", "append", "prepend"}
REQUIRED_FRONTMATTER_KEYS = {"cssclasses", "tags"}


@dataclass(frozen=True)
class ResolvedNotePath:
    relative_path: str
    absolute_path: Path


def _normalize_relative_note_path(raw_path: str) -> PurePosixPath:
    if not raw_path.strip():
        raise ValueError("Note path must not be empty.")

    note_path = PurePosixPath(raw_path)
    if note_path.is_absolute():
        raise ValueError("Note path must be repository-relative, not absolute.")
    if ".." in note_path.parts:
        raise ValueError("Note path must not escape the repository root.")
    if note_path.suffix.lower() != ".md":
        raise ValueError("Note path must point to a markdown file.")
    if not note_path.parts:
        raise ValueError("Note path must not be empty.")
    if note_path.parts[0] in EXCLUDED_ROOTS:
        raise ValueError("Note path points into an excluded repository area.")
    return note_path


def _resolve_note_path(
    raw_path: str,
    *,
    repo_root: Path,
    allow_create: bool,
) -> ResolvedNotePath:
    note_path = _normalize_relative_note_path(raw_path)
    absolute_path = (repo_root / note_path).resolve()
    resolved_repo_root = repo_root.resolve()
    if not absolute_path.is_relative_to(resolved_repo_root):
        raise ValueError("Resolved note path escaped the repository root.")

    if absolute_path.exists():
        if not absolute_path.is_file():
            raise ValueError("Resolved note path is not a regular file.")
        return ResolvedNotePath(
            relative_path=absolute_path.relative_to(repo_root).as_posix(),
            absolute_path=absolute_path,
        )

    if not allow_create:
        raise FileNotFoundError(f"Note does not exist: {note_path.as_posix()}")

    if note_path.parts[0] not in {"EN", "UA"}:
        raise ValueError("New notes may only be created under EN/ or UA/.")

    return ResolvedNotePath(relative_path=note_path.as_posix(), absolute_path=absolute_path)


def _extract_title(markdown_text: str, *, fallback: str) -> str:
    body = strip_frontmatter(markdown_text)
    match = re.search(r"(?m)^#\s+(.+?)\s*$", body)
    return match.group(1).strip() if match else fallback


def _frontmatter_lines(markdown_text: str) -> list[str]:
    if not markdown_text.startswith("---\n"):
        return []
    parts = markdown_text.split("\n---\n", 1)
    if len(parts) != 2:
        return []
    return [line.rstrip() for line in parts[0].splitlines()[1:] if line.strip()]


def _has_frontmatter_key(markdown_text: str, key: str) -> bool:
    pattern = re.compile(rf"(?m)^{re.escape(key)}\s*:")
    return bool(pattern.search("\n".join(_frontmatter_lines(markdown_text))))


def _language_label(branch: str) -> str:
    if branch == "EN":
        return "English"
    if branch == "UA":
        return "Українська"
    return "root"


def _mirror_breadcrumb_line(source_branch: str, source_path: str) -> str:
    label = _language_label(source_branch)
    icon = "🇬🇧" if source_branch == "EN" else "🇺🇦" if source_branch == "UA" else "🌐"
    return f"{icon} [[{source_path}|{label}]]"


def _render_mirror_content(
    source_content: str,
    *,
    source_path: str,
    source_branch: str,
) -> str:
    lines = source_content.splitlines()
    counterpart_line = _mirror_breadcrumb_line(source_branch, source_path)
    if len(lines) >= 3 and lines[0].startswith("# ") and lines[2].startswith(("🇺🇦 [[", "🇬🇧 [[", "🌐 [[")):
        lines[2] = counterpart_line
        rendered = "\n".join(lines)
    else:
        rendered = source_content
        if not rendered.endswith("\n"):
            rendered += "\n"
        rendered += f"\n{counterpart_line}\n"
    return rendered if rendered.endswith("\n") else f"{rendered}\n"


def _target_branch_for_mirror(source_branch: str) -> str:
    if source_branch == "EN":
        return "UA"
    if source_branch == "UA":
        return "EN"
    raise ValueError("Mirror notes can only be created from EN/ or UA/ notes.")


def list_notes_tool(
    *,
    branch: Literal["EN", "UA", "root", "all"] = "all",
    contains: str | None = None,
    limit: int = 200,
    repo_root: Path | None = None,
) -> dict[str, object]:
    if limit <= 0:
        raise ValueError("limit must be positive.")

    base_repo_root = repo_root or default_repo_root()
    results: list[dict[str, str]] = []
    needle = contains.casefold() if contains else None

    for markdown_path in list_markdown_paths(base_repo_root):
        relative_path = markdown_path.relative_to(base_repo_root).as_posix()
        language_branch = detect_language_branch(relative_path)
        if branch != "all" and language_branch != branch:
            continue

        title = _extract_title(
            markdown_path.read_text(encoding="utf-8"),
            fallback=markdown_path.stem,
        )
        if needle:
            haystack = f"{relative_path}\n{title}".casefold()
            if needle not in haystack:
                continue

        results.append(
            {
                "path": relative_path,
                "title": title,
                "language_branch": language_branch,
            }
        )
        if len(results) >= limit:
            break

    return {
        "count": len(results),
        "branch": branch,
        "contains": contains,
        "notes": results,
    }


def read_note_tool(
    *,
    path: str,
    repo_root: Path | None = None,
) -> dict[str, object]:
    base_repo_root = repo_root or default_repo_root()
    resolved = _resolve_note_path(path, repo_root=base_repo_root, allow_create=False)
    content = resolved.absolute_path.read_text(encoding="utf-8")
    return {
        "path": resolved.relative_path,
        "title": _extract_title(content, fallback=resolved.absolute_path.stem),
        "language_branch": detect_language_branch(resolved.relative_path),
        "content": content,
    }


def write_note_tool(
    *,
    path: str,
    content: str,
    mode: Literal["overwrite", "append", "prepend"] = "overwrite",
    create: bool = False,
    repo_root: Path | None = None,
) -> dict[str, object]:
    if mode not in WRITE_MODES:
        raise ValueError(f"Unsupported write mode: {mode}")

    base_repo_root = repo_root or default_repo_root()
    resolved = _resolve_note_path(path, repo_root=base_repo_root, allow_create=create)
    existed_before = resolved.absolute_path.exists()
    original = resolved.absolute_path.read_text(encoding="utf-8") if existed_before else ""

    resolved.absolute_path.parent.mkdir(parents=True, exist_ok=True)
    normalized_content = content if content.endswith("\n") else f"{content}\n"
    if mode == "overwrite":
        rendered = normalized_content
    elif mode == "append":
        separator = "" if not original or original.endswith("\n") else "\n"
        rendered = f"{original}{separator}{normalized_content}"
    else:
        rendered = f"{normalized_content}{original}"

    resolved.absolute_path.write_text(rendered, encoding="utf-8")
    return {
        "path": resolved.relative_path,
        "mode": mode,
        "created": not existed_before,
        "language_branch": detect_language_branch(resolved.relative_path),
        "title": _extract_title(rendered, fallback=resolved.absolute_path.stem),
        "bytes_written": len(rendered.encode("utf-8")),
    }


def create_mirror_note_tool(
    *,
    source_path: str,
    target_path: str,
    overwrite: bool = False,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    source_payload = read_note_tool(path=source_path, repo_root=repo_root)
    source_branch = str(source_payload["language_branch"])
    target_branch = _target_branch_for_mirror(source_branch)
    target_resolved = _resolve_note_path(
        target_path,
        repo_root=repo_root or default_repo_root(),
        allow_create=True,
    )
    actual_target_branch = detect_language_branch(target_resolved.relative_path)
    if actual_target_branch != target_branch:
        raise ValueError(
            f"Mirror target must live under {target_branch}/ for a source note in {source_branch}/."
        )
    if target_resolved.absolute_path.exists() and not overwrite:
        raise FileExistsError(f"Mirror note already exists: {target_resolved.relative_path}")

    mirror_content = _render_mirror_content(
        str(source_payload["content"]),
        source_path=str(source_payload["path"]),
        source_branch=source_branch,
    )
    write_payload = write_note_tool(
        path=target_resolved.relative_path,
        content=mirror_content,
        mode="overwrite",
        create=True,
        repo_root=repo_root,
    )
    return {
        "source_path": source_payload["path"],
        "target_path": target_resolved.relative_path,
        "source_branch": source_branch,
        "target_branch": target_branch,
        "created": write_payload["created"],
        "bytes_written": write_payload["bytes_written"],
    }


def validate_note_tool(
    *,
    path: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    note_payload = read_note_tool(path=path, repo_root=repo_root)
    content = str(note_payload["content"])
    branch = str(note_payload["language_branch"])
    issues: list[dict[str, str]] = []

    if not content.startswith("---\n"):
        issues.append({"code": "missing_frontmatter", "message": "Frontmatter block is missing."})
    else:
        for key in REQUIRED_FRONTMATTER_KEYS:
            if not _has_frontmatter_key(content, key):
                issues.append(
                    {
                        "code": f"missing_frontmatter_{key}",
                        "message": f"Frontmatter key '{key}' is missing.",
                    }
                )

    if not re.search(r"(?m)^#\s+.+$", strip_frontmatter(content)):
        issues.append({"code": "missing_title", "message": "Top-level markdown title is missing."})

    content_lines = [line.strip() for line in content.splitlines()]
    body_lines = [line for line in content_lines if line]
    breadcrumb = body_lines[1] if len(body_lines) > 1 else ""
    if branch == "EN" and "[[Home" not in breadcrumb:
        issues.append({"code": "missing_breadcrumb", "message": "EN note is missing a Home breadcrumb."})
    if branch == "UA" and "[[UA/Головна" not in breadcrumb:
        issues.append(
            {"code": "missing_breadcrumb", "message": "UA note is missing a UA/Головна breadcrumb."}
        )
    if branch == "root" and "[[Home" not in breadcrumb and "[[UA/Головна" not in breadcrumb:
        issues.append(
            {"code": "missing_breadcrumb", "message": "Root note is missing a recognizable breadcrumb."}
        )

    if branch in {"EN", "UA"}:
        counterpart_marker = "🇺🇦 [[" if branch == "EN" else "🇬🇧 [["
        if counterpart_marker not in content:
            issues.append(
                {
                    "code": "missing_counterpart_link",
                    "message": "Mirror-language link is missing from the note header.",
                }
            )

    return {
        "path": note_payload["path"],
        "language_branch": branch,
        "title": note_payload["title"],
        "valid": not issues,
        "issue_count": len(issues),
        "issues": issues,
    }
