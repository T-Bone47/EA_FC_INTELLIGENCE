# STADIUM 3.0 — INTELLIGENCE STUDIO VISUAL REVIEW
**EA FC Intelligence — Football Intelligence Operating System**
*Revision: 3.0.0 | Module: frontend/src/intelligence/Intelligence.tsx*

---

## 1. Executive Summary

The Player Intelligence Studio has been redesigned from a static form-results layout into an interactive **Tactical Intelligence Command Workspace**.

Instead of leaving empty space when awaiting user input, the workspace now features an intuitive 3-step tactical workflow stepper, Quick Tactical Archetypes (e.g. "4-3-3 Counter ST", "Possession CDM"), a live miniature pitch preview, a Scouting Mission Briefing, and a Dynamic Tactical Demand Blueprint in the inspector rail.

---

## 2. Architectural Upgrades

### 2.1 3-Step Guided Workflow Stepper
- Visual progress indicator above the workbench:
  1. **Tactical Context:** Select game version, formation, position, and division.
  2. **Pitch Alignment:** Choose exact formation slot duty and tactical emphasis (λ = 0.50 – 0.90).
  3. **Ranked Intelligence:** Explore deterministic player rankings, inspect key trade-offs, and launch head-to-head comparisons.

### 2.2 Quick Tactical Archetypes
- One-click tactical presets allowing rapid scouting setup:
  - ⚡ *4-3-3 Counter ST:* Explosive transition striker with high acceleration and finishing.
  - 🎯 *Possession CDM:* Press-resistant deep-lying playmaker with high passing and vision.
  - 🛡️ *High-Press RB:* Relentless defensive full-back with stamina and aggression.
  - 🧠 *Creative CM:* Dynamic central controller with high ball control and short passing.

### 2.3 Interactive Miniature Pitch Context (`TacticalPreview.tsx`)
- Dynamic 2D pitch widget illustrating the manager's target formation and highlighted slot.
- Visual confirmation of positional duty (e.g. Advanced Forward vs Target Forward) before running candidate ranking.

### 2.4 Contextual Scouting Inspector (Right Rail)
- **Active State (When Player Selected):**
  - Player avatar and club/nation crest display via `PlayerIdentity`.
  - V3.2 Suitability Score gauge with evidence coverage percentage.
  - Deterministic data integrity badge via `EvidenceBadge`.
  - Bulleted **Key factors** explaining why the player fits the tactical system.
  - Explicit **Trade-offs** alerting the manager to any physical or defensive compromises.
  - Near-tie alerts when candidates fall within statistical noise thresholds.
- **Empty State (Pre-Execution):**
  - Replaces dead blank space with a **Tactical Demand Blueprint**:
    - Tactical system summary (e.g. Possession, High Press, Counter Attack).
    - Demanded Attributes tags.
    - Benchmark PlayStyles badges (Tiki Taka+, Quick Step+, Relentless+).
    - V3.2 Engine mathematical formula transparency.

---

## 3. Data Honesty & Test Invariant Compliance

- **Single Find Players Trigger:** Retains strict unique accessible name `button: Find players` for unambiguous automated testing.
- **Strict Version Wall:** FC26 and FC27 separation strictly maintained; FC27 requires explicit Men's / Women's / Both selection.
- **No Fabricated Stats:** If attributes are missing from official EA feeds, `missing_attributes` are explicitly rendered.
