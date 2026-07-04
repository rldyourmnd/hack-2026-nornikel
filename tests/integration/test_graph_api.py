from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nornikel_kg.services import runtime
from services.api.main import app


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("DUCKDB_PATH", str(tmp_path / "graph.duckdb"))
    monkeypatch.setenv("ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("GLINER_ENABLED", "false")
    monkeypatch.setenv("SYNC_ENRICHMENT", "true")
    for cache in (
        runtime.get_ledger_repository,
        runtime.get_qa_service,
        runtime.get_ingestion_service,
        runtime.get_extraction_service,
        runtime.get_graph_service,
    ):
        cache.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    for cache in (
        runtime.get_ledger_repository,
        runtime.get_qa_service,
        runtime.get_ingestion_service,
        runtime.get_extraction_service,
        runtime.get_graph_service,
    ):
        cache.cache_clear()


def test_graph_neighborhood_404_for_unknown_entity(client: TestClient) -> None:
    response = client.get("/graph/neighborhood", params={"entity_id": "ent_missing"})
    assert response.status_code == 404
