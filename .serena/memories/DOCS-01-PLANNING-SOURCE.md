<!-- Memory Metadata
Last updated: 2026-07-04
Last commit: 97407f4
Scope: README.md; AGENTS.md; .claude/CLAUDE.md; docs/deployment/; .serena/memories/
Area: DOCS
-->

# DOCS-01-PLANNING-SOURCE

## Purpose

Capture documentation precedence for the cleaned submission repository.

## Source Of Truth

- Code/config/tests at `HEAD`: highest authority.
- `README.md`: public product and architecture overview.
- `AGENTS.md`: repository engineering instructions.
- `.claude/CLAUDE.md`: project assistant notes.
- `docs/deployment/full-ingest-runbook.md`: current ingest/swap procedure.
- `docs/deployment/nornikel-nddev.md`: stand deployment notes.
- `.serena/memories/`: durable maintainer facts.

## Current Behavior

Historical planning and review archives were removed from the tracked submission
tree. Keep future planning concise and either update the public docs directly or
store current durable facts in `.serena/memories/`.

## Invariants

- Do not copy stale planning statements into implementation without verifying against code.
- Keep `AGENTS.md` and `.claude/CLAUDE.md` separate first-class instruction docs.
- Store durable facts in `.serena/memories`; do not store runtime snapshots, session transcripts, secrets, or account-specific operational history.

## Verification

- `rg --hidden` against code/config/docs for documented behavior before relying on it.
- `git log --oneline` for implementation provenance.
