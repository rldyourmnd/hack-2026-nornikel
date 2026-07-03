from __future__ import annotations

from pathlib import Path

import pytest

from nornikel_kg.adapters.duckdb.repositories import DuckDBLedgerRepository
from nornikel_kg.ports.parser import (
    FetchedPage,
    NoTextLayerError,
    ParsedBlock,
    ParsedDocument,
    ParsedTable,
    ParsedTableCell,
    ParsedTableRow,
    ParserError,
)
from nornikel_kg.services.ingestion_service import IngestionService

PDF_BYTES = b"%PDF-1.4 fake"
DOCX_BYTES = b"PK fake docx"


class StubParser:
    def __init__(self, result: ParsedDocument | Exception) -> None:
        self.result = result
        self.calls: list[str] = []

    def parse(self, *, content: bytes, filename: str) -> ParsedDocument:
        self.calls.append(filename)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class StubFetcher:
    def __init__(self, page: FetchedPage | Exception) -> None:
        self.page = page

    def fetch(self, url: str) -> FetchedPage:
        if isinstance(self.page, Exception):
            raise self.page
        return self.page


@pytest.fixture()
def repository(tmp_path: Path) -> DuckDBLedgerRepository:
    repo = DuckDBLedgerRepository(tmp_path / "test.duckdb")
    repo.migrate()
    return repo


def _parsed_document() -> ParsedDocument:
    return ParsedDocument(
        blocks=[
            ParsedBlock(text="Отчет о старении Ni-30Cu", page=1, locator="block_1"),
            ParsedBlock(text="Твердость выросла до 245 HV", page=2, locator="block_2"),
        ],
        tables=[
            ParsedTable(
                rows=[
                    ParsedTableRow(
                        cells=[
                            ParsedTableCell(text="Ni-30Cu", row_index=1, col_index=1),
                            ParsedTableCell(text="245 HV", row_index=1, col_index=2),
                        ],
                        row_index=1,
                    )
                ],
                table_index=1,
                page=2,
            )
        ],
        title="aging-report",
        parser_profile="docling_v1",
    )


def test_pdf_ingest_writes_spans_and_completed_run(
    repository: DuckDBLedgerRepository, tmp_path: Path
) -> None:
    service = IngestionService(
        repository, parser=StubParser(_parsed_document()), artifact_root=tmp_path / "artifacts"
    )
    response = service.ingest_upload(filename="report.pdf", content=PDF_BYTES)
    assert response.source.status == "completed"
    assert response.evidence_count == 3  # 2 text blocks + 1 table row
    spans = repository.list_evidence_spans(response.source.source_id)
    span_types = sorted(span.span_type for span in spans)
    assert span_types == ["table_row", "text", "text"]
    table_span = next(span for span in spans if span.span_type == "table_row")
    assert "table_1:row_1" in str(table_span.locator)
    assert (tmp_path / "artifacts" / "sources" / response.source.source_id).exists()


def test_no_text_layer_pdf_is_quarantined(repository: DuckDBLedgerRepository) -> None:
    service = IngestionService(
        repository, parser=StubParser(NoTextLayerError("PDF has no text layer"))
    )
    response = service.ingest_upload(filename="scan.pdf", content=PDF_BYTES)
    assert response.source.status == "quarantined"
    assert response.evidence_count == 0
    assert response.warnings and "text layer" in response.warnings[0]
    runs = repository.list_ingestion_runs(response.source.source_id)
    assert runs[0]["status"] == "quarantined"
    assert repository.list_evidence_spans(response.source.source_id) == []


def test_parser_crash_is_quarantined_not_500(repository: DuckDBLedgerRepository) -> None:
    service = IngestionService(repository, parser=StubParser(ParserError("boom")))
    response = service.ingest_upload(filename="broken.docx", content=DOCX_BYTES)
    assert response.source.status == "quarantined"


def test_url_ingest_creates_url_source(repository: DuckDBLedgerRepository) -> None:
    page = FetchedPage(
        url="https://example.org/report",
        text="Первая строка\nВторая строка про Ni-30Cu",
        title="Отчет онлайн",
        date="2026-07-01",
    )
    service = IngestionService(repository, url_fetcher=StubFetcher(page))
    response = service.ingest_url("https://example.org/report")
    assert response.source.status == "completed"
    assert response.source.document_type == "url"
    assert response.source.title == "Отчет онлайн"
    assert response.evidence_count == 2


def test_csv_upload_still_works_and_records_run(repository: DuckDBLedgerRepository) -> None:
    csv_content = (
        b"experiment_id,material,regime,temperature_c,duration_h,atmosphere,"
        b"property,method,baseline_value,treated_value,unit,effect\n"
        b"exp_x,Ni-30Cu,aging,700,8,air,hardness,HV10,210,245,HV,increase\n"
    )
    service = IngestionService(repository, parser=StubParser(ParserError("unused")))
    response = service.ingest_upload(filename="data.csv", content=csv_content)
    assert response.source.status == "completed"
    runs = repository.list_ingestion_runs(response.source.source_id)
    assert runs[0]["counters"]["measurements"] >= 1
