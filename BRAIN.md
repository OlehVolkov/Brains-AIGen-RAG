# BRAIN.md

Guide for external agents that need to use this repository's local RAG + MCP stack.

This project is brand-neutral. It is intended for local knowledge bases, with Obsidian vaults as the primary use case in this repository.

## Purpose

Use this repository to:

- search indexed markdown knowledge
- search indexed PDFs
- read notes by repository-relative path
- write notes in a controlled way
- run multi-step local research synthesis
- maintain local indexes and derived artifacts

This repository is not the knowledge base itself. It is the local tooling layer around a knowledge base.

## Source Of Truth

Treat hand-authored repository content as the source of truth.

- notes and governance files are authoritative
- `/.brains/.index` is derived data only
- search results, embeddings, manifests, and pointers are implementation artifacts
- do not treat generated artifacts as canonical knowledge

If the knowledge base uses a bilingual or otherwise structured layout, preserve that layout. Do not invent a parallel note hierarchy just because the tooling could support one.

## Default Agent Workflow

For knowledge work, follow this order:

1. Retrieve relevant context first.
2. Read the exact target notes before editing.
3. Synthesize only after retrieval.
4. Edit notes or code only after grounding the task in repository content.
5. Rebuild or validate indexes only through this repository's tooling.

In short: retrieval first, synthesis second, edits last.

## Preferred Interfaces

External agents should prefer the MCP tool surface when available.

Primary interface:

- `search_vault`
- `search_pdfs`
- `search_graph`
- `explain_path`
- `find_related_notes`
- `read_note`
- `write_note`
- `create_mirror_note`
- `validate_note`
- `list_notes`
- `run_experiment`

Secondary interface when MCP is unavailable and the agent is operating inside the repository:

- `brains search-vault`
- `brains search-graph`
- `brains explain-path`
- `brains search`
- `brains think`
- `brains index-vault`
- `brains index-graph`
- `brains index`
- `brains check-index`

Do not bypass these interfaces when the task depends on:

- active index pointers
- fallback index roots
- repository-specific note filtering
- repository-specific path rules
- grounded note selection before synthesis

## MCP Usage

Use MCP as the canonical contract for repository-grounded operations.

### Retrieval

- `search_vault`
  - use for markdown notes and knowledge-base content
  - prefer this before manually scanning many files
  - use `mode=hybrid-graph` when the query is about relationships, paths, or how notes connect
- `search_pdfs`
  - use for indexed PDF content under the local PDF corpus
  - use this before making claims about paper contents
- `search_graph`
  - use when you need repository-relationship evidence instead of semantic similarity only
  - prefer it for note-to-note navigation, mirror checks, and structural neighborhood lookup
- `explain_path`
  - use when you need an explicit graph path between two notes or note-like queries
  - prefer it for explainability, related-note evidence, and path-style questions

### Note Operations

- `read_note`
  - use before editing an existing note
- `list_notes`
  - use when locating candidate notes, mirrors, or branches
- `find_related_notes`
  - use when extending an existing note and you need candidate related links
- `write_note`
  - use for controlled note creation or updates
  - prefer explicit target paths
- `create_mirror_note`
  - use when the repository expects a mirrored branch note and the target path is explicit
- `validate_note`
  - use after creating or editing a note when you need a structural sanity check

### Research Synthesis

- `run_experiment`
  - use for reproducible retrieval bundles that an external agent will synthesize
  - use after retrieval, not instead of retrieval
  - expect it to include vault, graph, PDF, memory context, and agent handoff text when available
- `brains think`
  - use for the same retrieval-bundle workflow from the local CLI
  - do not treat it as a local LLM synthesis stage
  - do not reintroduce a local Ollama chat model as the default backend for this workflow

## Retrieval Rules

When answering repository questions:

- use local search before answering when indexes exist
- ground conclusions in repository content
- avoid unsupported extrapolation
- prefer note paths and snippets over vague summaries
- connect conclusions back to existing notes

Manual file traversal is acceptable for very small targeted edits. It is not the default mode for research or large knowledge-maintenance tasks.

## Editing Rules

When modifying notes:

- preserve the existing knowledge-base structure
- prefer updating existing notes over duplicating content
- keep automation logic out of the note tree
- keep generated artifacts out of the note tree
- use repository-relative paths
- verify that no secrets, credentials, `.env` values, or personal data are written into versioned files

When modifying this tooling:

- keep logic in the `brains/` package
- keep generated artifacts under `/.brains/.index`
- preserve the modular package layout
- avoid reintroducing flat compatibility wrappers when the canonical package API is already clear

## Indexing Rules

This repository uses local indexes for vault and PDF retrieval.

