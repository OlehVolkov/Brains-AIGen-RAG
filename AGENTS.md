# .brains AGENTS.md

Local instructions for agents working on the repository's `brains` tooling and its generated artifacts under `/.brains`.

## Scope

- `/.brains` is the home for local research tooling, helper scripts, prompts, manifests, and small automation utilities.
- `/.brains/.index` stores generated artifacts only: indexes, caches, manifests, embeddings, and similar derived data.
- The Obsidian knowledge base itself stays in `UA/`, `EN/`, and root governance files.
- Prefer the current modular package layout in `brains/`; do not collapse logic back into a few oversized files.

## Target Structure

- The preferred long-term package hierarchy inside `brains/` is:
  - `brains/config/`
  - `brains/shared/`
  - `brains/sources/pdf/`
  - `brains/sources/pdf/backends/`
  - `brains/sources/vault/`
  - `brains/research/`
  - `brains/mcp/tools/`
  - `brains/commands/`
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
- The current local default in `/.brains` is:
  - `PyMuPDF` for default PDF parsing
  - `pdfplumber` as a table-aware fallback
  - `LangChain` for chunking
  - `LanceDB` for vector + FTS + hybrid retrieval
  - `Ollama` for local embeddings and optional reranking
  - `brains/sources/vault/` modules for markdown indexing over `UA/`, `EN/`, and root knowledge files
- This is the preferred default for the vault unless the task clearly needs:
  - better scientific-paper structure extraction (`Grobid`, `Docling`),
  - stronger scientific embedding models (`SPECTER2`, `SciBERT`),
  - or a different storage backend for scale / deployment constraints.
- When better scientific-paper structure extraction is needed without a separate service, prefer local `Docling` over `Grobid`.
- For markdown notes, keep the native vault parser as the default, but allow `Docling` when notes contain dense scientific structure such as tables, formulas, diagrams, or image-heavy sections.
- For vault markdown ingestion, prefer parser routing over one-size-fits-all parsing:
  - ordinary Obsidian notes -> native markdown parser
  - rich scientific notes with tables / formulas / diagrams -> `Docling` or `auto`

## Retrieval Quality Rules

- Optimize RAG around retrieval quality first: parser choice, chunking, metadata, candidate generation, reranking, and evaluation should be treated as a connected pipeline.
- For canonical vault indexing, prefer `index-vault --parser auto`.
- Treat `index-vault --parser docling` as a comparison or deep-debug mode unless the task explicitly requires a docling-only canonical vault index.
- The intended repository-specific behavior of `--parser auto` is:
  - route rich scientific markdown to `docling`,
  - keep simpler notes on the native parser,
  - reduce the runtime overhead of full-docling ingestion on every note.
- Keep all experimental or comparison index roots under `/.brains/.index/...`; do not leave repository-root `/.index` directories behind.
- Run a pre-clean step before chunking:
  - remove repeated PDF headers, footers, page numbers, and similar page furniture
  - remove markdown navigation-only lines and link-only related-note scaffolding when they do not add retrieval value
- For markdown notes that contain formulas, tables, code fences, or diagrams, use block-aware chunking so those structures are not split across chunks unless there is no other practical option.
- If a single table, code block, formula, or similarly special block grows beyond `chunk_size`, split it deterministically instead of sending an oversized embedding request downstream.
- Prefer chunk-level indexing over whole-document retrieval; use sections, paragraphs, or similarly meaningful passages instead of large document blobs.
- Keep chunk metadata rich and explicit. At minimum preserve stable source identity plus source-local context such as section, page, parser, language branch, and chunk-size diagnostics.
- When reranking is enabled, retrieve a wider candidate pool first and rerank that pool before cutting down to final `k`.
- Prefer hybrid retrieval as the default for broad knowledge search, then test vector-only or FTS-only only when corpus behavior justifies it.
- Use query-aware retrieval routing when the query shape is a strong signal:
  - exact path, quoted phrase, note title, or file-like lookup -> prefer `fts` or metadata-constrained retrieval
  - broad conceptual lookup -> prefer `hybrid`
