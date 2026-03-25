from __future__ import annotations

from pathlib import Path

from brains.research import (
    MemoryStore,
    ResearchRunConfig,
    format_think_report,
    rank_memories,
    run_think_loop,
)
from brains.config import ResearchPaths


def make_research_paths(tmp_path: Path) -> ResearchPaths:
    index_root = tmp_path / ".brains" / ".index" / "research"
    return ResearchPaths(
        repo_root=tmp_path,
        brains_root=tmp_path / ".brains",
        index_root=index_root,
        memory_path=index_root / "memory.jsonl",
        sessions_dir=index_root / "sessions",
    )


def test_rank_memories_prefers_overlap() -> None:
    records = [
        {"session_id": "a", "query": "pairformer architecture", "summary": "pair updates"},
        {"session_id": "b", "query": "ligand docking", "summary": "small molecules"},
    ]
    ranked = rank_memories("pairformer updates", records, limit=2)
    assert ranked[0]["session_id"] == "a"


def test_memory_store_roundtrip(tmp_path: Path) -> None:
    store = MemoryStore(make_research_paths(tmp_path))
    payload = {
        "session_id": "demo",
        "query": "pairformer",
        "summary": "architecture",
        "final_answer": "result",
    }
    store.append(payload)
    rows = store.load_all()
    assert rows == [payload]
    session_path = store.save_session("demo", {"ok": True})
    assert session_path.exists()


def test_run_think_loop_builds_bundle_and_saves_memory(monkeypatch, tmp_path: Path) -> None:
    paths = make_research_paths(tmp_path)

    monkeypatch.setattr(
        "brains.research.orchestration.search_vault_knowledge",
        lambda **kwargs: {
            "results": [{"source_path": "EN/Index.md", "snippet": "vault hit"}],
            "warnings": [],
        },
    )
    monkeypatch.setattr(
        "brains.research.orchestration.search_graph_knowledge",
        lambda **kwargs: {
            "results": [{"source_path": "EN/Graph.md", "snippet": "graph hit"}],
            "warnings": [],
        },
    )
    monkeypatch.setattr(
        "brains.research.orchestration.explain_graph_path_knowledge",
        lambda **kwargs: {
            "path_found": True,
            "resolved_source_path": kwargs["source"],
            "resolved_target_path": kwargs["target"],
            "hops": 1,
            "summary": ["A --links_to--> B"],
            "warnings": [],
        },
    )
    monkeypatch.setattr(
        "brains.research.orchestration.search_pdf_corpus",
        lambda **kwargs: {
            "results": [{"source_path": "PDF/paper.pdf", "snippet": "pdf hit"}],
            "warnings": [],
        },
    )
    payload = run_think_loop(
        ResearchRunConfig(
            paths=paths,
            query="pairformer",
            session_id="pairformer-session",
        )
    )

    assert payload["session_id"] == "pairformer-session"
    assert payload["mode"] == "retrieval_bundle"
    assert "Prepared external-agent retrieval bundle" in payload["summary"]
    assert "External agent handoff:" in payload["agent_handoff"]
    assert payload["graph_results"][0]["source_path"] == "EN/Graph.md"
    assert paths.memory_path.exists()
    assert (paths.sessions_dir / "pairformer-session.json").exists()


def test_format_think_report_renders_bundle_sections() -> None:
    rendered = format_think_report(
        {
            "session_id": "demo",
            "query": "pairformer",
            "warnings": ["fallback"],
            "vault_results": [{"source_path": "EN/Index.md", "snippet": "vault hit"}],
            "graph_results": [{"source_path": "EN/Graph.md", "snippet": "graph hit"}],
            "graph_paths": [
                {
                    "resolved_source_path": "EN/A.md",
                    "resolved_target_path": "EN/B.md",
                    "hops": 1,
                    "summary": ["A --links_to--> B"],
                }
            ],
            "pdf_results": [],
            "memory_results": [],
            "summary": "bundle summary",
            "agent_handoff": "handoff text",
        }
    )
    assert "### Graph" in rendered
    assert "### Graph Paths" in rendered
    assert "## Summary" in rendered
    assert "## Agent Handoff" in rendered
    assert "bundle summary" in rendered
