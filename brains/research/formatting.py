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
    lines.extend(_render_hits("### Graph", payload.get("graph_results", [])))
    lines.append("")
    graph_paths = payload.get("graph_paths", [])
    lines.append("### Graph Paths")
    if not graph_paths:
        lines.append("- none")
    else:
        for row in graph_paths:
            lines.append(
                "- "
                f"{row.get('resolved_source_path')} -> {row.get('resolved_target_path')} "
                f"(hops={row.get('hops')})"
            )
            for step in row.get("summary", [])[:3]:
                lines.append(f"  {step}")
    lines.append("")
    lines.extend(_render_hits("### PDF", payload.get("pdf_results", [])))
    lines.append("")
    lines.extend(_render_hits("### Memory", payload.get("memory_results", [])))
    lines.append("")
    lines.append("## Summary")
    lines.append(payload.get("summary", payload.get("final_answer", "")))
    lines.append("")
    lines.append("## Agent Handoff")
    lines.append(payload.get("agent_handoff", ""))
    return "\n".join(lines).rstrip()
