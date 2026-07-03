# Wave 10 — Real-Corpus MVP: Audit Response Plan (verified)

Status: **plan only, not implemented.** Every claim below was checked against
HEAD by five parallel code-reading passes; each item carries a verdict, the
decisive `file:line`, and a real-corpus-MVP value. The goal is to keep only
work that genuinely moves the product from demo-MVP to real-corpus MVP.

## Framing correction (load-bearing)

The audit is written as "remove the demo, switch to the real corpus." But the
stand **already runs on the real corpus** (66 real sources, DeepSeek graph
3107/6771). The synthetic Ni-Cu fixture is **seeded on top** of it, because
`SEED_SYNTHETIC_FIXTURE` defaults to `"true"` and the stand `.env` never sets
it. Verified live: `grep ^SEED_SYNTHETIC /srv/.../.env → not set → default
true`. So the highest-value action is not "rebuild for real corpus" — it is
**stop seeding synthetic data on top of the real corpus**, then make the eval
and demo tell the real-corpus story.

Second correction: the auditor read the **code defaults** (`.env.example`,
`DemoQAService` naming) without the **stand config** (LLM on, DeepSeek, real
corpus) and without this session's recent changes (packet `data_version`
cache, `parse_time_scope`). Several claims are therefore stale or overstated.

## Verification method

Five read-only passes over the tree, one per cluster (demo-removal,
ingest/formats, case-requirements, accuracy/UI, security/ops/eval), each
returning verdict + `file:line` + value. Cross-checks run against the live
stand `.env` and the eval/test seeding path.

---

## TIER 1 — Do now (real-corpus MVP blockers, all code-verified)

### T1.1 — Stop seeding synthetic Ni-Cu on the real corpus  *(audit #1, HIGH, S)*
- CONFIRMED: `runtime.py:47` seeds when `SEED_SYNTHETIC_FIXTURE` unset (default
  `"true"`); `seed_synthetic_fixture` (`repositories.py:112`) writes a real
  "Synthetic Ni-Cu aging report" source into the same ledger every answer reads.
  Stand verified seeding right now.
- Change: default `"false"`; set `SEED_SYNTHETIC_FIXTURE=false` in the stand
  `.env` and `.env.example`; after the flip, delete the seeded synthetic source
  from the stand ledger (one-off) so existing rows don't linger.
- **Code-verified constraint (proved against the eval):** `run_eval.py:168-174`
  and `tests/integration/test_duckdb_ledger.py` rely on the *default* seeding —
  they never seed explicitly. Flipping the default to `false` breaks `make eval`
  and CI unless those two set `SEED_SYNTHETIC_FIXTURE=true` (or call
  `seed_synthetic_fixture` directly) on their temp DB. This must ship in the
  same change.

### T1.2 — Structured facts from real tables, not only the synthetic CSV  *(audit #11/12/13, HIGH, L)*
- CONFIRMED, this is the biggest real gap. `PropertyMeasurement`/`EffectClaim`
  are written **only** by `_insert_csv_rows` (`repositories.py:1319`), which
  requires the fixed synthetic schema `CSV_REQUIRED_COLUMNS`
  (`repositories.py:37`). Every real PDF/DOCX/XLSX goes through
  `ingest_parsed_document` (`repositories.py:224`) which writes **spans only,
  no facts**. Table rows serialize cells with `" | "` and drop headers
  (`ports/parser.py:34`).
- Change (phased):
  1. Preserve table headers: give `ParsedTableRow` a `headers` list and
     per-cell `(row, col, header, value, unit)`; carry it into the `table_row`
     span payload (currently `visible_text=row.text`).
  2. Add a generic table→facts extractor over parsed tables (CSV/XLS/XLSX/PDF/
     DOCX) with header schema inference (RU/EN column names, unit-in-header),
     producing `PropertyMeasurement`/`EffectClaim` with `evidence_span_ids`.
     Keep the LLM extraction path (already on for DeepSeek) for narrative facts.
- Value: without this the KG's structured-fact layer is demo-only. Highest
  single lever for the four case questions (all need numbers off real tables).

### T1.3 — Bind numeric constraints to subjects  *(audit #15/16, HIGH, M)*
- CONFIRMED and worse than stated: `NumericConstraint` (`quantities.py:43`) has
  `op/value/unit` but **no subject**; `satisfies_constraints` matches on unit
  only; `мг/дм³` canonicalizes to `мг/л` (`quantities.py:10`) so dry-residue
  collides with ion ranges; all same-unit constraints AND together against one
  `measurement.value`.
