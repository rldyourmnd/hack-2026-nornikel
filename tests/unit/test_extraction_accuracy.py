from __future__ import annotations

from pathlib import Path

import pytest

from nornikel_kg.adapters.duckdb.repositories import DuckDBLedgerRepository
from nornikel_kg.adapters.gliner_ner.extractor import sentence_chunks
from nornikel_kg.adapters.llm.gateway import _strictify
from nornikel_kg.domain.extraction import EXTRACTION_JSON_SCHEMA
from nornikel_kg.ports.parser import ParsedBlock, ParsedDocument
from nornikel_kg.services.extraction_service import ExtractionService, _extract_authors


@pytest.fixture()
def repository(tmp_path: Path) -> DuckDBLedgerRepository:
    repo = DuckDBLedgerRepository(tmp_path / "accuracy.duckdb")
    repo.migrate()
    return repo


def test_alias_scan_respects_word_boundaries(repository: DuckDBLedgerRepository) -> None:
    """«руд» inside «оборудование» must not become the material «руда»."""
    service = ExtractionService(repository, use_gliner=False)
    mentions = service._dictionary_mentions(
        "Новое оборудование установлено в цехе; медицинский осмотр пройден."
    )
    texts = {(m.entity_type, m.text.lower()) for m in mentions}
    assert ("material", "руда") not in texts
    assert ("material", "медь") not in texts


def test_alias_scan_still_matches_inflected_forms(repository: DuckDBLedgerRepository) -> None:
    service = ExtractionService(repository, use_gliner=False)
    mentions = service._dictionary_mentions("Потери никеля со шлаком при обеднении шлака печи")
    types = {m.entity_type for m in mentions}
    assert "material" in types  # шлак / никель
    texts = {m.text.lower() for m in mentions}
    assert "шлак" in texts


def test_alloy_codes_never_cross_match(repository: DuckDBLedgerRepository) -> None:
    """Ni-30Cu alias must not fire on Ni-30Cr text (digit/Latin aliases match exactly)."""
    service = ExtractionService(repository, use_gliner=False)
    mentions = service._dictionary_mentions("Исследование сплава Ni-30Cr после отжига")
    assert all("cu" not in m.text.lower() for m in mentions if m.entity_type == "material")


def test_author_regex_rejects_abbreviations() -> None:
    head = "Contact: P.O. Box 123, U.S. Geological Survey. E-mail: info@usgs.gov"
    authors = _extract_authors(head)
    assert all("Box" not in author and "Geological" not in author for author in authors)


def test_authors_require_affiliation_context() -> None:
    bibliography = "1. Смирнов А.Б. Металлургия никеля. 2. Петров В.Г. Пирометаллургия."
    assert _extract_authors(bibliography) == []


def test_sentence_chunks_cover_text_with_overlap() -> None:
    text = " ".join(f"Предложение номер {i} о шлаке и штейне." for i in range(200))
    chunks = sentence_chunks(text, max_chars=500)
    assert all(len(chunk) <= 500 for _, chunk in chunks)
    # offsets are global: each chunk must reproduce the original text slice
    for offset, chunk in chunks:
        assert text[offset : offset + len(chunk)] == chunk
    # full coverage: last chunk reaches the end of the text
    last_offset, last_chunk = chunks[-1]
    assert last_offset + len(last_chunk) == len(text)


def test_sentence_chunks_short_text_is_single_chunk() -> None:
    assert sentence_chunks("Краткий текст.", max_chars=100) == [(0, "Краткий текст.")]


def test_strictify_enforces_required_completeness() -> None:
    strict = _strictify(dict(EXTRACTION_JSON_SCHEMA))
    entity_items = strict["properties"]["entities"]["items"]
    assert set(entity_items["required"]) == set(entity_items["properties"].keys())
    assert entity_items["additionalProperties"] is False
    relation_items = strict["properties"]["relations"]["items"]
    assert set(relation_items["required"]) == set(relation_items["properties"].keys())


def test_publication_gets_year_metadata(repository: DuckDBLedgerRepository) -> None:
    parsed = ParsedDocument(
        blocks=[
            ParsedBlock(
                text="Иванов И.И., инженер института. Отчет утвержден 5 июня 2021 г.",
                page=1,
                locator="block_1",
            ),
            ParsedBlock(
                text="Обеднение шлака печи Ванюкова изучено детально.",
                page=1,
                locator="block_2",
            ),
        ],
        tables=[],
        title="Отчет об обеднении шлака 2021",
        parser_profile="test_v1",
    )
    repository.ingest_parsed_document(
        source_id="src_dated",
        raw_sha256="1" * 64,
        title="Отчет об обеднении шлака 2021",
        document_type="pdf",
        parsed=parsed,
        artifact_locator="dated.pdf",
    )
    ExtractionService(repository, use_gliner=False).process_source("src_dated")
    publications = [
        repository.get_entity(e["entity_id"])
        for e in repository.list_graph_entities()
        if e["entity_type"] == "publication"
    ]
    assert publications
    metadata = publications[0]["metadata"]
    assert metadata.get("year") == 2021
    assert metadata.get("date") == "2021-06-05"
