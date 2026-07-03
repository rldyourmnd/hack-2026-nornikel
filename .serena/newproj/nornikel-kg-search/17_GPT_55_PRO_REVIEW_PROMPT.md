# GPT-5.5 Pro Review Prompt

Use this prompt in ChatGPT 5.5 Pro to get a second-pass implementation-readiness review.

```text
You are a senior AI product architect, staff backend engineer, information retrieval specialist, and materials-informatics reviewer.

Context:
We are building a hackathon MVP for Nornikel. The challenge is to create a knowledge graph or search-analytics system connecting articles, experiments, materials, properties, processing regimes, installations/equipment, research teams, decisions, conclusions, and data gaps.

The system must answer questions like:
"What has already been done for alloy/material X under processing regime Y, and what effect was observed on property Z?"

It must show:
- exact evidence from source documents/tables/images;
- related entities;
- experiment history;
- graph paths;
- contradictions;
- gaps in available data;
- grounded answer, not a generic chatbot response.

Current proposed direction:
Evidence-first Scientific Knowledge Graph + Hybrid Retrieval.

Current review-integrated correction:
The primary system is not a chatbot and not a full production KG stack. It is a scientific evidence ledger:

Artifact memory bank
→ stable EvidenceSpans
→ table/fact extraction
→ DuckDB system of record
→ Qdrant hybrid candidate retrieval
→ NetworkX graph path rendering
→ deterministic evidence packet
→ LLM summary with claim verification
→ evaluation/security dashboard

Critical MVP correction:
Do not start with a heavy production KG stack, but do build a real server-facing product slice:
- React 19 + Vite 8 + TypeScript workbench for the first UI;
- FastAPI API and application services for clean contracts;
- Docling artifact memory bank: Markdown + structured JSON + tables + images + manifest;
- DuckDB for source registry, artifacts, facts, evaluation, and gap analytics;
- Qdrant for dense+sparse hybrid retrieval;
- NetworkX for P0 graph path/neighborhood;
- LiteLLM/OpenAI-compatible external APIs for LLM extraction, answer synthesis, and embeddings;
- ports/adapters so DuckDB -> PostgreSQL, NetworkX -> Neo4j, local artifacts -> object storage later.

Non-negotiable invariant:
Every final-answer claim must map to an EvidenceSpan: exact source_id, span_id, page/row/image/table metadata, extraction run, validation status, and graph path or indexed retrieval unit.

Identifier policy:
- source_id: stable raw document identity.
- artifact_id: parsed object identity.
- span_id: stable evidence anchor generated from source, artifact type, page/table/row/bbox locator, and visible-content hash.
- extraction_run_id: mutable parser/extraction run identity.
- fact_id: normalized extracted fact identity.
- claim_id: extraction or answer claim identity.
- extraction_run_id must not be included in span_id.

P0 vertical slice:
1. Import/upload source files.
2. Parse into artifact memory bank.
3. Generate stable EvidenceSpan IDs.
4. Extract material/regime/property/measurement facts using dictionaries, rules, table extraction, and LLM JSON extraction on small chunks.
5. Materialize canonical graph path:
   Experiment -[:USES_SAMPLE]-> Sample
   Sample -[:MADE_OF]-> Material
   Material -[:HAS_COMPOSITION]-> MaterialComposition
   Experiment -[:APPLIES_REGIME]-> ProcessingRegime
   ProcessingRegime -[:HAS_STEP]-> ProcessStep
   Experiment -[:HAS_MEASUREMENT]-> PropertyMeasurement
   PropertyMeasurement -[:OF_PROPERTY]-> Property
   PropertyMeasurement -[:SUPPORTED_BY]-> EvidenceSpan
   EffectClaim -[:COMPARES_BASELINE]-> PropertyMeasurement
   EffectClaim -[:COMPARES_TREATED]-> PropertyMeasurement
   EvidenceSpan -[:FROM_DOCUMENT]-> Document
6. Index Markdown chunks, table rows, claims, and entity/experiment summaries in Qdrant.
7. Answer material-regime-property questions with experiment table, evidence cards, graph path, conflicts/gaps, and grounded summary.
8. Evaluate on one polished ideal demo scenario plus regression questions with Recall@10, citation coverage, unsupported claim count, source-label leak checks, and prompt-injection fixtures.

Deferrals until P0 works:
- Neo4j;
- PostgreSQL;
- worker queues;
- full review workflow;
- MatSciBERT/ChemDataExtractor;
- community/global GraphRAG summaries;
- complex ontology expansion.

Please perform a deep review and produce a rigorous report:

1. Challenge the MVP-lite architecture:
   - Is DuckDB + NetworkX + Qdrant + React/FastAPI the right first implementation?
   - What will break first?
   - What should stay as ports/adapters?
   - What should be simplified further?

2. Review the ingestion and artifact memory bank:
   - Is Markdown + structured JSON + extracted assets + manifest enough?
   - What metadata is missing?
   - How should stable EvidenceSpan IDs be generated?
   - How should tables/images/scanned PDFs be handled?

3. Review extraction:
   - Are dictionaries/rules/table extraction/LLM JSON extraction enough for a hackathon?
   - What schemas are required?
   - How should confidence and validation be handled?
   - What should be done when facts conflict?

4. Review retrieval and QA:
   - How should dense + sparse retrieval be configured?
   - What should be indexed as separate retrieval units?
   - What reranking features matter most?
   - How should the answer be assembled to avoid hallucinations?

5. Review graph design:
   - Is the canonical graph path correct?
   - Which relationships/nodes are missing for material science?
   - Is NetworkX acceptable for P0?
   - When exactly should we switch to Neo4j?

6. Review UI:
   - What screens are required for a convincing MVP?
   - What can be omitted?
   - How should the demo flow be structured for judges?

7. Review security:
   - What are the top risks for internal documents?
   - How should source security-label filtering happen before LLM context construction when P0 has no user auth/RBAC?
   - What prompt-injection and data-leak checks are required?

8. Review evaluation:
   - What 10-20 gold questions should we create?
   - What metrics are realistic for a hackathon?
   - What thresholds are good enough?

9. Produce final recommendations:
   - Must-fix before coding, if any remain.
   - Should-fix during scaffold.
   - Defer safely.
   - Check whether `18_IMPLEMENTATION_SPEC.md` is complete enough to scaffold from.
   - Proposed final P0 implementation plan by day/hour.
   - Proposed repository structure.
   - Any contradiction in the MVP-lite stack or evidence ledger contract.

Be skeptical. Prefer a working, high-quality, modular MVP over an impressive but unbuildable architecture. Do not give generic RAG advice; tailor the answer to materials science, internal documents, experiments, process regimes, properties, evidence spans, and hackathon constraints.
```
