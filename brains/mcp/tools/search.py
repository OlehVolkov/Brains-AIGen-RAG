from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from brains.mcp.tools.notes import read_note_tool
from brains.sources.graph.search import explain_graph_path_knowledge, search_graph_knowledge
from brains.sources.pdf.search import search_pdf_corpus
from brains.sources.vault.related import find_related_note_candidates
from brains.sources.vault.search import search_vault_knowledge


def search_vault_tool(
    *,
    query: str,
    mode: Literal["auto", "vector", "fts", "hybrid", "hybrid-graph"] = "hybrid",
    reranker: Literal["none", "rrf", "cross-encoder", "ollama"] = "none",
    k: int = 5,
    fetch_k: int = 20,
    graph_max_hops: int | None = None,
    min_score: float | None = None,
    max_distance: float | None = None,
    snippet_chars: int = 320,
    index_root: str | None = None,
) -> dict[str, Any]:
    return search_vault_knowledge(
        query=query,
        mode=mode,
        reranker=reranker,
        k=k,
        fetch_k=fetch_k,
        graph_max_hops=graph_max_hops,
        min_score=min_score,
        max_distance=max_distance,
        snippet_chars=snippet_chars,
        index_root=index_root,
    )


def search_pdfs_tool(
    *,
    query: str,
    mode: Literal["auto", "vector", "fts", "hybrid"] = "hybrid",
    reranker: Literal["none", "rrf", "cross-encoder", "ollama"] = "none",
    k: int = 5,
    fetch_k: int = 20,
    min_score: float | None = None,
    max_distance: float | None = None,
    snippet_chars: int = 320,
    index_root: str | None = None,
) -> dict[str, Any]:
    return search_pdf_corpus(
        query=query,
        mode=mode,
        reranker=reranker,
        k=k,
        fetch_k=fetch_k,
        min_score=min_score,
        max_distance=max_distance,
        snippet_chars=snippet_chars,
        index_root=index_root,
    )


def search_graph_tool(
    *,
    query: str,
    k: int = 5,
    max_hops: int = 1,
    index_root: str | None = None,
    graph_file: str | None = None,
) -> dict[str, Any]:
    return search_graph_knowledge(
        query=query,
        k=k,
        max_hops=max_hops,
        index_root=index_root,
        graph_file=graph_file,
    )


def explain_path_tool(
    *,
    source: str,
    target: str,
    max_hops: int = 3,
    index_root: str | None = None,
    graph_file: str | None = None,
) -> dict[str, Any]:
    return explain_graph_path_knowledge(
        source=source,
        target=target,
        max_hops=max_hops,
        index_root=index_root,
        graph_file=graph_file,
    )


def find_related_notes_tool(
    *,
    path: str,
    query: str | None = None,
    branch: Literal["same", "all"] = "same",
    k: int = 5,
    fetch_k: int = 20,
    graph_max_hops: int | None = None,
    snippet_chars: int = 240,
    index_root: str | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    note_payload = read_note_tool(path=path, repo_root=repo_root)
    return find_related_note_candidates(
        note_path=str(note_payload["path"]),
        note_title=str(note_payload["title"]),
        note_content=str(note_payload["content"]),
        note_branch=str(note_payload["language_branch"]),
        query=query,
        branch=branch,
        k=k,
        fetch_k=fetch_k,
        graph_max_hops=graph_max_hops,
        snippet_chars=snippet_chars,
        index_root=index_root,
    )
