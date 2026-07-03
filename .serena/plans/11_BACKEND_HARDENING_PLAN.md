# Wave 11 — Backend Hardening (owner-agent code review)

Status: in progress (2026-07-04). Branch `feat/backend-hardening` off `main@d2baec9`.
Amends `.serena/newproj/nornikel-kg-search/18_IMPLEMENTATION_SPEC.md`.

Source: owner-agent backend code review (code-not-run). Every claim re-verified
against actual code by 4 parallel read-only agents + 1 external-research agent
(DuckDB recursive-CTE cycle semantics, fact-layer schema patterns, deterministic
claim-grounding). All 11 points are at least partially live; the review is accurate.

Guiding rules: keep every quality gate green throughout (ruff/mypy/pytest,
front lint/tsc/build); CI must stay LLM-free and offline; response/DB contracts
consumed by the frontend stay byte-identical unless a field is purely additive;
DuckDB migrations are re-executed on every process start (no version table) so
migration `003+` MUST be idempotent (`CREATE TABLE/INDEX IF NOT EXISTS`).

---

## P0 — dangerous debt

### A. Remove demo remnants from production QA (Effort S — dead code)
- Evidence: `qa_service.py` `_fallback_packet()` (428-518) + `_demo_evidence()` (520-557)
  build a synthetic Ni-Cu packet; reached only from `_load_packet()` (411-413) when
  `ledger_repository is None`. `runtime.get_qa_service()` (54-64) ALWAYS passes the real
  `DuckDBLedgerRepository`; all 8 test constructions pass a repo → the branch is
  **unreachable dead code, pinned by no test**.
- Change:
  1. Delete `_fallback_packet` + `_demo_evidence`; `_load_packet` None-branch returns an
     empty `EvidenceLedgerPacket(evidence=[], measurements=[], effects=[], experiments=[],
     source_titles={}, conflicts=[], gaps=[])` (ask() already yields honest low-confidence
     empty — matches `test_answer_honesty::test_irrelevant_question_returns_honest_empty`).
  2. Rename `DemoQAService` → `EvidenceQAService` (update `runtime.py`, tests, `__all__`).
  3. Rename port/impl `load_demo_packet` → `load_evidence_packet` (`ports/ledger.py:10`,
     `repositories.py:160,957`, `qa_service.py:423`, `gaps.py:27`). It loads the REAL packet;
     the name is legacy.
  4. Drop now-unused plumbing in qa_service (`evidence_factory` only fed `_demo_evidence`;
     `PropertyMeasurement/EffectClaim/fact_id/claim_id/source_id_from_bytes` imports). Keep
     the `evidence_factory` ctor kwarg optional to avoid signature churn if still referenced.
  5. `ledger.py:18-44` `.measurement/.effect/.source_title` properties hardcode
     `exp_nicu_aging_700c_8h` (test-only) → plain `[0]` fallback; update `test_duckdb_ledger.py:14-16`.
  6. `routes/evals.py` `/eval/summary` fabricates a hardcoded Ni-30Cu baseline question when
     no stored run exists → replace with a neutral corpus-probe (or return empty summary).
- Files: `qa_service.py`, `runtime.py`, `ports/ledger.py`, `repositories.py`, `routes/gaps.py`,
  `routes/evals.py`, `domain/ledger.py`; tests: `test_duckdb_ledger.py`. Not touched:
  `SEED_SYNTHETIC_FIXTURE` (separate env-gated surface, default off — leave as-is).
- Risk: S. Behavioral delta only on the never-taken None-repo path + naming.

### B. De-hardcode Ni-Cu scoring (Effort M)
- Evidence: `_requested_property` (735-745) = 100% hardcoded 4-entry map; `_regime_matches`
  (756-764) = hardcoded aging/annealing only; `_score_experiment` (713-733) mixes generic
  material/property overlap with a Ni-Cu-family bonus + literal `"700"`/`"8"` bonuses;
  `_follow_up_queries` (932-950) else-branch returns two literal Ni-Cu strings. No unified
  slot planner; slots scattered (year=dates.py ✅, numeric=quantities.py ✅, material half-generic,
  property/process/geography hardcoded/absent).
