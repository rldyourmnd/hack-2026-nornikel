<!-- Memory Metadata
Last updated: 2026-07-05
Last commit: bc1495a ui(web): refine responsive header navigation
Scope: apps/web/src/widgets/app-layout/ui/Header.tsx; apps/web/src/shared/config/theme/theme.css; apps/web/src/shared/config/nav.ts
Area: DESIGN
-->

# DESIGN-01-WEB-UI

## Purpose

Capture durable web UI shell and browser-validation facts for the React/Vite
workbench.

## Source Of Truth

- `apps/web/src/widgets/app-layout/ui/Header.tsx`: header structure, brand,
  product badge, primary navigation, hackathon badge, and mobile menu toggle.
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

## Contracts And Data

- Primary navigation items must stay centralized in `NAV_ITEMS`; avoid duplicating
  labels/routes in `Header.tsx`.
- Header runtime status is only used as the `title` on the hackathon badge; it
  must not expose provider model IDs or secrets.

## Verification

- `npm --prefix apps/web run build`: proves TypeScript and production Vite build.
- Browser check: Playwright CLI screenshots at 2048px, 1440px, 1280px, and
  390px verify the header remains single-line on desktop and mobile menu remains
  usable.
