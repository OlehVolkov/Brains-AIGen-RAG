# brains

## Main Goal

The main goal of this project is to provide a local RAG + MCP tooling layer for this repository's knowledge base.

In practice, this means:

- indexing and searching Obsidian-style markdown notes
- indexing and searching local PDFs
- exposing note and retrieval operations through MCP
- supporting repository-grounded research workflows
- keeping all generated artifacts outside the hand-written knowledge base

This project is not the knowledge base itself. It is the local tooling around it.

## What This Repository Is For

This repository contains:

- the `brains/` Python package
- CLI commands for indexing, retrieval, health checks, research runs, and MCP serving
- MCP tools for note operations and repository-grounded retrieval
- configuration under `config/`
- generated artifacts under `/.brains/.index`

The knowledge base itself remains in:

- `UA/`
- `EN/`
- root governance files

Local PDFs belong in `PDF/`.

## What It Does Today

Current capabilities:

- index markdown notes into a local LanceDB-based retrieval layer
- search vault content with vector, FTS, or hybrid retrieval
- index local PDFs with multiple parser backends
- search PDF content with optional reranking
- run a local multi-step research loop through `think`
- expose the stack over MCP
- read, list, write, and experiment on notes through MCP tools
- validate active indexes and follow fallback pointer files

Note:

- retrieval is available through both CLI and MCP
- note operations are primarily exposed through MCP

## Project Model

Use this mental model:

- notes and governance files are the source of truth
- `/.brains/.index` is derived data only
- `brains/` is the implementation
- MCP is the preferred external interface
- CLI is the local/operator interface

Do not treat generated search artifacts as canonical knowledge.

## Repository Layout

Key paths:

- `brains/` — implementation
- `config/brains.toml` — committed defaults
- `config/local.toml` — ignored local override
- `.env` — ignored environment override
- `/.brains/.index/pdf_search` — PDF retrieval artifacts
- `/.brains/.index/vault_search` — vault retrieval artifacts
- `/.brains/.index/research` — memory, sessions, experiments
- `PDF/` — local PDF corpus
- `UA/`, `EN/` — knowledge-base content

## Core Commands

Run from the repository root.

Canonical Windows-from-WSL pattern:

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run ..."
```

Examples:

```bash
cmd.exe /c "cd /d %CD% && uv venv .venv --python 3.12"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv sync --all-groups"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brains --help"
```

### Vault

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brains index-vault"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brains search-vault \"pairformer\" --mode hybrid"
```

### PDFs

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brains index"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brains search \"knowledge retrieval\" --mode hybrid"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brains fetch-pdfs --reindex"
```

### Research

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brains think \"summarize the main retrieval gaps in this vault\""
```

### MCP

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brains mcp --transport stdio"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brains mcp --transport streamable-http --host 127.0.0.1 --port 8000"
```

### Health Checks

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brains check-index --target vault"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brains check-index --target pdf"
```

## MCP Surface

This project exposes the following MCP tools:

- `search_vault`
- `search_pdfs`
- `find_related_notes`
- `read_note`
- `write_note`
- `create_mirror_note`
- `validate_note`
- `list_notes`
- `run_experiment`

External agents should prefer MCP over manual file traversal when the task depends on retrieval, note discovery, or repository-grounded synthesis.

## Typical Workflow

For most knowledge tasks, the intended order is:

1. retrieve with `search_vault` and/or `search_pdfs`
2. inspect exact notes with `read_note`
3. synthesize with `think` or `run_experiment`
4. write back through `write_note` when an explicit update is needed
5. refresh or validate indexes only when retrieval state changed

## Configuration

Default config lives in:

- `config/brains.toml`

Local overrides belong in:

- `config/local.toml`
- `.env`

Environment variables use the `BRAINS_` prefix, for example:

- `BRAINS_OLLAMA__EMBED_MODEL`
- `BRAINS_OLLAMA__BASE_URL`
- `BRAINS_PDF__INDEX_ROOT`
- `BRAINS_VAULT__INDEX_ROOT`
- `BRAINS_RESEARCH__MODEL`

## Technology Choices

Current default stack:

- `Typer` for CLI
- `Rich` for CLI output
- `Loguru` for logging
- `PyMuPDF` as the default PDF parser
- `pdfplumber` as a table-aware fallback
- `LangChain` for chunking
- `LanceDB` for vector + FTS retrieval
- `Ollama` for local embeddings and optional reranking

## Verification

Default verification flow:

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run ruff check brains tests"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run mypy brains"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run pytest tests/test_cli.py -q"
```

Run full test suite only when needed:

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run pytest tests -q"
```

## WSL And Fallback Indexes

If the repository is mounted under `/mnt/c/...`, LanceDB may fail on the default index path inside `/.brains/.index/...`.

In that case:

- keep the canonical config unchanged
- rebuild into a Linux-native fallback path such as `/tmp/obsidian-kb-pdf-index`
- rely on the active pointer file under `/.brains/.index/.../active_index.json`
- use `brains check-index` before declaring the index corrupted

Example:

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brains index --index-root /tmp/obsidian-kb-pdf-index"
```

## Development Rules

This repository expects:

- `uv` as the primary Python workflow
- small, modular changes inside `brains/`
- generated artifacts only under `/.brains/.index`
- no secrets or `.env` values in tracked files
- no machine-specific overrides committed from `config/local.toml`
- no parallel note hierarchy introduced by tooling

If you are editing agent-facing behavior, also read:

- [BRAIN.md](/mnt/c/__PROJECTS/__AUSTIN/brains/BRAIN.md)
- [AGENTS.md](/mnt/c/__PROJECTS/__AUSTIN/brains/AGENTS.md)

## Short Version

This project is a local, repository-grounded RAG + MCP toolkit for an Obsidian-style knowledge base.

It exists to:

- search notes
- search PDFs
- expose those operations over MCP
- support local research workflows
- keep all retrieval artifacts separate from the hand-authored vault
