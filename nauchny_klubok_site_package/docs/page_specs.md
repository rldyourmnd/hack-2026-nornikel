# Page specs — 10 mockups

## P01 — Landing / главная

- **Файл:** `01_mockups/page01_landing_home.png`
- **Route:** `/`
- **Цель:** За 10 секунд объяснить ценность: единая R&D-карта знаний с проверяемыми источниками.

**Блоки:**
- Header: логотип, команда, навигация, hackathon badge
- Hero: оффер + CTA + knowledge graph
- Stats: sources, evidence spans, unsupported numbers, geography
- Feature cards: поиск, верификация, граф, gaps/conflicts
- How it works: ingest → extraction → evidence answer
- Final CTA

**Реализация:**
- Статы брать из backend overview, не хардкодить
- Граф в hero — статичная SVG/PNG-иллюстрация
- CTA ведёт в демо/поиск

## P02 — Поиск и анализ

- **Файл:** `01_mockups/page02_search_analysis.png`
- **Route:** `/search`
- **Цель:** Естественный вопрос + многопараметрические фильтры.

**Блоки:**
- Question textarea
- Filters: material, process, conditions, geography, years, confidence
- Draft evidence packet: 3–5 релевантных источников
- Query suggestions
- Verification explainer

**Реализация:**
- Формировать structured query object
- Не запускать OCR; no-text sources не участвуют
- Перед ответом показывать candidate sources

## P03 — Ответ с доказательствами

- **Файл:** `01_mockups/page03_answer_with_citations.png`
- **Route:** `/answer/:runId`
- **Цель:** Показать ответ, где каждое утверждение связано с evidence.

**Блоки:**
- Query recap + filters
- Answer bullets with citation chips
- Evidence cards with page/table/span locator
- Verification metrics: citation coverage, numeric mismatch, confidence
- Next checks / limitations

**Реализация:**
- Каждое предложение хранит supporting_span_ids
- Клик по citation скроллит к evidence card
- Числа показывать только если есть provenance

## P04 — Граф знаний

- **Файл:** `01_mockups/page04_knowledge_graph.png`
- **Route:** `/graph`
- **Цель:** Навигация по сущностям и связям: material/process/equipment/result/publication/expert.

**Блоки:**
- Entity search + filters
- Graph canvas
- Node details panel
- Example graph paths
- Conflicts card

**Реализация:**
- Не грузить полный граф на клиент; запрашивать neighborhood/path
- Цвета узлов фиксировать по entity type
- Каждая связь должна иметь evidence_span_ids

## P05 — Данные и импорт

- **Файл:** `01_mockups/page05_data_import.png`
- **Route:** `/data`
- **Цель:** Контроль корпуса: загрузка, статусы, карантин, enrichment.

**Блоки:**
- Corpus metrics
- Supported formats
- OCR disabled banner
- Upload/import buttons
- Sources table
- Archive unpacking row
- Pagination

**Реализация:**
- OCR выключен; scan/image-only → quarantine reason no_text_layer_ocr_disabled
- Архивы показывать как parent + member files
- Статусы: processed, queued, enrichment, quarantine

## P06 — Источник и evidence

- **Файл:** `01_mockups/page06_source_evidence.png`
- **Route:** `/sources/:id`
- **Цель:** Точная трассировка от ответа до страницы/таблицы/строки.

**Блоки:**
- Source browser
- Document/table preview
- Metadata panel
- Reliability card
- Extracted entities
- Provenance block
- Related facts

**Реализация:**
- Показывать locator: page, table, row, sheet, span_id
- Подсвечивать row/fragment, на который ссылается ответ
- Факты без locator не считать verified

## P07 — Пробелы и противоречия

- **Файл:** `01_mockups/page07_gaps_conflicts.png`
- **Route:** `/analytics/gaps`
- **Цель:** Управленческая матрица: где есть данные, где gaps, где conflicts.

**Блоки:**
- Coverage matrix
- Legend
- Conflict list
- Gap list
- Convert gap to hypothesis CTA
- What to study next

**Реализация:**
- Матрицу строить из реальных фактов, не из demo rules
- Conflict = несколько facts с несовместимыми значениями/методами
- Gap = отсутствует покрытие для выбранной комбинации

## P08 — Сравнение технологий

- **Файл:** `01_mockups/page08_technology_comparison.png`
- **Route:** `/compare`
- **Цель:** Сравнить варианты по эффективности, CAPEX/OPEX, климату, ограничениям и источникам.

**Блоки:**
- Summary / recommended strategy
- Verdict legend
- Filters
- Comparison table
- Source count per technology
- Notes

**Реализация:**
- Каждая ячейка таблицы должна иметь evidence source или статус needs_data
- Russia/foreign grouping по practice_geography
- Не смешивать относительные оценки и фактические числа

## P09 — Эксперты и лаборатории

- **Файл:** `01_mockups/page09_experts_labs.png`
- **Route:** `/experts`
- **Цель:** Показать носителей экспертизы по теме.

**Блоки:**
- Filters
- Stats: experts/labs/publications/topics
- Expertise network
- Who to ask panel
- Expert/lab cards
- Topic chips

**Реализация:**
- Эксперта связывать с темой через publications/projects/facts
- Не показывать персональные данные сверх справочника
- Рекомендация эксперта должна объясняться связями

## P10 — Демо для жюри

- **Файл:** `01_mockups/page10_jury_demo_dashboard.png`
- **Route:** `/demo`
- **Цель:** Один экран для питча: проблема, результат, метрики, ценность.

**Блоки:**
- Hero: Demo for jury
- Central result card
- KPI cards
- Mini previews: search, graph, data, analytics, security
- Problem → Solution → Value
- Final CTA

**Реализация:**
- Использовать реальные demo-run данные, без synthetic leakage
- KPI явно помечать: corpus/run/eval
- Экран должен работать как 5-minute pitch cockpit
