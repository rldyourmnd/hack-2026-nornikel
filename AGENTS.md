# rldyour Codex Global Instructions

## Purpose

This file is the compact global Codex instruction layer installed as
`~/.codex/AGENTS.md` in this repository copy.
Detailed workflows live in rldyour plugins, skills, references, docs, and Serena memories so
Codex only loads them when relevant.

The owner sets direction and priorities. Codex implements: research, code,
verification, documentation, git synchronization, and release follow-through.

## Language

- User-facing conversation with the owner is Russian unless explicitly requested otherwise.
- Repository artifacts are English: code, comments, commits, docs, ADRs, and memories.
- Technical identifiers stay ASCII.

## Operating Rules

- Quality and correctness outrank speed.
- No hacks, fake implementations, swallowed errors, hidden debt, or fake green checks.
- Code/config/tests are the source of truth. Docs and memories must reflect verified state.
- Keep semantic entropy low: reuse local patterns, clear boundaries, avoid duplicate policy sources.
- Use current source-backed dependency/product facts; do not upgrade or migrate blindly.
- Do not commit secrets, runtime markers, browser artifacts, caches, or accidental local state.
- Do not revert user changes unless explicitly requested.

## Plugin Router

Use installed rldyour plugins automatically when the task matches scope:

- `rldyour-flow`: `ry-init`, `ry-start`, `ry-review`, `ry-repair`, `ry-deploy`, instruction-docs sync,
  and post-task sync/lifecycle hooks.
- `rldyour-serena-mcp`: code understanding, semantic inspection/refactor, and memory sync.
- `rldyour-explore`: official docs, upstream research, web evidence, and current-version checks.
- `rldyour-rules`: quality, architecture, dependency policy, verification gates, ADR and instruction policy.
- `rldyour-lsps`: language-server routing, health checks, and Serena/LSP integration.
- `rldyour-browser`: browser validation/debugging, screenshots, user flows, console/network/runtime.
- `rldyour-design`: design systems, tokens, i18n, FSD, shadcn/ui, ReactBits.
- `rldyour-security`: OWASP-oriented implementation guidance and defensive review.

## Tool Priority

- Code structure: Serena symbols first, then `rg`/targeted reads for unsupported text.
- Technical docs: Context7/OpenAI Docs MCP or official sources before web search.
- Repo architecture: DeepWiki/source reads when needed.
- Security-sensitive changes: project security scripts + defensive guidance.

## Codex System Contract

- Approval policy is `never`, execution is non-sandboxed / full access where allowed by repo policy.
- Required features: hooks and multi-agent features remain enabled.
- Default parent model is `gpt-5.5` with high reasoning unless overridden.
- Safe mode is explicit only when requested by maintainers.

## Native Boundaries

- Workflows and behaviors are plugin/skill based and should be invoked through available rldyour skills.
- Plugin manifests live in `.codex-plugin/plugin.json` where applicable.
- Plugin-bundled hooks are discovered via manifests/hook tooling and must be respected.

## Git And Delivery

- Prefer atomic Conventional Commits.
- Split unrelated implementation/test/docs/metadata work when independently reviewable.
- Do not force-push `main`.
- Run checks matching touched scope and report exact commands.
- If changes are committed, push when release synchronization requires it.
- Standard finish order: Serena sync → instruction-docs sync → quality checks → atomized commits → push → branch cleanup after explicit confirmation.

## Key Commands

```bash
make ci
python3 /Users/rldyourmnd/.codex/plugins/cache/rldyour-codex/rldyour-flow/local/scripts/flow_post_task_state.py
python3 /Users/rldyourmnd/.codex/plugins/cache/rldyour-codex/rldyour-flow/local/scripts/git_sync_audit.sh
python3 /Users/rldyourmnd/.codex/plugins/cache/rldyour-codex/rldyour-serena-mcp/local/scripts/serena_memory_state.py
```

Runtime defaults:

- Upload hardening limit is `MAX_SOURCE_UPLOAD_BYTES` (default `5_242_880` bytes,
  `26_214_400` on the stand), configurable via `.env`; accepted upload types:
  `.csv .md .markdown .txt .text .pdf .docx .docm .doc .xlsx .xls`.
- The bundled web Nginx proxy sets `client_max_body_size 32m` and 300s `/api/`
  proxy timeouts; host-level reverse proxies must keep equal or larger limits.

Run repository-local validation scripts when present.

## Key Notes

- Working repository: `rldyourmnd/hack-2026-nornikel` (migrated 2026-07-03;
  `rldyourmnd/nornikel-kg-search` is a frozen archive — its deploy workflow is
  disabled, never push there). Auto-deploy runs from this repo's main.

- MVP (waves W0-W5 merged 2026-07-02/03) is a grounded evidence-led flow: Docling PDF/DOCX
  ingest with quarantine, trafilatura URL import, dictionary/GLiNER/LLM extraction with
  entity resolution, own DuckDB+NetworkX graph layer, Qdrant hybrid retrieval
  (USER-bge-m3 + BM25, RRF), LLM answer synthesis gated by the claim verifier with a
  deterministic fallback, conflict detector, gaps matrix, and recursive DATA_HACK
  corpus ingestion (archives, PDFs, spreadsheets).
- Remaining gaps: real-corpus gold eval set, geomechanics ontology coverage, CI without
  the `ingest` extra (GLiNER/Docling/spreadsheet paths untested there).
- Implementation plan package (2026-07-02): `.serena/plans/00_PLAN_INDEX.md` (waves W0-W5)
  plus `.serena/reviews/` (critical review, research evidence register). Plans amend
  `18_IMPLEMENTATION_SPEC.md`; scope/decision precedence is `.serena/plans/01_MVP_SCOPE_AND_DECISIONS.md`.
- LLM provider (2026-07-03): organizer-provided Yandex AI Studio via the LiteLLM SDK
  (OpenAI-compatible base `https://ai.api.cloud.yandex.net/v1`, stand model
  `aliceai-llm`, dense embeddings `text-embeddings` 1536-dim with
  `EMBEDDING_BACKEND=yandex`); previous dataeyes config kept as server-side backup.
  Langfuse self-host for observability; CI stays offline with deterministic LLM fakes.
