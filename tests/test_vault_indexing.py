from __future__ import annotations

import json
from pathlib import Path

from brain.config import BrainPaths
from brain.sources.vault.indexing import pointer_manifest_path, write_active_index_pointer
from brain.sources.vault.models import VaultIndexConfig


def make_paths(tmp_path: Path) -> BrainPaths:
    repo_root = tmp_path
    brain_root = repo_root / ".brain"
    index_root = brain_root / ".index" / "vault_search"
    return BrainPaths(
        repo_root=repo_root,
        brain_root=brain_root,
        pdf_dir=repo_root / "PDF",
        index_root=index_root,
        db_uri=index_root / "lancedb",
        manifest_path=index_root / "manifest.json",
        table_name="vault_markdown_chunks",
    )


def make_index_config(paths: BrainPaths) -> VaultIndexConfig:
    return VaultIndexConfig(
        paths=paths,
        embed_model="nomic-embed-text",
        ollama_base_url="http://127.0.0.1:11434",
        chunk_size=1200,
        chunk_overlap=200,
        batch_size=32,
        overwrite=True,
    )


def test_write_active_index_pointer_for_fallback_index(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    fallback_root = tmp_path / "tmp-vault-index"
    fallback_paths = BrainPaths(
        repo_root=paths.repo_root,
        brain_root=paths.brain_root,
        pdf_dir=paths.pdf_dir,
        index_root=fallback_root,
        db_uri=fallback_root / "lancedb",
        manifest_path=fallback_root / "manifest.json",
        table_name=paths.table_name,
    )
    config = make_index_config(fallback_paths)

    pointer_path = write_active_index_pointer(
        config,
        {
            "markdown_count": 99,
            "chunk_count": 1352,
        },
    )

    assert pointer_path == tmp_path / ".brain" / ".index" / "vault_search" / "active_index.json"
    payload = json.loads(pointer_path.read_text(encoding="utf-8"))
    assert payload["index_root"] == str(fallback_root)
    assert payload["db_uri"] == str(fallback_root / "lancedb")
    assert payload["manifest_path"] == str(fallback_root / "manifest.json")


def test_write_active_index_pointer_removed_for_default_index(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    config = make_index_config(paths)
    default_pointer = pointer_manifest_path(config)
    default_pointer.parent.mkdir(parents=True, exist_ok=True)
    default_pointer.write_text("stale\n", encoding="utf-8")

    pointer_path = write_active_index_pointer(
        config,
        {
            "markdown_count": 1,
            "chunk_count": 2,
        },
    )

    assert pointer_path is None
    assert not default_pointer.exists()
