from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from brains.mcp.tools.notes import read_note_tool
from brains.sources.pdf.search import search_pdf_corpus
from brains.sources.vault.related import find_related_note_candidates
from brains.sources.vault.search import search_vault_knowledge


def search_vault_tool(
    *,
    query: str,
    mode: Literal["vector", "fts", "hybrid"] = "hybrid",
    reranker: Literal["none", "rrf", "cross-encoder", "ollama"] = "none",
    k: int = 5,
    fetch_k: int = 20,
    snippet_chars: int = 320,
    index_root: str | None = None,
) -> dict[str, Any]:
    return search_vault_knowledge(
        query=query,
        mode=mode,
        reranker=reranker,
        k=k,
        fetch_k=fetch_k,
        snippet_chars=snippet_chars,
        index_root=index_root,
    )


def search_pdfs_tool(
    *,
    query: str,
    mode: Literal["vector", "fts", "hybrid"] = "hybrid",
    reranker: Literal["none", "rrf", "cross-encoder", "ollama"] = "none",
    k: int = 5,
    fetch_k: int = 20,
    snippet_chars: int = 320,
    index_root: str | None = None,
) -> dict[str, Any]:
    return search_pdf_corpus(
        query=query,
        mode=mode,
        reranker=reranker,
        k=k,
        fetch_k=fetch_k,
        snippet_chars=snippet_chars,
        index_root=index_root,
    )


def find_related_notes_tool(
    *,
    path: str,
    query: str | None = None,
    branch: Literal["same", "all"] = "same",
    k: int = 5,
    fetch_k: int = 20,
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
        snippet_chars=snippet_chars,
        index_root=index_root,
    )
