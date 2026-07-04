from __future__ import annotations

import pytest

from nornikel_kg.domain.evidence import EvidenceSpanFactory
from nornikel_kg.domain.models import AskRequest
from nornikel_kg.domain.security import SourceLabelPolicy
from nornikel_kg.services.qa_service import EvidenceQAService


def test_source_label_policy_filters_disallowed_spans() -> None:
    factory = EvidenceSpanFactory()
    public_span = factory.create(
        source_id="src_public",
        artifact_type="text",
        parser_profile="test",
        artifact_locator="public.md",
        span_type="text",
        visible_text="public",
        stable_locator="block_public",
        security_label="public",
    )
    restricted_span = factory.create(
        source_id="src_restricted",
        artifact_type="text",
        parser_profile="test",
        artifact_locator="restricted.md",
        span_type="text",
        visible_text="restricted",
        stable_locator="block_restricted",
        security_label="restricted",
    )
    policy = SourceLabelPolicy(allowed_labels=frozenset({"public"}))
    assert policy.filter_spans([public_span, restricted_span]) == [public_span]


def test_ask_request_labels_only_narrow_deployment_policy() -> None:
    deployment = SourceLabelPolicy(allowed_labels=frozenset({"public", "internal"}))
    service = EvidenceQAService(source_label_policy=deployment)

    # None -> deployment default unchanged.
    default = service._effective_label_policy(AskRequest(question="q"))
    assert default.allowed_labels == frozenset({"public", "internal"})
    # A narrower request applies.
    narrowed = service._effective_label_policy(
        AskRequest(question="q", allowed_labels=["public"])
    )
    assert narrowed.allowed_labels == frozenset({"public"})
    # A request can never widen beyond the deployment policy (confidential is dropped).
    widened = service._effective_label_policy(
        AskRequest(question="q", allowed_labels=["public", "internal", "confidential"])
    )
    assert widened.allowed_labels == frozenset({"public", "internal"})


def test_coerce_source_label_validates_and_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    from nornikel_kg.domain.security import coerce_source_label

    assert coerce_source_label("public") == "public"
    assert coerce_source_label("  Internal ") == "internal"
    assert coerce_source_label(None) == "internal"  # env default
    monkeypatch.setenv("DEFAULT_SOURCE_LABEL", "confidential")
    assert coerce_source_label(None) == "confidential"
    with pytest.raises(ValueError):
        coerce_source_label("bogus")
