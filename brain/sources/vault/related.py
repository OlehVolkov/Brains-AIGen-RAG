from __future__ import annotations

from typing import Any, Literal

from brain.sources.vault.markdown import strip_frontmatter
from brain.sources.vault.search import search_vault_knowledge


def find_related_note_candidates(
    *,
    note_path: str,
    note_title: str,
    note_content: str,
    note_branch: str,
    query: str | None = None,
    branch: Literal["same", "all"] = "same",
    k: int = 5,
    fetch_k: int = 20,
    snippet_chars: int = 240,
    index_root: str | None = None,
) -> dict[str, Any]:
    search_query = query or f"{note_title}\n\n{strip_frontmatter(note_content)}"
    search_payload = search_vault_knowledge(
        query=search_query,
        k=max(k, 1),
        fetch_k=max(fetch_k, k),
        snippet_chars=snippet_chars,
        index_root=index_root,
    )
    related: list[dict[str, Any]] = []
    for row in search_payload.get("results", []):
        if row.get("source_path") == note_path:
            continue
        if branch == "same" and note_branch in {"EN", "UA"} and row.get("language_branch") != note_branch:
            continue
        related.append(row)
        if len(related) >= k:
            break
    return {
        "path": note_path,
        "query": query,
        "branch_filter": branch,
        "results": related,
        "warnings": search_payload.get("warnings", []),
    }
