# Source Register

Project: Nornikel Materials Knowledge Graph and Search

Date: 2026-06-28

## Research Questions

1. Which architecture can answer evidence-backed questions over materials, regimes, experiments, equipment, teams, and conclusions?
2. Which storage and retrieval pattern is most suitable for a hackathon MVP while still scaling to an internal research corpus?
3. Which data model patterns preserve provenance, decision history, and data gaps instead of producing opaque summaries?
4. Which security and evaluation gates are required for internal documents and LLM-assisted extraction?

## Primary Sources

- Microsoft GraphRAG documentation: https://microsoft.github.io/graphrag/
- Microsoft Research GraphRAG paper: https://arxiv.org/abs/2404.16130
- Neo4j GraphRAG for Python: https://github.com/neo4j/neo4j-graphrag-python
- Qdrant hybrid queries documentation: https://qdrant.tech/documentation/concepts/hybrid-queries/
- Qdrant license: https://github.com/qdrant/qdrant/blob/master/LICENSE
- Neo4j license notice: https://github.com/neo4j/neo4j/blob/dev/LICENSE.txt
- FastAPI documentation: https://fastapi.tiangolo.com/
- Vite documentation: https://vite.dev/
- React documentation: https://react.dev/
- LiteLLM documentation: https://docs.litellm.ai/
- Docling documentation: https://docling-project.github.io/docling/
- Docling repository: https://github.com/docling-project/docling
- Docling license: https://github.com/docling-project/docling/blob/main/LICENSE
- GROBID repository: https://github.com/kermitt2/grobid
- Unstructured documentation: https://docs.unstructured.io/
- Microsoft MarkItDown repository: https://github.com/microsoft/markitdown
- Microsoft MarkItDown license: https://github.com/microsoft/markitdown/blob/main/LICENSE
- Marker repository: https://github.com/datalab-to/marker
- MinerU repository: https://github.com/opendatalab/MinerU
- BGE-M3 model card: https://huggingface.co/BAAI/bge-m3
- DuckDB documentation: https://duckdb.org/docs/
- NetworkX documentation: https://networkx.org/documentation/stable/
- W3C PROV-O provenance ontology: https://www.w3.org/TR/prov-o/
- FAIR Guiding Principles paper: https://www.nature.com/articles/sdata201618
- OPTIMADE materials database API standard: https://www.optimade.org/
- Materials Project documentation: https://docs.materialsproject.org/
- NOMAD Laboratory: https://nomad-lab.eu/
- OWASP API Security Top 10 2023: https://owasp.org/API-Security/editions/2023/en/0x11-t10/
- OWASP Top 10 for LLM Applications 2025: https://genai.owasp.org/resource/owasp-top-10-for-llm-applications-2025/
- Node.js releases: https://nodejs.org/en/about/previous-releases
- uv documentation: https://docs.astral.sh/uv/

## Source-Backed Findings

- A pure vector search system is insufficient because the target questions require explicit multi-hop relations: material to experiment, experiment to regime, regime to measured property, property to effect, effect to conclusion, and conclusion to source.
- A pure graph database is also insufficient for early ingestion because internal documents contain narrative text, synonym-heavy terminology, and partial facts. Hybrid sparse plus dense retrieval is needed to find relevant evidence before graph traversal.
- GraphRAG patterns fit the core product: retrieval should combine semantic search, graph traversal, community or neighborhood context, and grounded answers with citations.
- A Markdown document memory bank is useful as an auditable, human-readable intermediate corpus for RAG and demo review, especially when produced by tools such as Docling, Marker, MinerU, MarkItDown, GROBID, or Unstructured.
- Markdown alone is not a safe source of truth for scientific evidence because it can lose layout, coordinates, table cell identity, OCR confidence, image provenance, and fine-grained security metadata. Use paired artifacts: Markdown for readable retrieval, structured JSON for metadata/provenance, extracted assets for figures/tables/images, and indexes for search.
- Provenance must be first-class. W3C PROV-O is a good conceptual model for source documents, extracted claims, extraction activities, agents, reviewers, and derived facts.
- FAIR principles and materials database standards such as OPTIMADE suggest that materials data should be modeled with stable identifiers, machine-readable metadata, clear schemas, and reusable provenance.
- OWASP API and LLM guidance make two risks non-negotiable: object-level authorization for internal records and prompt-injection controls for untrusted source documents.
- License posture is acceptable for hackathon demo but must be reviewed for productization: Docling and MarkItDown are MIT, Qdrant is Apache-2.0, and Neo4j source is GPLv3 unless a commercial agreement supersedes it.
- For a working MVP, infrastructure should still be lighter than the productized architecture: DuckDB can persist source/artifact/extraction metadata and run gap analytics locally, NetworkX can render/explain the typed graph path, and Qdrant can handle retrieval. The owner has chosen React/Vite over Streamlit for P0 because server-hosted visual quality matters more than fastest local prototyping.
- FastAPI documentation recommends `fastapi[standard]` for standard dependencies and supports Uvicorn/FastAPI CLI deployment patterns.
- LiteLLM provides a Python SDK with OpenAI-compatible `completion()` and `embedding()` calls, router/fallback patterns, and provider configuration through environment variables or API parameters.
- Vite 8 requires Node.js 20.19+ or 22.12+; use Node 24 LTS as the server/frontend baseline.
- OpenAI documentation confirms `gpt-5.5` and current embedding endpoints, but `gpt-5.5-mini` must be treated as a configurable LiteLLM alias until the deployment account confirms the exact model ID.

## Engineering Conclusion

Use a hybrid product architecture:

- Artifact memory bank with Markdown, structured JSON, extracted assets, manifests, and checksums.
- DuckDB plus NetworkX for P0 graph paths; Neo4j is a later adapter for persistent graph queries.
- Qdrant for hybrid dense plus sparse retrieval over chunks, claims, and entity pages.
- DuckDB for application state, source registry, extraction jobs, evidence ledger, answer claims, evaluation, and gap analytics.
- FastAPI for the typed service API and ingestion/query orchestration.
- React/Vite-based workbench for search, evidence review, graph exploration, timeline, data-gap analysis, and evaluation/security dashboards.

This gives a strong hackathon demo without locking the final production design to one vendor.
