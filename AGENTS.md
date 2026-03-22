# .brain AGENTS.md

Local instructions for agents working inside `/.brain`.

## Scope

- `/.brain` is the home for local research tooling, helper scripts, prompts, manifests, and small automation utilities.
- `/.brain/.index` stores generated artifacts only: indexes, caches, manifests, embeddings, and similar derived data.
- The Obsidian knowledge base itself stays in `UA/`, `EN/`, and root governance files.
- Prefer the current modular package layout in `/.brain/brain`; do not collapse logic back into a few oversized files.

## Target Structure

- The preferred long-term package hierarchy inside `/.brain/brain` is:
  - `brain/config/`
  - `brain/shared/`
  - `brain/sources/pdf/`
  - `brain/sources/pdf/backends/`
  - `brain/sources/vault/`
  - `brain/research/`
  - `brain/mcp/tools/`
  - `brain/commands/`
- Use that hierarchy as the architectural reference even if the current repository is still mid-refactor.

## Why This Structure

- Organize packages by the nature of the logic, not by temporary implementation patterns.
- `config` is for settings models, settings sources, and path resolution only.
- `shared` is for reusable infrastructure such as logging, text helpers, retrieval helpers, and health checks.
- `sources/pdf` and `sources/vault` are the two primary knowledge-source domains, so parsing, indexing, search, and source-specific helpers should live there.
- `research` is a workflow/orchestration layer over retrieval and memory; it should not be treated as a datasource adapter.
- `mcp/tools` is an interface surface over internal services and should stay thin.
- `commands` is the CLI surface and should remain separate from domain logic.
- Avoid treating `RAG` as the top-level filesystem category. `RAG` is a capability, while package names should reflect stable domain boundaries.

## Ecosystem Overview

- Scientific PDF indexing is usually best designed as four layers:
  - parsing,
  - chunking and embeddings,
  - vector / full-text storage,
  - retrieval / reranking / RAG orchestration.
- Useful package families by layer:
  - parsing: `PyMuPDF`, `pdfplumber`, `Grobid`, `marker-pdf`, `Docling`
  - chunking / indexing: `LangChain`, `LlamaIndex`
  - embeddings: `sentence-transformers`, scientific models such as `SPECTER2` and `SciBERT`, or local `Ollama` embeddings
  - storage: `ChromaDB`, `FAISS`, `Qdrant`, `LanceDB`
  - retrieval / RAG: `Haystack`, `RAGatouille`, `rank_bm25`, `paper-qa`
- The current local default in `/.brain` is:
  - `PyMuPDF` for default PDF parsing
  - `pdfplumber` as a table-aware fallback
  - `LangChain` for chunking
  - `LanceDB` for vector + FTS + hybrid retrieval
  - `Ollama` for local embeddings and optional reranking
  - `brain/sources/vault/` modules for markdown indexing over `UA/`, `EN/`, and root knowledge files
- This is the preferred default for the vault unless the task clearly needs:
  - better scientific-paper structure extraction (`Grobid`, `Docling`),
  - stronger scientific embedding models (`SPECTER2`, `SciBERT`),
  - or a different storage backend for scale / deployment constraints.

## Project Rules

- Use `uv` as the primary tool for Python environments, dependency management, and execution.
- Install `uv` with the official installer when needed:
  - macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Windows PowerShell: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
- Install Python with `uv` when a managed interpreter is needed:
  - `uv python install`
  - `uv python install 3.12`
- Use the Windows virtual environment at `/.brain/.venv` as the single canonical local environment.
- Even when the agent is currently running from `WSL`, create, recreate, and sync `/.brain/.venv` through Windows `cmd.exe` with `uv`.
- Do not introduce or keep parallel canonical environments such as `/.brain/.venvx`.
- In `cmd.exe`, call `uv` directly from `PATH`; do not hardcode an absolute path to `uv.exe`.
- When Docker is needed for local services or tooling, invoke it through Windows `cmd.exe` too.
- Do not hardcode the repository path in commands, docs, scripts, tests, or examples.
- Treat portable path usage as a must-have: prefer `%CD%`, relative paths from the current working directory, or placeholders like `<REPO_ROOT>`.
- Use `BaseSettings`-driven `pydantic` config under `/.brain/config` and `/.brain/.env`.
- Keep the CLI on `Typer`; use `Rich` for user-facing output and `Loguru` for runtime logging.
- Virtual environments are local-only artifacts and must never be committed.
- Prefer running Python for `/.brain` through the Windows project environment:
  - `cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run ..."`
  - `cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv ..."`
- Prefer running Docker in the same style:
  - `cmd.exe /c "docker ..."`
- Prefer `uv add` over direct `pip install`.
- Prefer `uv venv` over manual `python -m venv`.
- `uvx` is for one-off external Python CLI tools that should not be installed into the project environment.
- `npx` is for one-off Node/npm CLI tools.
- Use `npx` for non-Python tools such as `markdownlint-cli`; do not route npm tools through `uvx`.
- Keep code changes in `/.brain` small, local, and automation-focused.
- Before adding or keeping a Python dependency, verify that it is actually needed by the current codebase.
- Prefer checking this explicitly via import search / usage search instead of assuming a package is still needed after refactors.
- If a direct dependency is no longer used, remove it from `pyproject.toml`, refresh `uv.lock`, and rerun tests.
- In Ruff `isort` settings, keep `known-first-party = ["brain"]`; do not leave template placeholders such as `your_package`.
- Do not make `pytest` re-run `ruff` or `mypy` indirectly; keep lint/type checks separate from the pytest suite.
- Default verification should be:
  - `uv run ruff check brain tests`
  - `uv run mypy brain`
  - targeted `uv run pytest ...`
