from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from nornikel_kg.services import runtime
from services.api.main import create_app


def client_with_tmp_ledger(tmp_path: Path, monkeypatch: MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DUCKDB_PATH", str(tmp_path / "catalog.duckdb"))
    monkeypatch.setenv("ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    runtime.get_ledger_repository.cache_clear()
    runtime.get_qa_service.cache_clear()
    runtime.get_ingestion_service.cache_clear()
    return TestClient(create_app())


def test_health_endpoint(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = client_with_tmp_ledger(tmp_path, monkeypatch)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_qa_endpoint_returns_grounded_answer(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    client = client_with_tmp_ledger(tmp_path, monkeypatch)
    response = client.post(
        "/qa/ask",
        json={
            "question": "Что делали по Ni-30Cu при старении 700 C 8 ч?",
            "language": "ru",
            "include_graph": True,
            "include_gaps": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["verification"]["unsupported_claim_count"] == 0
    assert payload["experiments"]
    assert payload["evidence"]


def test_qa_endpoint_returns_gap_without_hallucinating(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    client = client_with_tmp_ledger(tmp_path, monkeypatch)
    response = client.post(
        "/qa/ask",
        json={
            "question": "Есть ли электропроводность для Ni-30Cu после старения 700 C 8 ч?",
            "language": "ru",
            "include_graph": True,
            "include_gaps": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["answer_summary"] == []
    assert payload["experiments"] == []
    assert payload["gaps"]
    assert payload["verification"]["unsupported_claim_count"] == 0


@pytest.mark.parametrize(
    "question",
    [
        "что было с Ni-20",
        "что со сплавами? с ni-20",
        "что со сплавами? с ni 20",
        "что со сплавами? с Ni–20",
    ],
)
def test_qa_endpoint_does_not_return_nearby_material_for_unknown_explicit_material(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    question: str,
) -> None:
    client = client_with_tmp_ledger(tmp_path, monkeypatch)
    response = client.post(
        "/qa/ask",
        json={
            "question": question,
            "language": "ru",
            "include_graph": True,
            "include_gaps": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer_summary"] == []
    assert payload["experiments"] == []
    assert payload["evidence"] == []
    assert payload["gaps"] == []
    assert payload["confidence"] == "low"
    assert "Что было с Ni-30Cu?" in payload["follow_up_queries"]
    assert "Что было с CuNi30?" in payload["follow_up_queries"]


@pytest.mark.parametrize(
    ("question", "expected_material"),
    [
        ("что было с Ni-30Cu", "Ni-30Cu"),
        ("что со сплавами? с ni-30cu", "Ni-30Cu"),
        ("что со сплавами? с Ni 30 Cu", "Ni-30Cu"),
        ("что со сплавами? с Cu Ni 30", "CuNi30"),
    ],
)
def test_qa_endpoint_keeps_exact_material_query_scoped_to_that_material(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    question: str,
    expected_material: str,
) -> None:
    client = client_with_tmp_ledger(tmp_path, monkeypatch)
    response = client.post(
        "/qa/ask",
        json={
            "question": question,
            "language": "ru",
            "include_graph": True,
            "include_gaps": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["experiments"]
    assert {experiment["material_name"] for experiment in payload["experiments"]} == {
        expected_material
    }


def test_qa_endpoint_keeps_family_query_broad_without_treating_temperature_as_material(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    client = client_with_tmp_ledger(tmp_path, monkeypatch)
    response = client.post(
        "/qa/ask",
        json={
            "question": "что со сплавами Ni-Cu 700 C 8 ч",
            "language": "ru",
            "include_graph": True,
            "include_gaps": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert {experiment["material_name"] for experiment in payload["experiments"]} == {
        "CuNi30",
        "Ni-30Cu",
    }


def test_sources_upload_and_evidence_listing(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    client = client_with_tmp_ledger(tmp_path, monkeypatch)
    csv_content = (
        "experiment_id,material,regime,temperature_c,duration_h,atmosphere,"
        "property,method,baseline_value,treated_value,unit,effect\n"
        "exp_api_upload,Ni-30Cu,aging,700,8,air,Vickers hardness,HV10,200,231,HV,increase\n"
    )

    upload = client.post(
        "/sources/upload",
        files={"file": ("uploaded.csv", csv_content, "text/csv")},
    )

    assert upload.status_code == 200
    source_id = upload.json()["source"]["source_id"]
    evidence = client.get(f"/sources/{source_id}/evidence")
    assert evidence.status_code == 200
    assert evidence.json()["evidence"][0]["span_type"] == "table_row"


def test_sources_evidence_returns_404_for_missing_source(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    client = client_with_tmp_ledger(tmp_path, monkeypatch)

    response = client.get("/sources/not-existing-source/evidence")

    assert response.status_code == 404
    assert response.json()["detail"] == "Source not found"


def test_sources_upload_rejects_invalid_csv(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = client_with_tmp_ledger(tmp_path, monkeypatch)
    invalid_csv = (
        "experiment_id,material,regime,temperature_c,duration_h,atmosphere,"
        "property,method,baseline_value,treated_value,unit,effect\n"
        "exp_api_upload_bad,Ni-30Cu,aging,not-a-number,8,air,"
        "Vickers hardness,HV10,200,230,HV,increase\n"
    )

    response = client.post(
        "/sources/upload",
        files={"file": ("bad.csv", invalid_csv, "text/csv")},
    )

    assert response.status_code == 400
    assert "field 'temperature_c' must be a numeric value" in response.json()["detail"]


def test_sources_upload_rejects_empty_file(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = client_with_tmp_ledger(tmp_path, monkeypatch)

    response = client.post(
        "/sources/upload",
        files={"file": ("empty.csv", b"", "text/csv")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded file is empty."


def test_sources_upload_rejects_filename_with_path_separator(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    client = client_with_tmp_ledger(tmp_path, monkeypatch)

    response = client.post(
        "/sources/upload",
        files={"file": ("../bad.csv", b"id,x\n1,2", "text/csv")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded filename must not contain path separators."


def test_sources_upload_rejects_too_long_filename(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    client = client_with_tmp_ledger(tmp_path, monkeypatch)
    filename = f"{'a' * 161}.csv"

    response = client.post(
        "/sources/upload",
        files={"file": (filename, b"id,x\n1,2", "text/csv")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded filename is too long. Maximum length is 160."


def test_sources_upload_rejects_oversized_file(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_SOURCE_UPLOAD_BYTES", "16")
    client = client_with_tmp_ledger(tmp_path, monkeypatch)
    too_big = (
        b"experiment_id,material,regime,temperature_c,duration_h,atmosphere,property,method,"
        b"baseline_value,treated_value,unit,effect\n" + b"x" * 20
    )

    response = client.post(
        "/sources/upload",
        files={"file": ("big.csv", too_big, "text/csv")},
    )

    assert response.status_code == 413
    assert (
        response.json()["detail"]
        == "Uploaded file is too large. Maximum allowed size is 16 bytes."
    )


def test_sources_upload_rejects_unsupported_mime_for_csv_extension(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    client = client_with_tmp_ledger(tmp_path, monkeypatch)

    response = client.post(
        "/sources/upload",
        files={"file": ("report.csv", b"id,x\n1,2", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"].startswith("Unsupported MIME type")


def test_sources_upload_rejects_markdown_without_extractable_evidence(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    client = client_with_tmp_ledger(tmp_path, monkeypatch)

    response = client.post(
        "/sources/upload",
        files={"file": ("notes.md", "# Header\n\n", "text/markdown")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Markdown source has no extractable evidence."


def test_sources_delete_endpoint_removes_source(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    client = client_with_tmp_ledger(tmp_path, monkeypatch)
    csv_content = (
        "experiment_id,material,regime,temperature_c,duration_h,atmosphere,"
        "property,method,baseline_value,treated_value,unit,effect\n"
        "exp_api_upload,Ni-30Cu,aging,700,8,air,Vickers hardness,HV10,200,231,HV,increase\n"
    )

    upload = client.post(
        "/sources/upload",
        files={"file": ("deletable.csv", csv_content, "text/csv")},
    )
    source_id = upload.json()["source"]["source_id"]

    response = client.delete(f"/sources/{source_id}")
    assert response.status_code == 200
    assert response.json() == {"source_id": source_id, "deleted": True}

    response = client.get(f"/sources/{source_id}/evidence")
    assert response.status_code == 404


def test_sources_delete_endpoint_returns_404_for_missing_source(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    client = client_with_tmp_ledger(tmp_path, monkeypatch)

    response = client.delete("/sources/not-existing-source")
    assert response.status_code == 404


def test_sources_upload_rejects_unsupported_extension(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    client = client_with_tmp_ledger(tmp_path, monkeypatch)

    response = client.post(
        "/sources/upload",
        files={"file": ("report.exe", b"MZ binary", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert "Unsupported upload type" in response.json()["detail"]


def test_qa_endpoint_can_filter_by_source_id_and_material(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    client = client_with_tmp_ledger(tmp_path, monkeypatch)
    csv_payload = (
        "experiment_id,material,regime,temperature_c,duration_h,atmosphere,"
        "property,method,baseline_value,treated_value,unit,effect\n"
        "exp_filter,NiFilter,aging,700,8,air,Vickers hardness,HV10,210,220,HV,increase\n"
    )
    source_id = (
        client.post(
            "/sources/upload",
            files={"file": ("filter_source.csv", csv_payload, "text/csv")},
        )
        .json()["source"]["source_id"]
    )

    response = client.post(
        "/qa/ask",
        json={
            "question": "Что делали с NiFilter при старении 700 C 8 ч?",
            "language": "ru",
            "filters": {"source_ids": [source_id], "material": "NiFilter"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["experiments"]) == 1
    assert payload["experiments"][0]["source_id"] == source_id
    assert "NiFilter" in payload["experiments"][0]["material_name"]


def test_qa_endpoint_accepts_scalar_filter_values(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    client = client_with_tmp_ledger(tmp_path, monkeypatch)
    csv_payload = (
        "experiment_id,material,regime,temperature_c,duration_h,atmosphere,"
        "property,method,baseline_value,treated_value,unit,effect\n"
        "exp_filter_scalar,NiFilter,aging,700,8,air,Vickers hardness,HV10,210,220,HV,increase\n"
    )
    source_id = (
        client.post(
            "/sources/upload",
            files={"file": ("filter_scalar_source.csv", csv_payload, "text/csv")},
        )
        .json()["source"]["source_id"]
    )

    response = client.post(
        "/qa/ask",
        json={
            "question": "Что делали с NiFilter при старении 700 C 8 ч?",
            "language": "ru",
            "filters": {"source_ids": source_id, "material": "NiFilter"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["experiments"]) == 1
    assert payload["experiments"][0]["source_id"] == source_id


def test_qa_endpoint_rejects_unknown_filter_key(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    client = client_with_tmp_ledger(tmp_path, monkeypatch)

    response = client.post(
        "/qa/ask",
        json={
            "question": "Что делали по Ni-30Cu при старении 700 C 8 ч?",
            "language": "ru",
            "filters": {"unknown_key": ["x"]},
        },
    )

    assert response.status_code == 422
    assert "filters" in response.json()["detail"][0]["loc"]


def test_qa_endpoint_source_filter_empty_result(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    client = client_with_tmp_ledger(tmp_path, monkeypatch)

    response = client.post(
        "/qa/ask",
        json={
            "question": "Что делали по Ni-30Cu при старении 700 C 8 ч?",
            "language": "ru",
            "filters": {"source_ids": ["nonexistent_source_id"]},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["experiments"] == []
    assert payload["answer_summary"] == []
