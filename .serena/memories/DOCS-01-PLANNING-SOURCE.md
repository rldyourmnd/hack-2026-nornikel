<!-- Memory Metadata
Last updated: 2026-07-03
Last commit: 3e74473 docs(deploy): DuckDB lock contract and archive-aware batch procedure
Scope: README.md; .serena/newproj/nornikel-kg-search/; .serena/plans/; .serena/reviews/;
  .env.example; docs/deployment/
Area: DOCS
-->

# DOCS-01-PLANNING-SOURCE

## Purpose

Capture how to use and maintain the planning package given the current implementation state.

## Source Of Truth

- `.serena/newproj/nornikel-kg-search/`: original planning package; superseded on conflict by
  `.serena/plans/`.
- `.serena/plans/00_PLAN_INDEX.md` / `01_MVP_SCOPE_AND_DECISIONS.md` / `03_IMPLEMENTATION_PLAN.md`:
  the W0-W5 implementation plan, fully realized.
- `.serena/plans/06_DEPLOYMENT_AND_OBSERVABILITY.md`: deployment/observability plan, realized by
  `docs/deployment/nornikel-nddev.md`.
- `.serena/plans/08_TRACK_FULL_REQUIREMENTS_AND_GAPS.md`: full-track requirement brief («Научный
  клубок») and gap analysis G1-G10 against the real `DATA_HACK/` corpus.
- `.serena/plans/09_ACCURACY_SOTA_OVERHAUL.md` (new, `2368791`): the accuracy/SOTA overhaul plan
  — 4 evidence-based audits (GLiNER2 research, SOTA stack research, backend accuracy audit,
  eval/CI/frontend audit), locked research verdicts, and waves A-D (landed as PR #15) plus wave
  E (archive/legacy-format ingestion, landed as PR #16, tracked in the same doc's scope).
- `.serena/reviews/`: plan self-critique and source-backed research facts.
- `README.md`: current implementation status.
- `docs/deployment/nornikel-nddev.md`: primary live-stand deployment doc, now also documenting
  the DuckDB lock contract and archive-aware batch-ingest procedure.
- `AGENTS.md` / `.claude/CLAUDE.md`: Codex-native and Claude Code project instructions.

## Entry Points

- `README.md`: start here for status and document map.
- `.serena/plans/09_ACCURACY_SOTA_OVERHAUL.md`: current wave plan (research verdicts + waves
  A-D/E scope).
- `.serena/plans/08_TRACK_FULL_REQUIREMENTS_AND_GAPS.md`: full-track requirement brief (G1-G10);
  still the reference for the geomechanics ontology gap (`mem:TECHDEBT-01-NOW`).

## Current Behavior

Waves W0-W5 (2026-07-02 plan package) and the real-corpus hardening wave (`58760b3` and
follow-ons through `41ee7ac`) were implemented and merged to `main` as of the prior sync.

This sync covers ten additional commits on `main`: `2368791` (accuracy/SOTA overhaul plan doc),
`41b3acd`/`944e6f0`/`93f3f87`/`12bc5c1` (waves A-D, merged as PR #15 via `b611591`), `b7b12d6`
(per-source indexing perf fix), `2e5458a` (archive/legacy-format ingestion wave E, merged as
PR #16 via `65694a7`), `1db832d` (fail-fast DuckDB-lock fix in the batch ingester), and `3e74473`
(deployment-doc update documenting the lock contract and archive-aware batch procedure). All ten
commits are verified present in `git log --oneline 41ee7ac..HEAD`.

Local `main` and `origin/main` are in sync (`git rev-list --left-right --count
origin/main...main` -> `0\t0`, verified 2026-07-03); there is no pending push backlog.

`.env.example` now documents `SEED_SYNTHETIC_FIXTURE`, `SYNTHETIC_SAMPLE_DIR`,
`LLM_TOKEN_BUDGET`, `LLM_EXTRACTION_ENABLED`, `GLINER_ENABLED`, `SYNC_ENRICHMENT`,
`ENTITY_SEMANTIC_FALLBACK`, `SPARSE_LANGUAGE`, and `RERANKER_ENABLED`/`RERANKER_MODEL_ID`/
`RERANKER_BACKEND` — all of the env knobs introduced by the real-corpus and accuracy-overhaul
waves are now documented (previously several were read directly from `os.getenv` with
undocumented code-level defaults; this gap is now closed). `DATAEYES_API_BASE`'s example value
was corrected to `https://platform.dataeyes.ai/v1` (the prior example pointed at the wrong
dataeyes.ai product).

## Contracts And Data

Repository artifacts are written in English. User-facing conversation remains Russian unless
the owner requests otherwise.

## Invariants

- Synthetic fixtures should be committed; real internal corpora (`DATA_HACK/`, `data/corpus/`)
  must never be committed — they are gitignored.
- Planning docs under `.serena/plans/`/`.serena/newproj/` describe design intent at the time
  they were written; cross-check `README.md` and `.serena/memories/` for current implementation
  state, and cross-check `git cat-file -t <sha>` before trusting any commit SHA recorded in an
  older memory or plan document — history has been rewritten at least once (`58760b3`, prior to
  this sync's range).

## Change Rules

Keep planning updates source-backed when they mention external tools or current capabilities.
Update `README.md`'s implemented-scope section when a new wave lands.

## Verification

- Targeted `rg`/`grep` scans: consistency and accidental secret markers.
- `git cat-file -t <sha>`: verify a commit SHA still exists before citing it in a new memory.
- `git rev-list --left-right --count origin/main...main`: verify local/remote sync state
  (`0\t0`, verified 2026-07-03).
- `git log --oneline 41ee7ac..HEAD`: verify the exact commit range covered by this sync pass
  (10 commits, confirmed).