- Change (per-function, keep deterministic scaffolding + honesty invariants):
  - `_requested_property`: resolve requested property against the packet's actual
    `property_name`/`property_id` set (+ `resources/dictionaries/properties.yml`), not a fixed
    map. Preserve a `conductivity`-style token path for the gap branch (928) / confidence (876).
  - `_regime_matches`: generic content-token overlap between question and `regime_summary`
    (mirror the material-overlap approach) instead of aging/annealing literals.
  - `_score_experiment`: replace the Ni-Cu-family bonus (719-720) + literal `700`/`8` bonuses
    (727-731) with generic numeric-token overlap between question and `regime_summary`.
  - `_follow_up_queries` else-branch (947-950): corpus-derived suggestions from the selected
    experiments' material/property/regime, else `[]` (no test pins these literals).
- Critical: the synthetic fixture IS Ni-30Cu/Vickers/aging-700C-8h; the GENERIC path must still
  select those rows so `test_answer_honesty` / `test_scope_and_constraints` /
  `test_parameter_constraints` stay green. Verify after each function.
- Optional consolidation: a small `domain/query_slots.py` (`QuerySlots` dataclass) unifying
  material/property/regime/numeric/year — do only if it reads cleanly; else defer (review's L).
- Files: `qa_service.py` (+ maybe `domain/query_slots.py`). Risk: M.

### D. Generic CSV/table fall-through (Effort S-M)
- Evidence: `.csv` → `document_type=="table"` (`_document_type_from_filename:1793`) → strict
  experiment path; `_parse_csv_rows` raises on missing 12 cols (`repositories.py:1346`). A
  schema-free row-span path already exists for XLSX/PDF via `ingest_parsed_document` (288-305)
  but is unreachable from CSV. No test pins the "missing required columns" message.
- Change: in `ingest_source_bytes` (188) / `_parse_csv_rows`, when required columns are absent,
  build `ParsedTableRow`s (header+value cells) from the CSV and route through a shared
  `_insert_table_row_spans(...)` helper extracted from `ingest_parsed_document`'s table loop.
  Keep the strict experiment path when all 12 columns are present (row-level validation intact).
- Files: `repositories.py`; tests: add arbitrary-CSV-as-generic-table (extend
  `test_corpus_formats.py` / `test_ingest_api.py`). Risk: S-M. Do before C (shared path).

### C. Persist a queryable numeric-fact layer (Effort M)
- Evidence: only `property_measurements`/`effect_claims` exist; `numeric_facts`=0 grep hits;
  `extract_facts_from_row` (table_facts.py) is never called at ingest; QA re-parses span text at
  query time (`qa_service._drop_constraint_violating_evidence:325-352` →
  `parse_labeled_span_facts`). `answer_claims.supporting_fact_ids_json` column already reserves
  fact refs but no fact table exists.
- Change:
  1. `migrations/003_numeric_facts.sql` (idempotent): `numeric_facts(fact_id PK, source_id,
     span_id, subject, subject_label, prop, value DOUBLE, unit, qualifier TEXT DEFAULT '',
     confidence DOUBLE DEFAULT 1.0, validation_status TEXT DEFAULT 'candidate', created_at)`
     + indexes on `(source_id)`, `(subject)`, `(prop)`. (Pragmatic subset of the Kimball/Wikidata
     research schema — keeps raw subject_label + normalized subject; room for qualifier.)
  2. Persist in the shared table-row-span helper (D): for each row call
     `extract_facts_from_row(headers, values)` → insert `NumericFact`s with the row's `span_id`.
     Add `_delete_fact_records(source_id)` mirroring source re-ingest cleanup.
  3. QA reads it: new `list_numeric_facts_for_spans(span_ids)` (or by subject+unit); switch
     `_drop_constraint_violating_evidence` to SQL-filter facts; fall back to
     `parse_labeled_span_facts` when a source has no persisted facts (backfill safety for
     already-deployed DBs).
- Files: new migration, `repositories.py`, `qa_service.py`; tests: fact persistence unit +
  `test_duckdb_ledger.py`. Risk: M. Do with D.

---

## P1 — quality/scale/ops

### E. Sheet-level provenance in locator (Effort M)
- Evidence: `ParsedTable` (ports/parser.py:52) has no `sheet_name`; spreadsheet parser
  (`adapters/spreadsheet/parser.py:63,88-91`) reads sheet name but only logs it; locator
  (`repositories.py:290`) = `table_{i}:row_{j}`. `locator_json` (dict[str,object]) can already
  hold richer data (evidence.py:48 writes only `{stable_locator, bbox}`).
- Change: add `sheet_name: str | None = None` to `ParsedTable`; pass it in the parser; in the
  locator loop prefix **for spreadsheet tables only** `sheet:{name}:table_{i:03d}:row_{j:03d}`,
  keep the existing `table_{i}:row_{j}` for PDF/docling (pinned by `test_ingestion_service.py:92`
  `"table_1:row_1"`); enrich `locator_json` with `{sheet, headers}` via an optional factory arg.
- Files: `ports/parser.py`, `adapters/spreadsheet/parser.py`, `repositories.py`, `domain/evidence.py`;
  tests: add sheet assertion in `test_corpus_formats.py:81`. Risk: M (shared frozen dataclass +
  shared locator template; PDF format must stay unchanged).

### F. Unify text decoding (Effort S)
- Evidence: `ingestion_service.py:116` (`decode("utf-8","ignore")[:3000]`, corrupts CP1251 head
  for year/geo heuristics) and `repositories.py:202` (markdown `decode("utf-8","replace")`) bypass
  `domain/encoding.py:decode_text_bytes` (cascade utf-8-sig→utf-8→cp1251→charset-normalizer).
- Change: route both sites through `decode_text_bytes(content)[0]`. (Skip persisting detected
  encoding — CSV/markdown path writes no artifacts row; not worth adding one now.)
- Files: `ingestion_service.py`, `repositories.py`; tests: add CP1251 `.md` ingest test
  (markdown decode is currently unpinned). Risk: S.

### G. Archive upload endpoint + dynamic MIME error (Effort S+M)
- Evidence: `/sources/upload` rejects archives (`_ALLOWED_UPLOAD_EXTENSIONS`, sources.py:94);
  `expand_archives(files: list[Path], work_dir) -> (list[Path], Counter)` exists but only the
  batch script uses it. MIME error (sources.py:173-174) hardcodes a CSV/markdown-only "Allowed:"
  list though `allowed_mime_types` is computed per-extension at 168.
- Change:
  1. (S) Dynamic MIME error: `f"Unsupported MIME type '{content_type}' for {extension}. "
     f"Allowed: {', '.join(sorted(allowed_mime_types))}."` (test_api.py:284 pins only the prefix).
  2. (M) `POST /sources/upload-archive`: size-check, spool bytes to `tempfile.TemporaryDirectory`,
     `expand_archives`, loop `ingest_upload(filename=p.name, content=p.read_bytes())` over members,
     enforce `_max_upload_bytes()` per extracted member (decompression-bomb guard), return an
     aggregate manifest `{archive, members:[{member_path, status, reason_code, source_id}]}`.
     Reconcile `.text` vs `.txt` between upload extensions and `INGESTIBLE_EXTENSIONS`.
- Files: `services/api/routes/sources.py` (both); tests: `test_ingest_api.py`/`test_api.py`
  archive-upload integration + MIME reword. Risk: S (MIME) + M (archive).

### H. SQL graph neighborhood (Effort M)
- Evidence: `GraphService.build_graph()` (graph_service.py:16) full-scans ALL entities+relations
  on every `neighborhood()` call (45); `relations.src_entity_id/dst_entity_id` exist but are
  UNINDEXED. Return shape + ranking (type_boost person:1000/publication:500/team:500/lab:500,
  evidence_count desc, keep limit-1) pinned by `test_graph_api.py:46,66,90` + frontend
  `types.ts:99-118`.
- Change (research: per-hop Python with indexed SELECTs = best fit for hard node/edge caps and
  preserves our Python ranking; `UNION`-based recursive CTE is cycle-safe but can't cap
  mid-recursion):
  1. `migrations/004_graph_indexes.sql` (idempotent): `CREATE INDEX IF NOT EXISTS` on
     `relations(src_entity_id)` and `relations(dst_entity_id)`.
  2. `DuckDBLedgerRepository.neighborhood(entity_id, depth, limit)`: per-hop indexed SELECT over
     the undirected edge set (UNION of both directions), bounded to `limit` nodes/edges,
     returning the same node/edge rows the ranking needs.
  3. `GraphService.neighborhood()` uses the repo method, applies the existing type-boost ranking
     over the bounded result; keep `build_graph()` as a dev/fallback path. Response byte-identical.
- Files: new migration, `repositories.py`, `graph_service.py`; tests: `test_graph_api.py` stays
  green + a repo-level neighborhood unit. Risk: M (reproduce ranking + exact shape; undirected
  union both directions).

### I. Expose allowed_labels as a narrow-only request mode (Effort S)
- Evidence: threading done (retrieval_service.py:130-157, qa_service.py:398,134,190); default
  `SourceLabelPolicy` allows all 4 labels; `AskRequest` (models.py:191-198, `extra="forbid"`) has
  no way to narrow. 
- Change: add `allowed_labels: list[SecurityLabel] | None = None` (or `mode: Literal["full",
  "external"]`) to `AskRequest`; in `ask()` build a per-call policy = **intersection** of the
  request mask with the deployment policy (request may only NARROW, never widen — external mode
  must not escalate to confidential/restricted). Default `None` → unchanged. Optional env preset
  in `runtime.py` for a jury deployment default. Keep `extra="forbid"`.
- Files: `domain/models.py`, `qa_service.py`, maybe `runtime.py`; tests: `test_source_label_policy.py`
  + an ask-with-narrowed-labels case. Risk: S (correctness = narrow-only direction).

### J. Semantic support check in the verifier (Effort M)
- Evidence: `ClaimVerifier.verify` (answer_claims.py:36-74) checks citation coverage +
  source-label leak + literal-number support only; `if sentence.supporting_fact_ids: continue`
  (56-60) skips the numeric check for fact-backed sentences; verifier only COUNTS, never rejects.
- Change (research: rule-based containment ≥0.6 + hard num_ok/neg_ok gates; NLI stays out of CI):
  1. Add a deterministic `sentence_semantic_supported(sentence, cited_texts)` helper: content-lemma
     **containment** ratio (drop stopwords/numbers/punct) + a **negation-parity guard**
     (не/нет/без/no/not/never + key antonyms) so "не превышает 5%" vs "превышает 5%" fails. New
     counter `semantic_unsupported_count` (non-blocking metric, default 0).
  2. Stop unconditionally skipping the numeric check when `supporting_fact_ids` present: validate
     the sentence's numbers against the fact-derived values (available once C lands / pass fact
     values into `verify`), else keep the current skip. Avoid false `numeric_mismatch` on
     ledger-derived Δ (documented at answer_claims.py:57-59).
  3. Add fields to `AnswerVerification` (models.py) with default 0 (back-compat; frontend additive).
