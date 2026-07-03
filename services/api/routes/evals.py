from __future__ import annotations

from fastapi import APIRouter

from nornikel_kg.domain.models import AskRequest
from nornikel_kg.services.runtime import get_ledger_repository, get_qa_service

router = APIRouter(prefix="/eval", tags=["evaluation"])


@router.get("/summary")
def evaluation_summary() -> dict[str, object]:
    stored = get_ledger_repository().latest_eval_summary()
    if stored is not None:
        return {**stored, "status": "stored_eval_run"}
    # No stored eval run yet: report live verification of the ideal question,
    # never fabricated recall numbers.
    response = get_qa_service().ask(
        AskRequest(question="Что делали по Ni-30Cu при старении 700 C 8 ч?")
    )
    return {
        "metrics": {
            "citation_coverage": response.verification.citation_coverage,
            "unsupported_claim_count": response.verification.unsupported_claim_count,
            "source_label_leak_count": response.verification.source_label_leak_count,
            "prompt_injection_success_count": response.verification.prompt_injection_success_count,
        },
        "status": "live_baseline_no_stored_run",
    }
