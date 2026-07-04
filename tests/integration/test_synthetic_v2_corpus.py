from __future__ import annotations

import json
from pathlib import Path

import pytest

from nornikel_kg.adapters.duckdb.repositories import DuckDBLedgerRepository
from nornikel_kg.adapters.trafilatura.fetcher import TrafilaturaUrlFetcher
from nornikel_kg.services.extraction_service import ExtractionService
from nornikel_kg.services.ingestion_service import IngestionService

CORPUS_DIR = Path(__file__).resolve().parents[2] / "sample_docs" / "synthetic_v2"
MANIFEST = json.loads((CORPUS_DIR / "manifest.json").read_text(encoding="utf-8"))


@pytest.fixture()
def service(tmp_path: Path) -> IngestionService:
    repository = DuckDBLedgerRepository(tmp_path / "v2.duckdb")
    repository.migrate()
    return IngestionService(
        repository,
        artifact_root=tmp_path / "artifacts",
        extraction_service=ExtractionService(repository, use_gliner=False),
    )


def test_manifest_matches_committed_files() -> None:
    committed = {path.name for path in CORPUS_DIR.iterdir() if path.name != "manifest.json"}
    assert committed == set(MANIFEST["sources"])
    assert MANIFEST["source_count"] == len(committed) == 17


def test_csv_and_markdown_corpus_ingests_offline(service: IngestionService) -> None:
    """CSV/MD subset must ingest without any ML dependency (CI path)."""
    ingested = 0
    for filename, meta in MANIFEST["sources"].items():
        if meta["kind"] not in {"csv", "markdown"}:
            continue
        response = service.ingest_upload(
            filename=filename, content=(CORPUS_DIR / filename).read_bytes()
        )
        assert response.source.status == "completed", filename
        ingested += 1
    assert ingested == 7  # 4 csv + 3 md

    # Seeded conflicts must be detected from the ingested measurements alone.
    packet = service.repository.load_evidence_packet()
    conflict_types = {str(conflict.get("type")) for conflict in packet.conflicts}
    assert "method_mismatch" in conflict_types
    assert "contradictory_direction" in conflict_types

    # Alias merging: МН30 in notes must land on the CuNi30 dictionary entity.
    entity = service.repository.get_entity("mat_cuni_30")
    assert entity is not None
    assert entity["evidence_span_ids"], "МН30 mentions must attach evidence to CuNi30"


def test_html_fixture_extracts_via_trafilatura_offline(service: IngestionService) -> None:
    pytest.importorskip("trafilatura")
    html = (CORPUS_DIR / "v2_online_resource.html").read_text(encoding="utf-8")
    page = TrafilaturaUrlFetcher().extract(url="https://fixture.local/v2", html=html)
    assert "CuNi30" in page.text


def test_docx_corpus_ingests_with_docling(service: IngestionService) -> None:
    pytest.importorskip("docling")
    filename = "v2_protocol_01_aging.docx"
    response = service.ingest_upload(
        filename=filename, content=(CORPUS_DIR / filename).read_bytes()
    )
    assert response.source.status == "completed"
    assert response.evidence_count >= 3


def test_scan_pdf_quarantines_with_docling(service: IngestionService) -> None:
    pytest.importorskip("docling")
    response = service.ingest_upload(
        filename="v2_scan_no_text_layer.pdf",
        content=(CORPUS_DIR / "v2_scan_no_text_layer.pdf").read_bytes(),
    )
    assert response.source.status == "quarantined"