- Change: introduce `ParameterConstraint{subject, property, op, value_min,
  value_max, unit, evidence_span_ids}`; parse subject tokens (sulfate/chloride/
  Ca/Mg/Na/dry-residue/flow/temperature/CAPEX…) and range forms («200–300»,
  «≤1000», «менее», «от … т/сут»); match against subject-tagged facts from T1.2.
- Directly unblocks case Q1 (desalination multi-analyte).

### T1.4 — Extend ontology + relations to the case vocabulary  *(audit #19/20, HIGH, M)*
- CONFIRMED: `ENTITY_TYPES` is a closed 11-tuple (`domain/extraction.py:5`);
  `RELATION_TYPES` a closed 14-tuple (`:19`), filtered in `_write_llm_relations`
  (`extraction_service.py:302`). The DeepSeek stand graph matches exactly these
  11 types — so `process/facility/organization/location/economic_indicator/
  technology_solution/condition/expert` and relations `USES_MATERIAL/
  OPERATES_AT_CONDITION/HAS_ECONOMIC_INDICATOR/HAS_LIMITATION/RECOMMENDED_FOR`
  are genuinely absent.
- Change: extend the two tuples + the extraction system prompt with the
  case-required types/relations; re-enrich (the DeepSeek rebuild pipeline from
  Wave 09 already exists). Cheap edit, high case-alignment payoff.

### T1.5 — Per-sentence clickable citations + `locator` in the UI  *(audit #25/26, HIGH, M)*
- CONFIRMED end-to-end gap: backend emits `supporting_span_ids` per sentence
  and `locator` per span, the UI discards both. `AnalysisWorkbench.tsx:329`
  renders sentence text only; `types.ts` has no `locator`; evidence is a flat
  unlinked list.
- Change: add `locator` to the TS `EvidenceSpan`; render each answer sentence
  with its citations (source title / page / table row / span id), click →
  scroll+highlight the evidence card; add a per-sentence verification badge
  (verified / partial / numeric-mismatch). No backend change — the data already
  crosses the wire. This is the core trust affordance of an evidence product.

### T1.6 — Real-case eval on the four track questions  *(audit #52, HIGH, M)*
- CONFIRMED exact: all 17 `EVAL_QUESTIONS` (`run_eval.py:13-165`) are synthetic
  Ni-Cu; zero cover desalination / catholyte / Au-Ag-PGM / mine-water.
- Change: add a real-corpus eval set (the 4 track questions + variants) asserting
  citation coverage, numeric correctness, geography, year filtering, source
  grouping, and **no synthetic leakage**. Keep the Ni-Cu set as a *safety* suite
  but run it on an explicitly-seeded temp DB (ties to T1.1). Retire/rewrite
  `q_year_phrase_is_not_a_filter` — it only passes because the synthetic source
  has no year (see T2.5).

### T1.7 — Archive extraction must not flatten paths  *(audit #7/8, HIGH, S)*
- CONFIRMED silent data loss: `archive_expansion.py:37` uses
  `Path(member.filename).name` then truncating-writes into one flat dir → same
  basename across the year-partitioned corpus (`ICSG-reports-2010/2011/…`)
  overwrites. (RAR path already preserves nested paths.)
- Change: preserve the archive-relative path, generate a collision-free target,
  store `archive_member_path` provenance; add the two-`report.pdf`-in-different-
  folders test.

### T1.8 — CSV CP1251 + configurable Excel caps  *(audit #9/10, HIGH, S)*
- CONFIRMED: `_parse_csv_rows` (`repositories.py:1283`) hard-requires UTF-8 →
  CP1251 RU CSV rejected with 400; Excel caps 20/300/30 hardcoded
  (`spreadsheet/parser.py:22`) drop the bulk of real workbooks.
- Change: CSV encoding cascade (utf-8-sig → utf-8 → cp1251 → charset-normalizer),
  persist detected encoding; make Excel caps env-configurable and raise defaults
  for batch. Both are small and unblock real files.

---

## TIER 2 — Worthwhile (MED)

