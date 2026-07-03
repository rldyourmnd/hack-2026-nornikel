from __future__ import annotations

from pathlib import Path

import pytest

from nornikel_kg.adapters.duckdb.repositories import DuckDBLedgerRepository
from nornikel_kg.ports.parser import ParsedBlock, ParsedDocument
from nornikel_kg.ports.retrieval import IndexableUnit, RetrievalHit
from nornikel_kg.services.retrieval_service import RetrievalService


class InMemoryIndex:
    """Substring-scoring stand-in for Qdrant used in offline tests."""

    def __init__(self) -> None:
        self.collections: dict[str, dict[str, IndexableUnit]] = {}

    def index_units(self, collection: str, units: list[IndexableUnit]) -> int:
        bucket = self.collections.setdefault(collection, {})
        for unit in units:
            bucket[unit.unit_id] = unit
        return len(units)

    def hybrid_search(
        self,
        collection: str,
        *,
        query: str,
        top_k: int = 10,
        allowed_labels: list[str] | None = None,
        source_ids: list[str] | None = None,
    ) -> list[RetrievalHit]:
        hits = []
        for unit in self.collections.get(collection, {}).values():
            label = str(unit.payload.get("security_label", ""))
            if allowed_labels and label not in allowed_labels:
                continue
            if source_ids and str(unit.payload.get("source_id", "")) not in source_ids:
                continue
            tokens = [token for token in query.lower().split() if len(token) > 2]
            score = sum(token in unit.text.lower() for token in tokens)
            if score > 0:
                hits.append(RetrievalHit(unit_id=unit.unit_id, score=float(score)))
        hits.sort(key=lambda hit: -hit.score)
        return hits[:top_k]

    def delete_source_units(self, collection: str, source_id: str) -> None:
        bucket = self.collections.get(collection, {})
        for unit_id in [
            unit_id
            for unit_id, unit in bucket.items()
            if unit.payload.get("source_id") == source_id
        ]:
            del bucket[unit_id]


class ExplodingIndex:
    def index_units(self, collection: str, units: list[IndexableUnit]) -> int:
        raise ConnectionError("qdrant down")

    def hybrid_search(self, collection: str, **kwargs: object) -> list[RetrievalHit]:
        raise ConnectionError("qdrant down")

    def delete_source_units(self, collection: str, source_id: str) -> None:
        raise ConnectionError("qdrant down")


@pytest.fixture()
def repository(tmp_path: Path) -> DuckDBLedgerRepository:
    repo = DuckDBLedgerRepository(tmp_path / "retrieval.duckdb")
    repo.migrate()
    parsed = ParsedDocument(
        blocks=[
            ParsedBlock(text="Ni-30Cu показал рост твердости после старения", page=1),
            ParsedBlock(text="Электропроводность CuNi30 не измерялась", page=2),
        ],
        tables=[],
        title="doc",
        parser_profile="test_v1",
    )
    repo.ingest_parsed_document(
        source_id="src_ret",
        raw_sha256="0" * 64,
        title="doc",
        document_type="pdf",
        parsed=parsed,
        artifact_locator="doc.pdf",
    )
    return repo


def test_index_and_retrieve_rejoins_duckdb(repository: DuckDBLedgerRepository) -> None:
    service = RetrievalService(repository, InMemoryIndex())
    indexed = service.index_source("src_ret")
    assert indexed >= 2
    span_ids = service.retrieve_span_ids(
        question="твердости старения", allowed_labels=["internal"]
    )
    assert span_ids, "hybrid search must return span candidates"
    known = {span.span_id for span in repository.list_evidence_spans("src_ret")}
    assert set(span_ids) <= known


def test_label_filter_excludes_forbidden(repository: DuckDBLedgerRepository) -> None:
    service = RetrievalService(repository, InMemoryIndex())
    service.index_source("src_ret")
    span_ids = service.retrieve_span_ids(question="твердости", allowed_labels=["public"])
    assert span_ids == []


def test_qdrant_outage_degrades_to_empty(repository: DuckDBLedgerRepository) -> None:
    service = RetrievalService(repository, ExplodingIndex())
    assert service.index_source("src_ret") == 0
    assert service.retrieve_span_ids(question="твердости", allowed_labels=["internal"]) == []


def test_disabled_index_is_noop(repository: DuckDBLedgerRepository) -> None:
    service = RetrievalService(repository, None)
    assert not service.enabled
    assert service.index_source("src_ret") == 0
    assert service.retrieve_span_ids(question="q", allowed_labels=["internal"]) == []
