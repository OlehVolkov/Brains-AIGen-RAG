from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from brains.mcp import (
    create_mirror_note_tool,
    explain_path_tool,
    find_related_notes_tool,
    list_notes_tool,
    read_note_tool,
    run_experiment_tool,
    search_graph_tool,
    search_pdfs_tool,
    search_vault_tool,
    validate_note_tool,
    write_note_tool,
)
from brains.mcp.tools import explain_path_tool as exported_explain_path_tool
from brains.mcp.tools import search_graph_tool as exported_search_graph_tool
from brains.mcp.server import build_mcp_server
from brains.sources.pdf.search import search_pdf_corpus
from brains.sources.vault.related import find_related_note_candidates
from brains.sources.vault.search import search_vault_knowledge
from brains.config import ResearchPaths


def _make_repo(tmp_path: Path) -> Path:
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


def test_list_notes_filters_by_branch_and_contains(tmp_path: Path) -> None:
    repo_root = _make_repo(tmp_path)

    payload = list_notes_tool(branch="EN", contains="boltz", repo_root=repo_root)

    assert payload["count"] == 1
    assert payload["notes"] == [
        {
            "path": "EN/3. Models/3.7. Boltz-1.md",
            "title": "Boltz-1",
            "language_branch": "EN",
        }
    ]


def test_read_note_returns_content_and_metadata(tmp_path: Path) -> None:
    repo_root = _make_repo(tmp_path)

    payload = read_note_tool(path="EN/3. Models/3.7. Boltz-1.md", repo_root=repo_root)

    assert payload["path"] == "EN/3. Models/3.7. Boltz-1.md"
    assert payload["title"] == "Boltz-1"
    assert payload["language_branch"] == "EN"
    assert "Open model note." in payload["content"]


def test_write_note_creates_new_branch_note(tmp_path: Path) -> None:
    repo_root = _make_repo(tmp_path)

    payload = write_note_tool(
        path="EN/3. Models/3.10. Test Model.md",
        content="# Test Model\n\nDraft content.",
        mode="overwrite",
        create=True,
        repo_root=repo_root,
    )

    assert payload["created"] is True
    assert payload["language_branch"] == "EN"
    assert (
        repo_root / "EN" / "3. Models" / "3.10. Test Model.md"
    ).read_text(encoding="utf-8").startswith("# Test Model")


def test_write_note_rejects_new_root_note(tmp_path: Path) -> None:
    repo_root = _make_repo(tmp_path)

    with pytest.raises(ValueError, match="New notes may only be created under EN/ or UA/"):
        write_note_tool(
            path="NewRoot.md",
            content="# Bad\n",
            create=True,
            repo_root=repo_root,
        )