- Do not treat `top-k` as a relevance guarantee. Prefer trimming weak hits with explicit score or distance thresholds when the backend returns usable ranking signals.
- Treat chunk-size tuning as empirical work. Adjust `chunk_size` and `chunk_overlap` against real queries and inspect manifest statistics instead of assuming one default fits every corpus.
- Any change that claims retrieval improvement should be evaluated on a small representative query set and compared against the prior behavior.
- Put retrieval diagnostics in generated artifacts and manifests under `/.brains/.index`; do not spill them into notes or governance files.
- Retrieval debugging should separate:
  - query routing decisions
  - raw retrieved candidates
  - threshold filtering
  - final context passed into generation
- When changing parsing, chunking, indexing, manifests, or retrieval/ranking:
  - rebuild the affected index from scratch,
  - run `check-index`,
  - inspect `manifest.json`, parser counts, block/chunk counts, warnings, and pointer behavior,
  - run retrieval probes against real notes or PDFs instead of relying only on tests.
- Retrieval evaluation must look beyond "the command succeeded":
  - verify that top hits point to the right note or PDF family,
  - watch for frontmatter leakage such as `cssclasses` or `tags`,
  - watch for code-block-heavy false positives,
  - inspect whether section paths and snippets remain useful for the query.
- Search commands should prefer the active index manifest's `embed_model` for query embedding unless the caller explicitly overrides the model. Do not assume one global embedding dimension across vault and PDF indexes.
- Treat transient Ollama embedding failures such as intermittent `HTTP 500` on `/api/embed` as retryable runtime issues before treating the index build as structurally broken.
- Phrase-style quoted queries may fail on FTS paths when the active LanceDB FTS index was not built with positional data. Prefer unquoted semantic queries unless phrase search is explicitly verified for the current index.
- If a runtime finding changes the practical workflow, update the `/.brains` documentation in the same change when it fits.

## Project Rules

- Use `uv` as the primary tool for Python environments, dependency management, and execution.
- Install `uv` with the official installer when needed:
  - macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Windows PowerShell: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
- Install Python with `uv` when a managed interpreter is needed:
  - `uv python install`
  - `uv python install 3.12`
- Use the Windows virtual environment at `.venv` as the single canonical local environment.
- Even when the agent is currently running from `WSL`, create, recreate, and sync `.venv` through Windows `cmd.exe` with `uv`.
- Do not run canonical `.venv` lifecycle commands from the Linux side of `WSL`; for this repository that prohibition covers `uv venv`, `uv sync`, `uv run`, and direct use of `.venv/bin/python`.
- Treat `.venv/bin/`, `.venv/lib/`, or `.venv/lib64/` as evidence of a broken environment in this repository, not as an acceptable alternative layout.
- If `.venv/Scripts/python.exe` is missing, or if Linux-style `.venv` directories appear beside it, stop and repair the environment before running indexing, health checks, linting, typing, or tests.
- Do not introduce or keep parallel canonical environments such as `.venvx`.
- In `cmd.exe`, call `uv` directly from `PATH`; do not hardcode an absolute path to `uv.exe`.
- When Docker is needed for local services or tooling, invoke it through Windows `cmd.exe` too.
- Do not hardcode the repository path in commands, docs, scripts, tests, or examples.
- Treat portable path usage as a must-have: prefer `%CD%`, relative paths from the current working directory, or placeholders like `<REPO_ROOT>`.
- Use `BaseSettings`-driven `pydantic` config under `config/` and `.env`.
- Keep repository-specific operational defaults in TOML instead of Python constants when they are expected to vary between repositories or vault layouts.
- In particular:
  - keep graph governance exclusions in `[graph].governance_files`,
  - keep explicit special mirror exceptions in `[graph].special_page_pairs`,
  - keep default health probes in `[health].pdf_probe_query` and `[health].vault_probe_query`.
- Keep the CLI on `Typer`; use `Rich` for user-facing output and `Loguru` for runtime logging.
- Virtual environments are local-only artifacts and must never be committed.
- Prefer running Python for `/.brains` through the Windows project environment:
  - `cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run ..."`
  - `cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv ..."`
- Prefer running Docker in the same style:
  - `cmd.exe /c "docker ..."`
