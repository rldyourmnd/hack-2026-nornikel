# Document Memory Bank

## Decision

Use a document memory bank as the first durable ingestion product:

- parse every source document, spreadsheet, image, and catalog export;
- create readable Markdown for search, review, and demo explainability;
- preserve structured parse JSON and extracted assets for exact evidence;
- build indexes over Markdown chunks, table rows, claims, and entity pages;
- write only validated or high-confidence facts into the canonical graph.

This is a better formulation than "search over Markdown files only".

## Why This Is Effective

Markdown is a strong intermediate for hackathon delivery because:

- it is human-readable and easy to inspect during demos;
- it works well with LLM context formatting;
- it is convenient for semantic chunking;
- it can preserve headings, lists, tables, captions, and source-oriented text;
- it allows a fallback retrieval path even before graph extraction is complete.

For this project, it also creates a visible evidence layer: the user can move from answer to chunk to source page/table quickly.

## Why Markdown Alone Is Not Enough

Markdown is lossy for scientific evidence. It can fail to preserve:

- exact PDF coordinates;
- table cell identity and merged cells;
- OCR confidence;
- figure regions and image provenance;
- page images;
- formula layout;
- security labels at span level;
- parser version and conversion settings;
- source checksums;
- stable row/cell IDs needed for measurements.

Therefore the memory bank must store paired artifacts, not just `.md` files.

## Artifact Bundle

Each source gets a stable directory:

```text
src_.../
├── original/
│   └── source.ext
├── markdown/
│   └── document.md
├── structured/
│   └── document.json
├── tables/
│   ├── table_001.csv
│   └── table_001.html
├── images/
│   ├── page_001.png
│   ├── figure_001.png
│   └── table_001.png
└── manifest.json
```

`manifest.json` should include:

- source ID;
- original filename;
- checksum;
- parser name and version;
- parser settings;
- conversion timestamp;
- security label;
- artifact checksums;
- page count;
- detected language;
- OCR enabled flag;
- extraction job ID.

## Recommended Parser Strategy

### Default: Docling

Use Docling first for PDF, Office formats, HTML, images, OCR, table/layout handling, Markdown export, structured document export, image export, and RAG chunking.

### Scholarly PDFs: GROBID

Use GROBID when scholarly article structure matters:

- title/authors/abstract;
- sections;
- references;
- citation contexts;
- TEI/XML output.

### Fast Simple Conversion: MarkItDown

Use MarkItDown only for quick conversion of simple documents where layout precision is not critical. It is useful as a baseline converter, not as the evidence-grade parser.

### Hard PDFs And Parse QA: Unstructured, Marker, MinerU

Keep these as evaluation alternatives for difficult sources:

- scanned PDFs;
- multi-column reports;
- complex tables;
- formulas;
- image-heavy documents.

Do not bind the architecture to one parser. Store parser metadata so artifacts can be regenerated and compared.

## Retrieval Model

Index four retrieval units:

1. Markdown sections and paragraphs.
2. Table rows and table summaries.
3. Extracted claims.
4. Entity pages and experiment summaries.

Search should combine:

- exact filters from source metadata;
- sparse lexical retrieval for alloy names, units, equipment IDs, and property names;
- dense retrieval for paraphrases and Russian/English cross-language matches;
- graph traversal for experiment/material/regime/property paths;
- reranking by evidence quality and exact slot match.

## Extraction Model

Recommended cascade:

1. deterministic rules for units, temperatures, durations, compositions, and measurement values;
2. dictionaries for materials, properties, equipment, labs, and teams;
3. table-specific extraction from structured table artifacts;
4. domain NLP if available;
5. LLM JSON extraction on small evidence chunks;
6. schema validation and entity resolution;
7. graph write after confidence and provenance checks.

## Answering Rule

The answer generator can read Markdown chunks, but every answer claim must map back to:

- source ID;
- stable span ID;
- page or row;
- extraction run;
- validation status;
- graph path or indexed retrieval unit.

If a Markdown chunk cannot be mapped to a source span, it can support exploration but not final evidence.

## Parser Quality Gate

Run a parser bakeoff before committing to a parser for the full corpus:

- 3 born-digital PDFs;
- 2 scanned PDFs or images;
- 2 table-heavy reports;
- 2 DOCX/PPTX files;
- 2 XLSX/CSV experiment catalogs;
- at least one Russian document and one English document.

Measure:

- text reading order;
- table row/cell recovery;
- page/span stability;
- OCR confidence;
- figure/table image extraction;
- processing time;
- artifact size;
- failure mode clarity.

Docling remains the default, but any parser output can enter the memory bank if it produces the required artifact contract.

## MVP Recommendation

Implement the memory bank before the graph writer:

1. Parse documents into artifact bundles.
2. Build Markdown/table search.
3. Extract key material-regime-property facts.
4. Write canonical facts to graph.
5. Answer with hybrid retrieval plus graph paths.

This gives a working demo even if KG extraction is incomplete, while preserving the path to a stronger evidence-first scientific graph.
