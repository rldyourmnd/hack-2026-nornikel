from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from nornikel_kg.services import runtime
from services.api.main import create_app


def _client(tmp_path: Path, monkeypatch: MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DUCKDB_PATH", str(tmp_path / "catalog.duckdb"))
    monkeypatch.setenv("ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("SYNC_ENRICHMENT", "true")
    monkeypatch.setenv("GLINER_ENABLED", "false")
    # Analytics tests use an isolated test ledger; runtime seeding stays OFF.
    runtime.get_ledger_repository.cache_clear()
    runtime.get_qa_service.cache_clear()
    runtime.get_ingestion_service.cache_clear()
    runtime.get_extraction_service.cache_clear()
    runtime.get_retrieval_service.cache_clear()
    runtime.get_graph_service.cache_clear()
    return TestClient(create_app())


def test_gaps_analyze_returns_matrix(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    response = client.get("/gaps/analyze")
    assert response.status_code == 200
    payload = response.json()
    assert payload["cells"]
    assert payload["gap_count"] + payload["covered_count"] == len(payload["cells"])


def test_timeline_lists_dated_events(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    upload = client.post(
        "/sources/upload",
        files={
            "file": (
                "dated_report.md",
                "# Отчет 2021\n\nИванов И.И., инженер института. Утверждено 5 июня 2021 г. "
                "Обеднение шлака печи Ванюкова снижает потери никеля.\n".encode(),
                "text/markdown",
            )
        },
    )
    assert upload.status_code == 200
    response = client.get("/graph/timeline")
    assert response.status_code == 200
    events = response.json()["events"]
    publication_events = [e for e in events if e["entity_type"] == "publication"]
    assert publication_events
    assert any(e.get("year") == 2021 for e in publication_events)


def test_enrich_endpoint_reruns_extraction(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    upload = client.post(
        "/sources/upload",
        files={
            "file": (
                "enrich_source.md",
                "Электроэкстракция никеля в диафрагменной ячейке.\n".encode(),
                "text/markdown",
            )
        },
    )
    assert upload.status_code == 200
    source_id = upload.json()["source"]["source_id"]
    response = client.post(f"/sources/{source_id}/enrich")
    assert response.status_code == 200
    assert response.json()["scheduled"] is True
    runs = client.get(f"/sources/{source_id}/runs")
    assert runs.status_code == 200
    assert runs.json()["runs"]


def test_enrich_missing_source_is_404(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    response = client.post("/sources/src_missing/enrich")
    assert response.status_code == 404


def test_reindex_all_reports_disabled_backend(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("EMBEDDING_BACKEND", "off")
    client = _client(tmp_path, monkeypatch)
    response = client.post("/sources/reindex-all")
    assert response.status_code == 200
    assert response.json()["scheduled"] is False


def test_eval_summary_reports_status_field(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    response = client.get("/eval/summary")
    assert response.status_code == 200
    assert "status" in response.json()


def test_source_summary_carries_year_and_geography(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    upload = client.post(
        "/sources/upload",
        files={
            "file": (
                "meta_report.md",
                "Отчет о выщелачивании, 2019 г. Кучное выщелачивание руды в холодном "
                "климате изучено детально.\n".encode(),
                "text/markdown",
            )
        },
    )
    assert upload.status_code == 200
    sources = client.get("/sources").json()["sources"]
    uploaded = [s for s in sources if s["title"].startswith("meta_report")]
    assert uploaded
    assert uploaded[0]["year"] == 2019
    assert uploaded[0]["geography"] == "ru"

def test_answer_runs_verification_trail(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    ask = client.post(
        "/qa/ask",
        json={"question": "Что делали по Ni-30Cu при старении 700 C 8 ч?", "language": "ru"},
    )
    assert ask.status_code == 200
    response = client.get("/stats/answer-runs?limit=5")
    assert response.status_code == 200
    runs = response.json()["runs"]
    assert runs and "verification" in runs[0]
