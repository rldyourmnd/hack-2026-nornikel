from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from nornikel_kg.domain.models import AskRequest, AskResponse
from nornikel_kg.services.runtime import get_ledger_repository, get_qa_service

router = APIRouter(prefix="/qa", tags=["qa"])


@router.post("/ask")
def ask(request: AskRequest) -> AskResponse:
    return get_qa_service().ask(request)


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, object]:
    run = get_ledger_repository().get_answer_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run
