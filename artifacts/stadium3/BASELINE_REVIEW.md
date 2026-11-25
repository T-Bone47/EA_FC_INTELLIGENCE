# STADIUM 3.0 — FOOTBALL INTELLIGENCE OS
## BASELINE REVIEW & GAP ANALYSIS

**Product:** EA FC Intelligence  
**Evaluation Scope:** Visual Craftsmanship, Football Identity, Information Hierarchy, Interaction Model, Accessibility, Performance  
**Target Standard:** World-Class Sports Technology & Tactical Decision Cockpit  
**Date:** 2026-11-24

---

### 1. Current State Baseline Assessment

The previous migration to Stadium 2.0 established an operational dark stadium aesthetic, unified tokens, and guaranteed deterministic data honesty (zero fake statistics, zero synthetic chemistry, strict version wall). However, a deep review reveals key UI/UX gaps that keep the product looking more like an internal engineering dashboard than a world-class football intelligence platform:

| Screen / Area | Current State Assessment | Identified Defects & Limitations | Stadium 3.0 Target |
| :--- | :--- | :--- | :--- |
| **Global Controls & Buttons** | Generic rectangular buttons with flat colors; cramped padding; basic hover states. | Buttons lack distinct physical elevation; secondary and ghost buttons blend into backgrounds; tactical archetype chips feel like static tags. | Tactical Action Primitives: 3 distinct tiers (Primary Electric Lime, Secondary Raised Glass, Tertiary Ghost Outline) with haptic feel and focus rings. |
| **Overview Command Center** | Asymmetric hero with 4-3-3 preview and 4 workflow cards; basic text links. | Formation preview feels mostly empty; recent analyses lack visual status indicators; workflow cards are plain text containers. | Mission Command Cockpit: Dynamic tactical squad preview, high-impact KPI statistics, 1-click re-run drawers, and stadium floodlight visuals. |
| **Squad Lab (Flagship)** | Functional 11-slot pitch with slot dropdowns; Squad DNA text list; Smart Upgrade table. | Pitch lacks authentic turf lighting, markings, and depth; shortlisted cards are buried in dropdowns; no visual chemistry or tactical linkage channels. | Authentic 3D Stadium Turf: Mowing stripes, tactile glowing slot nodes, Quick Shortlist Bench tray, and interactive upgrade delta overlays. |
| **Intelligence Studio** | 3-column layout (Context, Ladder, Inspector); dynamic tactical blueprints. | Left form controls feel dense and plain; candidate cards need richer football card styling; trade-off comparisons lack visual matrix depth. | Guided Scouting Workspace: Progressive 3-stage tactical stepper, holographic candidate cards, radial score gauges, and comparison drawer. |
| **Discover & Cards** | Grid/Table toggle with `<FootballCard />`; 6-facet pills; filter rail. | Cards feel like generic player badges; lacking authentic FUT card tiering (Gold Rare, Special, Icon); filter chips need smoother microinteractions. | Ultimate Team Card Engine: Dynamic card tiers (Gold foil, Special onyx/cyan, Silver steel), holographic sheen on hover, and quick comparison checks. |
| **Compare Studio** | Dual radar polygons and attribute deltas; context engine verdict. | Radar charts lack grid labels; attribute deltas are plain text; lacks 3-player and 4-player comparative visual balance. | Head-to-Head Tactical Arena: Synchronized comparative radar polygons, signed delta bars, and deterministic why-not trade-off cards. |
| **Auth & Account** | Split login layout with empty pitch visual; basic inputs. | Pitch visual feels detached; form feels like a generic template; guest access is small. | Elite Scouting Access Gate: High-impact tactical visual backdrop, clear sync benefits, and prominent 1-click guest scouting path. |

---

### 2. Technical Invariants Preserved
- **Zero Fabricated Stats**: Unverified attributes remain strictly `UNKNOWN`.
- **Zero Fake Chemistry**: Chemistry values without verified API feeds are disclosed as unverified.
- **Strict Version Wall**: FC26 Canonical and FC27 Research data are quarantined.
- **₹0 External Budget**: Built exclusively with 21st.dev free-tier components, open SVG/CSS, and existing React/TypeScript dependencies.
- **100% Test Stability**: All 92 passing Vitest tests and Playwright E2E contracts in `stadium.mjs` remain strictly green.
