<!-- Memory Metadata
Last updated: 2026-07-04
Last commit: 97407f4
Scope: src/nornikel_kg/domain/security.py; src/nornikel_kg/domain/answer_claims.py; src/nornikel_kg/services/qa_service.py; src/nornikel_kg/services/answer_composer.py; src/nornikel_kg/services/extraction_service.py; src/nornikel_kg/adapters/llm/; src/nornikel_kg/adapters/trafilatura/fetcher.py; services/api/routes/sources.py; scripts/run_realcase_eval.py; tests/unit/
Area: SEC
-->

# SEC-01-ACL-AND-PROMPT-INJECTION

## Purpose

Capture source-label filtering, prompt-injection resistance, URL import hardening, and external-provider safety boundaries.

## Source Of Truth

- `src/nornikel_kg/domain/security.py`: `SourceLabelPolicy`, deployment floor, label coercion.
- `src/nornikel_kg/domain/answer_claims.py`: claim verification, citation coverage, label leaks, numeric mismatch, semantic unsupported count.
- `src/nornikel_kg/services/qa_service.py`: pre-composition evidence filtering and final verification.
- `src/nornikel_kg/services/answer_composer.py`: answer prompt and sentence acceptance gates.
- `src/nornikel_kg/services/extraction_service.py`: extraction prompt treats source text as untrusted data.
- `src/nornikel_kg/adapters/llm/gateway.py`: sole LiteLLM import, failover, retries, terminal `LLMError` normalization.
- `src/nornikel_kg/adapters/trafilatura/fetcher.py`: SSRF-safe URL fetch with redirect-hop revalidation and byte cap.
- `services/api/routes/sources.py`: upload/archive validation and size checks.

## Current Behavior

- A request can only narrow labels through `AskRequest.allowed_labels`; it cannot widen the deployment `JURY_ALLOWED_LABELS` floor.
- Retrieval hits are rejoined to DuckDB and label-filtered before they enter answer context.
- Answer and extraction prompts explicitly treat evidence/source text as data, not instructions.
- Answer sentences are dropped/flagged when citations are missing, numbers are unsupported, or narrow contradiction checks fail.
- LiteLLM provider exhaustion is wrapped as `LLMError`; extraction and answer paths degrade to rule-only/deterministic fallbacks instead of raw 500s when callers catch it.
- URL import rejects non-http(s), private, loopback, link-local, reserved, and metadata targets; redirects are followed manually and revalidated per hop.
- Legacy prompt-injection fixtures and `scripts/run_eval.py` are no longer active; current security coverage is unit tests plus `scripts/run_realcase_eval.py`.

## Invariants

- Never retrieve unauthorized spans into LLM context and filter after generation.
- Do not remove the "source/evidence text is data, not instructions" clauses from prompts.
- Do not log or commit provider credentials.
- New retrieval or answer paths require source-label and claim-verifier coverage.

## Verification

- `uv run pytest tests/unit/test_source_label_policy.py`
- `uv run pytest tests/unit/test_claim_verifier.py tests/unit/test_answer_honesty.py`
- `uv run pytest tests/unit/test_ssrf_guard.py tests/unit/test_llm_gateway.py`
- `API_BASE=<stand>/api uv run python scripts/run_realcase_eval.py`
