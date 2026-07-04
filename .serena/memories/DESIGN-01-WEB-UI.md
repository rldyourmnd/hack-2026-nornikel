<!-- Memory Metadata
Last updated: 2026-07-05
Last commit: 3a3b13e feat(web): polish full graph workbench UI
Scope: apps/web/src/pages/landing/ui/LandingPage.tsx; apps/web/src/pages/search/ui/SearchPage.tsx; apps/web/src/pages/graph/ui/GraphPage.tsx; apps/web/src/pages/data/ui/DataPage.tsx; apps/web/src/pages/analytics/ui/AnalyticsPage.tsx; apps/web/src/pages/compare/ui/ComparePage.tsx; apps/web/src/pages/experts/ui/ExpertsPage.tsx; apps/web/src/pages/eval/ui/EvalPage.tsx; apps/web/src/widgets/analysis-workbench/ui/AnalysisWorkbench.tsx; apps/web/src/widgets/graph-view/ui/GraphNeighborhood.tsx; apps/web/src/widgets/artifact-bank/ui/EvidenceList.tsx; apps/web/src/shared/config/theme/theme.css; apps/web/src/shared/config/nav.ts
Area: DESIGN
-->

# DESIGN-01-WEB-UI

## Purpose

Capture durable web UI shell and browser-validation facts for the React/Vite
workbench.

## Source Of Truth

- `apps/web/src/widgets/app-layout/ui/Header.tsx`: header structure, brand,
  product badge, primary navigation, hackathon badge, and mobile menu toggle.
- `apps/web/src/pages/landing/ui/LandingPage.tsx`: public landing page content,
  dynamic stat binding, feature narrative, pipeline section, and CTA.
- `apps/web/src/pages/search/ui/SearchPage.tsx` and
  `apps/web/src/widgets/analysis-workbench/ui/AnalysisWorkbench.tsx`: QA chat,
  jury question, loading state, answer verification, source-colored citations,
  and evidence cards.
- `apps/web/src/pages/graph/ui/GraphPage.tsx` and
  `apps/web/src/widgets/graph-view/ui/GraphNeighborhood.tsx`: optimized graph
  neighborhood explorer and full-graph KPI context.
- `apps/web/src/pages/data/ui/DataPage.tsx`: live corpus, quarantine,
  extraction-density, unit, subject, and source-density surfaces.
- `apps/web/src/pages/analytics/ui/AnalyticsPage.tsx`: live graph analytics,
  entity/relation distributions, numeric-fact topics, gaps, timeline, and QA
  run summary.
- `apps/web/src/pages/compare/ui/ComparePage.tsx`: comparison matrix shell with
  live graph counters and jury-question CTA into Search.
- `apps/web/src/pages/experts/ui/ExpertsPage.tsx`: real entity search for
  experts/organizations and selected-entity neighborhood publication display.
- `apps/web/src/pages/eval/ui/EvalPage.tsx`: quality/health/eval/QA-run
  dashboard.
- `apps/web/src/shared/config/nav.ts`: canonical primary navigation labels,
  routes, and icons shared by header/menu surfaces.
- `apps/web/src/shared/config/theme/theme.css`: design tokens and layout CSS
  for the shell, header, responsive navigation, page hero, landing, and panels.

## Current Behavior

- Desktop header uses a three-column grid: brand group, centered segmented
  navigation, and right-side hackathon badge.
- Primary navigation is single-line on desktop and does not wrap. The secondary
  `R&D Knowledge Graph` badge is hidden below 1360px to preserve header
  alignment while keeping all navigation sections visible.
- Below 980px the primary navigation moves into the existing menu-toggle flow;
  below 720px the hackathon badge is hidden to preserve compact mobile header
  spacing.
- Landing page uses an executive R&D command-center presentation: large
  evidence-first hero, dynamic stats from `fetchStats()`, graph visual callouts,
  KPI surfaces, feature cards, a dark pipeline section, insight cards, and a
  jury-question CTA.
- Landing stat fallbacks are presentation-only for local/offline rendering. When
  `/stats/overview` is available, `sources` and `evidence_spans` are rendered
  from the API.
- Critical landing illustrations (`hero-graph.png`, geography image) use eager
  image loading and sync decoding hints so deploy/browser screenshots do not
  capture empty visual frames while large PNGs are still decoding.
- Search defaults to the jury mine-water literature-review question and shows a
  chat-style answer area, animated retrieval status, verified sentence bubbles,
  source-colored citation chips, evidence cards, and verification metrics.
- Graph renders a limited neighborhood (default mine-water entity) with
  relation/type summaries, selected-node details, and full-graph totals. It must
  not attempt to render all relations in the browser.
- Data, Analytics, Compare, Experts, and Quality pages use live API data from
  `/stats/overview`, entity endpoints, answer runs, and health/eval endpoints
  rather than hardcoded graph totals.
- Experts defaults to a real high-signal author with linked publications and
  lets users search/select real `person`, `expert`, `organization`,
  `laboratory`, and `facility` entities.

## Contracts And Data

- Primary navigation items must stay centralized in `NAV_ITEMS`; avoid duplicating
  labels/routes in `Header.tsx`.
- Header runtime status is only used as the `title` on the hackathon badge; it
  must not expose provider model IDs or secrets.
- Landing UI must keep corpus/search claims evidence-oriented and avoid implying
  uncited answers. Public model/provider names stay out of the landing page.
- Workbench pages may present live graph counts and answer metrics, but must not
  claim all Qdrant/DuckDB facts are rendered client-side. Large graph views stay
  sampled/neighborhoood-based for performance.
- Search evidence coloring is derived from `source_id` and must stay tied to
  actual returned evidence cards.

## Verification

- `npm --prefix apps/web run build`: proves TypeScript and production Vite build.
- `npm --prefix apps/web run typecheck`: proves the frontend TypeScript
  contracts compile without a production bundle.
- Browser check: Playwright CLI screenshots at 2048px, 1440px, 1280px, and
  390px verify the header remains single-line on desktop and mobile menu remains
  usable.
- Landing v2 browser check: Playwright CLI full-page screenshots at 1440px and
  390px verify the redesigned landing remains responsive. Local Vite proxy
  errors for `/health` and `/stats/overview` are expected when the backend is not
  running; the page falls back for stats and continues rendering.
- Full-graph workbench browser check: local Vite with
  `VITE_API_BASE_URL=https://nornikel.nddev.asia/api`, Playwright CLI
  screenshots for `/search`, `/graph`, `/data`, `/analytics`, `/compare`,
  `/experts`, and `/eval`, plus public `/search` and `/eval` smoke screenshots.
  Console error checks were clean in the validated run.
