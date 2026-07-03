# Plan Critical Review

Date: 2026-07-02
Scope: `.serena/plans/00–07` against the hackathon rules, the existing codebase, and
the two-week deadline. Style follows `.serena/newproj/nornikel-kg-search/15_CRITICAL_REVIEW.md`.

## Executive Verdict

The plan is a vertical extension of a healthy evidence-first scaffold, not a rewrite.
The two failure modes that could sink it are (R1) LLM extraction quality on Russian
scientific prose and (R2) unknowns of the dataeyes provider. Both have deterministic
fallbacks designed in, so the demo cannot go dark — the worst case degrades gracefully.

## Findings (self-critique)

### R1 High: LLM JSON extraction quality is the critical path

Confidence: 85

Risk: small open-weight models may emit invalid JSON or wrong slots on RU scientific
text; W2 gate (>=85% slot accuracy) may fail on the first model choice.

Mitigations in plan: guided JSON (`response_format`/Ollama schema), temperature 0,
Pydantic validation + one retry + rule-only fallback (dictionary/regex slots — the
CSV path already proves the slot model); per-span batching keeps prompts small;
GLiNER pre-pass narrows candidate mentions; `extraction_claims` audit allows cheap
re-runs with a different model without re-parsing.

Residual risk: acceptable — the synthetic corpus is generated from a ground-truth
registry, so extraction is measurable daily and model swap is a config change.

### R2 High: dataeyes.ai is only partially verified

Confidence: 90 (that it is a risk), facts registered in the evidence register

Known: Singapore reseller, `https://api.dataeyes.ai` base, env conventions, catalog
mixes proprietary (GPT/Claude/Gemini/Grok — forbidden for us) with open-weight-class
entries (DeepSeek V4, GLM 5.2, Kimi K2.7, MiniMax M3). Unknown: exact `/v1` path
shape, `json_schema` support, embeddings availability, rate limits, small-model
availability, RU quality of catalog models.

Mitigations: W0 discovery hour is the first task with a hard deliverable (model
matrix); embeddings are local by default so provider embeddings are a bonus, not a
dependency; Ollama fallback profile (`qwen3:4b/8b`, Apache-2.0) is pre-designed;
weights-openness check on the exact model version is a hard gate before configuring.

### R3 High: catalog "open-weight" labels can be wrong per version

Confidence: 80

"Qwen 3.7 Max" is likely API-only (Max tier historically proprietary); "DeepSeek V4
Pro" openness is unverified for the Pro variant. Configuring a closed-weight model
would violate the track rules even through an allowed router.

Mitigation: rule in `01_MVP_SCOPE_AND_DECISIONS.md` — a model may be configured only
after its exact version's weights are found on HF; the pitch includes the
model/license table, making compliance auditable. Safe harbor: Ollama-served Qwen3.

### R4 Medium: Docling footprint and first-run latency

Confidence: 75

torch-CPU + TableFormer weights enlarge the API image and first run. Mitigations:
HF cache volume + `make warmup` + BuildKit cache mounts; DOCX path needs no ML
weights; quarantine keeps parser failures honest. Residual: image size is a
cosmetic cost, not a functional risk.

### R5 Medium: Langfuse SDK v2 callback vs v3 server

Confidence: 70

LiteLLM documents the callback with `langfuse==2.59.x` (SDK v2) while the server
stack is v3; v3 recommends OTEL. Plan pins SDK v2 (documented compatible ingestion)
and pre-records the OTEL fallback decision. Observability failure never blocks the
app (fire-and-forget callbacks) — worst case the pitch loses live cost numbers, for
which `answer_runs` keeps a local copy of tokens/latency.

### R6 Medium: DuckDB single-writer concurrency under live ingest + QA

Confidence: 70

Current code opens short-lived connections per operation and the repository build is
lock-guarded, but W1 adds long ingest transactions concurrent with QA reads.
Mitigation: ingest stages commit in small transactions (per-span batches); a single
process-level write lock (existing pattern) serializes writers; QA reads are
snapshot-consistent. At demo scale (tens of documents) this is sufficient; Postgres
remains the documented scale path.

