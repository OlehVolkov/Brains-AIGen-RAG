from __future__ import annotations

import json
from typing import Any


def format_index_summary(summary: dict[str, Any]) -> str:
    return json.dumps(summary, ensure_ascii=False, indent=2)
