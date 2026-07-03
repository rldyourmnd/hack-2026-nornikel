# Accuracy / SOTA Overhaul Plan (Waves A-D)

Date: 2026-07-03. Goal: maximum output-data accuracy for the track jury.
Status: waves A-E implemented, merged (PR #15, #16) and deployed 2026-07-03.

## Deploy results (measured on the stand, 2026-07-03)

- Graph rebuilt from scratch: polluted 1727 entities / 13408 co-occurrence
  relations wiped; re-enriched with word-boundary scan; full Qdrant reindex
  with russian BM25 (10k+ points) done.
- **Reranker verdict: OFF on this stand.** bge-reranker-v2-m3 measured 58 s
  warm per question (30 pairs, 8 shared vCPU, ONNX unquantized export 153 s
  cold) vs 8.4 s without — fails the latency budget; retrieval precision is
  carried by russian BM25 + title-context + honest rejoin. Revisit only with
  int8 quantization or gte-multilingual-reranker-base (306M).
- **LLM extraction (strict schema fix) verified live**: one real .doc source
  -> 132 entities, 151 typed relations, ZERO schema-invalid payloads
  (previously 100% rejected). LLM_EXTRACTION_ENABLED=true on the stand;
  mass corpus enrichment launched (staggered, ~770 calls).
- Warm QA latency: **8.4 s** with LLM synthesis (was ~32 s).
- Eval run eval_1783081424 stored: 17 questions, citation 1.0, 0 numeric
  mismatches, 0 leaks, injections ignored.
- Timeline: 18 events, all dated (publication year/date extraction works).
- Wave E formats verified on real corpus files: multipart .zip.001+.002 ->
  journal PDF (2026 spans), .rar via bsdtar (3 members), .xls (667 spans),
  .xlsx (144), .doc via antiword (2 sources); one non-standard .docm
  honestly quarantined by the Docling backend.
- Ops: `docker compose restart` does NOT re-read .env — use `up -d` to apply
  env changes; batch ingester and the api are mutually exclusive on the
  DuckDB lock (documented in docs/deployment/nornikel-nddev.md).
- curestry platform reduced to nginx-proxy + acme + landing (frees ~5 GiB
  RAM + ~1 CPU core for this project).
Inputs: 4 deep audits (GLiNER2 research, SOTA stack research, backend accuracy
audit, eval/CI/frontend audit), all claims verified against code and primary
sources (HF cards, Qdrant/Docling/LiteLLM docs, arXiv, GitHub issues).

## Locked research verdicts (evidence-based, do not relitigate)

- **GLiNER2 is rejected.** English-only training (arXiv 2507.18546 §3.1),
  `fastino/gliner2-multi-v1` has no `ru` tag, zero published RU benchmarks,
  relation extraction broken (open issue fastino-ai/GLiNER2#101). Same
  mdeberta-v3-base backbone as our current `urchade/gliner_multi-v2.1` — no
  language gain, only young-codebase risk. KEEP `gliner_multi-v2.1`; improve
  integration (sentence-boundary overlap chunking, batching); typed relations
  come from the LLM path, not GLiNER.
- **Embeddings stay `deepvk/USER-bge-m3`** (RU Retrieval 0.934, strong on long
  docs MLDR-rus 58.53; FRIDA is RU-only by card; e5 needs prefixes+reindex with
  no proven retrieval gain).
- **Add reranker `BAAI/bge-reranker-v2-m3`** (Apache-2.0, multilingual XLM-R),
  ONNX int8 via sentence-transformers backend, rerank top-30 -> top-10,
  env-gated; measure on stand before enabling.
- **BM25 sparse is broken for RU**: fastembed `Bm25` defaults to
  `language="english"`. Fix `language="russian"` + `query_embed()` for queries;
  full reindex required.
- **LLM structured-output root cause**: `EXTRACTION_JSON_SCHEMA` violates the
  strict contract (properties not all in `required`); `_strictify` fixes only
  `additionalProperties`. Fix schema, add `json_repair`, retry-with-feedback
  (pattern already in answer_composer), few-shot.
- **Entity-resolution fallback thresholds** (production refs: neo4j-graphrag
  0.8 default, graphiti 0.6+LLM): auto-merge >=0.90 with digit/formula veto,
  0.80-0.90 log-only (LLM adjudication later), plus curated RU<->EN domain
  alias pairs in dictionaries.
- **Numbers/dates**: deterministic regex + unit-equivalence canonicalization
  (мг/дм³ ≡ мг/л); quantulum3 is EN-only — not used. Dates: narrow regexes +
  dateparser normalization with `languages=['ru','en']`; never `search_dates`
  on full spans.

## Wave A — extraction & parsing accuracy (branch feat/accuracy-wave-a)

- A1 Dictionary alias scan: word-boundary regex with bounded RU-suffix
  tolerance instead of raw substring (`руд` in «оборудование» false hit —
  audit C2). Cached compiled patterns.
- A2 Authors: EN regex false hits (P.O. Box, U.S. Geological — audit H8);
  require affiliation signal (email/@/институт/университет/УДК) near match or
  first-spans context; deterministic head-span ordering.
- A3 Numeric constraints (audit H2/H3): shared unit canonicalization for both
  question and measurement units + equivalence map (мг/дм³≡мг/л, г/дм³≡г/л,
  °с≡c…); range forms («от X до Y», «X–Y», «в диапазоне»); unit-less
  constraints never filter (precision-first); year-context guard («до 2020
  года» is not a value constraint).
- A4 LLM extraction unblock: strict-valid schema (all-required), entities+
  relations persisted (typed relations src/dst resolved through
  EntityResolutionService — replaces co-occurrence as the quality path),
  json_repair in gateway, one retry with ValidationError feedback, few-shot;
  keep LLM_EXTRACTION_ENABLED gate.
- A5 Year/geography heuristics (audit H5/M9/M10): bounded years with context
  guard, ё counted as Cyrillic, metadata applied on CSV/MD/TXT/URL paths too.
- A6 Dates for timeline (audit U1): regex+dateparser date extraction at
  publication-linking time; publication entities carry year/date metadata;
  timeline endpoint includes dated publications.
- A7 canonical_key: strip quotes/punctuation edges, Cyrillic/Latin homoglyph
  folding for digit-bearing tokens (700 С vs 700 C — audit M7).
- A8 GLiNER integration: sentence-boundary chunks with overlap + global-offset
  dedup (boundary-cut entities — research risk 9), batch inference.

## Wave B — retrieval & resolution accuracy (branch feat/accuracy-wave-b)

- B1 BM25 `language="russian"` + `query_embed()` split (index vs query).
- B2 Reranker adapter (CrossEncoder ONNX int8, `RERANKER_ENABLED` env, default
  off until stand latency measured), prefetch 50/50 -> rerank top-30 -> top-10.
- B3 Index-text enrichment: source-title/section prefix for embedded text
  (retrieval units), span_id provenance unchanged.
- B4 Embedding fallback in EntityResolutionService (0.90/0.80 thresholds,
  digit-veto, learned-alias write-back) + RU<->EN domain aliases in
  dictionaries (electrowinning, leaching, matte, slag…).
- B5 Source-scope propagation to retrieval (`source_id` + `source_ids` keys,
  filter in prefetch too — audit H9).

## Wave C — answer/graph honesty & quality (branch feat/accuracy-wave-c)

- C1 Kill demo fallbacks (audit C1/C4/M17): no arbitrary experiments[:5];
  honest confidence levels; chemical-formula veto (CO2/Al2O3/SO2…) in material
  token detection; per-token unmatched handling (comparisons degrade
  gracefully).
- C2 Synthetic fixture seeding env-gated (`SEED_SYNTHETIC_FIXTURE`, default
  true; keep on stand for the ideal-question demo — leakage fixed by C1).
- C3 Conflicts: relevance-filtered (no unconditional conflicts[:1] — M1);
  regime bucketing by regime_id (not `reg` prefix — H4); unit-aware numeric
  disagreement (M11).
- C4 ClaimVerifier numeric check (audit H1): numbers in an answer sentence
  must appear in cited span texts (decimal-comma tolerant); failing sentences
  are dropped -> regeneration path.
- C5 Graph: type-aware neighborhood ranking (person/publication boost — the
  «кто эксперт» query); cascade deletion of relations/entity span refs/
  extraction claims/Qdrant points on source delete (H6).
- C6 Literature-review answer mode: per-span year/geography in composer packet,
  grouping instruction (year/geo/method, consensus vs disagreement — track G6).

## Wave D — provable quality, UI, deploy (branch feat/accuracy-wave-d)

- D1 Eval: assert conflicts/citation coverage/injection on adversarial cases;
  numeric+geo/year eval cases; real-corpus gold set run against the stand.
- D2 Tests for every fix above; route tests for /gaps, /graph/timeline,
  /sources/{id}/enrich, /sources/reindex-all.
- D3 UI: source polling while running; conflicts panel; confidence badge;
  year/geography chips on source cards (extend SourceSummary); gap details.
- D4 Deploy: rebuild, full reindex (russian BM25), re-enrich corpus,
  GLINER_ENABLED=true (after A8 perf check), LLM_EXTRACTION_ENABLED=true
  (after A4 live check), measure reranker latency, store real eval run,
  memory sync.

## Standing rules

- Every wave lands with green `uv run ruff check . && uv run mypy && uv run
  pytest` + frontend build when touched; deploy per wave; deterministic FakeLLM
  paths stay green with all toggles off.
- DuckDB remains authoritative; no unverified answer sentences; litellm only
  in the gateway adapter.
