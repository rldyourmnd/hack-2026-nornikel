<!-- Memory Metadata
Last updated: 2026-07-05
Last commit: 1db4c68 docs(instructions): note sharded ingest workflow
Scope: AGENTS.md; .claude/CLAUDE.md; docs/deployment/full-ingest-runbook.md
Area: DOCS
-->

# DOCS-01-INSTRUCTIONS

## Purpose

Track durable instruction/docs contract and the accepted source-of-truth order.

## Source Of Truth

- `AGENTS.md`: repository execution, risk, and deployment rules.
- `.claude/CLAUDE.md`: task-facing assistant instructions.
- `docs/deployment/full-ingest-runbook.md`: production ingest profile and measured benchmark results.

## Current Behavior

- `AGENTS.md` and `.claude/CLAUDE.md` now define the high-throughput ingest contract:
  each worker shard must use its own DuckDB file via `--shard-count`/`--shard-index`.
- `scripts/merge_duckdb_shards.py` is the canonical merge step before ledger swap.
- `docs/deployment/full-ingest-runbook.md` is the durable runbook source for shard commands and verified profile tuning.

## Verified Facts

- DataEyes profile baseline and optimized benchmarks were recorded in the runbook:
  - previous single-process DataEyes/MiniMax: 40/40 in 1439s;
  - single-process `gpt-5.4-mini` + `text-embedding-3-small`: 40/40 in 790s;
  - 4-shard variant: 40/40 in ~500s wall-clock with 0 failed files.
- Merge result includes 40 sources, 16,102 evidence spans, 1,067 entities, 23,672 numeric facts.
- Shared Qdrant collection point count was verified at 16,102.

## Contracts

- Public docs must remain provider-neutral, but operational profiles can be captured in runbooks as verified evidence.
- New instruction docs must keep durable facts and avoid account-specific or ephemeral operational noise.
- All merges touching instruction docs should keep `.serena/memories` synchronized via post-task hooks.

