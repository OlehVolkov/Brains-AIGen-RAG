from __future__ import annotations

from typing import Any, Literal

from brains.sources.graph.search import explain_graph_path_knowledge
from brains.sources.vault.markdown import strip_frontmatter
from brains.sources.vault.search import search_vault_knowledge


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
    graph_max_hops: int | None = None,
    snippet_chars: int = 240,
    index_root: str | None = None,
) -> dict[str, Any]:
    search_query = query or f"{note_title}\n\n{strip_frontmatter(note_content)}"
    search_payload = search_vault_knowledge(
        query=search_query,
        mode="hybrid-graph",
        k=max(k, 1),
        fetch_k=max(fetch_k, k),
        graph_max_hops=graph_max_hops,
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

    graph_warnings: list[str] = []
    for row in related:
        try:
            graph_payload = explain_graph_path_knowledge(
                source=note_path,
                target=str(row.get("source_path", "")),
                max_hops=graph_max_hops if graph_max_hops is not None else 2,
            )
        except FileNotFoundError:
            graph_warnings.append("Graph artifacts not found; related-note graph evidence unavailable.")
            break
        except Exception as exc:
            graph_warnings.append(
                f"related-note graph evidence unavailable ({type(exc).__name__}: {exc})."
            )
            break
        if graph_payload.get("path_found"):
            row["graph_evidence"] = list(graph_payload.get("summary", []))[:3]
            row["graph_hops"] = graph_payload.get("hops")
    return {
        "path": note_path,
        "query": query,
        "branch_filter": branch,
        "results": related,
        "warnings": [*search_payload.get("warnings", []), *graph_warnings],
    }
