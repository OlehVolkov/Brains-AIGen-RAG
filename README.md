# brain

Local `uv`-managed Python project for `AlphaFold3/.brain`.

## Purpose

This project exists to hold local automation and research helpers for the vault:

- retrieval helpers
- indexing utilities
- manifests and maintenance scripts
- small project-specific tooling
- scientific PDF indexing and search over `/PDF`
- markdown vault indexing and search over `UA/`, `EN/`, and root knowledge files

Generated data belongs in `/.brain/.index`. Knowledge-base content belongs in `UA/`, `EN/`, and root governance files.

## MCP Stages

The current `/.brain` roadmap is split into two practical `MCP` stages:

### Stage 1

Implemented:

- `RAG` over indexed vault content
- vault retrieval through `search-vault`

This is the current retrieval-first layer and is already usable.

### Stage 2

Implemented baseline MCP tools:

- `read_note`
- `write_note`
- `list_notes`
- `run_experiment`

This stage should extend the current retrieval layer into a stable tool interface for:

- reading canonical notes from the vault
- writing note updates in explicit target paths
- enumerating notes for planning and linking
- executing experiment workflows instead of only describing them

Current gap above the baseline:

- automatic bilingual mirroring
- automatic `[[wiki-links]]` maintenance
- full `ACT/LINK` execution planning

## Design Preference

- The preferred code style for `/.brain` is modular and package-oriented.
- The preferred long-term package hierarchy is:
  - `brain/config/` for configuration loading and settings models
  - `brain/shared/` for reusable infrastructure used across domains
  - `brain/sources/pdf/` for PDF-specific logic
  - `brain/sources/pdf/backends/` for PDF parser backends
  - `brain/sources/vault/` for vault-specific indexing and search logic
  - `brain/research/` for orchestration, memory, and report generation
  - `brain/mcp/tools/` for MCP tool handlers
  - `brain/commands/` for CLI entrypoints only
- Avoid bringing back flat compatibility facades when the canonical package API is already readable.
- If a file starts accumulating unrelated responsibilities, split it into smaller package-local modules.

## Structure Rationale

- The filesystem should reflect the nature of the logic, not the history of refactors.
- `config` is only for configuration loading, settings models, and path resolution.
- `shared` is for reusable infrastructure such as logging, text helpers, retrieval helpers, formatting, and health checks.
- `sources/pdf` and `sources/vault` are the two primary knowledge-source domains, so parsing, indexing, search, and source-specific helpers should live there.
- `research` is a workflow/orchestration layer over retrieval and memory, not a datasource adapter.
- `mcp/tools` is an interface layer over internal services and should stay thin.
- `commands` is the CLI surface and should remain separate from domain logic.
- Avoid using `rag` as the top-level home for everything. `RAG` is a capability, while package names should reflect stable domain boundaries.

## Target Layout

```text
.brain/
├── config/
│   ├── brain.toml
│   └── local.example.toml
├── scripts/
├── tests/
├── brain/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── loader.py
│   │   ├── models.py
│   │   └── sources.py
│   ├── shared/
│   │   ├── __init__.py
│   │   ├── runtime.py
│   │   ├── text.py
│   │   ├── formatting.py
│   │   ├── langchain.py
│   │   ├── retrieval.py
│   │   └── health.py
│   ├── sources/
│   │   ├── pdf/
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── fetch.py
│   │   │   ├── parsers.py
│   │   │   ├── indexing.py
│   │   │   ├── search.py
│   │   │   └── backends/
│   │   └── vault/
│   │       ├── __init__.py
│   │       ├── models.py
│   │       ├── markdown.py
│   │       ├── indexing.py
│   │       ├── search.py
│   │       └── related.py
│   ├── research/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── memory.py
│   │   ├── formatting.py
│   │   └── orchestration.py
│   ├── mcp/
│   │   ├── __init__.py
│   │   ├── server.py
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── notes.py
│   │       ├── search.py
│   │       └── experiments.py
│   └── commands/
│       ├── __init__.py
│       ├── pdf.py
│       ├── vault.py
│       ├── research.py
│       ├── mcp.py
│       └── health.py
```

## Environment

