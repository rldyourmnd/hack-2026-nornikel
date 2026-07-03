# Testing Strategy

## Unit Tests

- Entity normalization.
- Unit conversion.
- Regime parameter parsing.
- Schema validation.
- Provenance attachment.
- Gap detection rules.
- Query planning.

## Integration Tests

- Ingest sample document and experiment row.
- Extract candidate facts.
- Resolve entities with dictionaries.
- Write graph nodes and relationships.
- Index chunks and claims.
- Ask a QA question and verify evidence links.

## Retrieval Evaluation

Create a small gold set:

- 20-50 material/regime/property questions;
- expected source IDs;
- expected experiment IDs;
- expected answer direction;
- expected gap or conflict labels.

Metrics:

- retrieval hit rate at 5/10/20;
- evidence-span hit rate at 5/10/20;
- graph path correctness;
- citation coverage;
- answer faithfulness;
- unsupported claim count;
- gap detection precision.
- source-label leak count.
- restricted source in context count.
- prompt injection success count.

P0 pass thresholds for demo:

- 100% of answer claims cite an `EvidenceSpan`.
- At least 80% Recall@10 on the curated demo QA set.
- At least 75% TableRowRecall@10 on table-backed questions.
- At least 85% numeric value + unit accuracy on curated numeric facts.
- At least 80% effect direction accuracy on curated effect claims.
- Zero final-answer claims from chunks without stable span mapping.
- Zero disallowed-source-label evidence in generated answer context.
- Zero prompt-injection fixture successes.

## Extraction Evaluation

Measure:

- entity precision/recall on sample documents;
- relation precision/recall;
- measurement value and unit accuracy;
- duplicate entity merge accuracy;
- reviewer correction rate.

## UI Validation

Manual demo flows:

1. Search for material/regime/property.
2. Open answer evidence.
3. Expand graph path.
4. Compare experiments.
5. Open timeline.
6. Open gaps.
7. Inspect the evaluation/security dashboard.

Validate the React UI with browser screenshots for desktop and laptop widths.

## Quality Gates

Before demo:

- parser smoke test passes on representative PDF, scanned image/PDF, DOCX, XLSX/CSV, and at least one table-heavy source;
- backend tests pass;
- ingestion smoke test passes;
- QA gold set report generated;
- no uncited answer in test set;
- no source-label filtering bypass;
- no restricted source in answer context;
- no unsupported generated answer claims;
- adversarial prompt-injection fixtures pass;
- Docker Compose starts from clean checkout;
- seed dataset import is reproducible.
