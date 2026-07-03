from __future__ import annotations

from fastapi import APIRouter

from nornikel_kg.domain.ledger import EvidenceLedgerPacket
from nornikel_kg.domain.models import AskRequest
from nornikel_kg.services.runtime import get_ledger_repository, get_qa_service

router = APIRouter(prefix="/eval", tags=["evaluation"])


def _baseline_probe_question(packet: EvidenceLedgerPacket) -> str | None:
    """Derive a live-baseline question from the corpus itself.

    The eval summary must never hardcode a demo material: when no eval run is
    stored we probe the first available experiment so the baseline reflects the
    actual corpus (empty corpus -> no probe).
    """
    for experiment in packet.experiments:
        material = experiment.material_name.strip()
        prop = experiment.property_name.strip()
        if material and prop:
            return f"Что известно про {material} — {prop}?"
        if material:
            return f"Что известно про {material}?"
    return None


@router.get("/summary")
def evaluation_summary() -> dict[str, object]:
    stored = get_ledger_repository().latest_eval_summary()
    if stored is not None:
        return {**stored, "status": "stored_eval_run"}
    # No stored eval run yet: report live verification of a corpus-derived probe
    # question (never a hardcoded material, never fabricated recall numbers).
    packet = get_ledger_repository().load_evidence_packet()
    probe = _baseline_probe_question(packet)
    if probe is None:
        return {"metrics": {}, "status": "no_corpus_no_stored_run"}
    response = get_qa_service().ask(AskRequest(question=probe))
    return {
        "metrics": {
            "citation_coverage": response.verification.citation_coverage,
            "unsupported_claim_count": response.verification.unsupported_claim_count,
            "source_label_leak_count": response.verification.source_label_leak_count,
            "prompt_injection_success_count": response.verification.prompt_injection_success_count,
        },
        "status": "live_baseline_no_stored_run",
    }
