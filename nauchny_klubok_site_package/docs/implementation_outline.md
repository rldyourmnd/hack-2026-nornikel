# Implementation outline

## UI structure

- `Landing`: питч и переход в демо/поиск.
- `Search`: natural-language question + structured filters.
- `Answer`: тезисы + citation chips + evidence cards + verification metrics.
- `Graph`: neighborhood/path explorer с details panel.
- `Data`: загрузка, импорт, архивы, статусы, no-OCR quarantine.
- `Source`: документ/table preview + metadata + provenance + facts.
- `Gaps`: coverage matrix + conflicts/gaps + next research suggestions.
- `Compare`: comparison matrix with evidence-backed cells.
- `Experts`: topic → expert/lab recommendations.
- `Demo`: pitch cockpit для жюри.

## Non-negotiable quality rules

- No answer sentence without `supporting_span_ids` or verified fact provenance.
- No numeric claim without source-visible number or documented derived formula.
- No OCR promise; show `OCR выключен` and quarantine status.
- No synthetic seed leakage in product demo.
- All UI confidence labels must map to stored validation/confidence fields.

## Recommended component split

- `Header`, `PageHero`, `StatCard`, `FeatureCard`.
- `QuestionComposer`, `FilterChips`, `EvidencePacketPreview`.
- `AnswerClaim`, `CitationChip`, `EvidenceCard`, `VerificationPanel`.
- `GraphCanvas`, `NodeDetailsPanel`, `GraphPathCard`.
- `SourceTable`, `ImportStatusBadge`, `QuarantineBanner`.
- `CoverageMatrix`, `ConflictCard`, `GapCard`.
- `ComparisonTable`, `ExpertCard`, `LabCard`, `JuryDemoPanel`.
