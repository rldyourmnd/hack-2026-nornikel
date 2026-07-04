<!-- Memory Metadata
Last updated: 2026-07-05
Last commit: 1db4c68 docs(instructions): note sharded ingest workflow
Scope: AGENTS.md; .claude/CLAUDE.md
Area: CODEX
-->

# CODEX-01-PLUGIN-CANON

## Purpose

Record durable Codex integration and lifecycle contract for this repository.

## Source Of Truth

- `AGENTS.md`: global and repository instruction layers for workflow, plugin usage, and safety rules.
- `.claude/CLAUDE.md`: concise runtime-facing assistant notes.

## Current Behavior

- `rldyour-flow` owns project lifecycle actions: init/start/review/repair/deploy/post-task sync hooks.
- `rldyour-serena-mcp` owns semantic memory inspection and sync marker analysis.
- `rldyour-explore` is the source for external evidence checks and docs lookup.
- `rldyour-rules` is used for implementation discipline, architecture, dependency policy, and verification expectations.
- `rldyour-security` and `rldyour-design` are invoked by task scope.
- `serena-memory-sync` style requirement is enforced on stop when non-Serena files changed and high-priority areas are touched.

## Contracts

- Git/sync lifecycle: non-knowledge changes to instruction files require explicit memory-sync to keep `serena_memory_state` current.
- Sync scope is verified by git diff, then memory taxonomy/state scripts, then durable memory updates.
- High-priority instruction area changes (`AGENTS.md`, `.claude/CLAUDE.md`) are considered `risk_profile: high`.
- On finalization, changed non-knowledge files should not remain stale without synced evidence in `.serena/memories`.

## Verification

- `python3 .../rldyour-serena-mcp/local/scripts/serena_memory_state.py`
- `python3 .../rldyour-flow/local/scripts/flow_post_task_state.py`
- `python3 .../rldyour-serena-mcp/local/scripts/commit_serena_knowledge.sh`
