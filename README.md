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
- search PDF content with optional reranking over a wider candidate pool
- build external-agent retrieval bundles through `think`
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

Environment invariants:

- `.venv` is the single canonical local environment and it must be the Windows layout with `.venv/Scripts/python.exe`
- from `WSL`, create, recreate, sync, and verify `.venv` through `cmd.exe`, not through `.venv/bin/python`
- if `.venv/bin/`, `.venv/lib/`, or `.venv/lib64/` appear, treat that as a broken state and repair the environment before running indexing or verification
- when Node/npm tooling matters for local workflow compatibility, prefer invoking `npm` and `npx` through Windows `cmd.exe`
- distinguish the actual Node runtime before documenting markdownlint behavior:
  - current `WSL`-side `node` is `v18.19.1`
  - current Windows-side `node` via `cmd.exe` is `v20.20.2`, and that Windows runtime is the canonical local runtime for this repository
- current checked markdownlint path:
  - Windows-side `cmd.exe /c "npx --yes markdownlint-cli ..."` is working and should be treated as the normal path
- recovery note:
  - do not launch multiple Windows-side `npx` installs in parallel against the same shared cache
  - if `%LocalAppData%\\npm-cache\\_npx` starts producing `TAR_ENTRY_ERROR`, `EPERM`, or `MODULE_NOT_FOUND`, clear that `_npx` directory and rerun the command once, sequentially

Recovery sequence for a broken canonical `.venv`:

1. stop Windows processes still holding `.venv/Scripts/python.exe`
2. remove `.venv`
3. recreate it with `cmd.exe /c "cd /d %CD% && uv venv .venv --python 3.12"`
4. resync it with `cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv sync --all-groups --python 3.12"`
5. verify it with `cmd.exe /c "cd /d %CD% && .venv\\Scripts\\python.exe -V"`

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
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brains index-vault --parser auto"
```

Canonical default for this repository:

- use `index-vault --parser auto` for the main vault index
- use `index-vault --parser docling` for parser comparison, rich-markdown debugging, or explicit docling validation runs
- keep comparison roots under `/.brains/.index/...` such as `/.brains/.index/vault_search_auto` or `/.brains/.index/vault_search_docling`
- do not leave repository-root `/.index` directories behind after experiments

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brains search-vault \"pairformer\" --mode hybrid"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brains search-vault \"how is pairformer related to diffusion module\" --mode auto"
```

- `search-vault --mode auto` can route relation-style queries into `hybrid-graph`
- auto routing also prefers `hybrid-graph` for more graph-semantics phrasing such as `between X and Y`, `shared`, `common`, or `bridge`
- `search-vault --mode hybrid-graph` keeps the normal vault retriever as the seed stage and then expands through the repository graph

### Note Graph

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brains index-graph"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brains search-graph \"pairformer\" --max-hops 1"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brains explain-path \"Pairformer\" \"Diffusion Module\" --max-hops 2"
```

- `index-graph` builds a note-centric `NetworkX` graph from markdown notes, sections, wiki-links, mirror pairs, tags, and DOI references
- the graph now also includes a lightweight heuristic entity layer built from mirrored note titles and note mentions
- graph artifacts live under `/.brains/.index/graph_search`
- `search-graph` is for explainable repository-relationship lookup, not a replacement for semantic vector retrieval
- `explain-path` returns an explicit note-to-note graph explanation with edge types and hop count

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

Portable helper wrapper for the same workflow:

```bash
python3 .brains/scripts/fetch_literature_pdfs.py
```

Use this Python wrapper when you want a reusable local helper around `fetch-pdfs --reindex` without relying on a shell-specific script. Extra CLI flags are forwarded to `brains fetch-pdfs`.

### Research

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brains think \"summarize the main retrieval gaps in this vault\""
```

- `think` now prepares a retrieval bundle for an external agent instead of running a local Ollama synthesis step
- the bundle includes graph context and short graph path explanations when the vault results expose connected notes
- `find_related_notes` can now attach graph evidence for candidate note relationships

