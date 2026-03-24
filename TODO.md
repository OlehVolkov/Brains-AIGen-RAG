# TODO

Working backlog for aligning `/.brains` implementation with the repository-level `BRAIN.md` workflow.

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

## GraphRAG Roadmap

Goal:

- add a note-centric graph layer alongside the existing vector/FTS retrieval stack;
- keep `LanceDB` as the semantic retrieval layer;
- use `NetworkX` for repository-grounded graph indexing, graph traversal, and explainable related-note expansion.

### Phase 1

Status:

- implemented

Implement a repository graph MVP with local artifacts and basic search.

Scope:

- add `brains/sources/graph/`
- build graph artifacts under `/.brains/.index/graph_search`
- index note-level and section-level structure from markdown notes
- add node types:
  - `note`
  - `section`
  - `tag`
  - `doi`
- add edge types:
  - `has_section`
  - `links_to`
  - `has_tag`
  - `cites_doi`
  - `mirror_of`
  - `same_top_level_domain`
- add CLI commands:
  - `index-graph`
  - `search-graph`
- keep retrieval rule-based and lexical/structural for the first iteration
- add targeted tests for graph indexing and graph search

### Phase 2

Status:

- baseline implemented
- current scope includes `hybrid-graph` search mode, seed-note graph expansion, and auto-routing for relation-style vault queries
- deeper reranking and broader graph-aware retrieval heuristics can still be refined

Integrate graph expansion with the existing vault retriever.

Scope:

- add `hybrid-graph` retrieval mode on top of `search-vault`
- use vector/FTS results as seed notes
- expand one or two hops through graph edges
- rerank merged results with structural bonuses
- add deterministic routing rules for:
  - semantic lookup
  - exact/path lookup
  - relation/path-style questions

### Phase 3

Status:

- implemented
- current scope includes `explain-path`, MCP graph tools, graph context inside `think` / `run_experiment`, and graph evidence on related-note candidates

Expose explainability and research-loop usage.

Scope:

- add `explain-path` style graph traversal output
- expose graph search/explanation through MCP
- add graph context into `run_experiment` / `think`
- improve related-note generation with graph evidence

### Phase 4

Status:

- baseline implemented
- current scope includes heuristic entity nodes, `defines_entity` / `mentions_entity` edges, entity-aware graph traversal, and stronger graph-oriented auto-routing
- richer extraction and aggregation can still be refined later if the heuristic entity layer proves useful on real queries

Expand beyond note-centric structure into richer domain/entity graph logic.

Scope:

- optional entity extraction
- richer typed edges between notes and extracted entities
- graph-assisted aggregation and reasoning
- stronger query routing once graph semantics prove useful on real tasks

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
- staged scientific PDF ingestion:
  - structure reconstruction
  - reference exclusion
  - citation/formula cleanup
  - structure-aware chunking
  - richer scholarly metadata
- staged scientific vault markdown ingestion:
  - parser routing (`native` vs `docling`)
  - block-aware chunking for tables, formulas, diagrams, and images
  - richer note metadata for explainability and filtering
  - benchmark-driven decision on when `docling` should beat the native parser
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

- add a reviewable note-update executor under `brains/research/` or `brains/sources/vault/`
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

- add a reusable sanitization layer in `brains/shared/`
- scan derived text before writing:
  - research session JSON
  - memory rows
  - fetch manifests
- generated note drafts
- support mask / redact behavior and warning logs

### 5. Build staged PDF ingestion for scientific retrieval quality

Current gap:

- PDF indexing still depends mainly on page-level parser output plus generic chunking.
- Scientific-paper structure is only partially preserved, and references are not handled as a first-class exclusion stage.

Needed:

- Stage 2: structure reconstruction
  - extract or infer:
    - title
    - abstract
    - section hierarchy (`H1` / `H2` / `H3`)
    - paragraphs
    - figure captions
    - tables
    - references
  - preserve `section_path` metadata instead of flattening everything into page text
  - exclude `references` from indexed retrieval chunks
- Stage 3: cleaning
  - remove inline citation noise such as `[1]`
  - remove author-year parenthetical citations when they are not semantically useful
  - continue removing repeated header/footer boilerplate
  - repair line-wrap artifacts
  - normalize formulas into stable placeholders when full structural math extraction is unavailable
- Stage 4: structure-aware chunking
  - chunk by semantic blocks and section boundaries instead of only fixed-size recursive splitting
  - keep tables and formulas intact
  - include section/title context in chunk text or chunk metadata
  - target roughly retrieval-friendly chunk sizes with controlled overlap
- Stage 5: richer metadata
  - add per-chunk fields such as:
    - `title`
    - `section`
    - `section_path`
    - `authors`
    - `year`
    - `source`
    - `block_kind`
    - `chunk_kind`
  - use that metadata for filtering, reranking, and explainability

Implementation notes:

