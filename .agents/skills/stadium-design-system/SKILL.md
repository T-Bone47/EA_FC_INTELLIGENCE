---
name: stadium-design-system
description: Authoritative Stadium 3.0 product design system skill for EA FC Intelligence. Governs surface hierarchy, obsidian/lime color contrast rules, tabular numeric typography, workflow navigation, SVG vector icons, motion discipline, and strict football evidence honesty across all frontend components.
---

# Stadium 3.0 Design System Skill

## Precedence Rules
1. Product functionality, frozen V3.2.1 suitability parity, and epistemic honesty (`OBSERVED` vs `MODELLED` vs `SYNTHETIC_FIXTURE` vs `UNAVAILABLE`).
2. Accessibility (WCAG 2.2 AA: `>= 4.5:1` body/placeholder text, `>= 11px` functional text floor, `>= 24×24px` target floor, sequential headings, keyboard reachability).
3. Authoritative [`DESIGN.md`](../../DESIGN.md) tokens.
4. Structural clarity over decoration (zero `[side-tab]` left borders, zero `[dark-glow]` chromatic box shadows, zero `[nested-cards]`, zero Unicode emoji UI icons).

## Color & Contrast Tokens
- Canvas `#0B1018` · Surface `#121B27` · Elevated `#1B2735` · Hover `#223142` · Inset `#080D14`
- Lime `#B6F279` (active states/primary CTA only, ink `#080D14` = `14.81:1`) · Intelligence Cyan `#67C8F2` · Warning `#F2BB65` · Negative `#F07575`
- Text `#EDF2F7` (primary) · `#94A3B8` (secondary, `5.90:1+`) · `#7D91A8` (muted floor, `4.65:1+` on `#121B27` — never use sub-`4.5:1` grays).

## Typography & Layout Guardrails
- Base body text `>= 14px`; prose measure capped cleanly at `65ch–72ch`.
- Tabular monospace numerals (`font-variant-numeric: tabular-nums`) on all ratings, delta columns, timestamps, interception margins, and utility scores.
- Pitch & spatial components render crisp SVG/Canvas geometry on `#0A1D16` grass canvas without radial neon spotlight haloes.

## Motion & React Engineering Guardrails
- Animate only `transform` and `opacity` with explicit durations (`140ms–220ms cubic-bezier(0.16, 1, 0.3, 1)`), never `transition: all`.
- Honor `@media (prefers-reduced-motion: reduce)` with crisp state changes (`duration: 0.01ms` ONLY for decorative transitions while preserving state visibility).
- Split heavy feature routes via `React.lazy` + `Suspense` so initial navigation stays light and fast.
