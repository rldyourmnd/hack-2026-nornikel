# Plan Index

Date: 2026-07-02
Status: approved direction, pre-implementation
Owner decisions source: session 2026-07-02 (two clarification rounds)

## Purpose

This package is the implementation plan for upgrading the current P0 scaffold to the
hackathon-winning MVP. It amends, and does not replace, the planning package in
`.serena/newproj/nornikel-kg-search/`. Where documents conflict, the precedence is:

1. `.serena/plans/01_MVP_SCOPE_AND_DECISIONS.md` (this package, decisions)
2. `.serena/newproj/nornikel-kg-search/18_IMPLEMENTATION_SPEC.md` (base contract)
3. Other planning documents

## Reading Order

| Doc | Content | Read when |
| --- | --- | --- |
| `01_MVP_SCOPE_AND_DECISIONS.md` | Locked decisions, hackathon-rule deltas, non-goals | First, always |
| `02_TARGET_ARCHITECTURE.md` | Components, data flow, DuckDB schema delta, ports, LLM gateway | Before any backend work |
| `03_IMPLEMENTATION_PLAN.md` | Two-week wave plan with acceptance gates and cut lines | Before starting each wave |
| `04_SYNTHETIC_CORPUS_PLAN.md` | Corpus x10 composition, generator, gold questions | Before W2 extraction and W5 eval work |
| `05_QUALITY_GATES_AND_EVAL.md` | Metrics, thresholds, test plan, CI rules | Before merging each wave |
| `06_DEPLOYMENT_AND_OBSERVABILITY.md` | New-server topology, env matrix, Langfuse, backups | Before W5 rollout |
| `07_DEMO_AND_PITCH_PLAN.md` | Demo script, pitch numbers, jury Q&A prep | During W5 |

Reviews live in `.serena/reviews/`:

| Doc | Content |
| --- | --- |
| `01_PLAN_CRITICAL_REVIEW.md` | Self-critique: risks, mitigations, rejected alternatives, open questions |
| `02_RESEARCH_EVIDENCE_REGISTER.md` | Source-backed facts (licenses, versions, availability) behind every plan choice |

## Invariants Carried Over Unchanged

- DuckDB is the system of record; Qdrant is retrieval-only; NetworkX is materialization-only.
- Every answer sentence must cite exact `EvidenceSpan` IDs; unsupported sentences are rejected.
- Source-label filtering happens before any LLM context construction.
- `make ci` and `make eval` stay green after every wave without network or secrets.

## Change Rules

Update this index when a plan document is added, split, or superseded. Record scope
changes in `01_MVP_SCOPE_AND_DECISIONS.md` with a date, not in chat history.
