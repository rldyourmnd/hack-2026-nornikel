# Implementation Plan (Two Weeks)

Date: 2026-07-02
Deadline: ~2026-07-16 (live stand + GitHub repo + pitch)
Team: owner + Claude Code, solo-operated

## Purpose

Wave-by-wave build order with acceptance gates, effort, and cut lines. Each wave ends
committed, `make ci` green (no network/secrets needed), and demoable on the stand.

## Standing Rules (every wave)

- All LLM/embedding/network calls sit behind ports with deterministic fakes;
  CI never needs secrets and never calls the network.
- Keep the deterministic QA path working at all times (`LLM_ENABLED=false` mode) —
  it is the demo's safety net.
- Extend `tests/`, `eval/`, and Serena memories in the same change as behavior.
- Conventional atomic commits; feature branches merged to `main` per wave.
- DuckDB writes stay serialized: ingest stages commit in small per-batch transactions
  under the existing process-level write lock; QA reads remain snapshot-consistent
  (single-writer discipline — Postgres is the documented scale path, not an MVP fix).

## W0 — Alignment And Seams (Day 1)

| # | Task | Acceptance |
| --- | --- | --- |
| 0.1 | Provider discovery with the dataeyes key: `GET {DATAEYES_API_BASE}/v1/models` (also try without `/v1`); smoke `chat/completions` (RU JSON schema) and `embeddings` if present; record catalog + verify weights-openness of shortlisted models on HF | Model matrix committed to `06_DEPLOYMENT_AND_OBSERVABILITY.md`; extraction+answer model IDs chosen; embeddings decision confirmed (expected: local) |
| 0.2 | Docs amendments per `01_MVP_SCOPE_AND_DECISIONS.md` (19_OWNER_DECISIONS amendment, 05/08 tech-stack LLM sections, `.env.example`, README scope) | `rg` check from 01 passes |
| 0.3 | Dependency wave: add `ingest` extra to API image (docling, torch CPU), `gliner`, `sentence-transformers`, `fastembed`, `trafilatura`, `langfuse==2.59.*`; pin versions; HF cache volume (`HF_HOME=/app/data/hf-cache`) | `uv lock` clean; image builds; `make ci` green |
| 0.4 | Migration `002_graph.sql` (tables from `02_TARGET_ARCHITECTURE.md`) + dictionaries loader (`resources/dictionaries/*.yml` -> entities + entity_aliases seed) | Unit tests: loader idempotent; aliases resolve `МН30`->CuNi30 |
| 0.5 | `adapters/llm/gateway.py` + `FakeLLM` + Langfuse callback wiring behind `LLM_ENABLED` | Gateway unit tests with fake; no litellm import outside adapter |

Cut line: none — W0 is mandatory.

## W1 — Ingest Vertical (Days 2–4)

| # | Task | Acceptance |
| --- | --- | --- |
| 1.1 | `DocumentParserPort` + Docling adapter: PDF (`do_ocr=False`, `do_table_structure=True`), DOCX; artifacts under `data/artifacts/sources/src_<hash>/`; EvidenceSpans for text blocks (page+locator) and table_row/table_cell | Upload real PDF+DOCX -> spans listed in UI with correct page/locator; table rows are separate spans |
| 1.2 | `ingestion_runs` lifecycle + quarantine: text-layer-absent PDF or parser error -> `quarantined`, never 500; `/sources` exposes run status | Integration test with a no-text-layer PDF fixture |
| 1.3 | URL ingest: `POST /sources/import-url` -> trafilatura -> text artifact + spans (title/date metadata kept) | HTML fixture ingested; URL source visible in artifact bank |
| 1.4 | Upload surface update: accept `.pdf/.docx` (+ size/MIME rules extended), frontend accept list + status chips | API tests for new types; browser check |
| 1.5 | Fix latent 500: empty-ledger `load_demo_packet` LookupError -> graceful empty packet | Regression test: delete all sources -> `/qa/ask` returns empty grounded result |

Gate: fresh checkout -> upload PDF/DOCX/URL -> spans visible with provenance; CI green.
Cut line: 1.3 (URL) can slip to W4 if Docling integration overruns.

## W2 — Extraction, Resolution, Graph Tables (Days 5–7)

| # | Task | Acceptance |
| --- | --- | --- |
| 2.1 | GLiNER service (multi-v2.1, chunked spans, RU/EN labels) -> entity mentions with offsets | Unit test on RU+EN fixtures; CPU latency logged |
| 2.2 | LLM extraction (guided JSON, LightRAG-style prompt adapted; per-span batching; retry then rule-only fallback) -> `extraction_claims` + candidate facts | With FakeLLM in CI; with real model on server fixture: >=85% slot accuracy on synthetic gold |
| 2.3 | EntityResolutionService: canonical_key -> aliases -> Qdrant embedding fallback (>=0.90) -> create; merge appends evidence + aliases; conflict guard (composition/params) | Unit tests incl. alias merge and near-duplicate materials that must NOT merge (`Ni-30Cu` vs `Ni-20Cu`) |
| 2.4 | Relations + measurements/effects writes (evidence-carrying), wired into ingest pipeline after parse | Upload doc -> new entities+relations appear linked to existing graph (auto-link demo works) |
| 2.5 | `/entities/search`, `/entities/{id}` (card with evidence), NetworkX `GraphService` + `/graph/neighborhood` | API tests; neighborhood JSON has typed nodes/edges with evidence counts |

