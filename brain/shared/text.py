from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable, Sequence


def _with_warnings(
    rows: Sequence[dict[str, Any]],
    warnings: Sequence[str],
) -> list[dict[str, Any]]:
    prepared = [dict(row) for row in rows]
    if prepared and warnings:
        prepared[0]["_brain_warnings"] = list(warnings)
    return prepared


def chunked(items: Sequence[str], batch_size: int) -> Iterable[Sequence[str]]:
    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def snippet(text: str, max_chars: int) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def chunk_id(
    *,
    source_path: str,
    page: int,
    chunk_index: int,
    text: str,
) -> str:
    return hashlib.sha1(
        f"{source_path}:{page}:{chunk_index}:{text}".encode("utf-8")
    ).hexdigest()
