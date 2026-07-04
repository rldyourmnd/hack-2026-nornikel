<!-- Memory Metadata
Last updated: 2026-07-04
Last commit: a81edd1 Merge pull request #14 from rldyourmnd/perf/table-row-cap
Scope: README.md; AGENTS.md; .claude/CLAUDE.md; apps/web/; services/api/; src/nornikel_kg/; scripts/; docs/deployment/full-ingest-runbook.md; pyproject.toml; tests/
Area: CORE
-->

# CORE-01-INDEX

## Purpose

Index the durable project knowledge for the Nornikel hackathon R&D knowledge-graph MVP.

## Source Of Truth

- `AGENTS.md`: Codex project instructions and delivery policy.
- `.claude/CLAUDE.md`: Claude Code project notes; currently more accurate than `README.md` for provider/runtime facts.
- `README.md`: product overview, but provider/model wording is stale at `a81edd1`.
- `src/nornikel_kg/`: backend domain, ports, services, adapters, resources.
- `services/api/`: FastAPI app and route layer.
- `apps/web/`: React/Vite frontend.
- `scripts/ingest_corpus.py`: direct container batch ingest for real DATA_HACK corpora.
- `scripts/run_realcase_eval.py`: live real-corpus honesty gate over the four organizer questions.
- `docs/deployment/full-ingest-runbook.md`: sampled/full ingest and atomic-swap runbook.
- `.serena/memories/`: this current fact set; no separate agent-context branch.

## Memory Map

- `ARCH-01-EVIDENCE-MVP.md`: architecture, no-GPU parse path, provider/retrieval flow.
- `DATA-01-EVIDENCE-LEDGER.md`: DuckDB schema, evidence IDs, graph/fact/index contracts.
- `SEC-01-ACL-AND-PROMPT-INJECTION.md`: source labels, prompt-injection, SSRF, LLM failure safety.
- `TEST-01-EVALUATION-GATES.md`: current checks and eval commands.
- `RELEASE-01-VALIDATION.md`: deployment, compose, batch ingest, swap, validation.
- `DOCS-01-PLANNING-SOURCE.md`: documentation precedence and planning package usage.
- `TECHDEBT-01-NOW.md`: current verified gaps only.

## Current Behavior

- Runtime stack: FastAPI + DuckDB ledger + Qdrant hybrid retrieval + LiteLLM/dataeyes + React/Vite UI.
- Working provider profile: dataeyes through LiteLLM, `openai/gpt-5.4-mini` for extraction and `openai/gpt-5.5` for answers; dense embeddings use `EMBEDDING_BACKEND=openai` against an OpenAI-compatible `/embeddings` endpoint. Sparse BM25 remains local.
- Yandex support remains in code (`LLM_API_BASE`, `YandexEmbeddingBackend`), but the organizer key was verified denied operationally; do not assume Yandex works until a fresh credential is tested.
- Synthetic/demo seed/runtime data was removed. `scripts/run_eval.py`, `eval/*.yml`, and `tests/integration/test_synthetic_v2_corpus.py` are gone; clean ledgers should not contain synthetic sources.
- Default PDF ingest is no-GPU/no-layout-model: `.pdf` routes to `PyPdfiumFastParser` unless `PDF_PARSE_MODE=docling`.
- Fast graph build controls are active: `LLM_EXTRACTION_MODE=source_packet`, `MAX_EXTRACTION_SPANS=400`, `MAX_TABLE_ROWS_PER_SOURCE=400`, `DuckDBLedgerRepository.batch_transaction()`, and `scripts/ingest_corpus.py --sample N`.

## Invariants

- DuckDB is authoritative. Qdrant is retrieval-only and must be rejoined back to DuckDB.
- Every answer sentence must cite evidence spans; numbers must be supported by cited text or structured facts.
- Do not commit secrets, `.env`, runtime DBs, browser artifacts, caches, or local state.
- Do not reintroduce synthetic/demo data as runtime truth.
- Only `src/nornikel_kg/adapters/llm/gateway.py` may import `litellm`.

## Verification

- `uv run ruff check .`: Python lint.
- `uv run mypy`: strict backend typing.
- `uv run pytest`: backend tests; 184 passed at `a81edd1`.
- `cd apps/web && npm run typecheck`: frontend TS check.
- `cd apps/web && npm run build`: production frontend build.
- `API_BASE=<stand>/api uv run python scripts/run_realcase_eval.py`: live real-corpus honesty eval.

## Known Gaps

- `README.md` provider/model section is stale; prefer code, `.claude/CLAUDE.md`, `.env.example`, and the full ingest runbook.
- Real-corpus gold-answer eval is still absent; `run_realcase_eval.py` checks honesty properties, not expected answer text.
