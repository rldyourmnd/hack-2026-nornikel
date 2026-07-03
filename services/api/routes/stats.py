from __future__ import annotations

from fastapi import APIRouter, Query

from nornikel_kg.services.runtime import get_ledger_repository

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/overview")
def overview() -> dict[str, object]:
    """Corpus, graph and security-label counters for the UI dashboards."""
    return get_ledger_repository().corpus_stats()


@router.get("/answer-runs")
def answer_runs(limit: int = Query(default=20, ge=1, le=100)) -> dict[str, object]:
    """Recent answer runs: the audit trail (question, mode, verification)."""
    return {"runs": get_ledger_repository().list_answer_runs(limit)}
