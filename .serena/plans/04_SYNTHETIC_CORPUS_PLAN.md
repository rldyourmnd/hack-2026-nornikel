# Synthetic Corpus Plan (x10)

Date: 2026-07-02
Status: planned (built in W5, generator started earlier if W1 needs fixtures)

## Purpose

Scale the committed synthetic corpus ~x10 so the demo proves ingest, auto-linking,
retrieval, conflicts, gaps, and decision history on realistic Word/PDF material —
while staying deterministic and small enough to commit.

## Composition (~28 sources)

| Type | Count | Generator | Content pattern |
| --- | --- | --- | --- |
| PDF reports | 10 | reportlab (platypus) | RU (2 EN, 1 mixed): abstract, method, results table (baseline/treated/unit/method), discussion with team+equipment mentions, dated conclusion |
| DOCX protocols | 8 | python-docx | experiment protocols: regime steps, sample IDs, measurement tables, executing team, installation |
| CSV tables | 4 | csv module | existing 12-column schema (unchanged contract) |
| MD/TXT notes | 3 | text | lab notes incl. qualitative-only effects |
| HTML pages | 2 | static fixtures | "online resource" for URL ingest (served from test fixture / file) |
| No-text-layer PDF | 1 | reportlab (image-only page) | MUST land in quarantine — proves honest failure handling |

Committed under `sample_docs/synthetic_v2/` with `manifest.json` (expected source
count, span counts per source, entity counts) used by ingest smoke tests. Existing
`sample_docs/synthetic/` stays untouched (seed fixture keeps current tests green).

## Domain Spread (from dictionaries, extended)

- Materials: 6–8 across three families (Ni-Cu: Ni-30Cu, Ni-20Cu; Cu-Ni: CuNi30 with
  alias «МН30», CuNi10; Ni-Cr-Mo: two named variants) + composition blocks.
- Regimes: aging, annealing, cold rolling, solution treatment + quench,
  welding/cladding — with varied temperature/duration/atmosphere parameters.
- Properties: 8 from `properties.yml` (hardness HV/HRC, tensile, elongation,
  conductivity, corrosion rate, grain size, porosity, phase fraction).
- Equipment/teams/labs: from `equipment.yml`/`teams.yml` so PERFORMED_BY /
  USED_EQUIPMENT edges exist and the graph shows organizational context.

## Seeded Analytics (what the demo must find)

| Seed | Count | Demo purpose |
| --- | --- | --- |
| Method-mismatch conflict (HV vs HRC same slots) | 1 | conflict card (existing scenario, now data-driven) |
| Contradictory direction, same method+slots, two sources | 1 | real ConflictDetector proof |
| Missing property/regime cells (e.g. no conductivity after aging; no corrosion for Ni-Cr-Mo) | >=3 | gaps coverage matrix |
| Dated decisions/conclusions (e.g. "решение: перейти на режим 650C — 2024-11-12") | >=3 | decisions timeline |
| Cross-document alias pairs (CuNi30 vs «МН30»; Ni-30Cu vs "Ni30Cu") | >=2 | entity-resolution merge on ingest |
| Cross-document same-experiment references | >=2 | auto-link demo: uploading doc #2 attaches to existing nodes |
| Prompt-injection line inside a report | 1 | adversarial fixture stays 0-success |
| One `restricted`-labeled source | 1 | source-label leak checks |

## Generator Design

- Extend `scripts/generate_synthetic_docs.py` (fixtures extra: reportlab, python-docx,
  openpyxl already declared). Deterministic content from a fixed experiment registry
  (single Python data module = ground truth), fixed ordering — no randomness, so
  span IDs are stable across regenerations.
- Cyrillic PDF text: register DejaVu Sans via
  `pdfmetrics.registerFont(TTFont("DejaVuSans", ...))` — font file vendored from the
  `fonts-dejavu-core` package path or bundled (Bitstream Vera license permits
  redistribution). CI must not download fonts.
- Tables built with platypus `Table` so the text layer stays extractable by Docling.
- The ground-truth registry also emits `manifest.json` and the gold-question
  expectations — corpus and eval can never drift apart.

## Gold Questions (25–40, `eval/gold_questions.yml` extension)

Categories (each with expected evidence spans / entities / metrics):

1. Slot QA: material+regime+property -> effect (>=8, RU phrasing variants incl. «что
   уже делали по X при Y, эффект на Z»).
2. Comparison: two materials same regime; two regimes same material (>=3).
3. Provenance: "откуда известно, покажи источник" (>=2).
4. Alias resolution: query by «МН30» must return CuNi30 evidence (>=2).
5. URL-source question (>=1).
6. Conflict surfacing (>=2) and gap questions (>=3).
7. Related entities: "кто делал", "на какой установке" (>=3).
8. Decision history: "какие решения принимались по X" (>=2).
9. Negative controls: unknown material -> empty + follow-ups (keep existing 3).
10. Adversarial: injection + restricted-label (keep existing 2).

## Verification

- `make generate-fixtures` reproduces `synthetic_v2/` byte-identically (hash check).
- Ingest smoke: counters equal manifest; quarantine case quarantined.
- `make eval` (deterministic) and `make eval-full` (LLM) consume the same gold file.
