from __future__ import annotations

import asyncio
from pathlib import Path

from typer.testing import CliRunner

from brains import cli
from brains.commands import graph as graph_commands
from brains.commands import health as health_commands
from brains.commands import mcp as mcp_commands
from brains.commands import pdf as pdf_commands
from brains.commands import research as research_commands
from brains.commands import tasks as task_commands
from brains.commands import vault as vault_commands
from brains.config import BrainsPaths, GraphPaths, ResearchPaths
from brains.mcp import (
    create_mirror_note_tool,
    list_notes_tool,
    read_note_tool,
    validate_note_tool,
    write_note_tool,
)
from brains.mcp.server import build_mcp_server


def make_dummy_paths() -> BrainsPaths:
    repo_root = Path("/tmp/repo")
    brains_root = repo_root / ".brains"
    index_root = brains_root / ".index" / "dummy"
    return BrainsPaths(
        repo_root=repo_root,
        brains_root=brains_root,
        pdf_dir=repo_root / "PDF",
        index_root=index_root,
        db_uri=index_root / "lancedb",
        manifest_path=index_root / "manifest.json",
        table_name="dummy_table",
    )


def make_dummy_graph_paths() -> GraphPaths:
    repo_root = Path("/tmp/repo")
    brains_root = repo_root / ".brains"
    index_root = brains_root / ".index" / "graph_search"
    return GraphPaths(
        repo_root=repo_root,
        brains_root=brains_root,
        index_root=index_root,
        graph_path=index_root / "graph.json",
        manifest_path=index_root / "manifest.json",
    )


def make_dummy_research_paths() -> ResearchPaths:
    repo_root = Path("/tmp/repo")
    brains_root = repo_root / ".brains"
    index_root = brains_root / ".index" / "research"
    return ResearchPaths(
        repo_root=repo_root,
        brains_root=brains_root,
        index_root=index_root,
        memory_path=index_root / "memory.jsonl",
        sessions_dir=index_root / "sessions",
    )


def make_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    (repo_root / "EN" / "3. Models").mkdir(parents=True)
    (repo_root / "UA").mkdir(parents=True)
    (repo_root / ".brains" / ".index" / "research").mkdir(parents=True)
    (repo_root / "Home.md").write_text("# Home\n\nRoot page.\n", encoding="utf-8")
    (repo_root / "EN" / "3. Models" / "3.7. Boltz-1.md").write_text(
        "# Boltz-1\n\nOpen model note.\n",
        encoding="utf-8",
    )
    (repo_root / "UA" / "Індекс.md").write_text(
        "# Індекс\n\nНавігація.\n",
        encoding="utf-8",
    )
    return repo_root


