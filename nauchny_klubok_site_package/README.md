# Научный клубок — mockups + site assets

Состав архива:

- `01_mockups/` — 10 страниц-мокапов сайта.
- `02_assets_batch01_branding/` — ассеты 01–10: бренд, маскот, hero.
- `03_assets_batch02_product/` — ассеты 11–20: продуктовые фичи.
- `04_assets_batch03_analytics_transparent/` — ассеты 21–30: аналитика/демо, RGBA с прозрачностью.
- `docs/page_specs.md` — краткое ТЗ по всем страницам.
- `docs/asset_catalog.md` — каталог всех 30 ассетов.
- `docs/implementation_outline.md` — короткие правила реализации.
- `docs/pages.json` — машинно-читаемая структура страниц.

Ключевые правила дизайна/реализации:

1. Не использовать synthetic/demo data в production-потоке.
2. OCR выключен: scan/image-only документы идут в quarantine с явной причиной.
3. Каждый ответный тезис должен иметь citation/span/provenance.
4. Числа выводить только при подтверждении источником или validated fact.
5. География “Россия / зарубежная практика” не должна определяться только по языку документа.
