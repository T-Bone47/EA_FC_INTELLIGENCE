# Baseline Visual & Usability Audit (Project Stadium 2.0)

**Evaluation Date:** 2026-11-24  
**Evaluator:** Principal Product Designer & UI/UX Engineering Lead  
**Scope:** Full-page evaluation across 7 standard target viewports (1600×900, 1440×900, 1280×800, 1024×768, 768×1024, 390×844, 360×800) for all primary product journeys: Overview, Discover (`/search`), Intelligence Studio (`/intelligence`), Squad Lab (`/cards/squad-lab`), Comparison (`/compare`), and Performance Evidence Lab (`/cards/performance`).

---

## 1. Visual Quality Rubric Evaluation

| Rubric Dimension | Baseline Rating | Key Problem Observed | Impact on Football Intelligence |
|---|:---:|---|---|
| **1. Information Hierarchy** | Needs Work | Hero typography and page titles compete with action controls; primary data points (OVR, Suitability Score, Position) blend into dark background. | Users cannot immediately discern high-fit players from candidates. |
| **2. Layout Composition** | Poor | Massive blank center and right columns on initial load in Intelligence Studio and Squad Lab; Discover cards leave unmanaged vertical voids. | Feels like an empty internal admin tool rather than a finished football workspace. |
| **3. Typography** | Acceptable | Space Grotesk headings occasionally pair with oversized form labels; tabular numbers lack monospaced alignment in attribute tables. | Hard to scan numeric deltas and comparisons quickly. |
| **4. Color and Contrast** | Acceptable | Monolithic navy surfaces (`#111B29`, `#192535`) lack depth cues; subtle borders (`#2A3A4C`) offer insufficient contrast against pitch textures. | Lacks visual prestige and tactical depth. |
| **5. Football Identity** | Needs Work | Generic round monograms (`identity-monogram`) with 2-letter player initials dominate Discover; pitch markings look flat and stylized rather than authentic. | Does not feel like a true sports scouting or FUT decision cockpit. |
| **6. Component Consistency**| Acceptable | Buttons, tabs, and form controls share standard tokens, but cards vary in proportion and action layout across pages. | Disjointed mental model when moving between Discover, Compare, and Squad Lab. |
| **7. Interaction Feedback** | Acceptable | Hover states exist (`#223249`), but tactile micro-interactions (slot focus, candidate elevation, before/after diffs) are absent. | Static feel; lack of responsive football tactile feedback. |
| **8. Data Visualization** | Needs Work | Numerical text displays predominate; missing contextual suitability dials, horizontal attribute bars, or radar comparisons. | Engine mathematical superiority (V3.2) is hidden behind plain text numbers. |
| **9. Responsiveness** | Good | Layout wraps without horizontal scroll down to 360px, but pitch becomes cramped and requires vertical scrolling without compact mode. | Usable on mobile, but lacks purpose-built mobile-first football interactions. |
| **10. Accessibility (A11y)**| Good | Zero automated axe violations in Phase 32; visible skip-link; keyboard slot assignment works. Needs higher focus ring contrast. | Solid baseline, requires enhanced target sizing (>= 44px) and aria descriptions. |
| **11. Empty & Loading States**| Poor | Initial renders show blank panels or "Set the football context..." text with no guidance or starter archetypes. | New users face a cold-start problem with zero guided discovery. |
| **12. User Journey Efficiency**| Acceptable | Searching and filtering work well, but requires multiple disconnected steps to add to comparison or test what-if scenarios. | Friction in discovering and evaluating alternatives. |

---

## 2. Top 3 Problems Identified Per Key Screen

### A. Discover (`/search`)
1. **Generic Initial Monograms:** Large circular avatars with two-letter initials (e.g. "EH", "LY") in huge rectangular cards make players indistinguishable.
2. **Weak Facet Attribute Density:** Essential football attributes (Pace, Shooting, Passing, Dribbling, Defending, Physicality) are hidden or displayed as plain text lines rather than high-impact attribute badges.
3. **Unorganized Filter Rail:** All filter dropdowns stacked vertically without visual categorization, active filter chip tray, or quick one-click position filters.

### B. Intelligence Studio (`/intelligence`)
1. **Empty Right & Center Workspace:** Before clicking "Find players", 75% of the viewport is blank with a single muted instruction sentence.
2. **Missing Tactical Slot Context:** No interactive visual formation slot selector to ground the recommendation (e.g., seeing where the "LCM" sits in a 4-3-3).
3. **Lack of Guided Starters:** Users must manually select Game Version, Division, Formation, Slot, and Tactical Style with zero one-click tactical presets (e.g., "Counter-Attack Striker", "High-Press Fullback").

### C. Squad Lab (`/cards/squad-lab`)
1. **Empty Pitch on Initial Load:** Pitch slots appear blank with generic buttons and no contextual player silhouettes or initial suggestions.
2. **Disconnected Research Banner:** FC27 research availability appears as an external toggle above the pitch rather than an integrated tactical cockpit feature.
3. **Shortlist Friction:** Shortlist management requires scrolling down below the pitch rather than living in an accessible side-rail or drawer.

### D. Comparison (`/compare`)
1. **Text-Heavy Attribute Tables:** Comparison displays raw attribute tables without visual delta bars (e.g. `+4 Pace`, `-2 Defending`) or radar profiles.
2. **Weak Special Item Differentiation:** Exact card special versions look identical to base cards with text IDs alone distinguishing them.
3. **No Direct "Why Higher Item Leads" Visualization:** Engine trade-offs are printed as paragraphs rather than actionable capability bars.

---

## 3. Immediate Stadium 2.0 Action Plan
- **Stage 1:** Deploy Design System V2 with deep carbon canvas (`#070B12`), pitch-line greens, gold rating tiers, and tactile card framing.
- **Stage 2:** Re-engineer Discover with `<FootballCard />` including silhouette avatars, rating badges, 6-facet attribute pills, and active filter chips.
- **Stage 3:** Re-engineer Intelligence Studio with a 3-step decision flow, interactive tactical formation slot preview, and contextual scouting inspector.
- **Stage 4:** Re-engineer Squad Lab with a dominant tactical pitch rendered on mount, slot lock controls, and integrated Squad DNA / Upgrade Studio cockpit.
- **Stage 5-8:** Elevate shell, comparison, evidence lab, responsive layouts, and full verification.