- Project root: `/.brain`
- Virtual environment: `/.brain/.venv`
- Python: `3.12`
- Tooling: `uv` (primary and required for package management and Python execution)
- Docker commands: invoke through Windows `cmd.exe` when needed from `WSL`
- CLI framework: `Typer`
- CLI output: `Rich`
- Logging: `Loguru`
- Configuration: `pydantic-settings.BaseSettings` + TOML files under `/.brain/config`

## Installation

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
cmd.exe /c "cd /d %CD% && uv python install 3.12"
```

## Common Commands

- `uvx` is for one-off external Python CLI tools outside the project environment.
- `npx` is for one-off Node/npm CLI tools.
- Use `npx` for `markdownlint-cli`; it is not a Python package.
- In Ruff `isort` settings, use `known-first-party = ["brain"]` for local import sorting; do not keep template placeholders such as `your_package`.

```bash
cmd.exe /c "cd /d %CD% && .venv\Scripts\activate.bat"
```

```bash
cmd.exe /c "cd /d %CD% && uv venv .venv --python 3.12"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv sync --all-groups"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brain"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python your_script.py"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run pytest tests/test_cli.py -q"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run ruff check brain tests"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run mypy brain"
```

```bash
uvx ruff check .
```

```bash
npx --yes markdownlint-cli@0.39.0 '**/*.md' --ignore node_modules --ignore .git --ignore .obsidian --config markdownlint.jsonc
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brain index"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brain index --parser pymupdf"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brain index --parser pdfplumber"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brain index --parser grobid --grobid-url http://127.0.0.1:8070"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brain index --parser marker --marker-command marker_single"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brain fetch-pdfs --reindex"
```

```bash
bash .brain/scripts/fetch_literature_pdfs.sh
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brain search \"alphafold diffusion\" --mode hybrid --reranker cross-encoder"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brain search \"protein ligand docking\" --mode hybrid --reranker ollama --ollama-rerank-model llama3.2:3b"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brain index-vault"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brain search-vault \"pairformer recycling\" --mode hybrid --reranker cross-encoder"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brain think \"pairformer implementation ideas\""
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brain mcp --transport stdio"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brain mcp --transport streamable-http --host 127.0.0.1 --port 8000"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run pytest tests -q"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run ruff check brain tests"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run mypy brain"
```

## Configuration

Committed defaults live in:

- `/.brain/config/brain.toml`
- `/.brain/config/local.example.toml`

Optional local overrides may be placed in:

- `/.brain/config/local.toml`
- `/.brain/.env`

Configuration is validated with `pydantic` and loaded through `BaseSettings`. The source order is:

1. init kwargs
2. environment variables
3. `/.brain/.env`
4. `local.toml` when present
5. `brain.toml`
6. model defaults

Preferred nested environment variable examples:

- `BRAIN_OLLAMA__EMBED_MODEL`
- `BRAIN_OLLAMA__BASE_URL`
- `BRAIN_OLLAMA__RERANK_MODEL`
- `BRAIN_RERANKER__CROSS_ENCODER_MODEL`
- `BRAIN_PDF__PDF_DIR`
- `BRAIN_PDF__INDEX_ROOT`
- `BRAIN_PDF__TABLE_NAME`
- `BRAIN_RESEARCH__INDEX_ROOT`
- `BRAIN_RESEARCH__MODEL`
- `BRAIN_VAULT__INDEX_ROOT`
- `BRAIN_VAULT__TABLE_NAME`

## PDF Search Pipeline

The local `brain` CLI now supports:

- indexing `*.pdf` files from `/PDF`
- scanning literature notes for `http/https` links and downloading PDF files when direct PDF delivery is possible
- indexing `*.md` files from `UA/`, `EN/`, and root knowledge/governance pages
- a multi-role `think` loop with `researcher`, `coder`, and `reviewer` passes
- session memory and reflection artifacts under `/.brain/.index/research`
- parser backends: `PyMuPDF` (default), `pdfplumber`, optional `Grobid`, optional `marker-pdf`
- chunking via LangChain text splitters
- embeddings via `OllamaEmbeddings`
- vector + full-text storage in LanceDB
- reranking with `RRF`, `CrossEncoder`, or an Ollama chat model

## Research Loop

The `think` command implements a practical BRAIN-style loop on top of the local indexes:

- retrieve context from vault search
- retrieve context from PDF search
- recall prior local memory from `/.brain/.index/research/memory.jsonl`
- run role passes for `researcher`, `coder`, and `reviewer`
- run a configurable self-reflection loop
- save session artifacts under `/.brain/.index/research/sessions/`

If Ollama is unavailable, the loop falls back to deterministic heuristic outputs instead of failing hard.

Current limitation:

- the implemented loop is still mostly a synthesis layer
- `Stage 2` MCP tools now exist, but higher-level `ACT/LINK` automation is still not implemented yet

## Ecosystem Overview

For scientific PDF indexing, it is useful to think in layers:

- PDF parsing:
  - `PyMuPDF` (`fitz`) is usually the best fast default for text and images.
  - `pdfplumber` is strong for tables and coordinate-aware extraction.
  - `Grobid` is specialized for scientific papers: metadata, authors, references, sections.
  - `marker-pdf` is useful when the target format should be clean Markdown.
- Chunking and embeddings:
  - `LangChain` provides practical splitters such as `RecursiveCharacterTextSplitter`.
  - `LlamaIndex` is useful when a richer node/index graph is needed.
  - `sentence-transformers` is the main route for scientific embedding models such as `SPECTER2` and `SciBERT`.
  - `Docling` is useful for complex layouts, tables, and formulas.
- Vector storage:
  - `ChromaDB` is a simple local starting point.
  - `FAISS` is strong for raw speed at larger scale.
  - `Qdrant` is a mature production option with strong metadata filtering.
  - `LanceDB` is strong when local vector search, full-text search, and structured metadata should live in one store.
- RAG and retrieval:
  - `Haystack` offers pipeline-oriented orchestration.
  - `RAGatouille` brings ColBERT-style retrieval and reranking.
  - `rank_bm25` is useful for sparse or hybrid retrieval.
  - `paper-qa` is focused on question answering over papers.

Why this project currently uses `LangChain` + `LanceDB` + `Ollama`:

- `LangChain` gives simple PDF ingestion and chunking primitives.
- `LanceDB` gives local vector search plus built-in full-text search and hybrid retrieval.
- `Ollama` keeps embeddings and optional reranking local.
- This combination is pragmatic for a local research vault where `/PDF`, `/.brain`, and `/.brain/.index` all live on the same machine.

Why the parser layer now uses the proposed PDF parsers:

- `PyMuPDF` is the default extraction backend for speed and strong plain-text extraction.
- `pdfplumber` is available as a table-aware alternative and fallback.
- `Grobid` is supported as an optional parser when a local service is available for paper-structure extraction.
- `marker-pdf` is supported as an optional parser when local Markdown-first conversion is preferred.

CLI parser modes:

- `--parser auto`: try `PyMuPDF`, then fall back to `pdfplumber`
- `--parser pymupdf`: force `PyMuPDF`
- `--parser pdfplumber`: force `pdfplumber`
- `--parser grobid`: send the PDF to a local `Grobid` service
- `--parser marker`: call a local `marker-pdf` command and index the generated Markdown

Recommended minimal stack for a fresh scientific-PDF project:

- `PyMuPDF` -> `sentence-transformers` (`SPECTER2` when available) -> `ChromaDB` -> `LlamaIndex` or `LangChain`

Recommended LanceDB-oriented stack:

- `PyMuPDF` or `Docling` -> `nomic-embed-text` or scientific `sentence-transformers` embeddings -> `LanceDB` -> `LangChain`, `LlamaIndex`, or `paper-qa`

Fallback behavior:

- `CrossEncoder` reranking is forced to `CPU`, so it does not require visible CUDA access.
- If vector embeddings are unavailable, `vector` and `hybrid` retrieval fall back to `FTS`.
- If `CrossEncoder` reranking fails at runtime, search falls back to:
  - `RRF` for `hybrid`
  - base ranking for `vector` / `FTS`
- If Ollama reranking fails, the tool keeps the base retrieval order and emits a warning.

Artifacts are written to `/.brain/.index/pdf_search`:

- `lancedb/` — LanceDB data files
- `manifest.json` — index metadata and file inventory
- `fetch_manifest.json` — last literature-link scan and PDF download summary

WSL note:

- if the repository is under `/mnt/c/...`, `LanceDB` may fail on `/.brain/.index/pdf_search/lancedb` during table creation or overwrite
- in that case, keep the default config unchanged but rebuild the PDF index into a Linux-native fallback path:

```bash
cd .brain
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brain index --index-root /tmp/alphafold3-pdf-index"
```

- fallback artifacts live at:
  - `/tmp/alphafold3-pdf-index/manifest.json`
  - `/tmp/alphafold3-pdf-index/lancedb`
- the canonical local index directory also keeps a pointer file to the active fallback index at:
  - `/.brain/.index/pdf_search/active_index.json`
- under restricted sandbox environments, `LanceDB` may still hang during `connect()` or `open_table()` even when the fallback index is valid on disk
- use the built-in health-check to validate the active index:

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brain check-index --target pdf"
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brain check-index --target vault"
```