### R7 Low: react-force-graph React 19 peer range

Confidence: 60

No blocking issue found in public tracker, but not positively verified against
React 19.2. Plan makes it a same-day decision in W4 with `reagraph` (Apache-2.0,
React-native WebGL) as the tested fallback. UI risk is contained to one widget.

### R8 Low: fastembed lacks bge-m3 — dense/sparse split across two libraries

Confidence: 85 (fact confirmed)

Dense goes through sentence-transformers (torch already present), sparse through
fastembed BM25. Two embedding stacks is mild complexity; accepted because it keeps
the best RU dense model (USER-bge-m3) and the cheapest robust sparse (BM25 + RRF).
Alternative (all-fastembed with multilingual-e5-large ONNX) is pre-approved as a
one-line config change if sentence-transformers misbehaves in the container.

### R9 Guarded: demo overfitting to synthetic corpus

Confidence: 80

Threat: tuning extraction/eval until they only work on our generated documents.
Mitigations: corpus and gold questions derive from one ground-truth registry but
documents vary phrasing/language/layout; W0 keeps ingest format-agnostic; negative
controls and family queries stay in eval; the demo script explicitly ingests a NEW
document live (not in the eval set).

## Anti-Over-Engineering Checklist (what we consciously did NOT include)

- No graph-RAG framework, no Neo4j/Postgres/queues/S3, no LiteLLM proxy, no OCR,
  no reranker, no review UI, no auth — all have documented extension points instead.
- No materialized `conflict_groups`/`data_gaps`/`retrieval_units` tables — computed
  on demand at MVP scale (sync burden > demo value).
- Decisions/conclusions are entity rows, not new tables/services.
- One LLM gateway module; one prompt family adapted from MIT LightRAG rather than a
  prompt framework.

## Rejected Alternatives (register)

| Alternative | Why rejected |
| --- | --- |
| Adopt LightRAG/RAG-Anything wholesale | provenance lives in framework chunk-ids -> breaks EvidenceSpan contract; parallel storage; DuckDB unsupported |
| Microsoft GraphRAG | indexing cost (LLM-heavy), Parquet pipeline beside our ledger |
| Cognee / RAGFlow / kotaemon / txtai | platform-shaped or similarity-graph; not embeddable over our ledger |
| Kuzu embedded graph DB | archived Oct 2025 — dead upstream |
| DuckPGQ for graph queries | community extension, not production-stable; recursive CTE + NetworkX suffice |
| YandexGPT-5-Lite / Saiga(Llama) / Gemma 3 | proprietary or restrictive community licenses vs "non-proprietary" rule |
| PyMuPDF4LLM as main parser | AGPL-3.0; weak tables. marker: GPL + gated weights; MinerU: GPU-oriented |
| Provider embeddings as default | unverified availability; local USER-bge-m3 is deterministic and free |
| LiteLLM Proxy server | extra service; SDK callbacks give the same observability |

## Open Questions To Owner (non-blocking, needed before W5)

1. Final public domain/URL for the new stand (nginx vhost + README links).
2. dataeyes key scope/limits (is there a spend cap to respect in `LLM_MAX_CONCURRENCY`?).
3. Does the new server have a GPU? (Only changes Ollama fallback speed; plan assumes CPU.)
4. Presentation slot format (minutes, live vs recorded) — affects demo-script timing.
5. Will organizers provide a real corpus before the deadline? If yes, W5 reserves a
   half-day calibration pass (dictionaries + one extraction prompt iteration).

## Verification Of This Review

Each High/Medium finding maps to an explicit task or standing rule in
`03_IMPLEMENTATION_PLAN.md`: R1 -> W2.2; R2/R3 -> W0.1 + model policy in plans/01;
R4 -> W0.3 + `make warmup` (plans/06); R5 -> W0.5 + W5.3; R6 -> standing rule on
transactional ingest. No mitigation exists only on paper here.
