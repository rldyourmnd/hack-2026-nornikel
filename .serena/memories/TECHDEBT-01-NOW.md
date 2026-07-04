<!-- Memory Metadata
Last updated: 2026-07-05
Last commit: a56aa02 Merge pull request #21 from rldyourmnd/fix/yandex-ai-studio-benchmark
Scope: README.md; .github/workflows/ci.yml; pyproject.toml; docker-compose.server.yml; docs/deployment/full-ingest-runbook.md; scripts/run_realcase_eval.py; src/nornikel_kg/
Area: TECHDEBT
-->

# TECHDEBT-01-NOW

## Purpose

Capture verified current gaps only; avoid using memory as a backlog for stale
historical issues.

## Source Of Truth

- `.github/workflows/ci.yml`: CI dependency scope.
- `pyproject.toml`: dependency versions and optional extras.
- `docker-compose.server.yml`: pinned runtime services.
- `docs/deployment/full-ingest-runbook.md`: current ingest profile.
- `scripts/run_realcase_eval.py`: current live eval scope.

## Known Gaps

- **No real-corpus gold-answer set**: `scripts/run_realcase_eval.py` checks honesty properties on four live track questions, not expected answer text.
- **CI does not install `--extra ingest`**: heavy Docling/GLiNER/spreadsheet/legacy paths are not fully exercised in CI.
- **Qdrant client/server mismatch warning**: Python client 1.18.0 warns against server `qdrant/qdrant:v1.16.3`.
- **Random-sample batch speed floor**: pypdfium2, source_packet, write batching, and caps are deployed, but large XLS/PDF sources still take tens/hundreds of seconds due to span volume, remote embeddings, and graph resolution. Deeper bulk-resolution/indexing work is the remaining speed path on the no-GPU stand.
- **Yandex embedding throughput is quota-bound**: the Yandex REST embedding
  backend sends one text-vectorization request per text. AI Studio vectorization
  quota and provider-side 429s make high-worker ingest slower unless
  `YANDEX_EMBED_RPS`/`YANDEX_EMBED_CONCURRENCY` are paced below the live folder
  limit. This is an operational constraint, not a local CPU/GPU issue.
- **Geomechanics ontology coverage is incomplete** unless verified otherwise against dictionary files and real DATA_HACK questions.

## Resolved / Do Not Reopen As Active Gaps

- Legacy fixture seed paths and `scripts/run_eval.py` are deleted.
- Old generated fixtures are not an active evaluation path.
- Full local GPU or graphics-dependent components are not acceptable requirements for the stand.
- Public README/runbook/env docs are provider-neutral and do not expose account-specific operational history.

## Verification

- `uv run ruff check . && uv run mypy && uv run pytest`
- `cd apps/web && npm run typecheck && npm run build`
- `API_BASE=<stand>/api uv run python scripts/run_realcase_eval.py`
