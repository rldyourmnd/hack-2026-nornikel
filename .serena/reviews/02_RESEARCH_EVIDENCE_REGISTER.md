# Research Evidence Register

Date checked: 2026-07-02
Method: two deep-research agent reports (GitHub API metadata, DeepWiki source
analysis, HF model cards, official docs) + targeted direct web verification.
Confidence: Confirmed = primary source read; Likely = strong secondary/known-stable;
Unverified = must be checked during implementation (owner of the check named).

## Graph-RAG Frameworks (decision: pattern, not framework)

| Fact | Confidence | Source |
| --- | --- | --- |
| LightRAG: MIT, ~37k stars, active (v1.5.4 06.2026); incremental insert with entity auto-merge; backends Qdrant/NetworkX/Postgres/Neo4j; DuckDB not supported; provenance = own chunk-ids; web UI React+Sigma.js | Confirmed | github.com/HKUDS/LightRAG; deepwiki.com/HKUDS/LightRAG |
| LightRAG entity resolution = exact normalized-name match; descriptions concatenated; LLM summarization only above token threshold | Confirmed | deepwiki.com/HKUDS/LightRAG (source-level) |
| fast-graphrag: MIT; embedding-threshold entity resolution (default cosine 0.9) + LLM merge policies; in-memory igraph/hnswlib; low release activity | Confirmed | deepwiki.com/circlemind-ai/fast-graphrag |
| Microsoft GraphRAG: MIT, incremental since 0.4.0, uses LiteLLM; indexing is LLM-cost-heavy; Parquet pipeline | Confirmed | deepwiki.com/microsoft/graphrag |
| RAG-Anything: MIT, embeddable LightRAG+parser bundle (MinerU/Docling) | Confirmed | deepwiki.com/HKUDS/RAG-Anything |
| RAGFlow/kotaemon = standalone platforms (own infra: ES/Infinity+MySQL+MinIO+Redis / Gradio app) | Confirmed | deepwiki.com/infiniflow/ragflow; github Cinnamon/kotaemon |
| Cognee: Apache-2.0, active, Qdrant-capable but brings triple-DB model | Confirmed | deepwiki.com/topoteretes/cognee |
| LightRAG extraction prompts live in `lightrag/prompt.py` (tuple-delimiter format), MIT-borrowable | Confirmed | deepwiki.com/HKUDS/LightRAG |

## Parsing / URL Ingest

| Fact | Confidence | Source |
| --- | --- | --- |
| Docling: MIT code, very active (v2.108 07.2026); DOCX/PPTX/XLSX native without ML weights; PDF tables via TableFormer (FAST/ACCURATE); CPU-capable; OCR optional (we disable) | Confirmed | deepwiki.com/docling-project/docling; github |
| Docling API details used in plan (PdfPipelineOptions.do_ocr/do_table_structure, artifacts_path/HF cache, provenance page+bbox, TableItem grid/export) | Likely (docs page fetch returned nav only; API stable in pinned `docling>=2.66`) | docling docs; version pinned in pyproject — verify in W1.1 |
| PyMuPDF4LLM = AGPL-3.0 (rejected as main parser); marker = GPL-3.0 + OpenRAIL-M gated weights; MinerU = Apache-2.0 + thresholds, GPU-oriented | Confirmed | respective LICENSE files (fetched 2026-07-02) |
| trafilatura: Apache-2.0, active v2.1 (06.2026), `fetch_url`+`extract`, metadata incl. title/date | Confirmed | github.com/adbar/trafilatura |

## Models And Licenses

| Fact | Confidence | Source |
| --- | --- | --- |
| Qwen3 family (0.6B–32B+): Apache-2.0, strong multilingual (119 langs) | Confirmed | qwenlm blog; arXiv 2505.09388; HF cards |
| RuadaptQwen3-4B/8B-Instruct: Apache-2.0; RU tokenizer (+~48k tokens) -> up to 2x faster RU generation | Confirmed | HF RefalMachine/RuadaptQwen3-4B-Instruct |
| RuadaptQwen3 GGUF availability for Ollama | Unverified — check HF in W0; fallback `ollama qwen3:4b/8b` (official) | — |
| GigaChat 3 Lightning (10B-A1.8B MoE): MIT, GGUF available, fast CPU inference | Confirmed | HF ai-sage; github salute-developers |
| T-pro 2.0 (32B, Apache-2.0): top open RU (MERA 0.66); T-lite Apache-2.0 | Confirmed | arXiv 2512.10430 |
| YandexGPT-5-Lite: proprietary license (10M tokens/mo cap + negotiation clause) — excluded | Confirmed | HF yandex LICENSE |
| Llama Community license (Saiga base) and Gemma 3 terms = restrictive/custom — excluded under "non-proprietary"; Gemma 4 is Apache-2.0 | Confirmed | llama.com license; ai.google.dev/gemma/terms |
| vLLM guided JSON (xgrammar default) and Ollama `format=<json schema>` structured outputs work incl. Qwen3; temperature 0 recommended | Confirmed | docs.vllm.ai; docs.ollama.com/capabilities/structured-outputs; ollama blog |
| LiteLLM Ollama route: `ollama_chat/<model>` recommended | Likely | litellm docs (provider page not re-fetched) — verify in W0.5 |

## Embeddings / Retrieval

