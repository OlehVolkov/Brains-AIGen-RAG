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
- `find_related_notes`
- `read_note`
- `write_note`
- `create_mirror_note`
- `validate_note`
- `list_notes`
- `run_experiment`

Secondary interface when MCP is unavailable and the agent is operating inside the repository:

- `brains search-vault`
- `brains search`
- `brains think`
- `brains index-vault`
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
- `search_pdfs`
  - use for indexed PDF content under the local PDF corpus
  - use this before making claims about paper contents

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
  - use for multi-step reasoning, idea generation, experiment planning, or report-style outputs
  - use after retrieval, not instead of retrieval

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
- PDF index artifacts belong under `/.brains/.index/pdf_search`
- research memory and sessions belong under `/.brains/.index/research`

If the active index uses a fallback location outside `/.brains/.index/...`, rely on the active pointer files rather than guessing paths manually.

Use the repository tooling to validate indexes:

- `brains check-index --target vault`
- `brains check-index --target pdf`

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

Keep lint, typing, and tests separate:

- `uv run ruff check brains tests`
- `uv run mypy brains`
- targeted `uv run pytest ...`

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
