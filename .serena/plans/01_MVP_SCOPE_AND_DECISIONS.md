# MVP Scope And Decisions

Date: 2026-07-02
Status: locked by owner (session decisions, two clarification rounds)

## Purpose

Fix the decisions that drive the two-week MVP build and record where they supersede
`.serena/newproj/nornikel-kg-search/19_OWNER_DECISIONS.md`.

## Hackathon Rule Deltas (supersede prior owner decisions)

The track organizers clarified rules that invalidate part of the original plan:

1. **Proprietary LLM APIs are forbidden.** OpenAI and Anthropic APIs must not be used.
   Open-weight models are allowed, including through API routers, as long as they are
   usable from Russia without extra technical measures.
   - Supersedes: `19_OWNER_DECISIONS.md` "Target answer/extraction model is
     `openai/gpt-5.5-mini`" and `openai/text-embedding-3-large` defaults in
     `05_TECH_STACK.md`, `08_INFRA.md`, and `.env.example`.
2. **Resource economy is a judged criterion.** Smaller models at equal accuracy score
   higher. The pitch must show per-answer cost/tokens and model sizes.
3. **The system must both answer questions and autonomously form new links** when the
   knowledge base grows. Auto-linking on ingest is a first-class demo requirement.
4. **Corpus shape:** mostly Word/PDF files with a text layer, plus online resources.
   Images carry no required text. OCR is therefore out of MVP scope; PDFs without a
   text layer are quarantined, not OCRed.

## Locked Owner Decisions (2026-07-02)

| Topic | Decision |
| --- | --- |
| LLM access | Hybrid: `dataeyes.ai` API key (owner-provided) through the LiteLLM SDK now; optional self-hosted Ollama fallback closer to the finals |
| Model policy | Only open-weight models from the provider catalog (DeepSeek/Qwen/GLM/Kimi class). Proprietary entries in the same catalog (GPT/Claude/Gemini/Grok) must never be configured |
| Observability | Self-hosted Langfuse on the server; LiteLLM native callback |
| Graph core | Own graph layer over the existing DuckDB ledger (LightRAG pattern: extract -> canonical key -> exact/alias match -> embedding fallback -> merge with EvidenceSpan provenance). No graph-RAG framework adoption |
| Corpus | Synthetic corpus scaled ~x10 (PDF/DOCX/CSV/MD/URL fixtures with seeded conflicts, gaps, teams, equipment, decisions); ingest stays ready for a real organizer corpus |
| Demo features | All four: (1) PDF/DOCX/URL ingest, (2) auto-linking on upload, (3) interactive graph, (4) systematic gaps/conflicts + decision history |
| Hosting | Migration to a new, more powerful server (owner-provided; sized for Langfuse v3 + local embeddings + optional Ollama). `fa.nddev.asia` remains the working stand until then; final public URL comes later |
| Deadline | ~2 weeks from 2026-07-02 (target 2026-07-16) |
| Delivery | Live stand (public URL) + GitHub repository + pitch deck presentation |

## Model Selection Policy

Exact model IDs are finalized during the W0 provider discovery (see
`03_IMPLEMENTATION_PLAN.md`), because the dataeyes catalog is only partially public.
Requirements, in priority order:

- **Extraction model:** small open-weight instruct model (4-9B class preferred),
  strong Russian, reliable JSON via `response_format`/guided decoding.
- **Answer model:** open-weight, strong Russian generation, mid-size acceptable.
- **Weights-openness check:** before configuring any catalog model, verify the exact
  version has published weights (Hugging Face) — e.g. "Qwen ... Max" tiers are
  historically API-only and would violate the rules even though Qwen3 open releases
  do not.
- **Fallback (self-host):** Ollama with `qwen3:4b`/`qwen3:8b` (Apache-2.0) or
  RuadaptQwen3-4B/8B-Instruct GGUF if published; structured output via Ollama JSON
  schema `format`.
- **Embeddings:** local by default — `deepvk/USER-bge-m3` (Apache-2.0, 1024-dim,
  ruMTEB leader for its size) via sentence-transformers; sparse `Qdrant/bm25` via
  fastembed. Provider embeddings only if discovery shows a suitable open-weight
  embedding endpoint.

## Explicit Non-Goals (over-engineering guard)

Not in this MVP, even if time remains — extension points stay documented instead:

- Neo4j, PostgreSQL, worker queues, S3/MinIO for artifacts (ports already isolate them).
- User auth / RBAC (source security labels only, as before).
- OCR and chart digitization (text-layer-only ingest; quarantine otherwise).
- LiteLLM Proxy server (SDK-as-library only), agentic tool use, chat history.
- Human review workflow UI (approve/reject queue) — validation statuses exist in data,
  a UI is P2 at most.
- Ontology editor, RDF/OWL, community-level GraphRAG summaries.
- Fine-tuning or training of any model.

## Documentation Amendments Required During W0

- `19_OWNER_DECISIONS.md`: append a dated amendment section pointing to this file.
- `05_TECH_STACK.md` + `08_INFRA.md` + `.env.example`: replace OpenAI model defaults
  with the open-weight env matrix from `06_DEPLOYMENT_AND_OBSERVABILITY.md`.
- `README.md`: current scope, quick start with LLM flags, new architecture summary.

## Verification

- `rg -n "gpt-5.5|text-embedding-3" .env.example .serena/newproj README.md` returns
  only historical/amended mentions after W0.
- Demo configuration references only models with verified open weights.
