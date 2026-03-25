from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from brains.research.models import ResearchRunConfig
from brains.research.orchestration import run_think_loop
from brains.config import ResearchPaths, get_config
from brains.config.loader import repo_root as default_repo_root
from brains.config.loader import resolve_repo_path


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:40] or "experiment"


def _resolve_research_paths_for_repo(base_repo_root: Path) -> ResearchPaths:
    config = get_config()
    index_root = resolve_repo_path(base_repo_root, config.research.index_root)
    return ResearchPaths(
        repo_root=base_repo_root,
        brains_root=base_repo_root / ".brains",
        index_root=index_root,
        memory_path=index_root / "memory.jsonl",
        sessions_dir=index_root / "sessions",
    )


def run_experiment_tool(
    *,
    name: str,
    query: str,
    description: str | None = None,
    save_memory: bool = True,
    vault_k: int | None = None,
    pdf_k: int | None = None,
    repo_root: Path | None = None,
) -> dict[str, object]:
    base_repo_root = repo_root or default_repo_root()
    timestamp = datetime.now(UTC)
    experiment_id = f"{timestamp.strftime('%Y%m%d-%H%M%S')}-{_slugify(name)}"
    research_paths = _resolve_research_paths_for_repo(base_repo_root)
    experiment_dir = research_paths.index_root / "experiments"
    experiment_dir.mkdir(parents=True, exist_ok=True)

    result = run_think_loop(
        ResearchRunConfig.from_settings(
            paths=research_paths,
            query=query,
            vault_k=vault_k,
            pdf_k=pdf_k,
            session_id=experiment_id,
            save_memory=save_memory,
        )
    )
    artifact_path = experiment_dir / f"{experiment_id}.json"
    payload = {
        "experiment_id": experiment_id,
        "created_at": timestamp.isoformat(),
        "name": name,
        "description": description,
        "query": query,
        "result": result,
    }
    artifact_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "experiment_id": experiment_id,
        "artifact_path": str(artifact_path),
        "session_id": result["session_id"],
        "query": query,
        "name": name,
        "description": description,
        "summary": result["summary"],
        "agent_handoff": result["agent_handoff"],
        "warnings": result.get("warnings", []),
    }
