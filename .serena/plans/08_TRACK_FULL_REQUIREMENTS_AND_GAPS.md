# Track Full Requirements And Gap Analysis

Date: 2026-07-03
Source: full track brief «Научный клубок» received from organizers (owner message),
plus the real case corpus in `DATA_HACK/` (~4.9 GB, NOT committed to git).

## Corpus Reality (DATA_HACK/Источники информации)

| Folder | Files | Size | Content |
| --- | --- | --- | --- |
| Материалы конференций | 879 | 1.7G | Cu/Ni/Co/PGM conference papers, RU+EN, PDF/DOC/PPTX/ZIP |
| Журналы | 394 | 2.6G | «Цветные металлы», «Горный журнал», «Горная промышленность», «Обогащение руд» |
| Обзоры | 104 | 274M | internal-style reviews (DOCX/PDF), e.g. Long Harbour, Уэльва |
| Статьи | 60 | 181M | RU/EN research articles incl. Gipronikel pyrometallurgy |
| Доклады | 16 | 98M | tech-council presentations (PPTX/PDF) |

Types: 1163 PDF, 115 DOCX, 79 ZIP, 46 XLS, 18 DOC, 16 RAR, 5 PPTX.
Domains: pyrometallurgy (slag depletion, matte), hydrometallurgy/electrowinning,
water desalination, beneficiation, geomechanics, markets.

First live test (2026-07-03): a real 816KB Gipronikel DOCX parsed into 278
evidence spans. Pre-fix, per-span LLM extraction blocked the API for >5 min;
fixed by capping LLM spans per source (12) and moving enrichment off the
request thread (`fix/real-corpus-ingest`).

## Requirement Deltas vs Our MVP (gap analysis)

Covered already (keep, demo-ready):
- Upload PDF/DOCX/CSV/MD/URL with quarantine; EvidenceSpan provenance; verified
  answers (citation gate); entity/alias resolution; graph neighborhoods; gaps
  matrix; conflicts; RU/EN corpus support (Docling + multilingual embeddings);
  source-label filtering (base for RBAC story); eval dashboard.

Gaps, ranked by judge impact:

| # | Gap | Requirement | Severity | Direction |
| --- | --- | --- | --- | --- |
| G1 | Ontology breadth: no Publication/Expert/Facility entity types; relations lack described_in/validated_by | «Типы сущностей: Material, Process, Equipment, Property, Experiment, Publication, Expert, Facility» | HIGH | extend dictionaries + extraction types; authors/emails are extractable from real articles (seen in test doc) |
| G2 | Numeric constraints & ranges in queries («сульфаты ≤300 мг/л», диапазоны) | «Обязательна поддержка числовых ограничений и диапазонов» | HIGH | parse value+unit constraints in question slot-parser; store measurements with units (already have value/unit on measurements — need query-side comparison) |
| G3 | Geography + time filters (отечественная vs зарубежная, «за последние 5 лет») | «различать отечественную и зарубежную практику», date ranges | HIGH | add source metadata (country, year) at ingest + filters in /qa/ask and search |
| G4 | Corpus scale: 1163 PDFs incl. 100+ MB journals; ZIP/DOC/PPTX/XLS unsupported | «5 ГБ данных», импорт разнородных документов | MED-HIGH | batch CLI ingester with per-file timeout+quarantine; convert legacy .doc via LibreOffice (server); PPTX/XLS as P2; cap pages per PDF initially |
| G5 | Versioning/verification model (уровень достоверности, дата актуализации) | «модель верификации знаний» | MED | we have validation_status+confidence+created_at — surface them in UI/answers; add source year |
| G6 | Literature-review style synthesis (grouping by method/year/geo, consensus vs disagreement) | «Автоматическая генерация структурированных ответов типа литобзор» | MED | extend answer composer prompt with grouping; needs G3 metadata first |
| G7 | RBAC roles + audit log | «Ролевая модель… аудит действий» | LOW (P0 explicitly skipped auth) | keep security-label story + answer_runs/ingestion_runs as audit trail; document extension |
| G8 | Recommendations (experts/similar cases) | «Рекомендации: эксперты и команды…» | LOW-MED | falls out of G1: PERFORMED_BY/AUTHORED_BY edges enable «кто работал с темой» |
| G9 | Export PDF/MD/JSON-LD, notifications, expert graph editing, exec dashboards | «Дополнительные пожелания» | LOW | mention as extension points in pitch |
| G10 | Performance target: 3–5 s on 1M entities | НФТ | MED | Qdrant scales; DuckDB fine at demo scale; state honestly in pitch with measured numbers |

## Revised Wave Plan (W6–W8, before 2026-07-16)

- **W6 (critical, 2–3 дня): real-corpus vertical.**
  6.1 Batch CLI ingester over a curated DATA_HACK subset (~30–60 docs across all
       5 folders; per-file timeout, quarantine, progress log; runs on the server).
  6.2 Source metadata: year + geography (RU/foreign) + document kind columns;
      set at ingest (heuristics: language/journal), filterable in /qa/ask + UI.
  6.3 G1 ontology extension: publication/expert/facility entity types,
      AUTHORED_BY/DESCRIBED_IN edges from author blocks (real articles carry
      structured author+email headers — cheap rule extraction).
- **W7 (2 дня): query power.**
  7.1 Numeric constraint parsing in questions (≤/≥/ranges + units) applied to
      measurements (G2).
  7.2 Time/geo filters in QA + frontend filter chips (G3 UI).
  7.3 Literature-review answer mode: group retrieved sources by year/geo/method,
      consensus vs contradictions (G6) — reuse conflict detector output.
- **W8 (1–2 дня): scale + polish.**
  8.1 Ingest full curated corpus on server; measure ingest metrics for pitch.
  8.2 Latency work: answer packet trimming (fewer spans in prompt), parallel
      LLM extraction batches if needed.
  8.3 Pitch/demo update to the real corpus (replace synthetic-only story).

Cut lines: 7.3 degrades to «grouped source list»; 6.3 experts degrade to
AUTHORED_BY only; PPTX/XLS/ZIP ingest stays out (documented).

## Standing Cautions

- DATA_HACK stays out of git (5 GB, likely license-sensitive). Server copies
  live under /srv/nornikel-kg-search/data/corpus (gitignored path).
- Big-journal PDFs (100MB+) are hostile to Docling on CPU: enforce per-file
  size/time budget, quarantine over crash — never block the stand.