- prefer local `docling` or `marker` when better structure extraction is needed without a separate service
- keep `grobid` optional only for users who explicitly want an external service
- keep `pymupdf` / `pdfplumber` support through heuristic reconstruction, not by pretending they are fully structured parsers
- keep staged artifacts reviewable through manifest counters and targeted tests

## Should Have

### 6. Add grounded-claim verification after synthesis

Current gap:

- repository grounding depends on prompts, not on post-generation validation.

Needed:

- detect claims in final synthesis that are unsupported by retrieved vault/PDF context
- attach evidence references per claim where possible
- fail closed or warn when unsupported synthesis exceeds a threshold

### 7. Add retrieval score thresholds instead of fixed `top-k` only

Current gap:

- search paths always return `k` hits when available, even when lower-ranked hits are weak or only loosely related.

Needed:

- add configurable minimum score / similarity thresholds on retrieval results
- support corpus-specific defaults for vault and PDF search
- surface when results were trimmed by threshold instead of silently returning weak matches
- keep `k` as an upper bound, not a guarantee of relevance

### 8. Upgrade research memory beyond lexical token overlap

Current gap:

- memory recall is only token-overlap on `query`, `summary`, and `final_answer`.

Needed:

- embedding-based memory retrieval
- recency weighting
- deduplication of near-identical sessions
- better provenance tracking to source sessions and source notes

### 9. Add planner/router logic for task-aware workflows

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
- route retrieval itself based on query type:
  - semantic concept lookup -> hybrid/vector search
  - exact term or file/path lookup -> FTS / metadata-constrained retrieval
  - fact extraction -> thresholded retrieval with stronger source traceability

Target MCP tool alignment:

- `run_experiment`

### 10. Add retrieval-quality evaluation and diagnostics

Current gap:

- retrieval changes are not measured on a stable set of representative queries.

Needed:

- create a small benchmark set of vault and PDF queries with expected relevant notes/chunks
- compare retrieval settings before and after chunking, parser, model, and filtering changes
- persist retrieval-debug artifacts under `/.brains/.index`:
  - query
  - effective mode
  - thresholds
  - retrieved candidates
  - final selected chunks
- keep retrieval debugging separate from generation debugging so failures are easier to isolate

### 11. Add stronger preprocessing and boilerplate removal

Current gap:

- indexing normalizes text, but retrieval quality still depends on parser output that may include repeated headers, footers, navigation text, and low-value boilerplate.

Needed:

- remove repeated PDF page boilerplate before chunking
- strip low-value markdown scaffolding when it does not help retrieval
- preserve structural cues such as headings, section names, and table context
- audit parser-specific cleanup rules instead of applying one generic cleanup path everywhere

### 12. Add retrieval caching and source-traceability improvements

Current gap:

- repeated retrieval work is not cached, and final outputs can expose stronger provenance than they do today.

Needed:

- cache query embeddings and optionally repeated retrieval results for local research loops
- include stable source references in final payloads:
  - note path
  - section
  - page/page label
  - parser context where relevant
- expose why a chunk was selected when diagnostic mode is enabled

### 13. Add reviewable note patch generation

Current gap:

- there is no intermediate artifact between synthesis and direct note edits.

Needed:

- generate proposed markdown patch payloads
- include target file, section anchor, and rationale
- make outputs easy to inspect before commit

## Nice To Have

### 14. Add continuous / scheduled automation

Current gap:

- all workflows are manual CLI invocations.

Needed:

- optional watch or scheduled mode for:
  - new PDF detection
  - periodic reindex
  - stale-note detection
  - literature refresh

### 15. Add coverage tracking for knowledge gaps

Current gap:

- no implementation measures what themes are covered vs missing in the vault.

Needed:

- track topic coverage across notes and PDFs
- identify weakly covered domains
- rank missing-note candidates

### 16. Add experiment-idea structuring

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
2. Build staged PDF ingestion with structure reconstruction, reference exclusion, and structure-aware chunking.
3. Add structured action plans to `think`.
4. Add note patch generation and explicit target resolution.
5. Add auto-linking and related-note updates.
6. Add bilingual mirror generation for note creation/update.
7. Add retrieval score thresholds and stronger preprocessing.
8. Add grounded-claim verification.
9. Add retrieval benchmark coverage and diagnostics.
10. Upgrade memory and task-aware routing.
11. Add caching and optional scheduled automation.

## Acceptance Criteria

`/.brains` can be considered aligned with `BRAIN.md` when it can:

- retrieve from vault and PDF indices
- expose `Stage 1` retrieval as stable MCP-accessible vault search
- expose `Stage 2` note and experiment tools
- synthesize grounded outputs
- generate or update mirrored `EN/UA` notes
- maintain `[[wiki-links]]` automatically
- redact secrets / `PII` before saving artifacts
- keep all generated metadata under `/.brains/.index`
- expose reviewable action artifacts instead of only free-text suggestions
