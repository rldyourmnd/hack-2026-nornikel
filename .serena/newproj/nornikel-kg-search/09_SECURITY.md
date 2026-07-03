# Security

## Threat Model

The system handles research documents, experiment data, staff/lab metadata, and generated analytical summaries. P0 is open-demo access without user auth, but source security labels and provenance still exist so RBAC can be added later. Main risks:

- accidental disclosure of sources that should not be shown in a public/demo view;
- object-level filtering bugs once security labels are enabled;
- leakage through LLM prompts;
- prompt injection from untrusted documents;
- hallucinated or unsupported scientific claims;
- accidental exposure of personal or sensitive lab/team data;
- poisoned extraction due to malicious or malformed source files.

## Source Security Labels

- Every source, chunk, claim, graph node, and relationship should carry a security label.
- P0 does not implement user accounts, groups, or RBAC.
- Query results must still be filterable by source security labels before answer generation and before LLM context construction.
- The API must enforce object-level source-label filtering, not only route-level access.
- Audit every source access and answer run.

## Retrieval Filtering Sequence

1. Resolve active demo policy and allowed source-label set.
2. Query DuckDB for allowed `source_id` and `span_id` values.
3. Apply Qdrant payload filters for source IDs, confidentiality, project, and security label.
4. Rejoin Qdrant candidate unit IDs back to DuckDB.
5. Drop any candidate whose source/span is not allowed by the active policy.
6. Build LLM context only from allowed evidence.
7. During graph expansion, traverse only allowed evidence-backed edges.
8. Verify cited spans are still allowed before returning the answer.

## LLM Controls

- Treat source documents as untrusted input.
- Separate system/developer instructions from retrieved document text.
- Never allow source text to override tool or security policy.
- Use schema validation for extraction outputs.
- Do not write model output directly to the canonical graph.
- Hosted LLMs and embeddings are approved for this project through LiteLLM/OpenAI-compatible providers.
- Do not commit prompts, raw responses, or keys; runtime logs may include snippets during the hackathon by owner decision.
- Never include inaccessible source existence, filenames, snippets, embeddings, or graph paths in user-visible answers unless policy explicitly allows disclosure of restricted-result counts.
- Flag but preserve source spans containing prompt-injection-like text such as "ignore previous instructions", "system prompt", "do not cite", "send this data", "exfiltrate", or hidden OCR instructions.

## Data Handling

- No secrets in repository.
- No raw credentials in logs.
- Synthetic fixtures should be committed. Real internal documents may be committed only when owner-provided/approved for the private repository.
- Runtime source files should be stored in a controlled artifact volume or bucket.
- Parsed text should inherit source security labels.
- Export/demo bundles should support anonymization.

## Review And Governance

- Low-confidence extracted facts go to review queue.
- High-impact facts, such as property improvements or safety-relevant conclusions, require validation before they are treated as canonical.
- Conflicting evidence must not be hidden.
- Generated answers must show source evidence and confidence.

## Security Checks

MVP checks:

- API security-label filtering tests;
- object-level filtering tests;
- retrieval-layer source-label tests for vector payloads and graph traversal;
- prompt-injection regression examples;
- restricted-source-in-context checks;
- unsupported-claim blocking checks;
- source upload validation;
- secret scan before any commit;
- log review for sensitive data leakage.

Production checks:

- SSO integration;
- least-privilege service accounts;
- encrypted storage and transport;
- vulnerability scanning;
- audit export;
- backup encryption.
