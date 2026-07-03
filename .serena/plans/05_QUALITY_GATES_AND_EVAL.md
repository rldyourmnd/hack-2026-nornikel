# Quality Gates And Evaluation

Date: 2026-07-02
Status: planned (gates enforced per wave; thresholds align with `18_IMPLEMENTATION_SPEC.md`)

## Purpose

Define what "done" means for each capability: metrics, thresholds, test layout, CI
rules, and the split between offline-deterministic and LLM-backed evaluation.

## Two Eval Modes

| Mode | Command | LLM | Where | Writes |
| --- | --- | --- | --- | --- |
| Deterministic | `make eval` | FakeLLM (`LLM_ENABLED=false`) | CI + local | stdout JSON (existing contract) |
| Full | `make eval-full` | real provider models | server/local with key | `eval_results` table + stdout |

CI rule (hard): CI never uses network or secrets. Every LLM-path test runs against
`FakeLLM` fixtures. `eval-full` is a manual/server gate before demo freeze.

## Thresholds (demo corpus)

| Metric | Threshold | Measured in |
| --- | --- | --- |
| EvidenceRecall@10 | >= 0.80 | full |
| TableRowRecall@10 | >= 0.75 | full |
| Citation coverage | >= 0.95 (demo questions: 1.0) | both |
| Unsupported claim count | = 0 | both |
| Source-label leak count | = 0 | both |
| Prompt-injection success | = 0 | both |
| Numeric value+unit accuracy | >= 0.85 | full |
| Effect direction accuracy | >= 0.80 | full |
| Entity resolution accuracy (curated aliases) | >= 0.85 | full |
| Gap detection precision on seeded gaps | >= 0.80 (target: exact match) | both |
| Extraction slot accuracy (synthetic gold) | >= 0.85 | full |

`/eval/summary` serves the latest `eval_results` row + run date; the current
hardcoded `recall = 1.0` is removed in W4 (no fake metrics on the dashboard).

## Performance Budget

| Path | Budget | Notes |
| --- | --- | --- |
| PDF ingest (text layer, no OCR) | <= ~60 s/doc CPU | includes extraction LLM calls; async status via `ingestion_runs` |
| `/qa/ask` with LLM | p50 <= ~8 s, p95 <= 20 s | measured via `answer_runs.latency_ms`; concurrency cap protects the stand |
| `/qa/ask` deterministic | <= 1 s | fallback path |
| Graph neighborhood (depth 2, 500 nodes) | <= 1 s server-side | NetworkX on-demand build acceptable at MVP scale |
| Token budget | logged per run (Langfuse) | pitch metric: avg tokens + cost per answer |

## Test Plan Delta

Unit (`tests/unit/`):
- normalizers (material/regime/property canonical keys, dashes, ё/е, RU/EN),
- dictionaries loader idempotency, alias resolution incl. «МН30»,
- entity resolution decision table (exact/alias/embedding/create; no-merge guards),
- conflict detector (direction, >15% delta same method, method mismatch buckets),
- gap coverage query against seeded registry,
- LLM gateway: JSON-schema validation, retry, fallback, budget guard (FakeLLM),
- claim verifier regeneration/degradation path.

Integration (`tests/integration/`):
- Docling ingest of fixture PDF+DOCX -> spans with page/locator/table structure,
- quarantine path (no-text-layer PDF),
- URL ingest fixture,
- extraction pipeline with FakeLLM -> entities/relations/measurements written,
- auto-link: second document merges into existing entities (alias + embedding stub),
- Qdrant hybrid retrieval (dockerized qdrant in local run; recorded/embedded
  fallback in CI if container unavailable — decide once in W3, keep one way),
- `/qa/ask` LLM mode with FakeLLM: citations verified, injection fixtures,
- `/entities/search`, `/graph/neighborhood`, `/gaps/analyze`, `/eval/summary`.

Frontend: `npm run typecheck` + `npm run build` (existing) + browser validation
checklist per wave (desktop + mobile screenshots, ignored `browser/` prefix).

## Browser Validation Checklist (W4/W5)

1. Upload PDF -> status chip running -> completed -> spans visible.
2. Upload DOCX that references existing material -> graph gains linked nodes.
3. Ask ideal question -> answer sentences with evidence cards + graph path.
4. Open neighborhood, expand a node, open evidence from node panel.
5. Gaps board shows seeded empty cells; click -> follow-up query runs.
6. Conflict card shows both sides.
7. Timeline shows dated decisions.
8. Eval dashboard shows last real run numbers.
9. Mobile layout sanity for ask + evidence.

## Security Gates (unchanged, re-verified each wave)

- Allowed sources resolved before retrieval; Qdrant payload filter + post-retrieval
  recheck; packet-only LLM context; injection spans treated as untrusted data.
- Fixtures: `source_label_leak_count = 0`, `prompt_injection_success_count = 0`,
  restricted-source doc never enters packets.

## Release Gate Before Demo Freeze

`make ci` && `make eval` && `make eval-full` (thresholds) && clean-checkout
`docker compose up --build` && public smoke (health/ask/upload/graph) &&
browser checklist archived && stand frozen >= 24h before deadline.
