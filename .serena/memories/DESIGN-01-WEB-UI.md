<!-- Memory Metadata
Last updated: 2026-07-05
Last commit: d1c6fac ui(web): elevate landing page presentation
Scope: apps/web/src/pages/landing/ui/LandingPage.tsx; apps/web/src/widgets/app-layout/ui/Header.tsx; apps/web/src/shared/config/theme/theme.css; apps/web/src/shared/config/nav.ts
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

## Contracts And Data

- Primary navigation items must stay centralized in `NAV_ITEMS`; avoid duplicating
  labels/routes in `Header.tsx`.
- Header runtime status is only used as the `title` on the hackathon badge; it
  must not expose provider model IDs or secrets.
- Landing UI must keep corpus/search claims evidence-oriented and avoid implying
  uncited answers. Public model/provider names stay out of the landing page.

## Verification

- `npm --prefix apps/web run build`: proves TypeScript and production Vite build.
- Browser check: Playwright CLI screenshots at 2048px, 1440px, 1280px, and
  390px verify the header remains single-line on desktop and mobile menu remains
  usable.
- Landing v2 browser check: Playwright CLI full-page screenshots at 1440px and
  390px verify the redesigned landing remains responsive. Local Vite proxy
  errors for `/health` and `/stats/overview` are expected when the backend is not
  running; the page falls back for stats and continues rendering.