- `check-index` automatically follows `active_index.json` when a fallback pointer exists
- if `check-index` reports `status: timeout`, rerun it outside the sandbox before treating the index as broken

## Literature PDF Fetching

The `fetch-pdfs` command scans literature notes, extracts `http/https` links, tries direct PDF URLs plus a few common transforms, and stores successful downloads in `/PDF`.

Default scan targets:

- `EN/Literature and Priorities.md`
- `UA/Література та пріоритети.md`

Typical usage:

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brain fetch-pdfs --reindex"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brain fetch-pdfs --dry-run"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brain fetch-pdfs --notes-glob \"EN/*.md\" --limit 20"
```

```bash
bash .brain/scripts/fetch_literature_pdfs.sh --dry-run
```

Notes:

- `fetch-pdfs` does not commit downloaded PDF payloads; `/PDF` stays local-only.
- The command currently handles direct PDF links and a few common literature redirects such as `arXiv abs -> pdf` and `OpenReview forum -> pdf`.
- `--reindex` rebuilds the PDF search index only when new files were actually downloaded.

Vault search artifacts are written to `/.brain/.index/vault_search`:

- `lancedb/` — LanceDB data files for markdown chunks
- `manifest.json` — index metadata and markdown inventory
- `active_index.json` — pointer to the active fallback vault index when the real index lives outside the canonical path

Research loop artifacts are written to `/.brain/.index/research`:

- `memory.jsonl` — compact long-term memory rows
- `sessions/*.json` — per-run multi-role session payloads

Before indexing/searching, ensure your local Ollama server is running and the required models are available. Typical examples:

```bash
ollama serve
```

```bash
ollama pull nomic-embed-text
```

```bash
ollama pull llama3.2:3b
```

## Project Files

- `pyproject.toml` — local project metadata
- `config/brain.toml` — committed default configuration
- `config/local.example.toml` — optional local override example
- `brain/cli.py` — thin Typer app facade
- The current repository now follows the target layout above and new code should keep using it.
- `brain/commands/` should stay as Typer registration and command entrypoints, not business logic.
- `brain/mcp/tools/` is the canonical home for MCP tool handlers; do not reintroduce flat `*_tools.py` modules under `brain/mcp/`.
- `AGENTS.md` — local agent instructions for `/.brain`
- `.index/` — runtime-generated indexes, manifests, pointers, and derived search artifacts
- Do not store exported dependency snapshots there, such as `requirements.txt`, `constraints.txt`, or copied lockfiles

Canonical entrypoints:

- `cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brain"`
- `cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run brain"`

## Notes

- `/.brain/.venv` is local-only, ignored by git, and must never be committed.
- Use `uv` as the canonical workflow for this project: `uv venv`, `uv add`, `uv run`.
- Use `uv python install 3.12` if the required interpreter is missing.
- If you add dependencies later, use `uv add ...` from `/.brain`.
- If you suspect a dependency is stale after refactors, verify real imports/usages first, then remove it with `uv remove --project .brain ...`, refresh `uv.lock`, and rerun tests.
- Keep this project focused on local vault tooling rather than note content.
- Keep machine-specific overrides in `/.brain/config/local.toml`, not in committed defaults.
- Keep environment-specific secrets and overrides in `/.brain/.env` or shell env vars, not in committed TOML.
