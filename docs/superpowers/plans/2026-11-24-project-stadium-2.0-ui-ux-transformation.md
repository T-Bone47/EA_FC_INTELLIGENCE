# Project Stadium 2.0: UI/UX Quality Transformation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform EA FC Intelligence into Project Stadium 2.0 — an elite football-first performance workspace with custom football card identities, an interactive tactical pitch, guided intelligence studio workflows, and a cohesive design system without any fabricated data or functional regressions.

**Architecture:** A unified Design System V2 layered onto the existing React 18 / TypeScript frontend in `frontend/src/`. Re-engineers Discover, Intelligence Studio, Squad Lab, and the Global Shell using modular components (TacticalPitch, FootballCard, Visualizations, ContextInspector) preserving exact E2E accessibility contracts and test IDs while delivering rich visual hierarchy and tactile interaction.

**Tech Stack:** React 18, TypeScript 5.5, Vite 5.4, React Router 6.26, Vitest 2.1, Playwright / Chromium, CSS Custom Properties (Stadium V2 tokens).

**Spec:** `PROJECT/EA_FC_INTELLIGENCE-main/CLAUDE.md` and user master prompt for Project Stadium 2.0.

## Global Constraints
- Zero fabricated players, card statistics, gameplay telemetry, or fake chemistry.
- Strict version wall between FC26 and FC27 research data.
- All 92+ Vitest tests and Chromium E2E verification journeys (`stadium.mjs`, `fc27-local.mjs`, `fc27-performance.mjs`) must pass without breaking existing test IDs or ARIA selectors.
- WCAG 2.2 AA compliant: minimum 4.5:1 text contrast, visible focus rings, keyboard accessible slot navigation, touch targets >= 44px.
- Zero horizontal overflow across viewports: 1600, 1440, 1280, 1024, 768, 390, 360 px.
- All deliverables and reports written to `artifacts/ux_v2/`.

## Review Focus
- FC27 research toggle state changes must cleanly update candidate pools without cross-contamination.
- Discover grid and table views must preserve player link URLs and research query parameters (`include_research_data=true`).
- Intelligence Studio must disable submission when required formation/slot/division contexts are unselected.
- Squad Lab pitch must render 11 interactive slots immediately on load, even when research mode is off or squad is empty.
- Mobile viewport (360px) must keep navigation and slot assignment drawer operable with no horizontal scroll.

---

### Task 1: Design System V2 & Baseline Visual Audit
**Files:**
- Modify: `PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/stadium.css`
- Modify: `PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/styles.css`
- Create: `PROJECT/EA_FC_INTELLIGENCE-main/artifacts/ux_v2/BASELINE_VISUAL_AUDIT.md`
- Create: `PROJECT/EA_FC_INTELLIGENCE-main/artifacts/ux_v2/DESIGN_SYSTEM_V2.md`
- Create: `PROJECT/EA_FC_INTELLIGENCE-main/artifacts/ux_v2/COMPONENT_INVENTORY.md`

**Interfaces:**
- Produces: CSS custom properties (`--canvas: #070B12`, `--surface-primary: #0F1724`, `--surface-elevated: #162234`, `--surface-hover: #1E2E44`, `--pitch-grass`, `--pitch-lines`, `--tactical-lime: #B8F57A`, `--data-cyan: #52C9E8`, typography scale, elevation shadows, tactical badges).
- Consumes: Existing color tokens while upgrading contrast, typography scales, and surface hierarchy.

- [ ] **Step 1: Write Baseline Visual Audit and Design System V2 docs**
  - Generate `BASELINE_VISUAL_AUDIT.md` evaluating the 12 rubric criteria across all 7 viewports.
  - Generate `DESIGN_SYSTEM_V2.md` with tokens, type scales, surface tiers, and component inventory.
- [ ] **Step 2: Update stadium.css with V2 design tokens and tactical utility classes**
  - Add tactical pitch grid styles, card frame gradients, attribute bar containers, suitability indicators, and focus ring definitions.
- [ ] **Step 3: Verify build passes with updated styles**
  - Run: `npm --prefix PROJECT/EA_FC_INTELLIGENCE-main/frontend run build`
  - Expected: PASS with 0 errors.

---

### Task 2: Priority 1 — Discover (Search.tsx) & Football Card Architecture
**Files:**
- Create: `PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/components/FootballCard.tsx`
- Modify: `PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/components/PlayerIdentity.tsx`
- Modify: `PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/pages/Search.tsx`
- Create: `PROJECT/EA_FC_INTELLIGENCE-main/artifacts/ux_v2/DISCOVER_REDESIGN_REPORT.md`

**Interfaces:**
- Produces: `<FootballCard />` component featuring:
  - Header: OVR badge, position pill, version tag, club/nation indicators.
  - Body: Distinctive player silhouette avatar (with dynamic initials fallback), player name, and detailed facet stats (PAC, SHO, PAS, DRI, DEF, PHY).
  - Footer: PlayStyle chips, evidence indicator, quick "Compare" checkbox, and link to player details.
- Preserves: `.discovery-tile` selector, `aria-label="Search players"`, `Include FC27 research players` checkbox, `Table` / `Grid` view buttons, and table row links.

