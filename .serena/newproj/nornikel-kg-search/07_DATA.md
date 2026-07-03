# Data Model

## Canonical Entity Model

### Material And Composition

- Material: stable material or alloy family.
- Alloy: named alloy or composition variant.
- Element: chemical element.
- Composition: element percentages, uncertainty, source.
- Sample: physical specimen linked to material, batch/heat, and experiment.
- BatchOrHeat: production or lab batch identity when available.

### Experiment And Sample

- Experiment: planned or executed research activity.
- Sample: physical specimen or batch.
- ProcessingRegime: temperature, pressure, atmosphere, time, cooling, deformation, heat treatment, or other process parameters.
- ProcessStep: ordered operation inside a multi-step regime.
- ProcessParameter: typed parameter such as temperature, duration, pressure, deformation percentage, atmosphere, or cooling.
- Equipment: machine or measurement device.
- Installation: physical setup or facility.

### Properties And Results

- Property: tensile strength, hardness, corrosion resistance, phase composition, conductivity, etc.
- PropertyMeasurement: value, unit, method, uncertainty, conditions, direction of change.
- EffectClaim: baseline/treated comparison or qualitative effect: increase, decrease, no change, mixed, unknown.
- ConflictGroup: grouped disagreement across measurements, methods, conditions, or extraction uncertainty.

### Knowledge Objects

- Document: source article, report, protocol, table, presentation, or catalog row.
- EvidenceSpan: stable text, table cell/row, figure, image, or page region that can support a fact.
- Claim: extracted statement backed by source span.
- Conclusion: author or reviewer conclusion.
- Decision: project/lab decision derived from evidence.
- Gap: missing, weak, conflicting, outdated, or unreplicated data.

### Organization

- Person.
- Team.
- Lab.
- Project.
- TopicTag.

## Provenance Shape

Every fact-like node or relationship stores:

- `source_id`;
- `span_id`;
- `artifact_id`;
- `artifact_type`;
- `parser_name`;
- `parser_version`;
- `source_version`;
- `extraction_run_id`;
- `extraction_method`;
- `confidence`;
- `validation_status`;
- `reviewer_id`;
- `created_at`;
- `updated_at`.

This follows the PROV-O idea that information is produced by activities, derived from entities, and associated with agents.

## Identifier Policy

Do not collapse identities:

- `source_id`: stable raw document identity from raw bytes.
- `artifact_id`: parsed object identity from source, artifact type, parser profile, and locator.
- `span_id`: stable evidence anchor from source, artifact type, page/table/row/bbox locator, and visible-content hash.
- `extraction_run_id`: mutable run identity.
- `fact_id`: normalized fact identity.
- `claim_id`: extraction or answer claim identity.

Never include `extraction_run_id` in `span_id`; store parser changes in `evidence_span_versions`.

## Confidence Model

Use separate confidence dimensions:

- `evidence_confidence`: parser/OCR/table extraction confidence.
- `extraction_confidence`: confidence that a fact is present in the span.
- `normalization_confidence`: confidence that raw entity/unit maps to canonical entity/unit.

Validation status values:

- raw;
- extracted;
- normalized;
- validated_rule;
- validated_manual;
- rejected;
- conflict;
- needs_review.

## Entity Resolution

Resolution layers:

1. Exact dictionary match.
2. Alias/synonym match.
3. Unit and composition normalization.
4. Embedding-assisted candidate match.
5. Human review for ambiguous or high-impact merges.

Do not merge entities automatically when composition, regime parameters, or equipment identity conflict.

## Gap Model

Gap types:

- missing_property_measurement;
- missing_exact_regime;
- missing_equipment_metadata;
- unvalidated_claim;
- conflicting_effect;
- outdated_result;
- no_replication;
- source_access_restricted.

Gap records should reference the expected entity pair or path and the evidence that made the gap visible.

## P0 Graph Path Contract

The first working product must support this canonical path:

```text
(Experiment)-[:USES_SAMPLE]->(Sample)
(Sample)-[:MADE_OF]->(Material)
(Material)-[:HAS_COMPOSITION]->(MaterialComposition)
(Experiment)-[:APPLIES_REGIME]->(ProcessingRegime)
(ProcessingRegime)-[:HAS_STEP]->(ProcessStep)
(Experiment)-[:HAS_MEASUREMENT]->(PropertyMeasurement)
(PropertyMeasurement)-[:OF_PROPERTY]->(Property)
(PropertyMeasurement)-[:SUPPORTED_BY]->(EvidenceSpan)
(EvidenceSpan)-[:FROM_DOCUMENT]->(Document)
(EffectClaim)-[:COMPARES_BASELINE]->(PropertyMeasurement)
(EffectClaim)-[:COMPARES_TREATED]->(PropertyMeasurement)
```

All other graph relationships are secondary until this path works end to end.

## Indexing Strategy

Graph indexes:

- canonical IDs;
- aliases;
- material labels;
- property names;
- regime parameter buckets;
- source IDs;
- validation status.

Vector payload filters:

- material IDs;
- property IDs;
- regime IDs;
- equipment IDs;
- lab/team IDs;
- document type;
- date;
- security label;
- validation status.

## P0 Demo Dictionaries

Seed dictionaries should be easy to replace or extend and should cover:

- Materials: Ni-Cu, Cu-Ni, Ni-Cr-Mo, sample IDs, alloy aliases, and composition aliases.
- Regimes: annealing, aging, cold rolling, solution treatment, quench, welding, cladding.
- Properties: Vickers hardness, tensile strength, yield strength, elongation, electrical conductivity, corrosion rate, grain size, porosity, cracking, phase fraction.
- Equipment: furnace, rolling mill, tensile test machine, Vickers hardness tester, SEM, XRD, conductivity meter, corrosion cell.
- Teams/labs: synthetic metallurgy lab, corrosion lab, mechanical testing lab.

These dictionaries are bootstrap data, not ontology lock-in. New aliases and materials should be added without schema changes.

## Data Quality Rules

- Measurements require units.
- Regimes require typed parameters where available.
- Claims require source spans.
- Effect claims require baseline/treated measurements or `qualitative_only`.
- Final-answer claims require `EvidenceSpan`; generic Markdown chunks are not enough.
- Table rows and table cells are first-class evidence, not Markdown-only text.
- Conclusions require either source support or reviewer authoring.
- Decisions require actor, date, rationale, and linked evidence or gap.
