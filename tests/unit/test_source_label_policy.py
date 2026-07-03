from __future__ import annotations

from nornikel_kg.domain.evidence import EvidenceSpanFactory
from nornikel_kg.domain.security import SourceLabelPolicy


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
