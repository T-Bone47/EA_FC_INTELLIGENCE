# STADIUM 3.0 — COMPONENT INVENTORY & PATTERN REGISTRY
**EA FC Intelligence — Football Intelligence Operating System**
*Revision: 3.0.0 | Status: Production Active*

---

## 1. Component Architecture Overview

The Stadium 3.0 component library is organized into three distinct tiers:

```
src/
├── components/          # Reusable domain & interface primitives
│   ├── common.tsx       # Buttons, badges, stat boxes, empty states, drawers
│   ├── FootballCard.tsx # FIFA/UT style tactical card component
│   ├── StadiumPitch.tsx # 2D/3D tactical football pitch board
│   ├── PlayerIdentity.tsx # Avatar, club crest, nation flag, player name
│   ├── Visualizations.tsx # Radar charts, suitability gauges, evidence pills
│   ├── Nav.tsx          # Stadium navigation sidebar and top header bar
│   ├── Availability.tsx # Research dataset status banner
│   └── DataQuality.tsx  # Data confidence & provenance badges
├── intelligence/        # Decision-engine intelligence studio
│   └── Intelligence.tsx # Tactical recommendation workspace
└── pages/               # Full feature modules & workspaces
    ├── CardSquadLab.tsx # Flagship 11-player squad builder & upgrade studio
    ├── Dashboard.tsx    # Stadium 3.0 Bento command center
    ├── Search.tsx       # Player search & multi-attribute discovery
    ├── Cards.tsx        # UT Card version database & catalog
    ├── ResearchCards.tsx# FC27 experimental research lab
    ├── Compare.tsx      # Head-to-head tactical comparison
    ├── PerformanceEvidenceLab.tsx # Audit, provenance, and evaluation metrics
    ├── SquadDetail.tsx  # Individual saved squad inspection
    ├── Profile.tsx      # Football preferences & manager persona
    └── Login.tsx / Signup.tsx # Football manager authentication portal
```

---

## 2. Core Primitives & System Components

### 2.1 Buttons & Trigger Controls (`common.tsx` & `stadium.css`)
- **`Button`**: Stadium 3.0 action button supporting variants `primary`, `secondary`, `outline`, `ghost`, `danger`, and sizes `sm`, `md`, `lg`.
- **`IconButton`**: Compact square trigger for slot clearing, bookmarking, and modal dismissals.
- **`SegmentedControl`**: Dual or multi-option tactical pill switch (e.g. Card View vs Table View, 4-3-3 vs 4-2-3-1).

### 2.2 Metric & Data Displays
- **`StatCard` / `MetricCard`**: High-density numerical readout with trend indicator, label, and secondary delta.
- **`EvidenceBadge`**: Deterministic verification badge (`VERIFIED`, `RESEARCH`, `NO_DATA`) maintaining data honesty.
- **`SuitabilityScore`**: Color-coded tactical fit meter (0–100) with contextual commentary (e.g. "Elite Inverted Winger").
- **`HexRadarChart`**: Responsive SVG 6-axis attribute polygon comparing Player vs Role Target.

### 2.3 Football Card Artifacts (`FootballCard.tsx`)
- **Props:** `player`, `card` (optional), `variant` (`full`, `compact`, `pitch-slot`, `comparison`), `showAttributes`, `isInspected`.
- **Tiers:** Gold (85+), Special (Research/In-Form with holo shimmer), Silver, Bronze.
- **Slots:** Rating, Position badge, Nation/Club badges, Face avatar, Chemistry link indicator, 6 key UT attributes.

### 2.4 Stadium Tactical Pitch (`StadiumPitch.tsx` & `CardSquadLab.tsx`)
- **Pitch Lines:** SVG and CSS absolute vector markings for penalty areas, 6-yard boxes, center circle, halfway line, and 4 corner arcs.
- **Dynamic Slot System:** 11 coordinates dynamically mapped per formation (`4-3-3`, `4-2-3-1`, `4-4-2`, `3-5-2`, `5-3-2`).
- **Interaction Hooks:** Slot click selects target position; replacement mode surfaces inline shortlist; empty state highlights available candidates.

---

## 3. High-Level Feature Workspaces

| Workspace | File | Key Capabilities | Stadium 3.0 Enhancements |
| :--- | :--- | :--- | :--- |
| **Squad Lab** | `CardSquadLab.tsx` | 11-player pitch, formation switcher, chemistry analyzer, upgrade engine, bench tray | Corner arcs, bench shortlist tray, instant slot preview, before/after upgrade cards, Squad DNA breakdown. |
| **Intelligence Studio** | `Intelligence.tsx` | Role suitability ranking, tactical fit engine, radar visualization, factor trade-offs | Progressive disclosure form, sticky tactical inspector rail, live trade-off explanations, 1-click apply to squad. |
| **Discover Scouting** | `Search.tsx` / `Cards.tsx` | Multi-filter player search, attribute ranges, playstyle filters | Filter chip pill bar, quick sort dropdowns, dual grid/table view, UT card previews. |
| **Command Center** | `Dashboard.tsx` | Bento overview, recent squad status, scouting shortcuts | Asymmetric bento grid, quick launcher modules, active squad mini-pitch preview, football telemetry. |
| **Comparison Lab** | `Compare.tsx` | Head-to-head comparison between 2–4 players | Synchronized dual-radar overlay, stat delta highlighting (+/- tags), physical & playstyle breakdown. |
| **Evidence Lab** | `PerformanceEvidenceLab.tsx` | Data integrity audit, benchmark confidence scores, model evaluation | Provenance badges, sample size transparency, strict separation of FC26 vs FC27. |

---

## 4. Design System Compliance Checklist

- [x] Zero external runtime overhead (all icons and graphics are native SVG or CSS).
- [x] Zero fabricated statistics or simulated chemistry numbers.
- [x] High-contrast accessibility compliance (WCAG 2.2 AA).
- [x] Full responsive adaptation across mobile (<768px), tablet (768px-1024px), and desktop (1280px+).
- [x] Fluid animations with hardware acceleration and reduced-motion fallbacks.