### MCP

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brains mcp --transport stdio"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brains mcp --transport streamable-http --host 127.0.0.1 --port 8000"
```

- MCP now exposes `search_graph` for structural graph retrieval
- MCP now exposes `explain_path` for explicit graph path explanations between notes

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
3. prepare a bundle with `think` or `run_experiment`
4. synthesize outside `/.brains` with the external agent
5. write back through `write_note` when an explicit update is needed
6. refresh or validate indexes only when retrieval state changed

## Configuration

Default config lives in:

- `config/brains.toml`

Local overrides belong in:

- `config/local.toml`
- `.env`

Environment variables use the `BRAINS_` prefix, for example:

- `BRAINS_OLLAMA__PROFILES__EMBEDDINGS__PREFERRED_MODEL`
- `BRAINS_OLLAMA__BASE_URL`
- `BRAINS_PDF__INDEX_ROOT`
- `BRAINS_VAULT__INDEX_ROOT`
- `BRAINS_GRAPH__GOVERNANCE_FILES`
- `BRAINS_HEALTH__VAULT_PROBE_QUERY`
- `BRAINS_RESEARCH__VAULT_K`

Repository-specific graph and health defaults now live in TOML as well:

- `[graph].governance_files` controls which broad governance pages are excluded from graph seeding and entity extraction
- `[graph].special_page_pairs` controls explicit mirror pairs such as `Home.md` ↔ `UA/Головна.md`
- `[health].pdf_probe_query` and `[health].vault_probe_query` define the default `check-index` probes when the CLI call does not pass `--query`

## Technology Choices

Current default stack:

- `Typer` for CLI
- `Rich` for CLI output
- `Loguru` for logging
- `PyMuPDF` as the default PDF parser
- `pdfplumber` as a table-aware fallback
- `Docling` as the preferred local no-service option when stronger PDF structure extraction is needed
- native vault markdown parsing as the default for ordinary notes
- `Docling` as an optional vault markdown parser for notes with dense scientific structure
- `LangChain` for chunking
- `LanceDB` for vector + FTS retrieval
- `Ollama` for local embeddings and optional reranking

Current Ollama-oriented model defaults:

- primary embeddings: `bge-m3:latest`
- embedding fallbacks: `bge-large:latest`, then `nomic-embed-text:latest`, then lighter optional names such as `e5-small:latest` / `bge-small:latest` when available
- lightweight embedding profile: prefer `e5-small:latest`, but fall back to `nomic-embed-text:latest` or the installed BGE family instead of failing
- multilingual embedding profile: prefer `bge-m3:latest`
- practical reranker stack: `BAAI/bge-reranker-large` for cross-encoder reranking, with local Ollama family tracking via `qllama/bge-reranker-large:q8_0`

## Retrieval Guidance

Use these defaults unless a task proves they are wrong:

- pre-clean source text before chunking: strip repeated PDF page furniture and markdown navigation-only scaffolding
- index meaningful passages, not whole documents
- preserve retrieval metadata such as source, section/page context, parser, and chunk diagnostics
- for markdown notes with tables, formulas, or diagrams, prefer `index-vault --parser auto` or `index-vault --parser docling`
- keep block-heavy markdown structures intact during chunking instead of splitting them with fixed character windows
- if a single special block still exceeds `chunk_size`, split it deterministically instead of sending an oversized embedding payload
- start with `--mode hybrid`
- use `--mode auto` when queries mix exact lookups and semantic lookups in the same workflow
- when using `--reranker rrf`, `--reranker cross-encoder`, or `--reranker ollama`, keep `--fetch-k` comfortably above final `--k`
- use `--min-score` or `--max-distance` when weak tail results are worse than returning fewer hits
- let search use the active index manifest's `embed_model` by default; do not assume vault and PDF indexes share the same embedding dimension
- treat intermittent Ollama `/api/embed` failures as retryable before concluding that indexing is broken
- when full-corpus embedding on `bge-m3` or `bge-large` fails mid-run, prefer automatic fallback to the next configured embedding model over abandoning the reindex
- avoid quoted phrase queries unless the active FTS index is known to support positions; plain-text semantic queries are the safer default
- inspect `manifest.json` after reindexing to review chunk counts and chunk-size statistics before changing chunking defaults
- treat retrieval changes as measurable: compare them on a small representative query set before keeping them

Model management helpers:

```bash
python3 .brains/scripts/check_ollama_models.py --json-output
```

```bash
python3 .brains/scripts/ensure_ollama_models.py --json-output
```

Use them to confirm which Ollama models are installed before large reindex jobs. They are standalone stdlib scripts on purpose, so they still work even when the `/.brains` Python environment is not active.

## Verification

Default verification flow:

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run ruff check brains tests"
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run mypy brains"
```

Mypy guidance for this repository:

- `uv run mypy brains` is the canonical type-check command
- the checked-in configuration should remain runnable without extra ad hoc flags during routine verification
- `follow_imports = "skip"` is intentional here because heavy optional dependency trees such as `docling`, `sentence-transformers`, `transformers`, and `torch` can make full import traversal unstable or unreasonably slow
- if mypy appears to hang, diagnose third-party import traversal first
- for repeatable diagnosis, use `/.brains/scripts/diagnose_mypy_hang.py`

PyTorch/CUDA guidance:

- `torch` and `torchvision` are pinned to the explicit PyTorch `cu128` index on Windows so `uv lock` / `uv sync` keep a GPU-enabled build in the canonical `/.venv`
- after environment rebuilds, verify GPU access with a direct `torch.cuda.is_available()` probe from `.venv\\Scripts\\python.exe`

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run pytest tests/test_cli.py -q"
```

Run full test suite only when needed:

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run pytest tests -q"
```

- the checked-in pytest config already reports the slowest tests and enables a faulthandler timeout for the full suite
- use the plain full-suite command above before adding extra timing/debug flags

For indexing, parsing, chunking, manifest, or retrieval changes, default verification is broader than unit tests:

1. rebuild the affected index from scratch;
2. run `brains check-index` on the rebuilt target;
3. inspect `manifest.json`, parser counts, chunk counts, warnings, and pointer behavior;
4. run representative retrieval probes on real notes or PDFs;
5. compare the new behavior against the prior workflow before keeping the change.

When evaluating retrieval quality, check for:

- wrong note family in top hits,
- frontmatter leakage such as `cssclasses` or `tags`,
- code-block-heavy false positives,
- poor section-path or snippet quality.

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
