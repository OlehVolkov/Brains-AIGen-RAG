from __future__ import annotations

from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import FastMCP

from brain.mcp.tools.experiments import run_experiment_tool
from brain.mcp.tools.notes import (
    create_mirror_note_tool,
    list_notes_tool,
    read_note_tool,
    validate_note_tool,
    write_note_tool,
)
from brain.mcp.tools.search import find_related_notes_tool, search_pdfs_tool, search_vault_tool
from brain.config.loader import repo_root

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
ListNotesBranch = Literal["EN", "UA", "root", "all"]
SearchMode = Literal["vector", "fts", "hybrid"]
Reranker = Literal["none", "rrf", "cross-encoder", "ollama"]
RelatedBranch = Literal["same", "all"]
WriteMode = Literal["overwrite", "append", "prepend"]


def build_mcp_server(
    *,
    name: str = "AlphaFold3 Brain MCP",
    host: str = "127.0.0.1",
    port: int = 8000,
    debug: bool = False,
    log_level: LogLevel = "INFO",
    workspace_root: Path | None = None,
) -> FastMCP:
    active_repo_root = workspace_root or repo_root()
    server = FastMCP(
        name=name,
        instructions=(
            "MCP server for the AlphaFold3 Obsidian vault. "
            "Use repository-relative markdown note paths and preserve the canonical EN/UA structure."
        ),
        host=host,
        port=port,
        debug=debug,
        log_level=log_level,
    )

    @server.tool(
        name="list_notes",
        description="List markdown notes from the canonical vault structure.",
    )
    def list_notes(
        branch: ListNotesBranch = "all",
        contains: str | None = None,
        limit: int = 200,
    ) -> dict[str, object]:
        return list_notes_tool(
            branch=branch,
            contains=contains,
            limit=limit,
            repo_root=active_repo_root,
        )

    @server.tool(
        name="read_note",
        description="Read a markdown note by repository-relative path.",
    )
    def read_note(path: str) -> dict[str, object]:
        return read_note_tool(path=path, repo_root=active_repo_root)

    @server.tool(
        name="search_vault",
        description="Search the indexed markdown vault content.",
    )
    def search_vault_mcp(
        query: str,
        mode: SearchMode = "hybrid",
        reranker: Reranker = "none",
        k: int = 5,
        fetch_k: int = 20,
        snippet_chars: int = 320,
        index_root: str | None = None,
    ) -> dict[str, object]:
        return search_vault_tool(
            query=query,
            mode=mode,
            reranker=reranker,
            k=k,
            fetch_k=fetch_k,
            snippet_chars=snippet_chars,
            index_root=index_root,
        )

    @server.tool(
        name="search_pdfs",
        description="Search the indexed PDF corpus.",
    )
    def search_pdfs_mcp(
        query: str,
        mode: SearchMode = "hybrid",
        reranker: Reranker = "none",
        k: int = 5,
        fetch_k: int = 20,
        snippet_chars: int = 320,
        index_root: str | None = None,
    ) -> dict[str, object]:
        return search_pdfs_tool(
            query=query,
            mode=mode,
            reranker=reranker,
            k=k,
            fetch_k=fetch_k,
            snippet_chars=snippet_chars,
            index_root=index_root,
        )

    @server.tool(
        name="find_related_notes",
        description="Find candidate related notes for an existing vault note.",
    )
    def find_related_notes(
        path: str,
        query: str | None = None,
        branch: RelatedBranch = "same",
        k: int = 5,
        fetch_k: int = 20,
        snippet_chars: int = 240,
        index_root: str | None = None,
    ) -> dict[str, object]:
        return find_related_notes_tool(
            path=path,
            query=query,
            branch=branch,
            k=k,
            fetch_k=fetch_k,
            snippet_chars=snippet_chars,
            index_root=index_root,
            repo_root=active_repo_root,
        )

    @server.tool(
        name="write_note",
        description="Create or update a markdown note in the canonical vault structure.",
    )
    def write_note(
        path: str,
        content: str,
        mode: WriteMode = "overwrite",
        create: bool = False,
    ) -> dict[str, object]:
        return write_note_tool(
            path=path,
            content=content,
            mode=mode,
            create=create,
            repo_root=active_repo_root,
        )

    @server.tool(
        name="create_mirror_note",
        description="Create the EN/UA mirror note for an existing source note at an explicit target path.",
    )
    def create_mirror_note(
        source_path: str,
        target_path: str,
        overwrite: bool = False,
    ) -> dict[str, object]:
        return create_mirror_note_tool(
            source_path=source_path,
            target_path=target_path,
            overwrite=overwrite,
            repo_root=active_repo_root,
        )

    @server.tool(
        name="validate_note",
        description="Validate a markdown note for frontmatter, title, breadcrumb, and mirror-link basics.",
    )
    def validate_note(path: str) -> dict[str, object]:
        return validate_note_tool(path=path, repo_root=active_repo_root)

    @server.tool(
        name="run_experiment",
        description="Run a reproducible local research experiment using the think loop and save an artifact.",
    )
    def run_experiment(
        name: str,
        query: str,
        description: str | None = None,
        save_memory: bool = True,
        vault_k: int | None = None,
        pdf_k: int | None = None,
        reflection_rounds: int | None = None,
    ) -> dict[str, object]:
        return run_experiment_tool(
            name=name,
            query=query,
            description=description,
            save_memory=save_memory,
            vault_k=vault_k,
            pdf_k=pdf_k,
            reflection_rounds=reflection_rounds,
            repo_root=active_repo_root,
        )

    return server