- Use full `uv run pytest tests -q` only when the whole suite is needed.
- Prefer adding code to the existing package slices:
  - `brain/config/`
  - `brain/shared/`
  - `brain/sources/pdf/`
  - `brain/sources/pdf/backends/`
  - `brain/sources/vault/`
  - `brain/research/`
  - `brain/mcp/tools/`
  - `brain/commands/`
- Do not reintroduce compatibility facades such as flat re-export modules when the canonical package API is already clear.
- Do not write generated index data into notes or governance files.
- Do not commit secrets, credentials, `.env` values, or `PII`.
- Do not commit machine-specific overrides in `/.brain/config/local.toml`.
- Do not commit `/.brain/.env`.

Examples:

```bash
cmd.exe /c "cd /d %CD% && uv python install 3.12"
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
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run pytest tests/test_cli.py -q"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run ruff check brain tests"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run mypy brain"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run pytest tests -q"
```

## File Layout

- `pyproject.toml` defines the local `brain` project.
- Run the CLI through the Windows project interpreter at `/.brain/.venv/Scripts/python.exe`.
- `config/brain.toml` holds committed defaults.
- `config/local.toml` is an optional ignored local override file.
- `/.brain/.env` is an optional ignored dotenv override file.
- `brain/cli.py` is a thin Typer facade that registers commands from `brain/commands/`.
- `brain/config/` is the canonical configuration package for `BaseSettings`, settings sources, and path resolution.
- `brain/commands/` holds Typer command registration code.
- `brain/shared/` holds shared utilities used by multiple domains, including runtime helpers, retrieval helpers, formatting, and text utilities.
- Environment overrides should use nested names such as `BRAIN_OLLAMA__EMBED_MODEL`.
- `brain/sources/pdf/` contains parser routing, fetch, indexing, retrieval, and reranking logic for PDFs.
- `brain/sources/pdf/backends/` contains isolated parser backends (`PyMuPDF`, `pdfplumber`, optional `Grobid`, optional `marker`).
- `brain/sources/vault/` contains markdown file discovery, section splitting, indexing, retrieval, and related-note logic.
- `brain/research/` contains the multi-role research loop, memory handling, reflection steps, report formatting, and run models.
- `brain/mcp/tools/` is the canonical home for MCP note, search, and experiment handlers.
- Keep files readable: prefer extracting cohesive submodules before a file becomes long or mixed-responsibility.
- `README.md` explains how to use the local project.
- `.venv/` is local-only, canonical for `/.brain`, and must never be committed.
- `.index/` is for runtime-generated indexes, manifests, pointers, and search artifacts only.
- Do not store exported dependency snapshots or packaging artifacts there, such as `requirements.txt`, `constraints.txt`, lockfile copies, or similar temporary install files.

## Working Style

- Default to Python 3.12 via the local `uv` setup.
- Prefer deterministic scripts over ad hoc shell pipelines when logic will be reused.
- Keep outputs reproducible and scoped to repository needs.
- If a script updates vault content, make the target paths explicit and reviewable.
- Keep the modular structure stable; extend existing packages instead of adding new flat top-level helper files.
- Keep dependency hygiene strict: avoid stale direct dependencies and periodically audit `pyproject.toml` against actual imports.
- PDF search artifacts must stay under `/.brain/.index/pdf_search`.
- Vault markdown search artifacts must stay under `/.brain/.index/vault_search`.
- Research memory/session artifacts must stay under `/.brain/.index/research`.
- Under `WSL`, when the repository is mounted from `/mnt/c/...`, `LanceDB` may fail on the default `/.brain/.index/...` path.
- In that failure mode, keep the canonical default unchanged but rebuild the PDF index into `/tmp/alphafold3-pdf-index` and explicitly note that the active fallback artifacts are:
  - `/tmp/alphafold3-pdf-index/manifest.json`
  - `/tmp/alphafold3-pdf-index/lancedb`
- Also store the active fallback pointer in `/.brain/.index/pdf_search/active_index.json`.
- Apply the same rule to vault indexing when `index-vault` uses a fallback path:
  - fallback artifacts may live outside `/.brain/.index/vault_search`
  - store the active pointer in `/.brain/.index/vault_search/active_index.json`
- Under restricted sandbox environments, `LanceDB` may also hang during `connect()` or `open_table()` even when the fallback index under `/tmp/...` is valid.
- Use `brain check-index` to validate the active PDF or vault index, and make sure the command follows `active_index.json` when present.
- If `brain check-index` reports `status: timeout`, rerun it outside the sandbox before treating the index as corrupted.

## MCP Roadmap

- Treat the current `search-vault` capability as `MCP Stage 1`:
  - `RAG`
  - vault search over indexed markdown content
- Treat the next tool surface as `MCP Stage 2`:
  - `read_note`
  - `write_note`
  - `list_notes`
  - `run_experiment`
- The baseline `Stage 2` tool surface is now implemented.
- When extending `/.brain`, prefer building additional `Stage 2` behavior on top of the existing retrieval/index foundations instead of bypassing them.
- `read_note` and `list_notes` should preserve the canonical vault structure and avoid introducing a parallel note abstraction.
- `write_note` must preserve bilingual mirror rules, explicit target paths, and reviewable updates.
- `run_experiment` should produce reproducible outputs, explicit manifests, and repository-safe artifacts under `/.brain/.index` when applicable.