Gate: uploading a new synthetic DOCX visibly extends the graph (new nodes + edges to
existing material/property nodes) without manual steps.
Cut line: relation types beyond the core experiment path (equipment/team/decision) drop
to W4 if extraction quality needs tuning time.

## W3 — Retrieval And LLM QA (Days 8–9)

| # | Task | Acceptance |
| --- | --- | --- |
| 3.1 | Qdrant adapter: `evidence_units` (dense+sparse, payload filters) + `entities` collections; indexing hooked into ingest; reindex command | Collections rebuildable from DuckDB alone (`make reindex`) |
| 3.2 | Hybrid retrieval in QA (RRF prefetch, security-label payload filter, DuckDB rejoin + allowed-span recheck) | Retrieval unit tests with tiny local Qdrant (docker) or recorded fixtures; leak tests stay 0 |
| 3.3 | LLM answer synthesis (strict JSON sentences w/ span ids, packet-only) + ClaimVerifier gate + one regenerate + deterministic fallback | Adversarial fixtures: unsupported sentence never reaches response; injection fixtures pass |
| 3.4 | `answer_runs` persistence + `/qa/runs/{run_id}` (replay metadata) | Run recorded with model, tokens, latency; visible in Langfuse trace by run_id |

Gate: gold QA set passes thresholds from `05_QUALITY_GATES_AND_EVAL.md` with real LLM
on the server; `make eval` (deterministic mode) still green offline.
Cut line: 3.4 endpoint can slip to W5 (persistence itself stays).

## W4 — Frontend Experience (Days 10–11)

| # | Task | Acceptance |
| --- | --- | --- |
| 4.1 | Graph neighborhood widget: `react-force-graph-2d` (React 19 peer check at install; fallback `reagraph` decided same day), typed colors, click-expand, node panel with evidence | Browser validation desktop+mobile; 500-node fixture stays interactive |
| 4.2 | Gaps board: coverage matrix (material x regime x property) from `/gaps/analyze`; empty cells -> one-click follow-up query | Matrix matches seeded gaps exactly |
| 4.3 | Conflict detector + cards: same material+property+regime-bucket with opposite direction or >15% delta (same method) or method mismatch | Seeded conflicts detected; hardcoded string-match removed |
| 4.4 | Decisions timeline widget (dated decision/conclusion entities with evidence) | Timeline shows seeded decisions in order |
| 4.5 | Real eval dashboard: `/eval/summary` reads latest `eval_results` (hardcoded recall removed); ingest status chips polish | Dashboard equals last `make eval-full` run |

Gate: full demo script (07) clickable end-to-end on the stand; screenshots archived.
Cut line: 4.4 timeline is the first drop; 4.2 matrix collapses to a gap list if needed.

## W5 — Corpus, Eval, Deploy, Pitch (Days 12–14)

| # | Task | Acceptance |
| --- | --- | --- |
| 5.1 | Synthetic corpus x10 final (04 plan): generator + committed fixtures + manifest | Clean-checkout ingest of full corpus succeeds; counters match manifest |
| 5.2 | Eval expansion: 25–40 gold questions incl. alias, URL-source, conflict, gap, negative, adversarial; `make eval` (fake) + `make eval-full` (real LLM, writes `eval_results`) | Thresholds met; numbers exported for pitch |
| 5.3 | New server rollout: app compose + Langfuse compose project, volumes, nginx, healthchecks; migrate from fa.nddev.asia; smoke script | Public URL smoke: health, ask, upload, graph; Langfuse traces visible |
| 5.4 | Hardening: LLM concurrency cap + timeouts; ingest size/time guards; error surfaces in UI; backup script (duckdb+artifacts+qdrant snapshot) | Parallel-ask smoke (5 concurrent) stable; restore drill documented |
| 5.5 | Demo script + pitch deck numbers (07): per-answer tokens/cost from Langfuse, model sizes, latency; README/architecture polish for repo judges | Deck data table filled; README quick start reproduced on clean machine |

Gate: everything in `05_QUALITY_GATES_AND_EVAL.md` green; stand frozen 1 day before
deadline (buffer for surprises).

## Effort Summary

| Wave | Days | Risk buffer |
| --- | --- | --- |
| W0 | 1 | — |
| W1 | 3 | Docling integration unknowns |
| W2 | 3 | extraction quality tuning |
| W3 | 2 | provider behavior |
| W4 | 2 | graph lib compat |
| W5 | 3 | deploy + polish + 1 frozen buffer day |

Global cut order if the schedule slips: timeline (4.4) -> URL ingest (1.3) ->
gaps matrix->list (4.2) -> Ollama fallback (config stays documented) -> reduce corpus
to ~15 sources. Never cut: PDF/DOCX ingest, auto-linking, graph view, evidence-first
verification, real eval numbers.