- Files: `domain/answer_claims.py`, `domain/models.py`, maybe `qa_service.py`; tests:
  `test_claim_verifier.py` (+ negation-parity case), `test_answer_honesty.py`. Risk: M
  (RU lemma/threshold tuning; keep signals non-blocking metrics).

### K. CI/eval smoke for the new paths (Effort S)
- Evidence: gold eval is all synthetic Ni-Cu (`eval/gold_questions.yml`); real-case eval needs the
  real corpus (`DATA_HACK`, out of git). 
- Change: keep `make ci`/`make eval` green; add lightweight STRUCTURAL smoke (no LLM) for the new
  paths — generic CSV ingest, `numeric_facts` persistence+query, SQL neighborhood parity vs
  NetworkX, archive upload, narrowed-labels. Real-corpus gold eval stays a documented P1 TODO.
- Files: tests only. Risk: S.

---

## Sequencing (gates after every wave; commit per wave)
1. Wave A — A (demo removal + rename) → gates.
2. Wave B — B (de-hardcode scoring) → gates (honesty/scope tests are the guard).
3. Wave C — D then C (generic CSV + numeric_facts) → gates.
4. Wave D — E, F (parsing/provenance/decode) → gates.
5. Wave E — G (archive + MIME) → gates.
6. Wave F — H (SQL neighborhood) → gates.
7. Wave G — I, J (labels + semantic) → gates.
8. Wave H — K (eval smoke) + full `make ci`/`make eval` + front build + browser/deploy verify.
9. Post-task: serena sync, PR `feat/backend-hardening` → `main`.

## Non-goals / deferred
- Full Wikidata-grade fact schema (qualifiers/UCUM/rank tables) — pragmatic subset only now.
- Unified `QuerySlots` planner as a first-class module — per-function de-hardcode first.
- JWT/OIDC RBAC — only the narrow-only request mode now.
- Durable jobs table for enrichment/reindex (review P1) — not in this wave.
- NLI/AlignScore model in the grounding check — rule-based only in CI; NLI is a future offline path.
- Real-corpus gold eval — needs `DATA_HACK` ingest; stays a documented TODO.
