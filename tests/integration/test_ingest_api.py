from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nornikel_kg.ports.parser import (
    FetchedPage,
    NoTextLayerError,
    ParsedBlock,
    ParsedDocument,
)
from nornikel_kg.services import runtime
from services.api.main import app


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("DUCKDB_PATH", str(tmp_path / "api.duckdb"))
    monkeypatch.setenv("ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("SYNC_ENRICHMENT", "true")
    runtime.get_ledger_repository.cache_clear()
    runtime.get_qa_service.cache_clear()
    runtime.get_ingestion_service.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    runtime.get_ledger_repository.cache_clear()
    runtime.get_qa_service.cache_clear()
    runtime.get_ingestion_service.cache_clear()


def _stub_parsed() -> ParsedDocument:
    return ParsedDocument(
        blocks=[ParsedBlock(text="Протокол испытаний Ni-30Cu", page=1, locator="block_1")],
        tables=[],
        title="protocol",
        parser_profile="docling_v1",
    )


def test_upload_pdf_via_api_with_stub_parser(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = runtime.get_ingestion_service()
    monkeypatch.setattr(
        service, "_parser", type("P", (), {"parse": lambda self, **kw: _stub_parsed()})()
    )
    response = client.post(
        "/sources/upload",
        files={"file": ("report.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["source"]["status"] == "completed"
    assert payload["evidence_count"] == 1

    runs = client.get(f"/sources/{payload['source']['source_id']}/runs")
    assert runs.status_code == 200
    assert runs.json()["runs"][0]["status"] == "completed"


def test_upload_scan_pdf_quarantined_via_api(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class QuarantineParser:
        def parse(self, **kwargs: object) -> ParsedDocument:
            raise NoTextLayerError("PDF has no text layer")

    service = runtime.get_ingestion_service()
    monkeypatch.setattr(service, "_parser", QuarantineParser())
    response = client.post(
        "/sources/upload",
        files={"file": ("scan.pdf", b"%PDF-1.4 image only", "application/pdf")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["source"]["status"] == "quarantined"
    assert payload["evidence_count"] == 0


def test_import_url_via_api(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class StubFetcher:
        def fetch(self, url: str) -> FetchedPage:
            return FetchedPage(url=url, text="Онлайн отчет про CuNi30", title="Веб-источник")

    service = runtime.get_ingestion_service()
    monkeypatch.setattr(service, "_url_fetcher", StubFetcher())
    response = client.post("/sources/import-url", json={"url": "https://example.org/x"})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["source"]["document_type"] == "url"
    assert payload["source"]["status"] == "completed"


def test_docx_upload_allowed_extension(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    service = runtime.get_ingestion_service()
    monkeypatch.setattr(
        service, "_parser", type("P", (), {"parse": lambda self, **kw: _stub_parsed()})()
    )
    response = client.post(
        "/sources/upload",
        files={
            "file": (
                "protocol.docx",
                b"PK fake docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 200, response.text


def test_empty_ledger_ask_returns_grounded_empty(client: TestClient) -> None:
    sources = client.get("/sources").json()["sources"]
    for source in sources:
        assert client.delete(f"/sources/{source['source_id']}").status_code == 200
    response = client.post("/qa/ask", json={"question": "Что делали по Ni-30Cu?"})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["experiments"] == []
    assert payload["evidence"] == []
    assert payload["confidence"] == "low"
