<!-- Memory Metadata
Last updated: 2026-07-05
Last commit: f98c713 docs(ingest): record eight-shard dataeyes benchmark
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
- The runbook also records the verified 8-shard 300-file stress profile:
  300/300 in a 1341s max-shard wall clock, with 297 completed, 3 quarantined,
  0 failed files, and 0 provider retries.
- The 4-shard 40-file merge result includes 40 sources, 16,102 evidence spans,
  1,067 entities, 23,672 numeric facts, and 16,102 Qdrant points.
- The 8-shard 300-file merge result includes 299 unique sources, 92,118
  evidence spans, 5,500 entities, 8,322 relations, 155,143 numeric facts, and
  92,118 Qdrant points.

## Contracts

- Public docs must remain provider-neutral, but operational profiles can be captured in runbooks as verified evidence.
- New instruction docs must keep durable facts and avoid account-specific or ephemeral operational noise.
- All merges touching instruction docs should keep `.serena/memories` synchronized via post-task hooks.