- Prefer `uv add` over direct `pip install`.
- Prefer `uv venv` over manual `python -m venv`.
- `uvx` is for one-off external Python CLI tools that should not be installed into the project environment.
- `npx` is for one-off Node/npm CLI tools.
- Use `npx` for non-Python tools such as `markdownlint-cli`; do not route npm tools through `uvx`.
- When Node/npm tooling matters for local workflow compatibility, prefer invoking `npm` and `npx` through Windows `cmd.exe`.
- Distinguish the actual Node runtime before documenting markdownlint behavior:
  - current `WSL`-side `node` is `v18.19.1`,
  - current Windows-side `node` via `cmd.exe` is `v20.20.2`, and that Windows runtime is the canonical local runtime for this repository.
- Current checked markdownlint path:
  - Windows-side `cmd.exe /c "npx --yes markdownlint-cli ..."` is working and should be treated as the normal path.
- For `/.brains` helper scripts that belong to the normal local workflow, prefer portable Python wrappers over shell-only wrappers when practical.
- For literature PDF download/reindex workflow, treat `/.brains/scripts/fetch_literature_pdfs.py` as the canonical reusable wrapper around `brains fetch-pdfs --reindex`.
- On Windows, keep `torch` and `torchvision` pinned to the explicit PyTorch `cu128` index in `pyproject.toml` so `uv lock` / `uv sync` do not silently fall back to CPU-only wheels.
- Keep code changes in `/.brains` small, local, and automation-focused.
- Before adding or keeping a Python dependency, verify that it is actually needed by the current codebase.
- Prefer checking this explicitly via import search / usage search instead of assuming a package is still needed after refactors.
- If a direct dependency is no longer used, remove it from `pyproject.toml`, refresh `uv.lock`, and rerun tests.
- In Ruff `isort` settings, keep `known-first-party = ["brains"]`; do not leave template placeholders such as `your_package`.
- Do not make `pytest` re-run `ruff` or `mypy` indirectly; keep lint/type checks separate from the pytest suite.
- Default verification should be:
  - `uv run ruff check brains tests`
  - `uv run mypy brains`
  - targeted `uv run pytest ...`
- The checked-in pytest configuration already enables slow-test reporting and a faulthandler timeout for the full suite.
- When the whole suite is required, use the plain canonical command `uv run pytest tests -q`; do not add extra timing flags in routine runs unless you are debugging pytest itself.
- If GPU support matters for local ML tooling, verify it after `uv sync` with a direct `torch.cuda.is_available()` check from `.venv\\Scripts\\python.exe`.
- Treat `uv run mypy brains` as the canonical type-check command for this module.
- Keep the checked-in mypy configuration runnable as-is in the standard local environment; avoid relying on ad hoc flags for routine verification unless you are explicitly changing the mypy configuration.
- Keep `follow_imports = "skip"` as the default mypy policy unless a later verified change proves that full import following is stable in this repository.
- Reason: optional heavy dependency trees such as `docling`, `sentence-transformers`, `transformers`, and `torch` can cause very slow traversal or internal mypy failures in the Windows `.venv` workflow.
- If mypy appears to hang, first suspect third-party import traversal before assuming a local typing regression.
- For repeatable diagnosis, use `/.brains/scripts/diagnose_mypy_hang.py` instead of one-off shell probing.
- Do not remove the mypy import-skipping safeguards for those heavy third-party packages unless a real `uv run mypy brains` run succeeds after the change.
- If the canonical `.venv` becomes inconsistent, recover it in this order:
  - stop Windows processes still holding `.venv\\Scripts\\python.exe`,
  - remove `.venv`,
  - recreate it with `cmd.exe /c "cd /d %CD% && uv venv .venv --python 3.12"`,
  - resync with `cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv sync --all-groups --python 3.12"`,
  - verify with `cmd.exe /c "cd /d %CD% && .venv\\Scripts\\python.exe -V"`.
- Use full `uv run pytest tests -q` only when the whole suite is needed.
- Prefer adding code to the existing package slices:
  - `brains/config/`
  - `brains/shared/`
  - `brains/sources/pdf/`
  - `brains/sources/pdf/backends/`
  - `brains/sources/vault/`
  - `brains/research/`
  - `brains/mcp/tools/`
  - `brains/commands/`
