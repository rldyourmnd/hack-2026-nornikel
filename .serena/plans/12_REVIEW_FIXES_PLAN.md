# Plan 12 — GPT-5.5 Pro audit fixes + prod graph (gpt-5.4-mini, 1000+ docs)

Owner directive (2026-07-04): fix all audit findings; build the real prod graph on
**dataeyes.ai + gpt-5.4-mini** over 1000+ documents.

## Findings → fix waves (verify each against code first — auditor inferred line numbers)

### Wave A — LLM robustness (P0)
- **#1** Gateway `generate_json` final failure re-raises the raw provider exception;
  `answer_composer.compose()` catches only `LLMError` → `/qa/ask` can 500 instead of a
  deterministic (rule-based, no-LLM) cited fallback.
  Fix: gateway normalizes ALL final provider failures to `LLMError` (preserve cause);
  `compose()` catches broad Exception → fallback.
- **#8** Same root: a non-`LLMError` gateway exception aborts a whole source's extraction.
  Fix: gateway normalization + per-span broad catch in extraction → rule-only for that span.

### Wave B — security
- **#2** Archive decompression bomb: cap total UNCOMPRESSED bytes (ZipInfo.file_size per
  member + cumulative) BEFORE copy; byte-limited stream; RAR post-extract tempdir cap.
- **#3** SSRF via redirects: replace `trafilatura.fetch_url` with a controlled httpx client —
  no auto-redirects, revalidate each hop against the public-IP guard, max-bytes + timeout.
- **#5** Security labels: `DEFAULT_SOURCE_LABEL` env; per-source label on ingest; reject
  unknown labels; document mandatory `JURY_ALLOWED_LABELS` on the demo stand.

### Wave C — correctness / data integrity
- **#4** Batch provenance: pass sanitized relative path (not basename) in `ingest_corpus`;
  ensure same-content-hash ingests serialize under the process lock (verify _db_lock covers it).
- **#6** Qdrant dim mismatch: validate the existing collection's dense dim vs the backend's
  dim on ensure/reindex; fail loud (health) or use a per-model collection name.
- **#9** OpenAI embedding backend: validate `len(data)==len(batch)` + indexes 0..n-1; raise a
  retriable error; persist indexing failure to ingestion_runs.

### Wave D — invariant
- **#7** Rule-based semantic support passes direction inversions (повышает↔снижает). Add
  deterministic antonym/direction cues to `sentence_semantically_supported`.

### Wave E — config/docs
- **#10** Make the working demo profile explicit in `.env.example` (dataeyes + openai
  embeddings), commented Yandex fallback.

## Ops (H1) — prod graph throughput
Large docs are extraction-bound on gpt-5.4-mini (20-28 min for ~3000-span docs) → 2015 files
= days. Levers: raise `LLM_MAX_CONCURRENCY` + `--workers` (within dataeyes limits); resumable
(idempotent dedup). After deploying the fixes, **restart the batch fresh** so the graph carries
#4 provenance + #9 validation. Swap per docs/deployment/full-ingest-runbook.md.

## Gates: uv run ruff check . ; uv run mypy ; uv run pytest ; make eval ; frontend build.
