from __future__ import annotations

import json
import re
from typing import Any, Iterable

from brains.shared import logger
from brains.config import ResearchPaths


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9_]{3,}", text.lower())}


def rank_memories(
    query: str,
    records: Iterable[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    query_tokens = _tokenize(query)
    scored: list[tuple[int, dict[str, Any]]] = []
    for record in records:
        haystack = " ".join(
            str(record.get(field, ""))
            for field in ("query", "summary", "final_answer", "session_id")
        )
        score = len(query_tokens & _tokenize(haystack))
        if score > 0:
            scored.append((score, record))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [record for _, record in scored[:limit]]


class MemoryStore:
    def __init__(self, paths: ResearchPaths) -> None:
        self.paths = paths

    def ensure_layout(self) -> None:
        self.paths.index_root.mkdir(parents=True, exist_ok=True)
        self.paths.sessions_dir.mkdir(parents=True, exist_ok=True)

    def load_all(self) -> list[dict[str, Any]]:
        if not self.paths.memory_path.exists():
            return []
        logger.debug("Loading research memory from {}", self.paths.memory_path)
        rows: list[dict[str, Any]] = []
        for line in self.paths.memory_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
        return rows

    def recall(self, query: str, *, limit: int) -> list[dict[str, Any]]:
        return rank_memories(query, self.load_all(), limit=limit)

    def append(self, payload: dict[str, Any]) -> None:
        self.ensure_layout()
        logger.debug("Appending research memory row to {}", self.paths.memory_path)
        with self.paths.memory_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def save_session(self, session_id: str, payload: dict[str, Any]):
        self.ensure_layout()
        target = self.paths.sessions_dir / f"{session_id}.json"
        logger.debug("Saving research session payload to {}", target)
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return target
