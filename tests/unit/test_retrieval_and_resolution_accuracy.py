from __future__ import annotations

from pathlib import Path

import pytest

from nornikel_kg.adapters.duckdb.repositories import DuckDBLedgerRepository
from nornikel_kg.adapters.embeddings import FakeEmbeddingBackend
from nornikel_kg.ports.retrieval import IndexableUnit, RetrievalHit
from nornikel_kg.services.entity_resolution import EntityResolutionService
from nornikel_kg.services.retrieval_service import RetrievalService


@pytest.fixture()
def repository(tmp_path: Path) -> DuckDBLedgerRepository:
    repo = DuckDBLedgerRepository(tmp_path / "retrieval.duckdb")
    repo.migrate()
    return repo


class _StaticMatcher:
    def __init__(self, entity_id: str, score: float) -> None:
        self.entity_id = entity_id
        self.score = score
        self.calls: list[tuple[str, str]] = []

    def match(self, name: str, entity_type: str) -> tuple[str, float] | None:
        self.calls.append((name, entity_type))
        return (self.entity_id, self.score)


def test_semantic_fallback_merges_at_high_score(repository: DuckDBLedgerRepository) -> None:
    target = repository.find_entity("электроэкстракция", "regime")
    assert target is not None
    matcher = _StaticMatcher(target["entity_id"], 0.95)
    service = EntityResolutionService(repository, semantic_matcher=matcher)
    result = service.resolve_or_create(
        mention="катодное осаждение", entity_type="regime", span_ids=["sp1"]
    )
    assert result.action == "matched_semantic"
    assert result.entity_id == target["entity_id"]
    # the mention became a learned alias -> next resolution is an alias hit
    again = service.resolve_or_create(
        mention="катодное осаждение", entity_type="regime", span_ids=["sp2"]
    )
    assert again.action in {"matched_alias", "matched_key"}


def test_semantic_fallback_review_zone_does_not_merge(
    repository: DuckDBLedgerRepository,
) -> None:
    target = repository.find_entity("шлак", "material")
    assert target is not None
    matcher = _StaticMatcher(target["entity_id"], 0.85)
    service = EntityResolutionService(repository, semantic_matcher=matcher)
    result = service.resolve_or_create(
        mention="агломерат", entity_type="material", span_ids=["sp1"]
    )
    assert result.action == "created"


def test_semantic_fallback_digit_veto(repository: DuckDBLedgerRepository) -> None:
    """Ni-30Cu-like codes must never merge by cosine (compositions differ)."""
    target = repository.find_entity("шлак", "material")
    assert target is not None
    matcher = _StaticMatcher(target["entity_id"], 0.99)
    service = EntityResolutionService(repository, semantic_matcher=matcher)
    result = service.resolve_or_create(
        mention="Ni-20Cu", entity_type="material", span_ids=["sp1"]
    )
    assert result.action == "created"
    assert matcher.calls == []  # semantic stage skipped entirely


def test_fake_sparse_query_vectors_are_flat() -> None:
    backend = FakeEmbeddingBackend()
    [doc] = backend.embed_sparse(["шлак шлак штейн"])
    [query] = backend.embed_sparse_query(["шлак шлак штейн"])
    assert query.indices == doc.indices
    assert all(value == 1.0 for value in query.values)
    assert any(value > 1.0 for value in doc.values)  # doc keeps term weights


class _RecordingIndex:
    """VectorIndexPort fake capturing indexed units and returning canned hits."""

    def __init__(self) -> None:
        self.indexed: dict[str, list[IndexableUnit]] = {}
        self.hits: list[RetrievalHit] = []

    def index_units(self, collection: str, units: list[IndexableUnit]) -> int:
        self.indexed.setdefault(collection, []).extend(units)
        return len(units)

    def hybrid_search(self, collection: str, **kwargs: object) -> list[RetrievalHit]:
        return self.hits

    def dense_search(self, collection: str, **kwargs: object) -> list[RetrievalHit]:
        return []

    def delete_source_units(self, collection: str, source_id: str) -> None:
        return None


class _ReversingReranker:
    def rerank(
        self, query: str, candidates: list[tuple[str, str]], *, top_k: int
    ) -> list[str]:
        return [unit_id for unit_id, _ in reversed(candidates)][:top_k]


def test_indexed_units_carry_source_title_context(
    repository: DuckDBLedgerRepository,
) -> None:
    csv_content = (
        b"experiment_id,material,regime,temperature_c,duration_h,atmosphere,"
        b"property,method,baseline_value,treated_value,unit,effect\n"
        b"exp_ctx,Ni-30Cu,aging,700,8,air,Vickers hardness,HV10,210,245,HV,increase\n"
    )
    response = repository.ingest_source_bytes(filename="context.csv", content=csv_content)
    index = _RecordingIndex()
    service = RetrievalService(repository, index)
    service.index_source(response.source.source_id)
    units = index.indexed["evidence_units"]
    assert units and all("\n" in unit.text for unit in units)  # title prefix present


def test_reranker_reorders_verified_candidates(repository: DuckDBLedgerRepository) -> None:
    csv_content = (
        b"experiment_id,material,regime,temperature_c,duration_h,atmosphere,"
        b"property,method,baseline_value,treated_value,unit,effect\n"
        b"exp_r1,Ni-30Cu,aging,700,8,air,Vickers hardness,HV10,210,245,HV,increase\n"
        b"exp_r2,Ni-20Cu,aging,700,8,air,Vickers hardness,HV10,200,230,HV,increase\n"
    )
    repository.ingest_source_bytes(filename="rerank.csv", content=csv_content)
    spans = repository.list_evidence_spans()
    assert len(spans) >= 2
    index = _RecordingIndex()
    index.hits = [
        RetrievalHit(unit_id=span.span_id, score=1.0 - i / 10, payload={})
        for i, span in enumerate(spans[:2])
    ]
    service = RetrievalService(
        repository, index, reranker=_ReversingReranker(), rerank_candidates=2
    )
    result = service.retrieve_span_ids(
        question="q", allowed_labels=["internal"], top_k=1
    )
    # reranker reversed the fused order -> second hit wins
    assert result == [index.hits[1].unit_id]