def test_extended_cli_smoke(monkeypatch) -> None:
    class DummyServer:
        def __init__(self) -> None:
            self.transport: str | None = None

        def run(self, *, transport: str) -> None:
            self.transport = transport

    dummy_server = DummyServer()

    monkeypatch.setattr(pdf_commands, "resolve_pdf_paths", lambda **_: make_dummy_paths())
    monkeypatch.setattr(
        pdf_commands,
        "index_pdfs",
        lambda config: {
            "status": "ok",
            "table_name": config.paths.table_name,
            "active_index_pointer": None,
        },
    )
    monkeypatch.setattr(
        pdf_commands,
        "search_pdfs",
        lambda config: {
            "results": [
                {
                    "rank": 1,
                    "source_path": "PDF/demo.pdf",
                    "page_label": "1",
                    "chunk_index": 0,
                    "snippet": f"pdf result for {config.query}",
                }
            ],
            "warnings": [],
            "effective_mode": config.mode,
            "effective_reranker": config.reranker,
        },
    )
    monkeypatch.setattr(
        pdf_commands,
        "fetch_pdfs_from_notes",
        lambda *_, **__: {
            "downloaded_count": 1,
            "results": [{"url": "https://example.invalid/paper.pdf", "status": "downloaded"}],
            "manifest_path": "/tmp/repo/.brains/.index/dummy/fetch_manifest.json",
        },
    )

    monkeypatch.setattr(vault_commands, "resolve_vault_paths", lambda **_: make_dummy_paths())
    monkeypatch.setattr(
        vault_commands,
        "index_vault",
        lambda config: {
            "status": "ok",
            "table_name": config.paths.table_name,
            "active_index_pointer": None,
        },
    )
    monkeypatch.setattr(
        vault_commands,
        "search_vault",
        lambda config: {
            "results": [
                {
                    "rank": 1,
                    "source_path": "EN/3. Models/3.7. Boltz-1.md",
                    "language_branch": "EN",
                    "section": "Boltz-1",
                    "chunk_index": 0,
                    "snippet": f"vault result for {config.query}",
                }
            ],
            "warnings": [],
            "effective_mode": config.mode,
            "effective_reranker": config.reranker,
        },
    )

    monkeypatch.setattr(graph_commands, "resolve_graph_paths", lambda **_: make_dummy_graph_paths())
    monkeypatch.setattr(
        graph_commands,
        "index_graph",
        lambda config: {
            "status": "ok",
            "graph_path": str(config.paths.graph_path),
            "node_count": 3,
            "edge_count": 2,
        },
    )
    monkeypatch.setattr(
        graph_commands,
        "search_graph",
        lambda config: {
            "results": [
                {
                    "rank": 1,
                    "source_path": "EN/3. Models/3.7. Boltz-1.md",
                    "language_branch": "EN",
                    "score": 9.0,
                    "snippet": f"graph result for {config.query}",
                    "evidence": ["matched node"],
                }
            ],
            "warnings": [],
        },
    )
    monkeypatch.setattr(
        graph_commands,
        "explain_graph_path",
        lambda config: {
            "path_found": True,
            "resolved_source_path": config.source,
            "resolved_target_path": config.target,
            "hops": 1,
            "total_weight": 1.0,
            "summary": [f"{config.source} -> {config.target}"],
            "warnings": [],
        },
    )

    monkeypatch.setattr(health_commands, "resolve_pdf_paths", lambda **_: make_dummy_paths())
    monkeypatch.setattr(health_commands, "resolve_vault_paths", lambda **_: make_dummy_paths())
    monkeypatch.setattr(
        health_commands,
        "check_index_health",
        lambda paths, **kwargs: {
            "status": "ok",
            "table_name": paths.table_name,
            "probe_query": kwargs["probe_query"],
        },
    )

    monkeypatch.setattr(research_commands, "resolve_research_paths", lambda **_: make_dummy_research_paths())
    monkeypatch.setattr(
        research_commands,
        "run_think_loop",
        lambda config: {
            "session_id": config.session_id or "smoke-session",
            "query": config.query,
            "summary": "smoke summary",
            "agent_handoff": "smoke handoff",
            "warnings": [],
            "vault_results": [],
            "graph_results": [],
            "graph_paths": [],
            "pdf_results": [],
            "memory_results": [],
        },
    )

    monkeypatch.setattr(mcp_commands, "build_mcp_server", lambda **_: dummy_server)

    monkeypatch.setattr(
        task_commands,
        "enqueue_cli_job",
        lambda command, *, label=None: {
            "job_id": "smoke-job",
            "status": "queued",
            "label": label,
            "command": command,
            "stdout_path": ".brains/.cache/huey/jobs/smoke-job/stdout.txt",
            "stderr_path": ".brains/.cache/huey/jobs/smoke-job/stderr.txt",
            "returncode": None,
            "error": None,
        },
    )
    monkeypatch.setattr(
        task_commands,
        "load_job_record",
        lambda job_id: {
            "job_id": job_id,
            "status": "succeeded",
            "label": "smoke",
            "command": ["index-vault"],
            "stdout_path": ".brains/.cache/huey/jobs/smoke-job/stdout.txt",
            "stderr_path": ".brains/.cache/huey/jobs/smoke-job/stderr.txt",
            "returncode": 0,
            "error": None,
        },
    )
    monkeypatch.setattr(
        task_commands,
        "list_job_records",
        lambda *, limit: [
            {
                "job_id": "smoke-job",
                "status": "succeeded",
                "label": "smoke",
                "command": ["index-vault"],
            }
        ][:limit],
    )
    monkeypatch.setattr(task_commands, "get_job_output", lambda *_args, **_kwargs: "smoke output")

    runner = CliRunner()

    invocations = [
        (["index", "--json-output"], '"status": "ok"'),
        (["search", "ligand binding"], "pdf result for ligand binding"),
        (["fetch-pdfs", "--json-output"], '"downloaded_count": 1'),
        (["index-vault", "--json-output"], '"status": "ok"'),
        (["search-vault", "pairformer"], "vault result for pairformer"),
        (["index-graph", "--json-output"], '"node_count": 3'),
        (["search-graph", "boltz"], "graph result for boltz"),
        (["explain-path", "Boltz-1", "Home"], "Boltz-1 -> Home"),
        (["check-index", "--target", "pdf", "--json-output"], '"probe_query": "pairformer"'),
        (["check-index", "--target", "vault", "--json-output"], '"probe_query": "pairformer"'),
        (["think", "compare models", "--json-output"], '"summary": "smoke summary"'),
        (["tasks", "enqueue", "--label", "smoke", "--json-output", "index-vault"], '"job_id": "smoke-job"'),
        (["tasks", "status", "smoke-job", "--json-output"], '"status": "succeeded"'),
        (["tasks", "list", "--json-output"], '"job_id": "smoke-job"'),
        (["tasks", "output", "smoke-job", "--stream", "stdout"], "smoke output"),
    ]

    for argv, expected in invocations:
        result = runner.invoke(cli.main, argv)
        assert result.exit_code == 0, f"{argv} failed: {result.output}"
        assert expected in result.output, f"{argv} missing {expected!r}: {result.output}"

    mcp_result = runner.invoke(cli.main, ["mcp", "--transport", "stdio"])
    assert mcp_result.exit_code == 0
    assert dummy_server.transport == "stdio"


