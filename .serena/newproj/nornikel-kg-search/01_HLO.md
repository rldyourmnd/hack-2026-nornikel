# High-Level Overview

## Product

Nornikel Materials Knowledge Graph and Search is an internal research intelligence system for connecting documents, experiments, materials, properties, processing regimes, equipment, teams, conclusions, decisions, and known data gaps.

The system should answer questions like:

> What has already been done for alloy X under regime Y, and what effect was observed on property Z?

The answer must not be a plain LLM summary. It must return:

- direct answer;
- linked evidence snippets;
- related experiments, materials, equipment, and teams;
- graph path explaining why the answer was assembled;
- confidence and conflicting evidence;
- missing data and suggested next experiments.

## Product Hypothesis

The useful MVP is a hybrid analytical workbench:

- knowledge graph for entities, relationships, provenance, and explainable paths;
- hybrid semantic search for document and claim retrieval;
- GraphRAG answer assembly for grounded question answering;
- human review loop for extracted facts and uncertain relations.

## Primary Users

- Research scientist: asks prior-work and effect questions.
- Lab lead: checks experiment history, team ownership, and data gaps.
- Materials engineer: compares regimes and property changes.
- Knowledge curator: validates extracted entities and relations.
- Management/demo stakeholder: sees cross-corpus insight and explainability.

## MVP Capabilities

1. Ingest internal documents, experiment catalog, materials/equipment dictionaries, employee/lab directory, and topic tags.
2. Extract and normalize key entities: materials, alloys, properties, regimes, equipment, teams, documents, experiments, claims, conclusions, and decisions.
3. Build a canonical graph with provenance on every fact.
4. Index chunks, claims, and entity pages for dense plus sparse retrieval.
5. Answer structured research questions with citations and graph paths.
6. Show connected entities, timeline, decision history, conflicts, and data gaps.

## Non-Goals For Hackathon

- No fully autonomous scientific truth engine.
- No direct write-back to corporate systems.
- No training on internal documents.
- No hidden facts without source spans.
- No production-grade RBAC integration unless credentials and identity provider are provided.

## Demo Success

The demo should show three end-to-end scenarios:

1. Prior work: alloy plus regime plus property question returns matching experiments and effects.
2. Exploration: graph view shows connected materials, equipment, teams, and documents.
3. Gap analysis: system identifies missing measurements or under-tested regime/material combinations.

## Key Assumptions

- Corpus access is batch-based during hackathon.
- Some documents are semi-structured or scanned; OCR may be needed but is not the core differentiator.
- Domain dictionaries are incomplete and will need synonym/entity-resolution rules.
- LLM usage may be restricted; the architecture keeps the extraction and answering providers swappable.
