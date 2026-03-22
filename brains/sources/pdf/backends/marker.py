from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from brains.shared.text import normalize_text
from brains.sources.pdf.backends.factory import make_document


def load_pdf_with_marker(pdf_path: Path, repo_root: Path, marker_command: str):
    with tempfile.TemporaryDirectory(prefix="brains-marker-") as tmp_dir:
        output_dir = Path(tmp_dir)
        completed = subprocess.run(
            [
                marker_command,
                str(pdf_path),
                "--output_dir",
                str(output_dir),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        markdown_paths = sorted(output_dir.rglob("*.md"))
        if not markdown_paths:
            raise ValueError(
                f"marker command produced no markdown for {pdf_path.name}: "
                f"{completed.stdout.strip() or completed.stderr.strip()}"
            )
        text = normalize_text("\n\n".join(path.read_text(encoding="utf-8") for path in markdown_paths))
        if not text:
            return []
        return [
            make_document(
                text=text,
                pdf_path=pdf_path,
                repo_root=repo_root,
                page=1,
                page_label="1",
                parser="marker",
            )
        ]
