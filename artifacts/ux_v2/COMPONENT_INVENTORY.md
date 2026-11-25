# Project Stadium 2.0 — Component Inventory

This inventory documents all reusable football intelligence UI components, their interface props, accessibility characteristics, and target locations.

---

## 1. Core Football Primitives

### `<FootballCard />`
- **Location:** `frontend/src/components/FootballCard.tsx`
- **Props:**
  - `player`: `GamePlayer | UtCard`
  - `viewMode`: `'grid' | 'compact' | 'table'`
  - `isCompared?`: `boolean`
  - `onCompareToggle?`: `(id: string) => void`
  - `selected?`: `boolean`
  - `onClick?`: `() => void`
- **Visual Elements:**
  - OVR Badge with rating-tier color gradient (Elite Gold, High Lime, Mid Cyan, Low Silver).
  - Primary & secondary position pills.
  - Authentic player silhouette icon (with initials fallback).
  - Player name & club/nation labels.
  - 6-facet attributes block (`PAC`, `SHO`, `PAS`, `DRI`, `DEF`, `PHY`).
  - Known PlayStyle tags.
  - Action tray: "Compare" checkbox + "Inspect / Details" link.
- **Accessibility:** Semantic `article` role, full keyboard operability, explicit aria-label with player name and rating.

---

### `<TacticalPitch />`
- **Location:** `frontend/src/components/TacticalPitch.tsx`
- **Props:**
  - `formation`: `string` (e.g. `'4-3-3'`, `'4-4-2'`, `'4-2-3-1'`)
  - `slots`: `Array<{ id: string; role: string; label: string; player?: any; isLocked?: boolean }>`
  - `selectedSlotId?`: `string`
  - `onSelectSlot`: `(slotId: string) => void`
  - `interactive?`: `boolean`
  - `showSuitability?`: `boolean`
- **Visual Elements:**
  - Responsive SVG pitch markings (touchlines, penalty boxes, center circle, penalty arcs).
  - 11 slot nodes with designated goalkeeper zone (`GK`).
  - Active selection glow & locked-slot padlock icon.
  - Suitability score pill for assigned players.
- **Accessibility:** `role="region" aria-label="Tactical formation pitch"`, keyboard navigation across all 11 slots using Tab and Enter/Space, clear aria-pressed states.

---

### `<TacticalPreview />`
- **Location:** `frontend/src/components/TacticalPreview.tsx`
- **Props:**
  - `formation`: `string`
  - `highlightSlot`: `string`
  - `size?`: `'sm' | 'md'`
- **Visual Elements:**
  - Compact pitch thumbnail illustrating formation structure and pulsing the target formation slot (e.g. `ST` in `4-3-3`).
- **Use Case:** Intelligence Studio Step 2 context preview.

---

### `<SuitabilityScore />` & `<AttributeBar />`
- **Location:** `frontend/src/components/Visualizations.tsx`
- **Props:**
  - `<SuitabilityScore score={number} contextLabel={string} size={'sm'|'md'|'lg'} />`
  - `<AttributeBar label={string} value={number} max={99} delta={number} />`
  - `<TacticalDeltaMatrix basePlayer={any} targetPlayer={any} />`
  - `<EvidenceBadge status={'COMPLETE'|'PARTIAL'|'UNKNOWN'|'INSUFFICIENT'} />`
- **Visual Elements:**
  - Crisp numeric readout + circular/linear SVG meter.
  - Tabular monospace numbers (`IBM Plex Mono`).
  - Positive (+)/negative (-) stat deltas with color coding.
- **Accessibility:** Formatted string alternatives (`aria-valuenow`, `aria-valuetext`).

---

## 2. Page-Level Workspaces

| Page Component | Route | Primary Enhancements |
|---|---|---|
| **Search (Discover)** | `/search` | Dense scouting grid/table with `<FootballCard />`, collapsible filter categories, active filter chips, instant search. |
| **Intelligence** | `/intelligence` | Guided 3-step decision flow, tactical archetype quick-starts, `<TacticalPreview />`, candidate cards with attribute bars, contextual scouting inspector. |
| **CardSquadLab** | `/cards/squad-lab` | Dominant `<TacticalPitch />` on mount, integrated FC27 research alert, slot lock controls, shortlist drawer, `#squad-dna` & `#upgrade-studio`. |
| **Compare** | `/compare` | Side-by-side radar / attribute delta matrix, clear "Why Higher Item Leads" visualization, special item cards. |
| **PerformanceEvidenceLab** | `/cards/performance` | Live cohort comparison, empirical evidence badges, sample coverage indicators. |
| **Nav** | Global Shell | Distinct active states, FC26 vs FC27 research badge, command search bar, mobile slide-over drawer. |