def test_extended_mcp_smoke(tmp_path: Path) -> None:
    repo_root = make_repo(tmp_path)

    listed = list_notes_tool(branch="all", repo_root=repo_root)
    assert listed["count"] >= 2

    read_payload = read_note_tool(path="EN/3. Models/3.7. Boltz-1.md", repo_root=repo_root)
    assert read_payload["title"] == "Boltz-1"

    write_payload = write_note_tool(
        path="EN/3. Models/3.8. Smoke Model.md",
        content="# Smoke Model\n\nDraft note.\n",
        mode="overwrite",
        create=True,
        repo_root=repo_root,
    )
    assert write_payload["created"] is True

    mirror_payload = create_mirror_note_tool(
        source_path="EN/3. Models/3.8. Smoke Model.md",
        target_path="UA/3. Моделі/3.8. Smoke Model.md",
        repo_root=repo_root,
    )
    assert mirror_payload["target_path"] == "UA/3. Моделі/3.8. Smoke Model.md"

    validation = validate_note_tool(path="EN/3. Models/3.8. Smoke Model.md", repo_root=repo_root)
    assert validation["path"] == "EN/3. Models/3.8. Smoke Model.md"
    assert validation["valid"] is False

    server = build_mcp_server(workspace_root=repo_root)
    tool_names = sorted(tool.name for tool in asyncio.run(server.list_tools()))
    assert tool_names == [
        "create_mirror_note",
        "explain_path",
        "find_related_notes",
        "list_notes",
        "read_note",
        "run_experiment",
        "search_graph",
        "search_pdfs",
        "search_vault",
        "validate_note",
        "write_note",
    ]
