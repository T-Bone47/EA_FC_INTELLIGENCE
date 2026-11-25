---
name: EA FC Intelligence — Stadium 3.0
description: Authentic dark-navy & pitch-lime sports analytics design system for football card intelligence, squad building, tactical telemetry, and decision coaching.
colors:
  bg-canvas: "#0B1018"
  surface: "#121B27"
  surface-elevated: "#1B2735"
  surface-hover: "#223142"
  surface-inset: "#080D14"
  accent-primary: "#B6F279"
  accent-intelligence: "#67C8F2"
  text-primary: "#EDF2F7"
  text-secondary: "#94A3B8"
  text-muted-accessible: "#7D91A8"
  warning: "#F2BB65"
  negative: "#F07575"
  positive: "#5CE592"
  border-subtle: "#202E40"
  border-strong: "#2F4259"
typography:
  display:
    fontFamily: "\"Barlow Semi Condensed\", \"IBM Plex Sans\", -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "1.875rem"
    fontWeight: 700
    lineHeight: 1.18
    letterSpacing: "-0.02em"
  body:
    fontFamily: "\"IBM Plex Sans\", -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "0em"
  mono:
    fontFamily: "\"IBM Plex Mono\", ui-monospace, SFMono-Regular, Consolas, monospace"
    fontSize: "0.875rem"
    fontWeight: 500
    lineHeight: 1.4
rounded:
  sm: "6px"
  md: "10px"
  lg: "14px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.accent-primary}"
    textColor: "{colors.surface-inset}"
    rounded: "{rounded.md}"
    padding: "10px 18px"
    height: "40px"
  button-ghost:
    backgroundColor: "{colors.surface-elevated}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.md}"
    padding: "10px 16px"
    height: "40px"
---

# Stadium 3.0 Design System Specification

## 1. Overview
Stadium 3.0 pairs calm analytical restraint (inspired by Linear, Vercel, StatsBomb, and Football Manager build depth) with sharp football identity. Desktop (`1280px–1920px`) acts as an uninterrupted tactical workstation; tablet (`768px–1024px`) and mobile (`390px`) adapt seamlessly without horizontal overflow or undersized tap targets (`>= 44×44px` preferred, `>= 24×24px` WCAG 2.2 AA minimum).

## 2. Colors
- **Surface Ladder:** `#0B1018` (`--canvas`) -> `#121B27` (`--surface-primary`) -> `#1B2735` (`--surface-elevated`) -> `#223142` (`--surface-hover`). Clear hairline borders (`1px solid #202E40`) create depth without nested shadows or dark-mode glow halos.
- **Accents:** `#B6F279` (`--accent-lime`) is reserved strictly for active navigation markers, primary CTAs, selected state indicators, and best-alternative counterfactuals. `#67C8F2` (`--accent-cyan`) denotes analytical/intelligence metrics. Semantic signals `#F2BB65` (`--warn`) and `#F07575` (`--negative`) pair with readable labels/icons so meaning never depends on hue alone.
- **Contrast Discipline:** All body text, placeholders, labels, and badges achieve `>= 4.5:1` contrast (verified: `#EDF2F7` `15.39:1`, `#94A3B8` `6.76:1`, `#7D91A8` `>= 4.65:1` on `#121B27`). Functional UI text uses an `11px` absolute floor (`>= 12px` preferred for labels/cells, `14px` base body copy).

## 3. Typography
- Display headings use `"Barlow Semi Condensed"` (`-0.02em` tracking ceiling, balanced wrapping), body prose uses `"IBM Plex Sans"` (`max-width: 72ch` on prose blocks), and all OVR ratings, attribute facets, timestamps, interception margins, and Q-utilities enforce `IBM Plex Mono` with `font-variant-numeric: tabular-nums`.

## 4. Layout
- Persistent collapsible desktop sidebar (`236px` expanded / `68px` rail) organized into 5 clear gamer workflow groups (`Overview`, `Build`, `Play & Improve`, `Research`, `Settings`), paired with a sticky breadcrumb + edition switcher + command search topbar (`Ctrl+K` / `/`).

## 5. Elevation & Depth
- Declare elevation ONCE per container (`1px solid` hairline border OR neutral `0 8px 24px rgba(0,0,0,0.35)` overlay shadow). Zero chromatic glow box-shadows (`box-shadow: 0 0 20px rgba(lime)` prohibited), zero thick single-side `border-left` stripes (`[side-tab]` banned), zero radial spotlight gradients behind pitch diagrams, and flat spacing/dividers in place of card-inside-card nesting.

## 6. Shapes
- Cards use `12px–14px` radii, buttons & inputs use `8px–10px` radii with `40px–44px` comfortable height, and badges use `6px` crisp analytical chips rather than oversized pill clutter.

## 7. Components
- Shared primitives (`StadiumIcon`, `PageHeader`, `MetricTile`, `EvidenceBadge`, `SectionDivider`, `FootballCard`, `StadiumPitch`, `StadiumControls`) provide keyboard focus rings (`2px solid #67C8F2`, `outline-offset: 2px`), consistent empty/loading/error handling, and unified icons (`1.75px` clean vector strokes—never Unicode glyphs or emojis).

## 8. Do's and Don'ts
- **Do:** Keep Squad Lab pitch centered and uncluttered with a contextual right-hand inspector; show video & synchronized radar first in Gameplay Studio; keep Blind Review outcome hidden by default in Decision Replay Lab.
- **Don't:** Fabricate market prices/faces/EPV probabilities, expose internal development phase numbers (`Phase 39`/`Phase 41`) in user headings, nest bordered cards inside bordered cards, or animate continuously at rest (`prefers-reduced-motion` honored cleanly).