- **T2.1 — Structured quarantine reason code** *(audit #14, MED, S)*: `_quarantine`
  stores free-text `error` (`ingestion_service.py:312`); add a machine-readable
  `reason_code` enum (`no_text_layer_ocr_disabled`, `parser_error`,
  `unsupported`), surface counts in the Data page. Makes the "OCR out of scope"
  story explicit and honest (aligns with the audit's core constraint).
- **T2.2 — Archive upload via API/UI** *(audit #6/7, MED, M)*: add
  `/sources/upload-archive` (zip/multipart/rar) reusing `expand_archives`; per-
  member ingest run with `archive_name/member_path/member_sha` provenance.
- **T2.3 — SSRF guard on `/sources/import-url`** *(audit #38, MED security, S)*:
  only real security finding. `HttpUrl` allows any host; `trafilatura.fetch_url`
  (`fetcher.py:9`) reaches `169.254.169.254`/localhost/private ranges and
  returns the body (read-SSRF). Add private-IP/link-local/localhost blocklist +
  size + timeout. Cheap, worthwhile even for a private stand.
- **T2.4 — UI reads model/provider from `/health`, not hardcoded** *(audit #49,
  MED, S)*: `WorkbenchPage.tsx:105` shows the literal `Yandex AI Studio ·
  aliceai-llm` — now **wrong** (stand runs deepseek-v4-flash). Expose active
  models on `/health` or `/stats/overview`; render from it. Credibility fix.
- **T2.5 — Strict question-derived time scope + "undated" block** *(audit #18,
  MED, S)*: currently permissive by design and eval-locked
  (`q_year_phrase_is_not_a_filter`). Once synthetic seeding is off (T1.1) and
  real sources carry years, make «за последние N лет» strict for the primary
  answer and surface undated sources in a separate block. Must land together
  with the eval rewrite (T1.6) or the old case will fail.
- **T2.6 — Semantic support check in verification** *(audit #23, MED, M)*:
  `ClaimVerifier` (`answer_claims.py`) checks only span-id presence + numeric
  subset — a paraphrase-hallucination citing a valid span passes. Add a cheap
  evidence-only LLM judge (or NLI) returning supported/partial/unsupported/
  contradicted; drop or downgrade unsupported sentences. Pairs with T1.5 badges.
- **T2.7 — Geography from country/affiliation, not script** *(audit #17, MED,
  M)*: `_set_year_geography` (`ingestion_service.py:262`) counts Cyrillic vs
  Latin chars. Add country/affiliation/location signals → `practice_geography`
  (ru/foreign/mixed/unknown) distinct from `document_language`.
- **T2.8 — Unify LLM config naming** *(audit #48, MED docs, S)*: three endpoints
  and three model names across `settings.py:14` (`dataeyes_*` default),
  `.env.example`, `README`. Rename to `LLM_PROVIDER/LLM_API_BASE/LLM_API_KEY/
  LLM_*_MODEL` with startup validation; `.env.example` should match the stand.

---

## TIER 3 — Cleanup (LOW, cheap hygiene)

- **#2/#3/#27 dead demo remnants**: `_fallback_packet`/`_demo_evidence` are
  unreachable when a real ledger is injected (`qa_service.py:374`); `/graph/
  demo-path` is orphaned (no UI reference); one hardcoded "Сравнить Ni-30Cu…"
  suggestion at `qa_service.py:911`. Delete/isolate to tests. LOW — hygiene only.
- **#22 confidence constants**: per-format literals (1.0/0.97/0.98) carry no
  signal; either derive or stop presenting as reliability. LOW.
- **#36 upload label param + kill dead `DEFAULT_SOURCE_LABEL`/
  `ALLOWED_SOURCE_LABELS`** (referenced nowhere). LOW.
- **#50 reindex job status**: fire-and-forget daemon thread; a minimal jobs row
  + progress would help the Data page. LOW.

---

## OUT OF SCOPE for the hackathon MVP (P2 gold-plating — do NOT build now)

Confirmed-absent but not worth building before submission; each is a full
subsystem with little demo payoff:

- #32 graph DB (Neo4j/etc.) — NetworkX full-load is fine at 3107 entities;
  in-memory, fast. Only a 1M-scale concern.
- #34 fact versioning, #35 RBAC/users, #40 experts/lab import, #41 taxonomy,
  #43 curator UI, #45 notifications/subscriptions, #47 comparison workbench,
  #51 Postgres/job-queue split — all enterprise features, none on the demo path.
- #33 complex graph queries, #42 doc-type classifier, #44 export, #46 manager
  dashboards — partial demo value; consider only if Tier 1–2 finish early
  (export and a coverage dashboard are the most demo-worthy of these).
- #39 unified audit trail — `ingestion_runs` + `answer_runs` already exist;
  full view/export/delete audit is out of scope.

## Auditor claims that are FALSE or STALE (do not act)

- **#4** "whole corpus loaded before every question, no retrieval" — STALE:
  `_load_packet` caches by `data_version` (`qa_service.py:378`) and
  `_augment_with_retrieval` is query-scoped (`:357`). Only the true query-first
  refactor is optional MED work; the framing is wrong.
- **#53** "no real-format ingestion tests" — FALSE: `test_corpus_formats.py`
  (xlsx/doc/docm/zip/multipart/rar) and `test_synthetic_v2_corpus.py`
  (docx/pdf-quarantine/html) exist. Only genuine gap: a CP1251-CSV test and a
  real text-layer-PDF extraction assertion (folds into T1.8).
- **#21** "LLM extraction insufficient/off" — PARTIAL/STALE: implemented
  (`_llm_extract`), and the stand runs it on DeepSeek (0/6 JSON failures
  measured). Only the *default* is off; the runtime comment even notes it was
  disabled because it misbehaved on raw data — now mitigated by DeepSeek+repair.

## Recommended execution order

1. **T1.1** (stop synthetic seeding + fix eval/test seeding) — unblocks honesty
   and is prerequisite for T1.6/T2.5.
2. **T1.7 + T1.8** (archive de-flatten, CSV cp1251, Excel caps) — small, protect
   real ingest before re-ingesting the corpus.
3. **T1.2** (real table→facts + headers) — the big lever; re-enrich after.
4. **T1.3 + T1.4** (subject-bound constraints, extended ontology) — case
   alignment; re-enrich.
5. **T1.5** (UI citations + locator) — visible trust, parallelizable (frontend).
6. **T1.6 + T2.5** (real-case eval + strict time scope) — prove it.
7. Tier 2 remainder (T2.1–T2.8) as time allows; Tier 3 hygiene last.

Do NOT start Tier 1 implementation until this plan is approved — deliverable is
the plan, per the request.

---

## Implementation status (2026-07-04, approved and executed)

Shipped (atomic commits, gated ruff+mypy+pytest, deployed + verified live):
- **T1.1** — synthetic seeding defaults OFF; eval/tests opt in; stand cleaned
  (seeded source + 16 `synthetic_v2` fixtures deleted → 49 real sources,
  measurements 0, Ni-Cu no longer answers). Also surfaced+fixed that the
  source-delete cascade left the packet cache stale until data_version bump.
- **T1.7** — archive extraction preserves inner paths, collision-safe.
- **T1.8** — CSV encoding cascade (utf-8-sig→utf-8→cp1251→charset-normalizer);
  Excel caps raised + env-configurable.
- **T1.2** — table headers preserved end-to-end (spreadsheet+docling);
  `domain/table_facts` subject-tagged numeric-fact extraction.
- **T1.3** — `parse_parameter_constraints` subject-bound; QA drops
  constraint-violating evidence (honest recall).
- **T1.4** — entity/relation vocab extended; graph rebuilt on stand — live:
  process 317 / facility 54 / organization 83 / location 67 /
  economic_indicator 47 / expert 79; USES_MATERIAL 269 / OPERATES_AT_CONDITION
  225 / HAS_ECONOMIC_INDICATOR 43.
- **T1.5** — per-sentence clickable citations + `locator` in the UI.
- **T1.6** — `run_realcase_eval.py` (make eval-realcase); live run on the four
  track questions: status ok, citation 1.0, 0 fabrication, 0 synthetic leak.
- **T2.1** — machine-readable quarantine reason codes + Data-page display.
- **T2.3** — SSRF guard on URL import (blocks private/loopback/metadata).
- **T2.4** — /health reports active models; sidebar renders the real model.
- **T2.7** — geography from country/affiliation signals, not language.
- **T3** — removed the orphaned `/graph/demo-path`.

Deliberately deferred (documented, low value or eval-locked):
- **T2.5** strict question-time scope — the permissive rule is locked by
  `q_year_phrase_is_not_a_filter` and is the correct honest-recall choice;
  revisit only with a real-corpus gold set.
- **T2.6** semantic/NLI support check — adds per-answer LLM latency; the
  literal-number + citation gates already block fabrication.
- **T2.8** LLM settings rename — cosmetic; stand `.env` already correct.
- **T2.2** archive upload via API — batch path covers it.
- **T3** dead `_fallback_packet` / confidence constants / label param /
  reindex job status — harmless and test-coupled.

Applies-to-new-ingestion note: table headers (T1.2) and geography (T2.7) are
set at parse time, so they take effect for newly ingested sources; existing
stand sources keep their prior values until re-ingested (re-enrichment does not
re-parse). Not a regression — constraint matching degrades to honest recall on
unheadered legacy spans.