- Do not reintroduce compatibility facades such as flat re-export modules when the canonical package API is already clear.
- Do not write generated index data into notes or governance files.
- Do not commit secrets, credentials, `.env` values, or `PII`.
- Do not commit machine-specific overrides in `config/local.toml`.
- Do not commit `.env`.

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
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brains"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run pytest tests/test_cli.py -q"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run ruff check brains tests"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run mypy brains"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run pytest tests -q"
```

## File Layout

- `pyproject.toml` defines the local `brains` project.
- Run the CLI through the Windows project interpreter at `.venv/Scripts/python.exe`.
- `config/brains.toml` holds committed defaults.
- `config/local.toml` is an optional ignored local override file.
- `.env` is an optional ignored dotenv override file.
- `brains/cli.py` is a thin Typer facade that registers commands from `brains/commands/`.
- `brains/config/` is the canonical configuration package for `BaseSettings`, settings sources, and path resolution.
- `brains/commands/` holds Typer command registration code.
- `brains/shared/` holds shared utilities used by multiple domains, including runtime helpers, retrieval helpers, formatting, and text utilities.
- Environment overrides should use nested names such as `BRAINS_OLLAMA__PROFILES__EMBEDDINGS__PREFERRED_MODEL`.
- Do not reintroduce inline fallback configs in `/.brains/scripts` for settings that already belong to `config/brains.toml`; helper scripts should read committed TOML defaults and optional `config/local.toml` overrides instead.
- `brains/sources/pdf/` contains parser routing, fetch, indexing, retrieval, and reranking logic for PDFs.
- `brains/sources/pdf/backends/` contains isolated parser backends (`PyMuPDF`, `pdfplumber`, optional `Grobid`, optional `marker`).
- `brains/sources/vault/` contains markdown file discovery, section splitting, indexing, retrieval, and related-note logic.
- `brains/research/` contains retrieval-bundle orchestration, memory handling, report formatting, and external-agent handoff text.
- `brains/research/` must not reintroduce local Ollama synthesis as the default research backend; `think` and `run_experiment` are retrieval-bundle builders for an external agent.
- `brains/mcp/tools/` is the canonical home for MCP note, search, and experiment handlers.
- Keep files readable: prefer extracting cohesive submodules before a file becomes long or mixed-responsibility.
- `README.md` explains how to use the local project.
- `.venv/` is local-only, canonical for `/.brains`, and must never be committed.
- `.index/` is for runtime-generated indexes, manifests, pointers, and search artifacts only.
- Do not store exported dependency snapshots or packaging artifacts there, such as `requirements.txt`, `constraints.txt`, lockfile copies, or similar temporary install files.

## Working Style

- Default to Python 3.12 via the local `uv` setup.
- Prefer deterministic scripts over ad hoc shell pipelines when logic will be reused.
- Keep outputs reproducible and scoped to repository needs.
- If a script updates vault content, make the target paths explicit and reviewable.
- Keep the modular structure stable; extend existing packages instead of adding new flat top-level helper files.
- Keep dependency hygiene strict: avoid stale direct dependencies and periodically audit `pyproject.toml` against actual imports.
- PDF search artifacts must stay under `/.brains/.index/pdf_search`.
- Vault markdown search artifacts must stay under `/.brains/.index/vault_search`.
- Research memory/session artifacts must stay under `/.brains/.index/research`.
- Under `WSL`, when the repository is mounted from `/mnt/c/...`, `LanceDB` may fail on the default `/.brains/.index/...` path.
- In that failure mode, keep the canonical default unchanged but rebuild the PDF index into `/tmp/obsidian-kb-pdf-index` and explicitly note that the active fallback artifacts are:
  - `/tmp/obsidian-kb-pdf-index/manifest.json`
  - `/tmp/obsidian-kb-pdf-index/lancedb`
- Also store the active fallback pointer in `/.brains/.index/pdf_search/active_index.json`.
- Apply the same rule to vault indexing when `index-vault` uses a fallback path:
  - fallback artifacts may live outside `/.brains/.index/vault_search`
  - store the active pointer in `/.brains/.index/vault_search/active_index.json`
- Under restricted sandbox environments, `LanceDB` may also hang during `connect()` or `open_table()` even when the fallback index under `/tmp/...` is valid.
- Use `brains check-index` to validate the active PDF or vault index, and make sure the command follows `active_index.json` when present.
- If `brains check-index` reports `status: timeout`, rerun it outside the sandbox before treating the index as corrupted.
