from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from brain import cli
from brain.commands import health as health_commands
from brain.commands import pdf as pdf_commands
from brain.commands import research as research_commands
from brain.commands import vault as vault_commands
from brain.config import BrainPaths, ResearchPaths


def make_dummy_paths() -> BrainPaths:
    repo_root = Path("/tmp/repo")
    brain_root = repo_root / ".brain"
    index_root = brain_root / ".index" / "dummy"
    return BrainPaths(
        repo_root=repo_root,
        brain_root=brain_root,
        pdf_dir=repo_root / "PDF",
        index_root=index_root,
        db_uri=index_root / "lancedb",
        manifest_path=index_root / "manifest.json",
        table_name="dummy_table",
    )


def test_main_help_shows_commands() -> None:
    runner = CliRunner()
    result = runner.invoke(cli.main, ["--help"])
    assert result.exit_code == 0
    assert "index" in result.output
    assert "check-index" in result.output
    assert "fetch-pdfs" in result.output
    assert "mcp" in result.output
    assert "search" in result.output
    assert "think" in result.output
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
                    "snippet": "alphafold snippet",
                }
            ],
            "warnings": ["fallback used"],
            "effective_mode": "fts",
            "effective_reranker": "none",
        }

    monkeypatch.setattr(pdf_commands, "resolve_pdf_paths", fake_resolve_paths)
    monkeypatch.setattr(pdf_commands, "search_pdfs", fake_search_pdfs)

    runner = CliRunner()
    result = runner.invoke(cli.main, ["search", "alphafold", "--mode", "hybrid"])

    assert result.exit_code == 0
    assert "Fallbacks:" in result.output
    assert "PDF/paper.pdf" in result.output
    assert "alphafold snippet" in result.output
    assert captured["config"].query == "alphafold"
    assert captured["config"].mode == "hybrid"


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
            "manifest_path": "/tmp/repo/.brain/.index/dummy/fetch_manifest.json",
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


def test_mcp_command_starts_server(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class DummyServer:
        def run(self, *, transport: str) -> None:
            captured["transport"] = transport

    def fake_build_mcp_server(**kwargs):
        captured["kwargs"] = kwargs
        return DummyServer()

    from brain.commands import mcp as mcp_commands

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
        index_root = Path("/tmp/repo/.brain/.index/research")
        return ResearchPaths(
            repo_root=Path("/tmp/repo"),
            brain_root=Path("/tmp/repo/.brain"),
            index_root=index_root,
            memory_path=index_root / "memory.jsonl",
            sessions_dir=index_root / "sessions",
        )

    def fake_run_think_loop(config):
        captured["config"] = config
        return {
            "session_id": "demo-session",
            "query": config.query,
            "roles": {
                "researcher": {"content": "r"},
                "coder": {"content": "c"},
                "reviewer": {"content": "v"},
            },
            "reflections": [],
            "final_answer": "done",
            "warnings": [],
            "vault_results": [],
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
                    "source_path": "UA/1. AlphaFold3/1.2. Архітектура/1.2.2. Pairformer.md",
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
