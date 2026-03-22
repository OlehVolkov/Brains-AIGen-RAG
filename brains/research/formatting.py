from __future__ import annotations

from typing import Sequence


def _render_hits(title: str, rows: Sequence[dict]) -> list[str]:
    lines = [title]
    if not rows:
        lines.append("- none")
        return lines
    for row in rows:
        source_path = row.get("source_path", row.get("session_id", "?"))
        rendered = row.get("snippet") or row.get("summary") or ""
        lines.append(f"- {source_path}: {rendered}")
    return lines


def format_think_report(payload: dict) -> str:
    lines: list[str] = [
        f"# Session {payload['session_id']}",
        "",
        f"Query: {payload['query']}",
        "",
    ]
    warnings = payload.get("warnings", [])
    if warnings:
        lines.append("## Warnings")
        lines.extend(f"- {warning}" for warning in warnings)
        lines.append("")

    lines.append("## Retrieved Context")
    lines.extend(_render_hits("### Vault", payload.get("vault_results", [])))
    lines.append("")
    lines.extend(_render_hits("### PDF", payload.get("pdf_results", [])))
    lines.append("")
    lines.extend(_render_hits("### Memory", payload.get("memory_results", [])))
    lines.append("")

    for role_name in ("researcher", "coder", "reviewer"):
        role_payload = payload["roles"].get(role_name, {})
        lines.append(f"## {role_name.title()}")
        lines.append(role_payload.get("content", ""))
        lines.append("")

    reflections = payload.get("reflections", [])
    if reflections:
        lines.append("## Reflections")
        for index, reflection in enumerate(reflections, start=1):
            lines.append(f"### Reflection {index}")
            lines.append(reflection)
            lines.append("")

    lines.append("## Final Answer")
    lines.append(payload.get("final_answer", ""))
    return "\n".join(lines).rstrip()
