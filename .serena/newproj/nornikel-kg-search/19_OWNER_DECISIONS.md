# Owner Decisions For Implementation

Date: 2026-06-28

This file records owner decisions that close the pre-implementation questions and override earlier planning assumptions where they conflict.

> **Amendment (2026-07-02).** The track organizers clarified hackathon rules after this
> file was written: proprietary LLM APIs (OpenAI, Anthropic) are forbidden; only
> open-weight models usable from Russia are allowed. The "LLM And Embeddings" section
> below is superseded by `.serena/plans/01_MVP_SCOPE_AND_DECISIONS.md` (locked owner
> decisions, 2026-07-02): provider `dataeyes.ai` via the LiteLLM SDK, open-weight
> catalog models only, local `deepvk/USER-bge-m3` embeddings, optional Ollama fallback,
> self-hosted Langfuse observability. On any conflict, `.serena/plans/01` wins.

## Git And Delivery

- Implementation is approved.
- Merge completed planning work into `main` before implementation.
- Continue work in logical branches.
- Use atomic Conventional Commits.
- Add GitHub Actions CI/CD checks in the private GitHub repository.

## Runtime And Stack

- Package manager: `uv`.
- Backend runtime: Python 3.12.
- Frontend runtime: Node 24 LTS.
- UI: React 19, Vite 8, TypeScript.
- API: FastAPI.
- Deployment: Docker Compose on `fa.nddev.asia` through `ssh server-nddev`.
- Local machine is for validation, type checks, linting, LSP diagnostics, and development checks; the product runs on the server.

## LLM And Embeddings

- External APIs are allowed.
- LLM access goes through LiteLLM/OpenAI-compatible configuration.
- Target answer/extraction model is an owner-provided LiteLLM alias: `openai/gpt-5.5-mini`.
- Keep model names configurable because official OpenAI docs should be rechecked against the deployment account before final deploy.
- Embeddings should also be API-backed through LiteLLM/OpenAI-compatible providers first.
- `.env.example` must contain placeholders only; real secrets live on the server or in GitHub secrets.
- Add a deterministic fallback path only if it is quick and does not weaken the architecture.

## Data And Fixtures

- Support PDF, DOCX, XLSX, CSV, PPTX, images, and scanned PDFs.
- Create synthetic fixture documents for tests and demo.
- Synthetic fixtures should be committed.
- Real internal documents may be committed only when owner-provided/approved for this private repository.
- Corpus language is Russian, English, or mixed.
- OCR-heavy scans are expected; server-side SOTA OCR can be integrated later through `server-nddev` if needed.
- P0 image handling: evidence cards with captions/OCR/page crops; no automatic chart digitization unless a gold scenario requires it.

## Demo Scope

Use a focused, extensible materials scope:

- Material families: Ni-Cu alloys, Cu-Ni corrosion-resistant alloys, Ni-Cr-Mo heat-resistant alloys.
- Process regimes: annealing, aging, cold rolling, solution treatment plus quench, welding/cladding.
- Properties: Vickers hardness, tensile strength, elongation, electrical conductivity, corrosion rate, grain size, porosity/cracking, phase fraction.
- Include synthetic dictionaries for materials, properties, regimes, units, equipment, labs, teams, and topics.
- Include seeded contradictions and gaps so the demo reliably shows the analytical value.
- Main success target: one ideal scenario executed end to end with polished UI, plus regression/evaluation fixtures.

## Security Posture

- P0 has no user authentication, role management, or group authorization.
- Keep source security labels and object-level filtering interfaces so RBAC can be added later.
- Security dashboard is required.
- Runtime logs may include snippets during the hackathon, but secrets must never be logged or committed.

## UX

- UI language is Russian-first.
- First screen is the actual research workbench, not a landing page.
- Required flow: import/status -> artifact bank -> extraction workbench -> ask/analysis -> evidence cards -> graph visualization -> evaluation/security dashboard.
- Graph visualization should be visually strong and useful, not a minimal placeholder.