def test_search_vault_knowledge_uses_existing_search_stack(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_vault_paths(**kwargs):
        captured["resolve_kwargs"] = kwargs
        return "vault-paths"

    def fake_search_vault(config):
        captured["config"] = config
        return {"results": [{"source_path": "EN/Index.md"}], "warnings": []}

    monkeypatch.setattr("brains.sources.vault.search.resolve_vault_paths", fake_resolve_vault_paths)
    monkeypatch.setattr("brains.sources.vault.search.search_vault", fake_search_vault)
    monkeypatch.setattr(
        "brains.sources.vault.search.VaultSearchConfig.from_settings",
        classmethod(lambda cls, **kwargs: kwargs),
    )

    payload = search_vault_knowledge(query="pairformer", k=3)

    assert payload["results"][0]["source_path"] == "EN/Index.md"
    assert captured["resolve_kwargs"] == {"index_root": None}
    assert captured["config"]["query"] == "pairformer"
    assert captured["config"]["k"] == 3


def test_search_vault_tool_delegates_to_rag_layer(monkeypatch) -> None:
    monkeypatch.setattr("brains.mcp.tools.search.search_vault_knowledge", lambda **kwargs: {
        "results": [{"source_path": "EN/Index.md"}],
        "kwargs": kwargs,
    })

    payload = search_vault_tool(query="pairformer", k=3)

    assert payload["results"][0]["source_path"] == "EN/Index.md"
    assert payload["kwargs"]["query"] == "pairformer"


def test_search_vault_tool_forwards_graph_max_hops(monkeypatch) -> None:
    monkeypatch.setattr("brains.mcp.tools.search.search_vault_knowledge", lambda **kwargs: {
        "results": [],
        "kwargs": kwargs,
    })

    payload = search_vault_tool(
        query="how is pairformer related to diffusion",
        mode="hybrid-graph",
        graph_max_hops=2,
    )

    assert payload["kwargs"]["mode"] == "hybrid-graph"
    assert payload["kwargs"]["graph_max_hops"] == 2


def test_search_vault_tool_preserves_default_graph_hops(monkeypatch) -> None:
    monkeypatch.setattr("brains.mcp.tools.search.search_vault_knowledge", lambda **kwargs: {
        "results": [],
        "kwargs": kwargs,
    })

    payload = search_vault_tool(query="pairformer")

    assert "graph_max_hops" in payload["kwargs"]
    assert payload["kwargs"]["graph_max_hops"] is None


def test_search_pdf_corpus_uses_existing_search_stack(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_pdf_paths(**kwargs):
        captured["resolve_kwargs"] = kwargs
        return "pdf-paths"

    def fake_search_pdfs(config):
        captured["config"] = config
        return {"results": [{"source_path": "PDF/test.pdf"}], "warnings": []}

    monkeypatch.setattr("brains.sources.pdf.search.resolve_pdf_paths", fake_resolve_pdf_paths)
    monkeypatch.setattr("brains.sources.pdf.search.search_pdfs", fake_search_pdfs)
    monkeypatch.setattr(
        "brains.sources.pdf.search.SearchConfig.from_settings",
        classmethod(lambda cls, **kwargs: kwargs),
    )

    payload = search_pdf_corpus(query="ligand", k=2)

    assert payload["results"][0]["source_path"] == "PDF/test.pdf"
    assert captured["resolve_kwargs"] == {"index_root": None}
    assert captured["config"]["query"] == "ligand"
    assert captured["config"]["k"] == 2


def test_search_pdfs_tool_delegates_to_rag_layer(monkeypatch) -> None:
    monkeypatch.setattr("brains.mcp.tools.search.search_pdf_corpus", lambda **kwargs: {
        "results": [{"source_path": "PDF/test.pdf"}],
        "kwargs": kwargs,
    })

    payload = search_pdfs_tool(query="ligand", k=2)

    assert payload["results"][0]["source_path"] == "PDF/test.pdf"
    assert payload["kwargs"]["query"] == "ligand"


def test_search_graph_tool_delegates_to_graph_layer(monkeypatch) -> None:
    monkeypatch.setattr("brains.mcp.tools.search.search_graph_knowledge", lambda **kwargs: {
        "results": [{"source_path": "EN/Graph.md"}],
        "kwargs": kwargs,
    })

    payload = search_graph_tool(query="pairformer", k=3, max_hops=2)

    assert payload["results"][0]["source_path"] == "EN/Graph.md"
    assert payload["kwargs"]["query"] == "pairformer"
    assert payload["kwargs"]["max_hops"] == 2


def test_explain_path_tool_delegates_to_graph_layer(monkeypatch) -> None:
    monkeypatch.setattr("brains.mcp.tools.search.explain_graph_path_knowledge", lambda **kwargs: {
        "path_found": True,
        "kwargs": kwargs,
    })

    payload = explain_path_tool(source="Pairformer", target="Diffusion Module", max_hops=2)

    assert payload["path_found"] is True
    assert payload["kwargs"]["source"] == "Pairformer"
    assert payload["kwargs"]["target"] == "Diffusion Module"
    assert payload["kwargs"]["max_hops"] == 2


def test_find_related_note_candidates_filters_same_branch_and_self(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_search_vault_knowledge(**kwargs):
        captured["search_kwargs"] = kwargs
        return {
            "results": [
                {"source_path": "EN/3. Models/3.7. Boltz-1.md", "language_branch": "EN", "snippet": "self"},
                {"source_path": "EN/Index.md", "language_branch": "EN", "snippet": "related"},
                {"source_path": "UA/Індекс.md", "language_branch": "UA", "snippet": "cross-branch"},
            ],
            "warnings": [],
        }

    monkeypatch.setattr(
        "brains.sources.vault.related.search_vault_knowledge",
        fake_search_vault_knowledge,
    )
    monkeypatch.setattr(
        "brains.sources.vault.related.explain_graph_path_knowledge",
        lambda **kwargs: {
            "path_found": True,
            "hops": 1,
            "summary": ["Boltz-1 --links_to--> Index"],
        },
    )

    payload = find_related_note_candidates(
        note_path="EN/3. Models/3.7. Boltz-1.md",
        note_title="Boltz-1",
        note_content="# Boltz-1\n\nOpen model note.\n",
        note_branch="EN",
        k=5,
    )

    assert [row["source_path"] for row in payload["results"]] == ["EN/Index.md"]
    assert captured["search_kwargs"]["mode"] == "hybrid-graph"
    assert payload["results"][0]["graph_evidence"] == ["Boltz-1 --links_to--> Index"]
    assert payload["results"][0]["graph_hops"] == 1


def test_find_related_note_candidates_forwards_graph_max_hops(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "brains.sources.vault.related.search_vault_knowledge",
        lambda **kwargs: {
            "results": [{"source_path": "EN/Index.md", "language_branch": "EN", "snippet": "related"}],
            "warnings": [],
            "kwargs": kwargs,
        },
    )

    def fake_explain_graph_path_knowledge(**kwargs):
        captured["graph_kwargs"] = kwargs
        return {"path_found": False, "hops": None, "summary": []}

    monkeypatch.setattr(
        "brains.sources.vault.related.explain_graph_path_knowledge",
        fake_explain_graph_path_knowledge,
    )

    find_related_note_candidates(
        note_path="EN/3. Models/3.7. Boltz-1.md",
        note_title="Boltz-1",
        note_content="# Boltz-1\n\nOpen model note.\n",
        note_branch="EN",
        graph_max_hops=3,
    )

    assert captured["graph_kwargs"]["max_hops"] == 3


def test_find_related_notes_tool_delegates_to_rag_layer(monkeypatch, tmp_path: Path) -> None:
    repo_root = _make_repo(tmp_path)

    monkeypatch.setattr("brains.mcp.tools.search.find_related_note_candidates", lambda **kwargs: {
        "results": [{"source_path": "EN/Index.md"}],
        "kwargs": kwargs,
    })

    payload = find_related_notes_tool(
        path="EN/3. Models/3.7. Boltz-1.md",
        repo_root=repo_root,
        k=5,
        graph_max_hops=2,
    )

    assert [row["source_path"] for row in payload["results"]] == ["EN/Index.md"]
    assert payload["kwargs"]["note_path"] == "EN/3. Models/3.7. Boltz-1.md"
    assert payload["kwargs"]["graph_max_hops"] == 2


def test_create_mirror_note_creates_explicit_target(tmp_path: Path) -> None:
    repo_root = _make_repo(tmp_path)

    payload = create_mirror_note_tool(
        source_path="EN/3. Models/3.7. Boltz-1.md",
        target_path="UA/3. Моделі/3.7. Boltz-1.md",
        repo_root=repo_root,
    )

    target_path = repo_root / "UA" / "3. Моделі" / "3.7. Boltz-1.md"
    assert payload["target_path"] == "UA/3. Моделі/3.7. Boltz-1.md"
    assert target_path.exists()
    assert "🇬🇧 [[EN/3. Models/3.7. Boltz-1.md|English]]" in target_path.read_text(encoding="utf-8")


def test_validate_note_reports_missing_frontmatter_and_counterpart(tmp_path: Path) -> None:
    repo_root = _make_repo(tmp_path)

    payload = validate_note_tool(path="EN/3. Models/3.7. Boltz-1.md", repo_root=repo_root)

    issue_codes = {issue["code"] for issue in payload["issues"]}
    assert payload["valid"] is False
    assert "missing_frontmatter" in issue_codes
    assert "missing_breadcrumb" in issue_codes
    assert "missing_counterpart_link" in issue_codes


def test_run_experiment_writes_artifact(monkeypatch, tmp_path: Path) -> None:
    repo_root = _make_repo(tmp_path)
    research_root = repo_root / ".brains" / ".index" / "research"

    dummy_paths = ResearchPaths(
        repo_root=repo_root,
        brains_root=repo_root / ".brains",
        index_root=research_root,
        memory_path=research_root / "memory.jsonl",
        sessions_dir=research_root / "sessions",
    )

    def fake_run_think_loop(config):
        return {
            "session_id": config.session_id,
            "summary": "experiment result",
            "agent_handoff": "handoff",
            "warnings": [],
        }

    monkeypatch.setattr(
        "brains.mcp.tools.experiments._resolve_research_paths_for_repo",
        lambda _: dummy_paths,
    )
    monkeypatch.setattr("brains.mcp.tools.experiments.run_think_loop", fake_run_think_loop)

    payload = run_experiment_tool(
        name="Boltz benchmark",
        query="compare boltz-1 vs chai-1",
        repo_root=repo_root,
    )

    artifact_path = Path(payload["artifact_path"])
    assert artifact_path.exists()
    saved = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert saved["name"] == "Boltz benchmark"
    assert saved["result"]["summary"] == "experiment result"
    assert payload["summary"] == "experiment result"


def test_build_mcp_server_registers_stage_two_tools(tmp_path: Path) -> None:
    repo_root = _make_repo(tmp_path)
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


def test_mcp_tools_package_exports_graph_tools() -> None:
    assert exported_search_graph_tool is search_graph_tool
    assert exported_explain_path_tool is explain_path_tool
