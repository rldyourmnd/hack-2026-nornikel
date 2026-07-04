<!-- Memory Metadata
Last updated: 2026-07-04
Last commit: e95e434
Scope: Makefile; tests/; .github/workflows/ci.yml; pyproject.toml; scripts/run_realcase_eval.py
Area: TEST
-->

# TEST-01-EVALUATION-GATES

## Purpose

Capture current validation commands and what they prove.

## Source Of Truth

- `Makefile`: `lint`, `typecheck`, `test`, `ci`, `eval-realcase`, `reindex`, `warmup`.
- `.github/workflows/ci.yml`: CI backend/frontend gates.
- `tests/unit/`: domain/service/adapter tests.
- `tests/integration/`: FastAPI, DuckDB ledger, graph, ingest, analytics tests.
- `scripts/run_realcase_eval.py`: live real-corpus honesty eval.

## Current Behavior

`scripts/run_eval.py`, `eval/*.yml`, and the legacy fixture corpus test were removed. There is no `make eval` target at `a81edd1`.

Live-run verification at `a81edd1`:

- `uv run ruff check .`: clean.
- `uv run mypy`: clean, 82 source files.
- `uv run pytest`: 184 passed.
- `cd apps/web && npm run typecheck`: clean.
- `cd apps/web && npm run build`: clean.

`scripts/run_realcase_eval.py` checks four organizer track questions against a running API. It asserts citation coverage 1.0, zero fabricated numbers, zero source-label leaks, zero prompt-injection success, zero semantic unsupported sentences, non-empty evidence, and no legacy fixture leakage.

## Invariants

- Add or update tests in the same change as ingestion, extraction, retrieval, answer verification, or API contract changes.
- Keep CI offline: no provider secrets or external LLM calls are required for `make ci`.
- Use `eval-realcase` only against a live stand/API.

## Verification

- `make ci`: backend lint/type/test plus frontend build.
- `make eval-realcase`: live stand honesty check.
- `uv run pytest tests/integration/test_api.py::test_health_uses_llm_settings_aliases`:
  verifies `/health` uses the same LLM alias handling as runtime wiring while still
  hiding exact provider model IDs.