| Fact | Confidence | Source |
| --- | --- | --- |
| USER-bge-m3 (deepvk): Apache-2.0, 1024-dim, ruMTEB 0.706 (> bge-m3 0.689) | Confirmed | HF deepvk/USER-bge-m3; ruMTEB (arXiv 2408.12503) |
| bge-m3: MIT, dense+sparse+colbert, 8192 ctx | Likely (widely documented; card not re-fetched this session) | HF BAAI/bge-m3 |
| fastembed does NOT ship bge-m3/USER-bge-m3 dense; multilingual dense = e5-large (2.24GB) etc.; sparse: Qdrant/bm25, bm42, SPLADE(EN); rerankers incl. jina-v2-multilingual | Confirmed | qdrant.github.io/fastembed Supported Models (fetched 2026-07-02) |
| Qdrant hybrid: dense+sparse Prefetch + FusionQuery RRF; sparse via fastembed; IDF modifier for BM25 | Confirmed | qdrant docs/articles (incl. bm42) |
| bge-reranker-v2-m3: Apache-2.0, multilingual, CPU-viable for small candidate sets (not in MVP) | Confirmed | HF BAAI/bge-reranker-v2-m3 |

## NER / Graph Viz / Graph Storage

| Fact | Confidence | Source |
| --- | --- | --- |
| GLiNER `urchade/gliner_multi-v2.1`: Apache-2.0, multilingual zero-shot NER, char offsets | Confirmed | HF card (search-verified 2026-07-02); github urchade/GLiNER |
| Natasha/Slovnet: MIT, RU-only, ~30MB CPU-fast (optional helper) | Confirmed | github natasha/slovnet |
| MatSciBERT: EN-only — not applicable | Confirmed | arXiv 2109.15290 |
| react-force-graph: MIT, canvas/WebGL force graphs; no confirmed React 19 blocker found (not positively verified either) | Likely — verify at install (W4.1), fallback reagraph (Apache-2.0) | github vasturiano/react-force-graph (issues scan) |
| Kuzu archived Oct 2025 — avoid | Confirmed | The Register 2025-10-14; github kuzudb |
| DuckPGQ: community extension, active research project, not production-stable — not in MVP | Confirmed | duckdb.org community_extensions; github cwida/duckpgq |

## Provider (dataeyes.ai)

| Fact | Confidence | Source |
| --- | --- | --- |
| Operator: SG DataEyesAI Technology Limited (Singapore); global site dataeyes.ai (CN mirror shuyanai.com) | Confirmed | dataeyes.ai (fetched 2026-07-02); github dataeyesai |
| API base env convention: `DATAEYES_API_BASE_URL` default `https://api.dataeyes.ai`; key auth | Confirmed (for their MCP tooling; chat API path shape still to confirm) | github dataeyesai/dataeyes-mcp-server |
| Catalog (public pages): GPT-5.5, Claude Opus 4.8, Gemini 3.5 Flash, Grok (FORBIDDEN for us) + DeepSeek V4 Pro, Qwen 3.7 Max, GLM 5.2, MiniMax M3, Kimi K2.7, ByteDance Seed 2.0 | Confirmed (page snapshot) | dataeyes.ai/models |
| OpenAI-compatible `/v1/chat/completions`, `json_schema` support, embeddings endpoint, rate limits, small-model availability | Unverified — W0.1 discovery with the owner key | — |
| Weights-openness of exact catalog versions (DeepSeek V4 "Pro", "Qwen 3.7 Max", GLM 5.2, Kimi K2.7) | Unverified — HF check required before configuring (rule in plans/01) | — |

## Observability

| Fact | Confidence | Source |
| --- | --- | --- |
| Langfuse v3 self-host = 6 containers (web, worker, Postgres, ClickHouse, Redis, MinIO); ~4 vCPU/8GB comfortable; official docker-compose | Confirmed | langfuse.com/self-hosting (+containers/clickhouse pages) |
| LiteLLM SDK callback: `litellm.success_callback=["langfuse"]`, env LANGFUSE_PUBLIC_KEY/SECRET_KEY/HOST; docs pin `langfuse==2.59.7`; v3 prefers OTEL integration | Confirmed | docs.litellm.ai/docs/observability/langfuse_integration (fetched 2026-07-02) |
| metadata trace fields (trace_id, session_id, tags) pass through litellm `metadata` | Confirmed | same litellm docs page |
| SDK v2 ingestion accepted by self-hosted v3 server | Likely — smoke-test in W5.3; fallback OTEL pre-decided | langfuse upgrade guides |

## Gap Analysis Prior Art

| Fact | Confidence | Source |
| --- | --- | --- |
| Coverage-matrix + link-prediction gap detection is established for materials KGs (MatKG, PropNet) | Confirmed | arXiv 2210.17340; Nature Sci Data 2024; PropNet (Matter 2019) |

## Fonts (synthetic PDF generation)

| Fact | Confidence | Source |
| --- | --- | --- |
| DejaVu Sans covers Cyrillic; Bitstream Vera-derived license permits bundling; reportlab needs explicit TTF registration | Likely (well-known stable; not re-fetched) | dejavu-fonts.github.io — verify file path in W5.1 |

## Change Rules

When any Unverified/Likely row is checked during implementation, update its row in
place with the result and date; do not delete history (strike-through + note).
