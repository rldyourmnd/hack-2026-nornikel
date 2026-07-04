<!-- Memory Metadata
Last updated: 2026-07-04
Last commit: a81edd1 Merge pull request #14 from rldyourmnd/perf/table-row-cap
Scope: README.md; AGENTS.md; .claude/CLAUDE.md; docs/deployment/; .serena/newproj/; .serena/plans/; .serena/reviews/
Area: DOCS
-->

# DOCS-01-PLANNING-SOURCE

## Purpose

Capture documentation precedence and how to use planning artifacts without treating old plans as current code truth.

## Source Of Truth

- Code/config/tests at `HEAD`: highest authority.
- `.claude/CLAUDE.md`: current operational notes for provider/runtime state.
- `AGENTS.md`: Codex instruction layer.
- `docs/deployment/full-ingest-runbook.md`: current ingest/swap procedure.
- `docs/deployment/nornikel-nddev.md`: stand deployment notes.
- `.serena/plans/`: historical and implementation plans; useful context, not automatic truth.
- `.serena/reviews/`: review/audit artifacts.
- `README.md`: product overview; provider section is stale at `a81edd1`.

## Current Behavior

Planning docs remain useful for rationale and prior review context. Current implementation truth is code + tests + runbook. `README.md` still contains Yandex/aliceai wording; prefer `.claude/CLAUDE.md`, `.env.example`, runtime code, and `docs/deployment/full-ingest-runbook.md` until README is refreshed.

## Invariants

- Do not copy stale planning statements into implementation without verifying against code.
- Keep `AGENTS.md` and `.claude/CLAUDE.md` separate first-class instruction docs.
- Store durable facts in `.serena/memories`; store plans in `.serena/plans`; do not store runtime snapshots as memories.

## Verification

- `rg` against code/config for any documented behavior before relying on it.
- `git log --oneline` for recent implementation provenance.