- markdown index artifacts belong under `/.brains/.index/vault_search`
- repository graph artifacts belong under `/.brains/.index/graph_search`
- PDF index artifacts belong under `/.brains/.index/pdf_search`
- research memory and sessions belong under `/.brains/.index/research`
- prefer `brains index-vault --parser auto` for the canonical vault index
- use `brains index-graph` for the note-centric repository graph built from sections, wiki-links, mirrors, tags, and DOI references
- expect the graph index to also contain a lightweight heuristic entity layer derived from mirrored note titles and note mentions
- treat full `brains index-vault --parser docling` runs as verification/comparison runs unless the task explicitly needs a docling-only canonical index
- keep experimental comparison roots under `/.brains/.index/...`; do not leave repository-root `/.index` directories behind

If the active index uses a fallback location outside `/.brains/.index/...`, rely on the active pointer files rather than guessing paths manually.

Use the repository tooling to validate indexes:

- `brains check-index --target vault`
- `brains check-index --target pdf`

When changing parsing, chunking, retrieval, ranking, manifests, or pointer behavior:

1. rebuild the affected index from scratch;
2. run `brains check-index` on the rebuilt target;
3. inspect the generated `manifest.json` and debug output;
4. run representative retrieval queries against real notes or PDFs;
5. confirm that no unintended fallback pointer or stray index root remains.

Judge retrieval quality by relevance, not only by successful execution:

- confirm that the top hits point to the expected note or PDF family;
- watch for frontmatter leakage such as `cssclasses` or `tags`;
- watch for code-block-heavy false positives;
- inspect whether section paths and snippets are useful for the query.
- when using `search-graph`, confirm that top hits are explainable through concrete note relationships rather than only broad domain expansion.
- when entity-driven graph hits appear, confirm that they are anchored in meaningful note-title entities rather than generic navigation pages.
- when using `search-vault --mode hybrid-graph`, confirm that graph-expanded notes improve coverage without displacing the best seed hits.
- prefer the active index manifest's `embed_model` for query embeddings unless a task explicitly overrides it; vault and PDF indexes may legitimately use different embedding models.
- if Ollama embedding calls fail with transient `HTTP 500`-style errors during indexing, retry before treating the corpus or index as broken.
- for large indexing jobs, prefer a model ladder rather than a single hard requirement: `bge-m3` first, then `bge-large`, then `nomic-embed-text` as a pragmatic fallback if the stronger models fail or are absent.
- keep lightweight embedding intents separate from the canonical manifest model: `e5-small` / `bge-small` are allowed targets, but if they are unavailable locally the workflow should degrade to a smaller installed embedding model instead of aborting.
- treat `BAAI/bge-reranker-large` as the practical high-quality reranker in `brains`; local Ollama reranker-family models are tracked for availability, but this repository should not assume an Ollama native rerank endpoint exists.
- avoid assuming quoted phrase queries will work on every active FTS index; if phrase search is important, verify it explicitly for the current index first.

If an index health check reports a timeout under sandboxed or WSL-mounted environments, do not assume corruption immediately. Re-run the validation in a less restricted environment first.

## Environment And Execution

Python tooling in this repository uses `uv`.

