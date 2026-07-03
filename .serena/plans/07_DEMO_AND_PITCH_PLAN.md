# Demo And Pitch Plan

Date: 2026-07-02
Status: planned (executed in W5; deck is a separate deliverable built from this file)

## Purpose

Script the live-stand demo and the pitch so every judged criterion of the track is
explicitly shown, and every claim on a slide traces to a measured number.

## Judged Criteria -> Demo Mapping

| Track requirement | Demo moment |
| --- | --- |
| "что делали по сплаву X при режиме Y и эффект на свойство Z" | Step 3: ideal question, cited answer + experiment table |
| Связанные сущности (статьи, эксперименты, материалы, свойства, режимы, установки, команды, выводы) | Steps 4–5: evidence cards + graph neighborhood with typed nodes incl. equipment/team/conclusion |
| История решений | Step 6: decisions timeline |
| Пробелы в данных | Step 7: gaps coverage matrix -> suggested next experiment |
| Самостоятельное формирование новых связей | Step 2: live DOCX upload visibly extends the graph |
| Word/PDF + онлайн-ресурсы | Steps 1–2: PDF + DOCX + URL ingest |
| Экономия ресурсов | Step 9 + deck: model sizes, tokens/cost per answer (Langfuse), CPU-only footprint |
| Непроприетарные модели, RF-доступность | Deck slide: model/license table (all Apache-2.0/MIT weights), provider routing |

## Live Demo Script (~7 minutes)

1. **Стенд как есть** (30s): workbench, artifact bank with the pre-ingested corpus
   (28 sources), eval dashboard with real numbers. One quarantined source visible —
   "мы не притворяемся, что парсим сканы".
2. **Живая загрузка** (60s): upload a prepared DOCX protocol -> status chip ->
   completed -> open graph: new experiment node connected to EXISTING material
   Ni-30Cu and a new equipment node. Say: "связи построились сами: словари → алиасы
   → эмбеддинг-порог".
3. **Идеальный вопрос** (60s): «Что уже делали по Ni-30Cu при старении 700 C 8 ч и
   какой эффект на твердость?» -> answer sentences, each with EvidenceSpan chips;
   experiment table; confidence.
4. **Evidence-first** (45s): click a citation -> exact table row from the source PDF
   (page + locator). "Ни одного предложения без пруфа: verifier отбрасывает
   неподтверждённые фразы до ответа".
5. **Граф-эксплорация** (60s): neighborhood view, expand material -> experiments ->
   team/equipment; node panel shows supporting documents.
6. **История решений** (30s): timeline «какие решения принимались по Cu-Ni» ->
   dated decision with evidence.
7. **Пробелы и противоречия** (60s): gaps matrix (empty conductivity cell ->
   one-click follow-up query returns honest empty + gap record); conflict card
   with both sources side by side.
8. **Security** (20s): injection fixture question -> ignored instruction, metrics
   dashboard shows 0 leaks / 0 injections.
9. **Цена ответа** (25s): Langfuse trace of the last question: model, tokens, cost,
   latency. "Малые открытые модели: качество держим верификацией, а не размером".

Backup plan: if the provider is slow/down during judging, flip `LLM_ENABLED=false`
live — deterministic path answers the same ideal scenario instantly (honest note to
jury: synthesis off, evidence identical). Optional Ollama profile is the middle
option. Record a screencast of the full script beforehand as insurance.

## Pitch Deck Skeleton (10 slides)

1. Проблема: знания в отчётах, «что уже делали» ищется днями.
2. Решение: evidence-first KG workbench — ответ = таблица + пруфы + граф + пробелы.
3. Живое демо (или screencast) — ключевые 3 экрана.
4. Архитектура: DuckDB ledger как система записи; Qdrant retrieval; свой граф-слой
   (LightRAG-паттерн) — без тяжёлых платформ; порты для масштабирования
   (Postgres/Neo4j путь).
5. Автосвязи: exact → алиасы → embedding ≥0.9; никакого слепого мержа.
6. Соответствие правилам: только open-weight (таблица модель/лицензия/размер),
   маршрутизация через LiteLLM, всё воспроизводимо.
7. Экономия ресурсов (числа из Langfuse/eval): ~N токенов и ~$X за ответ, модели
   4–9B класса, CPU-only сервер, время ответа p50.
8. Качество (числа из eval-full): Recall@10, citation coverage 100%, 0 unsupported,
   0 leaks, extraction accuracy; слайд «как мы это меряем» (gold set + adversarial).
9. Расширяемость: реальный корпус вместо синтетики без изменений кода; SSO/RBAC,
   Neo4j/Postgres, OCR-профиль, review-очередь — по портам.
10. Команда + ask.

## Numbers To Collect In W5 (deck data table)

| Metric | Source |
| --- | --- |
| Tokens + cost per answer (avg/p95) | Langfuse over `answer_runs` |
| Latency p50/p95 (LLM and deterministic) | `answer_runs.latency_ms` |
| Ingest time per PDF/DOCX | `ingestion_runs` counters |
| Eval thresholds table | `eval_results` latest run |
| Graph size (entities/relations by type) | DuckDB counts |
| Model sizes + licenses | evidence register |

## Jury Q&A Prep

- «Почему не Neo4j/готовый GraphRAG?» — провенанс на наших EvidenceSpan против
  chunk-id фреймворков; DuckDB уже system of record; порты дают путь миграции.
- «Что со сканами?» — честный карантин + документированный OCR-профиль как P1.
- «Потянет ли реальный корпус?» — ingestion идемпотентен, ретривер и резолюция не
  зависят от размера словарей; узкие места и план масштабирования названы.
- «Почему верить ответам?» — verifier: предложение без span ID не выходит наружу;
  метрики на adversarial-фикстурах.