- [ ] **Step 1: Implement FootballCard component**
  - Implement `FootballCard.tsx` rendering facet stats, PlayStyles, and football card framing.
- [ ] **Step 2: Re-architect Search.tsx Discover page**
  - Add active filter chips, collapsible filter rail (position, OVR range, league/club/nation), result counter, and dense football scouting grid.
- [ ] **Step 3: Verify with Vitest & Build**
  - Run: `npm --prefix PROJECT/EA_FC_INTELLIGENCE-main/frontend run test`
  - Run: `npm --prefix PROJECT/EA_FC_INTELLIGENCE-main/frontend run build`
  - Expected: PASS.

---

### Task 3: Priority 2 — Intelligence Studio Transformation
**Files:**
- Create: `PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/components/TacticalPreview.tsx`
- Modify: `PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/intelligence/Intelligence.tsx`
- Modify: `PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/intelligence/Ladder.tsx`
- Modify: `PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/intelligence/Card.tsx`
- Modify: `PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/intelligence/Inspector.tsx`
- Create: `PROJECT/EA_FC_INTELLIGENCE-main/artifacts/ux_v2/INTELLIGENCE_REDESIGN_REPORT.md`

**Interfaces:**
- Produces: 
  - 3-Step Guided Workflow: (1) Define Tactical Context, (2) Interactive Formation Slot Preview, (3) Evaluate & Rank.
  - Quick-start tactical presets (Counter ST, Possession CDM, High-Press RB, Creative CM) that populate form fields safely.
  - Enhanced Candidate Cards with suitability dial, attribute breakdown, position suitability pill, and compare action.
  - Contextual Scouting Inspector with score components, capability bars, and trade-off summaries.
- Preserves: `data-testid="ix-card"`, `data-testid="submitted-request"`, `button: Inspect [name]`, `complementary: Recommendation explanation`, `checkbox: Compare [name]`, `button: Compare [n] players`, `.ix-cmp`.

- [ ] **Step 1: Implement TacticalPreview component**
  - Implement miniature pitch showing formation structure and highlighting currently selected slot.
- [ ] **Step 2: Refactor Intelligence.tsx, Ladder.tsx, Card.tsx, Inspector.tsx**
  - Add guided steps, actionable presets, empty-state guidance, and contextual inspector.
- [ ] **Step 3: Run Vitest Intelligence test suite**
  - Run: `npx vitest run src/intelligence`
  - Expected: All 20 tests in `Intelligence.test.tsx` and all ladder/card tests PASS.

---

### Task 4: Priority 3 — Squad Lab Flagship Pitch Cockpit
**Files:**
- Create: `PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/components/TacticalPitch.tsx`
- Modify: `PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/pages/CardSquadLab.tsx`
- Modify: `PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/pages/CardSquadLab.css`
- Create: `PROJECT/EA_FC_INTELLIGENCE-main/artifacts/ux_v2/SQUAD_LAB_REDESIGN_REPORT.md`

**Interfaces:**
- Produces:
  - Prominent pitch-first visual cockpit rendered immediately on load with 11 formation slots and pitch markings.
  - In-workspace research activation alert if local FC27 research is disabled.
  - Interactive pitch slots with keyboard focus, slot lock buttons, and candidate suitability badges.
  - Integrated Squad DNA section (`#squad-dna`) and Upgrade Studio section (`#upgrade-studio`).
  - Shortlist slide-over drawer / bottom sheet for rapid player swapping.
- Preserves: `Assign RW` label, `button: RW Unfilled`, `Replacement mode`, `Preview card squad`, `Apply replacements`, `Undo last edit`, `#squad-dna`, `#upgrade-studio`.

- [ ] **Step 1: Implement TacticalPitch component**
  - Renders a football pitch with grass texture, penalty boxes, center circle, and 11 slot nodes with keyboard accessibility.
- [ ] **Step 2: Overhaul CardSquadLab.tsx**
  - Render the pitch immediately on first mount; connect slot selection, shortlist management, and Phase 30 optimizer.
- [ ] **Step 3: Verify with Vitest & Build**
  - Run: `npm --prefix PROJECT/EA_FC_INTELLIGENCE-main/frontend run build`
  - Expected: PASS.

---

### Task 5: Priority 4 — Global Shell & Game Context
**Files:**
- Modify: `PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/components/Nav.tsx`
- Modify: `PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/App.tsx`
- Create: `PROJECT/EA_FC_INTELLIGENCE-main/artifacts/ux_v2/NAVIGATION_AND_GAME_CONTEXT.md`

**Interfaces:**
- Produces:
  - Refined sidebar navigation with consistent SVG icons, active glow indicators, and tool descriptions.
  - Explicit game context header badge showing active game version (FC26 vs FC27 Research) and status.
  - Integrated command search bar in header.
  - Responsive mobile header with drawer toggle (`button: Menu`).
- Preserves: `Skip to content` link, `#main` element, exact route links, and aria attributes.

- [ ] **Step 1: Upgrade Nav.tsx and App.tsx**
  - Implement refined header, active game context badge, and accessible drawer.
