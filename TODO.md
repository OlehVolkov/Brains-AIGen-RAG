# TODO

Working backlog for aligning `/.brain` implementation with the repository-level `BRAIN.md` workflow.

## Status Summary

Implemented well:

- PDF fetch, indexing, search, and index health-checks
- Vault markdown indexing, search, and index health-checks
- WSL fallback pointer handling via `active_index.json`
- Multi-role `think` loop with `researcher`, `coder`, `reviewer`, and optional reflection
- Research memory/session persistence
- baseline `MCP Stage 2` tool surface:
  - `read_note`
  - `write_note`
  - `list_notes`
  - `run_experiment`
- minimal knowledge-base and PDF `MCP` set:
  - `search_vault`
  - `search_pdfs`
  - `find_related_notes`
  - `create_mirror_note`
  - `validate_note`

## MCP Roadmap

### Stage 1

Implemented:

- `RAG` over the vault via vault search
- local retrieval over indexed markdown knowledge content

Current practical entry point:

- `search-vault`

### Stage 2

Implemented baseline tools:

- `read_note`
- `write_note`
- `list_notes`
- `run_experiment`

Stage 2 intent:

- expose a stable tool layer over the existing vault structure
- move from retrieval-only workflows to read/write execution on notes
- support experiment execution as a first-class tool instead of free-text planning only

Still missing above the baseline tool surface:

- auto-link generation
- bilingual mirror automation
- grounded note patch planning
- secrets / `PII` redaction hooks on all write paths

Current minimal implemented set for practical vault/PDF work:

- `search_vault`
- `search_pdfs`
- `find_related_notes`
- `create_mirror_note`
- `validate_note`

Missing or only partially implemented:

- automatic `ACT` stage
- automatic `LINK` stage
- PDF-to-summary-to-note pipeline
- mirrored `EN/UA` note creation and synchronization from research outputs
- secrets / `PII` verification before saving derived artifacts
- continuous automation loop
- stronger research memory model
- grounded-claim enforcement after synthesis

## Must Have

### 1. Implement `ACT` as real execution, not only synthesis text

Current gap:

- `think` produces analysis and recommendations but does not execute note updates or repository changes.

Needed:

- add a reviewable note-update executor under `brain/research/` or `brain/sources/vault/`
- support explicit write targets for:
  - creating a note
  - updating an existing note
  - appending summary sections
  - updating related-note blocks
- emit machine-readable patch plans before applying changes

Suggested outputs:

- structured action plan JSON
- proposed target paths
- generated markdown payloads
- optional dry-run diff mode

Target MCP tool alignment:

- `write_note`
- `run_experiment`

### 2. Implement `LINK` as automatic wiki-link generation

Current gap:

- no code currently creates or updates `[[wiki-links]]` or `Related Notes` blocks from research results.

Needed:

- extract candidate note references from retrieved vault hits
- map them to canonical vault paths
- generate `[[path|label]]` links where allowed
- update `## Related Notes` / `## Пов'язані нотатки` sections
- avoid duplicate or circular low-value links

Target MCP tool alignment:

- `read_note`
- `write_note`
- `list_notes`

### 3. Build end-to-end `PDF -> summary -> mirrored notes`

Current gap:

- PDFs can be fetched and indexed, but not transformed into repository notes automatically.

Needed:

- summarize indexed PDFs into note-ready sections
- classify whether content belongs in an existing note or a new note
- create mirrored `EN/UA` note payloads in one workflow
- preserve bilingual parity for sections, tables, formulas, and practical blocks

Target MCP tool alignment:

- `read_note`
- `write_note`
- `list_notes`

### 4. Add secrets / `PII` scanning before saving artifacts

Current gap:

- manifests, research sessions, and memory rows are written without a redaction pass.

Needed:

- add a reusable sanitization layer in `brain/shared/`
- scan derived text before writing:
  - research session JSON
  - memory rows
  - fetch manifests
  - generated note drafts
- support mask / redact behavior and warning logs

## Should Have

### 5. Add grounded-claim verification after synthesis

Current gap:

- repository grounding depends on prompts, not on post-generation validation.

Needed:

- detect claims in final synthesis that are unsupported by retrieved vault/PDF context
- attach evidence references per claim where possible
- fail closed or warn when unsupported synthesis exceeds a threshold

### 6. Upgrade research memory beyond lexical token overlap

Current gap:

- memory recall is only token-overlap on `query`, `summary`, and `final_answer`.

Needed:

- embedding-based memory retrieval
- recency weighting
- deduplication of near-identical sessions
- better provenance tracking to source sessions and source notes

### 7. Add planner/router logic for task-aware workflows

Current gap:

- all `think` runs use roughly the same retrieval path and role sequence.

Needed:

- classify tasks such as:
  - literature synthesis
  - note expansion
  - experiment generation
  - code generation
  - PDF ingestion follow-up
- route each class to a different retrieval/action strategy

Target MCP tool alignment:

- `run_experiment`

### 8. Add reviewable note patch generation

Current gap:

- there is no intermediate artifact between synthesis and direct note edits.

Needed:

- generate proposed markdown patch payloads
- include target file, section anchor, and rationale
- make outputs easy to inspect before commit

## Nice To Have

### 9. Add continuous / scheduled automation

Current gap:

- all workflows are manual CLI invocations.

Needed:

- optional watch or scheduled mode for:
  - new PDF detection
  - periodic reindex
  - stale-note detection
  - literature refresh

### 10. Add coverage tracking for knowledge gaps

Current gap:

- no implementation measures what themes are covered vs missing in the vault.

Needed:

- track topic coverage across notes and PDFs
- identify weakly covered domains
- rank missing-note candidates

### 11. Add experiment-idea structuring

Current gap:

- experiment ideas are free text only.

Needed:

- structured experiment cards with:
  - hypothesis
  - dataset
  - metrics
  - baseline
  - expected failure modes

## Suggested Implementation Order

1. Add sanitization and redaction hooks for all write paths.
2. Add structured action plans to `think`.
3. Add note patch generation and explicit target resolution.
4. Add auto-linking and related-note updates.
5. Add bilingual mirror generation for note creation/update.
6. Add grounded-claim verification.
7. Upgrade memory and task routing.
8. Add optional scheduled automation.

## Acceptance Criteria

`/.brain` can be considered aligned with `BRAIN.md` when it can:

- retrieve from vault and PDF indices
- expose `Stage 1` retrieval as stable MCP-accessible vault search
- expose `Stage 2` note and experiment tools
- synthesize grounded outputs
- generate or update mirrored `EN/UA` notes
- maintain `[[wiki-links]]` automatically
- redact secrets / `PII` before saving artifacts
- keep all generated metadata under `/.brain/.index`
- expose reviewable action artifacts instead of only free-text suggestions
