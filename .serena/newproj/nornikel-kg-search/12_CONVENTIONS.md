# Conventions

## Language

- Repository artifacts are English.
- User-facing UI can support Russian first.
- API field names are English snake_case.
- Stable IDs use typed prefixes: `mat_`, `exp_`, `reg_`, `prop_`, `src_`, `claim_`, `gap_`.

## Code Style

- Python: typed functions, Pydantic schemas, explicit exceptions.
- TypeScript: strict mode, typed API clients, no untyped response blobs.
- Avoid implicit global state.
- Keep provider-specific code behind interfaces.

## Domain Rules

- A measurement without unit is invalid.
- A claim without source span is invalid.
- An answer without evidence is a "not enough evidence" response, not a generated conclusion.
- DuckDB is authoritative for P0 facts and provenance; Qdrant is candidate retrieval only.
- Table rows and table cells are evidence units, not just Markdown text.
- Generated answer sentences without support IDs are rejected.
- Canonical graph writes require schema validation.
- Entity merge requires deterministic rule or reviewer approval.

## Provenance Rules

- Every fact-like node and relationship has source provenance.
- Source spans must be stable across re-indexing when the source version is unchanged.
- Extraction run IDs must be stored for reproducibility.
- Review decisions must be append-only audit events.

## API Rules

- Return structured errors.
- Return reproducibility IDs for QA and ingestion runs.
- Do source-label filtering before answer generation.
- Include validation status in evidence records.

## UI Rules

- The first screen is the workbench, not a landing page.
- Prioritize dense, scannable research workflows.
- Use tables for evidence and experiments.
- Use graph visualization only for meaningful entity neighborhoods.
- Never hide source evidence behind a generated summary.

## Documentation Rules

- Architecture decisions live in ADRs.
- Research sources live in source register or docs.
- Internal data samples must be synthetic or approved.