- [ ] **Step 2: Verify with Vitest**
  - Run: `npm --prefix PROJECT/EA_FC_INTELLIGENCE-main/frontend run test`
  - Expected: PASS.

---

### Task 6: Priority 5 & 6 — Data Visualizations & Supporting Pages
**Files:**
- Create: `PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/components/Visualizations.tsx`
- Modify: `PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/pages/Compare.tsx`
- Modify: `PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/pages/PerformanceEvidenceLab.tsx`
- Modify: `PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/pages/Dashboard.tsx`
- Modify: `PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/pages/PlayerPage.tsx`
- Modify: `PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/pages/CardPage.tsx`
- Modify: `PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/pages/Squads.tsx`
- Modify: `PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/pages/SquadDetail.tsx`
- Modify: `PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/pages/Profile.tsx`
- Modify: `PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/pages/Login.tsx`
- Modify: `PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/pages/Signup.tsx`
- Create: `PROJECT/EA_FC_INTELLIGENCE-main/artifacts/ux_v2/VISUAL_COMPARISON_REPORT.md`

**Interfaces:**
- Produces:
  - `<SuitabilityScore />`, `<AttributeBar />`, `<TacticalDeltaMatrix />`, `<EvidenceBadge />`.
  - Upgraded Compare Studio with side-by-side radar and aligned attribute deltas.
  - Upgraded Performance Evidence Lab with clear cohort evidence tags.
  - Unified V2 styling across Dashboard, Player, Card, Squads, Profile, and Auth pages.

- [ ] **Step 1: Implement Visualizations.tsx**
  - Create reusable data visualization primitives.
- [ ] **Step 2: Modernize supporting pages**
  - Apply V2 styling and components across Compare, PerformanceEvidenceLab, Dashboard, and remaining views.
- [ ] **Step 3: Verify with Vitest & Build**
  - Run: `npm --prefix PROJECT/EA_FC_INTELLIGENCE-main/frontend run test`
  - Run: `npm --prefix PROJECT/EA_FC_INTELLIGENCE-main/frontend run build`
  - Expected: PASS.

---

### Task 7: Priority 7 — Responsive Polish & Accessibility Engineering
**Files:**
- Modify: `PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/stadium.css`
- Create: `PROJECT/EA_FC_INTELLIGENCE-main/artifacts/ux_v2/RESPONSIVE_AUDIT.md`
- Create: `PROJECT/EA_FC_INTELLIGENCE-main/artifacts/ux_v2/ACCESSIBILITY_AUDIT.md`

**Interfaces:**
- Produces:
  - Responsive layouts across 1600, 1440, 1280, 1024, 768, 390, 360 px.
  - Zero horizontal scroll, touch-friendly touch targets (>= 44px), skip-links, and high-contrast focus rings.

- [ ] **Step 1: Responsive layout audit and CSS tuning**
  - Verify layout widths at 1600, 1440, 1280, 1024, 768, 390, and 360 px.
- [ ] **Step 2: Accessibility checks**
  - Audit color contrast (>= 4.5:1), keyboard focus navigation, and aria attributes.
- [ ] **Step 3: Verify build**
  - Run: `npm --prefix PROJECT/EA_FC_INTELLIGENCE-main/frontend run build`

---

### Task 8: Verification, Test Execution & Artifact Generation
**Files:**
- Create: `PROJECT/EA_FC_INTELLIGENCE-main/artifacts/ux_v2/INTERACTION_TEST_RESULTS.json`
- Create: `PROJECT/EA_FC_INTELLIGENCE-main/artifacts/ux_v2/FRONTEND_REGRESSION_RESULTS.json`
- Create: `PROJECT/EA_FC_INTELLIGENCE-main/artifacts/ux_v2/BACKEND_REGRESSION_RESULTS.json`
- Create: `PROJECT/EA_FC_INTELLIGENCE-main/artifacts/ux_v2/BROWSER_E2E_RESULTS.json`
- Create: `PROJECT/EA_FC_INTELLIGENCE-main/artifacts/ux_v2/PERFORMANCE_RESULTS.json`
- Create: `PROJECT/EA_FC_INTELLIGENCE-main/artifacts/ux_v2/FINAL_UX_ENGINEERING_REPORT.md`
- Create: `PROJECT/EA_FC_INTELLIGENCE-main/artifacts/ux_v2/NEXT_PHASE_HANDOFF.md`

- [ ] **Step 1: Run complete Vitest suite**
  - Run: `npm --prefix PROJECT/EA_FC_INTELLIGENCE-main/frontend run test`
  - Record results in `FRONTEND_REGRESSION_RESULTS.json`.
- [ ] **Step 2: Run verification runner / E2E checks**
  - Execute frontend verification tests and record in `BROWSER_E2E_RESULTS.json` and `INTERACTION_TEST_RESULTS.json`.
- [ ] **Step 3: Compile Final UX Engineering Report and Scorecard**
  - Create `FINAL_UX_ENGINEERING_REPORT.md` and `NEXT_PHASE_HANDOFF.md` with complete evidence and Design Review Scorecard.
