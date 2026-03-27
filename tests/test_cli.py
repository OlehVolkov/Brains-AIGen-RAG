from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from brains import cli
from brains.commands import graph as graph_commands
from brains.commands import health as health_commands
from brains.commands import pdf as pdf_commands
from brains.commands import research as research_commands
from brains.commands import tasks as task_commands
from brains.commands import vault as vault_commands
from brains.config import BrainsPaths, GraphPaths, ResearchPaths


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


def test_main_help_shows_commands() -> None:
    runner = CliRunner()
    result = runner.invoke(cli.main, ["--help"])
    assert result.exit_code == 0
    assert "index" in result.output
    assert "index-graph" in result.output
    assert "check-index" in result.output
    assert "fetch-pdfs" in result.output
    assert "mcp" in result.output
    assert "search" in result.output
    assert "explain-path" in result.output
    assert "search-graph" in result.output
    assert "think" in result.output
    assert "tasks" in result.output
    assert "index-vault" in result.output
    assert "search-vault" in result.output


def test_index_command_json_output(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_paths(**kwargs):
        captured["resolve_kwargs"] = kwargs
        return make_dummy_paths()

    def fake_index_pdfs(config):
        captured["config"] = config
        return {"status": "ok", "parser": config.parser, "active_index_pointer": None}

    monkeypatch.setattr(pdf_commands, "resolve_pdf_paths", fake_resolve_paths)
    monkeypatch.setattr(pdf_commands, "index_pdfs", fake_index_pdfs)

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        [
            "index",
            "--pdf-dir",
            "PDF",
            "--parser",
            "pdfplumber",
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload == {
        "status": "ok",
        "parser": "pdfplumber",
        "active_index_pointer": None,
    }
    assert captured["resolve_kwargs"] == {
        "pdf_dir": "PDF",
        "index_root": None,
        "table_name": "scientific_pdf_chunks",
    }
    assert captured["config"].parser == "pdfplumber"


def test_search_command_text_output(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_paths(**kwargs):
        captured["resolve_kwargs"] = kwargs
        return make_dummy_paths()

    def fake_search_pdfs(config):
        captured["config"] = config
        return {
            "results": [
                {
                    "rank": 1,
                    "source_path": "PDF/paper.pdf",
                    "page_label": "2",
                    "chunk_index": 3,
                    "snippet": "knowledge retrieval snippet",
                }
            ],
            "warnings": ["fallback used"],
            "effective_mode": "fts",
            "effective_reranker": "none",
        }

    monkeypatch.setattr(pdf_commands, "resolve_pdf_paths", fake_resolve_paths)
    monkeypatch.setattr(pdf_commands, "search_pdfs", fake_search_pdfs)

    runner = CliRunner()
    result = runner.invoke(cli.main, ["search", "knowledge retrieval", "--mode", "hybrid"])

    assert result.exit_code == 0
    assert "Fallbacks:" in result.output
    assert "PDF/paper.pdf" in result.output
    assert "knowledge retrieval snippet" in result.output
    assert captured["config"].query == "knowledge retrieval"
    assert captured["config"].mode == "hybrid"


def test_search_command_forwards_auto_mode_and_thresholds(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_paths(**kwargs):
        return make_dummy_paths()

    def fake_search_pdfs(config):
        captured["config"] = config
        return {
            "results": [],
            "warnings": [],
            "effective_mode": "fts",
            "effective_reranker": "none",
        }

    monkeypatch.setattr(pdf_commands, "resolve_pdf_paths", fake_resolve_paths)
    monkeypatch.setattr(pdf_commands, "search_pdfs", fake_search_pdfs)

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        [
            "search",
            "GraphRAG.pdf",
            "--mode",
            "auto",
            "--min-score",
            "0.4",
            "--max-distance",
            "0.8",
        ],
    )

    assert result.exit_code == 0
    assert captured["config"].mode == "auto"
    assert captured["config"].min_score == 0.4
    assert captured["config"].max_distance == 0.8


def test_fetch_pdfs_command_json_output(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_paths(**kwargs):
        captured["resolve_kwargs"] = kwargs
        return make_dummy_paths()

    def fake_fetch_pdfs_from_notes(paths, **kwargs):
        captured["fetch_kwargs"] = kwargs
        return {
            "downloaded_count": 1,
            "results": [],
            "manifest_path": "/tmp/repo/.brains/.index/dummy/fetch_manifest.json",
        }

    def fake_index_pdfs(config):
        captured["index_config"] = config
        return {"status": "reindexed"}

    monkeypatch.setattr(pdf_commands, "resolve_pdf_paths", fake_resolve_paths)
    monkeypatch.setattr(pdf_commands, "fetch_pdfs_from_notes", fake_fetch_pdfs_from_notes)
    monkeypatch.setattr(pdf_commands, "index_pdfs", fake_index_pdfs)

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        [
            "fetch-pdfs",
            "--notes-glob",
            "EN/Literature and Priorities.md",
            "--dry-run",
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["downloaded_count"] == 1
    assert captured["resolve_kwargs"] == {
        "pdf_dir": None,
        "index_root": None,
        "table_name": "scientific_pdf_chunks",
    }
    assert captured["fetch_kwargs"] == {
        "note_globs": ["EN/Literature and Priorities.md"],
        "limit": None,
        "dry_run": True,
        "timeout": 20,
    }
    assert "index_config" not in captured


def test_index_vault_command_json_output(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_vault_paths(**kwargs):
        captured["resolve_kwargs"] = kwargs
        return make_dummy_paths()

    def fake_index_vault(config):
        captured["config"] = config
        return {
            "status": "ok",
            "table_name": "vault_markdown_chunks",
            "active_index_pointer": None,
        }

    monkeypatch.setattr(vault_commands, "resolve_vault_paths", fake_resolve_vault_paths)
    monkeypatch.setattr(vault_commands, "index_vault", fake_index_vault)

    runner = CliRunner()
    result = runner.invoke(cli.main, ["index-vault", "--json-output"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["active_index_pointer"] is None
    assert captured["resolve_kwargs"] == {
        "index_root": None,
        "table_name": "vault_markdown_chunks",
    }


def test_index_vault_command_forwards_parser(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_vault_paths(**kwargs):
        return make_dummy_paths()

    def fake_index_vault(config):
        captured["config"] = config
        return {
            "status": "ok",
            "table_name": "vault_markdown_chunks",
            "active_index_pointer": None,
        }

    monkeypatch.setattr(vault_commands, "resolve_vault_paths", fake_resolve_vault_paths)
    monkeypatch.setattr(vault_commands, "index_vault", fake_index_vault)

    runner = CliRunner()
    result = runner.invoke(cli.main, ["index-vault", "--parser", "auto"])

    assert result.exit_code == 0
    assert captured["config"].parser == "auto"


def test_index_graph_command_json_output(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_graph_paths(**kwargs):
        captured["resolve_kwargs"] = kwargs
        return make_dummy_graph_paths()

    def fake_index_graph(config):
        captured["config"] = config
        return {
            "node_count": 10,
            "edge_count": 12,
            "graph_path": str(config.paths.graph_path),
        }

    monkeypatch.setattr(graph_commands, "resolve_graph_paths", fake_resolve_graph_paths)
    monkeypatch.setattr(graph_commands, "index_graph", fake_index_graph)

    runner = CliRunner()
    result = runner.invoke(cli.main, ["index-graph", "--json-output"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["node_count"] == 10
    assert captured["resolve_kwargs"] == {"index_root": None, "graph_file": None}


def test_search_graph_command_text_output(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_graph_paths(**kwargs):
        captured["resolve_kwargs"] = kwargs
        return make_dummy_graph_paths()

    def fake_search_graph(config):
        captured["config"] = config
        return {
            "results": [
                {
                    "rank": 1,
                    "source_path": "EN/1. AlphaFold3/1.2. Architecture/1.2.2. Pairformer.md",
                    "language_branch": "EN",
                    "score": 9.5,
                    "snippet": "Pairformer | tags: architecture, pairformer",
                    "evidence": ["matched note `EN/1. AlphaFold3/1.2. Architecture/1.2.2. Pairformer.md`"],
                }
            ],
            "warnings": [],
        }

    monkeypatch.setattr(graph_commands, "resolve_graph_paths", fake_resolve_graph_paths)
    monkeypatch.setattr(graph_commands, "search_graph", fake_search_graph)

    runner = CliRunner()
    result = runner.invoke(cli.main, ["search-graph", "pairformer", "--max-hops", "2"])

    assert result.exit_code == 0
    assert "Pairformer.md" in result.output
    assert "matched note" in result.output
    assert captured["resolve_kwargs"] == {"index_root": None, "graph_file": None}
    assert captured["config"].query == "pairformer"
    assert captured["config"].max_hops == 2


def test_explain_path_command_text_output(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_graph_paths(**kwargs):
        captured["resolve_kwargs"] = kwargs
        return make_dummy_graph_paths()

    def fake_explain_graph_path(config):
        captured["config"] = config
        return {
            "path_found": True,
            "resolved_source_path": "EN/1. AlphaFold3/1.2. Architecture/1.2.2. Pairformer.md",
            "resolved_target_path": "EN/1. AlphaFold3/1.2. Architecture/1.2.3. Diffusion Module.md",
            "hops": 1,
            "total_weight": 1.0,
            "summary": ["Pairformer --links_to--> Diffusion Module"],
            "warnings": [],
        }

    monkeypatch.setattr(graph_commands, "resolve_graph_paths", fake_resolve_graph_paths)
    monkeypatch.setattr(graph_commands, "explain_graph_path", fake_explain_graph_path)

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        ["explain-path", "Pairformer", "Diffusion Module", "--max-hops", "2"],
    )

    assert result.exit_code == 0
    assert "Pairformer --links_to--> Diffusion Module" in result.output
    assert captured["resolve_kwargs"] == {"index_root": None, "graph_file": None}
    assert captured["config"].source == "Pairformer"
    assert captured["config"].target == "Diffusion Module"
    assert captured["config"].max_hops == 2


def test_search_vault_command_forwards_hybrid_graph_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_vault_paths(**kwargs):
        return make_dummy_paths()

    def fake_search_vault(config):
        captured["config"] = config
        return {
            "results": [],
            "warnings": [],
            "effective_mode": "hybrid-graph",
            "effective_reranker": "rrf",
        }

    monkeypatch.setattr(vault_commands, "resolve_vault_paths", fake_resolve_vault_paths)
    monkeypatch.setattr(vault_commands, "search_vault", fake_search_vault)

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        [
            "search-vault",
            "how is pairformer related to diffusion",
            "--mode",
            "hybrid-graph",
            "--graph-max-hops",
            "2",
        ],
    )

    assert result.exit_code == 0
    assert captured["config"].mode == "hybrid-graph"
    assert captured["config"].graph_max_hops == 2


def test_mcp_command_starts_server(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class DummyServer:
        def run(self, *, transport: str) -> None:
            captured["transport"] = transport

    def fake_build_mcp_server(**kwargs):
        captured["kwargs"] = kwargs
        return DummyServer()

    from brains.commands import mcp as mcp_commands

    monkeypatch.setattr(mcp_commands, "build_mcp_server", fake_build_mcp_server)

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        ["mcp", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "9000"],
    )

    assert result.exit_code == 0
    assert captured["transport"] == "streamable-http"
    assert captured["kwargs"] == {
        "host": "0.0.0.0",
        "port": 9000,
        "debug": False,
        "log_level": "INFO",
    }


def test_check_index_command_uses_active_pdf_paths(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_paths(**kwargs):
        captured["resolve_kwargs"] = kwargs
        return make_dummy_paths()

    def fake_check_index_health(paths, **kwargs):
        captured["paths"] = paths
        captured["health_kwargs"] = kwargs
        return {
            "status": "ok",
            "table_name": paths.table_name,
            "pointer_used": True,
        }

    monkeypatch.setattr(health_commands, "resolve_pdf_paths", fake_resolve_paths)
    monkeypatch.setattr(health_commands, "check_index_health", fake_check_index_health)

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        [
            "check-index",
            "--target",
            "pdf",
            "--timeout-seconds",
            "7",
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["pointer_used"] is True
    assert captured["resolve_kwargs"] == {
        "pdf_dir": None,
        "index_root": None,
        "table_name": "scientific_pdf_chunks",
    }
    assert captured["health_kwargs"] == {
        "probe_query": "pairformer",
        "timeout_seconds": 7,
    }


def test_check_index_command_vault_target_uses_vault_paths(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_vault_paths(**kwargs):
        captured["resolve_kwargs"] = kwargs
        return make_dummy_paths()

    def fake_check_index_health(paths, **kwargs):
        captured["health_kwargs"] = kwargs
        return {
            "status": "timeout",
            "table_name": paths.table_name,
            "suggestion": "Retry outside sandbox.",
        }

    monkeypatch.setattr(health_commands, "resolve_vault_paths", fake_resolve_vault_paths)
    monkeypatch.setattr(health_commands, "check_index_health", fake_check_index_health)

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        [
            "check-index",
            "--target",
            "vault",
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "timeout"
    assert captured["resolve_kwargs"] == {
        "index_root": None,
        "table_name": "vault_markdown_chunks",
    }
    assert captured["health_kwargs"] == {
        "probe_query": "pairformer",
        "timeout_seconds": 10,
    }


def test_think_command_json_output(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_research_paths(**kwargs):
        captured["resolve_kwargs"] = kwargs
        index_root = Path("/tmp/repo/.brains/.index/research")
        return ResearchPaths(
            repo_root=Path("/tmp/repo"),
            brains_root=Path("/tmp/repo/.brains"),
            index_root=index_root,
            memory_path=index_root / "memory.jsonl",
            sessions_dir=index_root / "sessions",
        )

    def fake_run_think_loop(config):
        captured["config"] = config
        return {
            "session_id": "demo-session",
            "query": config.query,
            "summary": "done",
            "agent_handoff": "handoff",
            "warnings": [],
            "vault_results": [],
            "graph_results": [],
            "graph_paths": [],
            "pdf_results": [],
            "memory_results": [],
        }

    monkeypatch.setattr(research_commands, "resolve_research_paths", fake_resolve_research_paths)
    monkeypatch.setattr(research_commands, "run_think_loop", fake_run_think_loop)

    runner = CliRunner()
    result = runner.invoke(cli.main, ["think", "pairformer ideas", "--json-output"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["session_id"] == "demo-session"
    assert captured["resolve_kwargs"] == {"index_root": None}
    assert captured["config"].query == "pairformer ideas"


def test_search_vault_command_text_output(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_vault_paths(**kwargs):
        captured["resolve_kwargs"] = kwargs
        return make_dummy_paths()

    def fake_search_vault(config):
        captured["config"] = config
        return {
            "results": [
                {
                    "rank": 1,
                    "source_path": "UA/Research/Architecture/Pairformer.md",
                    "language_branch": "UA",
                    "section": "Pairformer",
                    "chunk_index": 0,
                    "snippet": "pairformer snippet",
                }
            ],
            "warnings": ["fallback used"],
            "effective_mode": "fts",
            "effective_reranker": "none",
        }

    monkeypatch.setattr(vault_commands, "resolve_vault_paths", fake_resolve_vault_paths)
    monkeypatch.setattr(vault_commands, "search_vault", fake_search_vault)

    runner = CliRunner()
    result = runner.invoke(cli.main, ["search-vault", "pairformer"])

    assert result.exit_code == 0
    assert "Fallbacks:" in result.output
    assert "Pairformer.md" in result.output
    assert "pairformer snippet" in result.output
    assert captured["config"].query == "pairformer"


def test_search_vault_command_forwards_auto_mode_and_thresholds(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_vault_paths(**kwargs):
        return make_dummy_paths()

    def fake_search_vault(config):
        captured["config"] = config
        return {
            "results": [],
            "warnings": [],
            "effective_mode": "fts",
            "effective_reranker": "none",
        }

    monkeypatch.setattr(vault_commands, "resolve_vault_paths", fake_resolve_vault_paths)
    monkeypatch.setattr(vault_commands, "search_vault", fake_search_vault)

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        [
            "search-vault",
            "EN/Research/Architecture/Pairformer.md",
            "--mode",
            "auto",
            "--min-score",
            "0.6",
            "--max-distance",
            "0.7",
        ],
    )

    assert result.exit_code == 0
    assert captured["config"].mode == "auto"
    assert captured["config"].min_score == 0.6
    assert captured["config"].max_distance == 0.7


def test_tasks_enqueue_command_forwards_extra_args(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_enqueue_cli_job(command, *, label=None):
        captured["command"] = command
        captured["label"] = label
        return {
            "job_id": "demo-job",
            "status": "queued",
            "label": label,
            "command": command,
            "stdout_path": ".brains/.cache/huey/jobs/demo-job/stdout.txt",
            "stderr_path": ".brains/.cache/huey/jobs/demo-job/stderr.txt",
        }

    monkeypatch.setattr(task_commands, "enqueue_cli_job", fake_enqueue_cli_job)

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        ["tasks", "enqueue", "--label", "pdf-reindex", "fetch-pdfs", "--reindex", "--json-output"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["job_id"] == "demo-job"
    assert captured["label"] == "pdf-reindex"
    assert captured["command"] == ["fetch-pdfs", "--reindex"]


def test_tasks_status_command_json_output(monkeypatch) -> None:
    def fake_load_job_record(job_id):
        assert job_id == "demo-job"
        return {
            "job_id": job_id,
            "status": "running",
            "label": "graph-index",
            "command": ["index-graph"],
            "stdout_path": ".brains/.cache/huey/jobs/demo-job/stdout.txt",
            "stderr_path": ".brains/.cache/huey/jobs/demo-job/stderr.txt",
        }

    monkeypatch.setattr(task_commands, "load_job_record", fake_load_job_record)

    runner = CliRunner()
    result = runner.invoke(cli.main, ["tasks", "status", "demo-job", "--json-output"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "running"
    assert payload["command"] == ["index-graph"]


def test_tasks_list_command_json_output(monkeypatch) -> None:
    def fake_list_job_records(*, limit):
        assert limit == 5
        return [
            {
                "job_id": "job-1",
                "status": "queued",
                "label": None,
                "command": ["index-vault"],
            }
        ]

    monkeypatch.setattr(task_commands, "list_job_records", fake_list_job_records)

    runner = CliRunner()
    result = runner.invoke(cli.main, ["tasks", "list", "--limit", "5", "--json-output"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["jobs"][0]["job_id"] == "job-1"


def test_tasks_output_command_uses_requested_stream(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_get_job_output(job_id, *, stream="stdout"):
        captured["job_id"] = job_id
        captured["stream"] = stream
        return "worker output"

    monkeypatch.setattr(task_commands, "get_job_output", fake_get_job_output)

    runner = CliRunner()
    result = runner.invoke(cli.main, ["tasks", "output", "demo-job", "--stream", "stderr"])

    assert result.exit_code == 0
    assert "worker output" in result.output
    assert captured == {"job_id": "demo-job", "stream": "stderr"}