Preferred patterns:

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run python -m brains ..."
```

```bash
cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv run brains ..."
```

Use:

- `uv run` for project commands
- `uv add` for dependencies
- `uv venv` for environment creation
- `uvx` for one-off external Python CLIs
- `npx` for one-off Node-based CLIs
- when Node/npm tooling matters for local workflow compatibility, prefer invoking `npm` and `npx` through Windows `cmd.exe`

Environment invariants for this repository:

- `.venv` is the single canonical local environment and it must be the Windows layout with `.venv/Scripts/python.exe`
- when operating from `WSL`, create, recreate, sync, and verify that environment through `cmd.exe`, not through `.venv/bin/python`
- if `.venv/bin/`, `.venv/lib/`, or `.venv/lib64/` appear, treat that as a broken environment and repair it before running local checks or indexing
- distinguish the actual Node runtime before documenting markdownlint behavior:
  - current `WSL`-side `node` is `v18.19.1`
  - current Windows-side `node` via `cmd.exe` is `v20.20.2`, and that Windows runtime is the canonical local runtime for this repository
- current checked markdownlint path:
  - Windows-side `cmd.exe /c "npx --yes markdownlint-cli ..."` is working and should be treated as the normal path
- recovery note:
  - do not launch multiple Windows-side `npx` installs in parallel against the same shared cache
  - if `%LocalAppData%\\npm-cache\\_npx` starts producing `TAR_ENTRY_ERROR`, `EPERM`, or `MODULE_NOT_FOUND`, clear that `_npx` directory and rerun the command once, sequentially

If the canonical `.venv` becomes inconsistent, recover it in this order:

1. stop Windows processes still holding `.venv/Scripts/python.exe`
2. remove `.venv`
3. recreate it with `cmd.exe /c "cd /d %CD% && uv venv .venv --python 3.12"`
4. resync it with `cmd.exe /c "cd /d %CD% && set \"UV_PROJECT_ENVIRONMENT=.venv\" && uv sync --all-groups --python 3.12"`
5. verify it with `cmd.exe /c "cd /d %CD% && .venv\\Scripts\\python.exe -V"`

Keep lint, typing, and tests separate:

- `uv run ruff check brains tests`
- `uv run mypy brains`
- targeted `uv run pytest ...`
- the checked-in pytest config already reports the slowest tests and enables a faulthandler timeout for the full suite
- when a full run is needed, use `uv run pytest tests -q` as-is before adding extra diagnostic flags

PyTorch/CUDA guidance for this repository:

- the Windows `/.venv` is pinned to PyTorch `cu128` wheels through `pyproject.toml`
- do not remove that explicit index/source mapping unless you have verified that `uv sync` still preserves a working GPU build
- after changing Python dependencies or rebuilding the environment, verify GPU status with a direct `torch.cuda.is_available()` check

Before large reindex or retrieval tuning work, check local Ollama model availability with:

```bash
python3 .brains/scripts/check_ollama_models.py --json-output
```

If the required model family is absent, bootstrap it with:

```bash
python3 .brains/scripts/ensure_ollama_models.py --json-output
```

Those helpers are intentionally standalone and should keep working even when the `/.brains` environment itself is not fully initialized.

For the standard literature-download workflow, use:

```bash
python3 .brains/scripts/fetch_literature_pdfs.py
```

Pass through any extra `fetch-pdfs` flags after it. This Python wrapper is the canonical reusable entrypoint for `brains fetch-pdfs --reindex` and should remain portable by resolving `uv` from `PATH` or `UV_BIN`.

Configuration notes:

- keep repository-specific governance filtering in `[graph].governance_files`
- keep explicit mirror exceptions in `[graph].special_page_pairs`
- keep default health-check probes in `[health].pdf_probe_query` and `[health].vault_probe_query`
- keep the Ollama helper scripts TOML-driven; do not reintroduce fallback inline configs inside the scripts
- when adapting `brains` to another repository, prefer changing those TOML sections first instead of patching Python constants

Typing guidance for this repository:

- treat `uv run mypy brains` as the canonical type-check command
- keep the checked-in mypy configuration runnable without extra ad hoc flags during normal verification
- keep `follow_imports = "skip"` as the default policy unless a later verified change proves full import following is stable here
- heavy optional dependency trees such as `docling`, `sentence-transformers`, `transformers`, and `torch` are the main reason to avoid full import traversal by default
- if mypy appears to hang, diagnose import traversal before assuming a local typing regression
- prefer the reusable helper script `/.brains/scripts/diagnose_mypy_hang.py` for mypy-hang diagnosis

## Typical External-Agent Playbooks

### Answer A Knowledge Question

1. Run `search_vault`.
2. Run `search_pdfs` if the question may depend on source documents.
3. Read the most relevant notes with `read_note`.
4. Synthesize the answer.
5. Cite note paths explicitly in the response when useful.

### Update A Note Safely

1. Run `search_vault` or `list_notes` to find the target.
2. Run `read_note`.
3. Decide whether to update an existing note or create a new explicit target path.
4. Run `write_note`.
5. If the task materially changes the knowledge base, consider refreshing the relevant index.

### Generate Research Ideas

1. Retrieve with `search_vault`.
2. Retrieve with `search_pdfs` if papers matter.
3. Run `run_experiment`.
4. Convert strong outputs into note updates only after reviewing grounding.

### Repair Retrieval

1. Run `brains check-index --target vault` or `--target pdf`.
2. If artifacts are missing, rebuild through the official indexing commands.
3. If a timeout occurs in a restricted environment, validate again outside that environment before declaring the index broken.

## What External Agents Must Not Do

- do not treat generated index artifacts as canonical knowledge
- do not rewrite the repository structure to fit a different vault model
- do not invent a parallel note tree
- do not skip retrieval and answer from guesswork
- do not write secrets or personal data into tracked files
- do not hand-edit index manifests or pointer files unless explicitly working on index internals

## Expected Output Style

When reporting results:

- be concise
- be explicit about what was retrieved
- separate retrieved facts from inferences
- name the note paths or PDF sources that drove the answer
- state when an answer depends on index state or fallback paths

## Short Version

If you are an external agent, use this stack like this:

1. retrieve with MCP
2. read the exact notes
3. synthesize from repository content
4. edit only with explicit paths
5. keep generated data in `/.brains/.index`

This is a repository-grounded RAG + MCP toolkit for local knowledge bases, especially Obsidian-style vaults.
