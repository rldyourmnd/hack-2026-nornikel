from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pytest import MonkeyPatch

from nornikel_kg.services import runtime


def test_project_root_prefers_environment_variable(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))

    assert runtime.project_root() == tmp_path.resolve()


def test_ledger_repository_first_build_is_thread_safe(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    db_path = tmp_path / "catalog.duckdb"
    monkeypatch.setenv("DUCKDB_PATH", str(db_path))
    runtime.get_ledger_repository.cache_clear()
    runtime.get_qa_service.cache_clear()

    with ThreadPoolExecutor(max_workers=2) as executor:
        repositories = list(executor.map(lambda _: runtime.get_ledger_repository(), range(2)))

    # concurrent first build must not corrupt the DB: both repositories are
    # usable and agree on the (empty) source list, no half-migrated state.
    assert all(repository.list_sources() == [] for repository in repositories)

    runtime.get_ledger_repository.cache_clear()
    runtime.get_qa_service.cache_clear()
