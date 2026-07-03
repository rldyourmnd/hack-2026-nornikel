from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from threading import Lock

from nornikel_kg.adapters.duckdb.repositories import DuckDBLedgerRepository
from nornikel_kg.adapters.llm import LLMSettings, build_llm
from nornikel_kg.services.answer_composer import LLMAnswerComposer
from nornikel_kg.services.extraction_service import ExtractionService
from nornikel_kg.services.graph_service import GraphService
from nornikel_kg.services.ingestion_service import IngestionService
from nornikel_kg.services.qa_service import DemoQAService
from nornikel_kg.services.retrieval_service import RetrievalService

_repository_build_lock = Lock()


def project_root() -> Path:
    configured_root = os.getenv("PROJECT_ROOT")
    if configured_root:
        return Path(configured_root).resolve()

    current_directory = Path.cwd()
    if (current_directory / "sample_docs").exists():
        return current_directory

    return Path(__file__).resolve().parents[3]


def resolve_project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else project_root() / path


@lru_cache
def get_ledger_repository() -> DuckDBLedgerRepository:
    with _repository_build_lock:
        db_path = resolve_project_path(os.getenv("DUCKDB_PATH", "data/catalog.duckdb"))
        sample_dir = resolve_project_path(
            os.getenv("SYNTHETIC_SAMPLE_DIR", "sample_docs/synthetic")
        )
        repository = DuckDBLedgerRepository(db_path)
        # Demo fixture seeding is env-gated: on a real-corpus stand the
        # synthetic Ni-Cu rows would otherwise mix into every answer packet.
        if os.getenv("SEED_SYNTHETIC_FIXTURE", "true").lower() in {"1", "true", "yes"}:
            repository.seed_synthetic_fixture(sample_dir)
        return repository


@lru_cache
def get_qa_service() -> DemoQAService:
    settings = LLMSettings()
    composer = LLMAnswerComposer(build_llm(settings)) if settings.llm_enabled else None
    repository = get_ledger_repository()
    return DemoQAService(
        ledger_repository=repository,
        retrieval_service=get_retrieval_service(),
        answer_composer=composer,
        run_recorder=repository,
    )


@lru_cache
def get_retrieval_service() -> RetrievalService:
    backend_kind = os.getenv("EMBEDDING_BACKEND", "off").lower()
    index = None
    if backend_kind in {"local", "fake", "yandex"}:
        from nornikel_kg.adapters.qdrant_index import QdrantVectorIndex

        if backend_kind == "local":
            from nornikel_kg.adapters.embeddings import LocalEmbeddingBackend

            embeddings: object = LocalEmbeddingBackend()
        elif backend_kind == "yandex":
            from nornikel_kg.adapters.embeddings import YandexEmbeddingBackend

            embeddings = YandexEmbeddingBackend()
        else:
            from nornikel_kg.adapters.embeddings import FakeEmbeddingBackend

            embeddings = FakeEmbeddingBackend()
        qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")
        index = QdrantVectorIndex(qdrant_url, embeddings)  # type: ignore[arg-type]
    reranker = None
    if index is not None and os.getenv("RERANKER_ENABLED", "false").lower() in {
        "1",
        "true",
        "yes",
    }:
        from nornikel_kg.adapters.reranker import CrossEncoderReranker

        reranker = CrossEncoderReranker()
    return RetrievalService(get_ledger_repository(), index, reranker=reranker)


@lru_cache
def get_ingestion_service() -> IngestionService:
    artifact_root = resolve_project_path(os.getenv("ARTIFACT_ROOT", "data/artifacts"))
    synchronous = os.getenv("SYNC_ENRICHMENT", "false").lower() in {"1", "true", "yes"}
    return IngestionService(
        get_ledger_repository(),
        artifact_root=artifact_root,
        extraction_service=get_extraction_service(),
        retrieval_service=get_retrieval_service(),
        synchronous_enrichment=synchronous,
    )


@lru_cache
def get_extraction_service() -> ExtractionService:
    settings = LLMSettings()
    # LLM_EXTRACTION_ENABLED gates ingest-time LLM calls separately from the
    # QA answer composer: real-corpus batches showed extraction payloads being
    # rejected consistently, so dictionary rules carry ingest by default.
    extraction_llm_on = os.getenv("LLM_EXTRACTION_ENABLED", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    llm = build_llm(settings) if settings.llm_enabled and extraction_llm_on else None
    use_gliner = os.getenv("GLINER_ENABLED", "true").lower() in {"1", "true", "yes"}
    semantic_matcher = None
    retrieval = get_retrieval_service()
    if retrieval.index is not None and os.getenv(
        "ENTITY_SEMANTIC_FALLBACK", "true"
    ).lower() in {"1", "true", "yes"}:
        from nornikel_kg.services.entity_resolution import QdrantSemanticMatcher

        semantic_matcher = QdrantSemanticMatcher(retrieval.index)
    return ExtractionService(
        get_ledger_repository(),
        llm=llm,
        use_gliner=use_gliner,
        semantic_matcher=semantic_matcher,
    )


@lru_cache
def get_graph_service() -> GraphService:
    return GraphService(get_ledger_repository())
