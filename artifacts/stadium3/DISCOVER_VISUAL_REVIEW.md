# STADIUM 3.0 — DISCOVER SCOUTING & UT CARDS VISUAL REVIEW
**EA FC Intelligence — Football Intelligence Operating System**
*Revision: 3.0.0 | Modules: Search.tsx, Cards.tsx, FootballCard.tsx*

---

## 1. Executive Summary

The Player Discovery and Ultimate Team Card Catalog experiences have been upgraded into high-performance scouting interfaces. Previously, candidate search results were plain boxes lacking physical football card attributes.

In Stadium 3.0, discovery combines tactical filter chips, high-density table views, and authentic Ultimate Team physical card tiles with dynamic tier styling, holographic shimmer animations, and direct links to the Intelligence Studio.

---

## 2. Visual Architecture & Key Components

### 2.1 The Tactical Scouting Rail (`Search.tsx`)
- **Active Filter Chips Tray:** Removable pill chips for every active facet (Query, Position, OVR range, Nation, League, PlayStyle).
- **Position Chips:** Horizontal touch-friendly segmented chips for fast position filtering.
- **OVR Numerical Range:** Dual input stepper with min/max bounds.
- **Multi-Facet Dropdowns:** Nation, League, and PlayStyle filters populated directly from backend reference data.
- **Sorting Engine:** Single-click column sorting (Overall, Name, Pace, Shooting, Passing, Dribbling, Defending, Physicality) with Ascending/Descending toggle.

### 2.2 Dual View Modes (Grid & Table)
- **Grid View (Default):** Renders responsive CSS grid of `FootballCard` tiles (`.discovery-tiles`).
- **Table View:** High-density tabular layout (`table.data`) with sortable column headers, compact attribute facades (`<Facades />`), and inline comparison checkboxes.
- **E2E Compatibility:** Preserves `.discovery-tile` container classes and exact link targets required by automated browser suites.

### 2.3 Ultimate Team Card Component (`FootballCard.tsx`)
- **Card Tiers:**
  - *Special / Research (`.card-tier-special`):* Holographic prismatic animation with `@keyframes holo-shimmer` and iridescent violet-cyan borders.
  - *Gold Tier (`.card-tier-gold`):* Rich gold metallic gradient for 85+ OVR players.
  - *Silver Tier (`.card-tier-silver`):* Clean brushed aluminum sheen for <75 OVR players.
- **Hex Attribute Grid:** 6-box attribute layout for Pace (PAC), Shooting (SHO), Passing (PAS), Dribbling (DRI), Defending (DEF), and Physicality (PHY).
- **Context Actions:**
  - Direct 1-click jump to Intelligence Studio (`Tactics ⚡`).
  - Head-to-head comparison selection checkbox.
  - Manager bookmarking (`★ Saved`).

---

## 3. Version Wall & Data Honesty Compliance

- **FC26 vs FC27 Isolation:** When switching to FC27, research players require explicit manager opt-in (`Include FC27 research players`).
- **Zero Hallucinated Values:** Missing stats or prices are never guessed or filled with zeros; they render explicitly as `UNKNOWN_LABEL` (`—`).
- **Full Responsive Behavior:** The grid smoothly scales from 1 column on mobile (360px), to 2–3 columns on tablet (768px–1024px), to 4–5 columns on desktop (1440px+).
