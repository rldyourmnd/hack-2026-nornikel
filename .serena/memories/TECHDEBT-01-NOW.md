<!-- Memory Metadata
Last updated: 2026-07-04
Last commit: a81edd1 Merge pull request #14 from rldyourmnd/perf/table-row-cap
Scope: README.md; .github/workflows/ci.yml; pyproject.toml; docker-compose.server.yml; docs/deployment/full-ingest-runbook.md; scripts/run_realcase_eval.py; src/nornikel_kg/
Area: TECHDEBT
-->

# TECHDEBT-01-NOW

## Purpose

Capture verified current gaps only; avoid using memory as a backlog for stale historical issues.

## Source Of Truth

- `README.md`: provider/model section is stale.
- `.github/workflows/ci.yml`: CI dependency scope.
- `pyproject.toml`: dependency versions and optional extras.
- `docker-compose.server.yml`: pinned runtime services.
- `docs/deployment/full-ingest-runbook.md`: current ingest profile and known speed levers.
- `scripts/run_realcase_eval.py`: current live eval scope.

## Known Gaps

- **README provider drift**: README still describes Yandex/aliceai as primary; current working stand is dataeyes (`openai/gpt-5.4-mini` extraction, `openai/gpt-5.5` answers) plus `EMBEDDING_BACKEND=openai`.
- **No real-corpus gold-answer set**: `scripts/run_realcase_eval.py` checks honesty properties on four live track questions, not expected answer text.
- **CI does not install `--extra ingest`**: heavy Docling/GLiNER/spreadsheet/legacy paths are not fully exercised in CI.
- **Qdrant client/server mismatch warning**: Python client 1.18.0 warns against server `qdrant/qdrant:v1.16.3`.
- **Random-sample batch speed floor**: pypdfium2, source_packet, write batching, and caps are deployed, but large XLS/PDF sources still take tens/hundreds of seconds due to span volume, remote embeddings, and graph resolution. Deeper bulk-resolution/indexing work is the remaining speed path on the no-GPU stand.
- **Yandex credential denied operationally**: keep the dataeyes/OpenAI-compatible profile active until a new Yandex credential is verified by direct API calls.
- **Geomechanics ontology coverage is still incomplete** unless verified otherwise against dictionary files and real DATA_HACK questions.

## Resolved / Do Not Reopen As Active Gaps

- Synthetic/demo seed and `scripts/run_eval.py` are deleted.
- Old `eval/*.yml` synthetic fixtures are not an active evaluation path.
- Full local GPU or graphics-dependent components are not acceptable requirements for the stand.

## Verification

- `uv run ruff check . && uv run mypy && uv run pytest`
- `cd apps/web && npm run typecheck && npm run build`
- `API_BASE=<stand>/api uv run python scripts/run_realcase_eval.py`
