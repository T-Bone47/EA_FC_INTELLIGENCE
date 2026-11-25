# STADIUM 3.0 — SQUAD LAB & TACTICAL PITCH VISUAL REVIEW
**EA FC Intelligence — Football Intelligence Operating System**
*Revision: 3.0.0 | Module: CardSquadLab.tsx & StadiumPitch.tsx*

---

## 1. Executive Summary

Squad Lab has been elevated into the flagship tactical center of Stadium 3.0. Previously, the squad builder suffered from small pitch dimensions, generic button styling, lack of pitch texture, and disconnected replacement controls.

In Stadium 3.0, the workspace is unified around an authentic match pitch experience with full keyboard navigation, tactile player slots, a dedicated shortlist bench tray, and rich analytical breakdown panels for Squad DNA and Smart Upgrades.

---

## 2. Key Visual & Architectural Upgrades

### 2.1 The Match Pitch (`StadiumPitch.tsx` & `stadium.css`)
- **Proportional Pitch Markings:** Vector-accurate white/lime lines for 18-yard box, 6-yard goal area, penalty spot, center circle, halfway line, and **4 corner arcs** (`.pitch-corner-tl`, `.pitch-corner-tr`, `.pitch-corner-bl`, `.pitch-corner-br`).
- **Turf Lighting & Texture:** Atmospheric gradient overlay simulating stadium floodlights reflecting off grass turf (`radial-gradient(ellipse at 50% 25%, rgba(184, 245, 122, 0.08), transparent 70%)`).
- **Dynamic Slot States:**
  - *Empty Slot:* Dashed translucent glass border with high-contrast lime dashed outline on hover.
  - *Filled Slot:* Tactile glass badge with player surname, position badge, and fit score.
  - *Elite Performer (85+ Fit):* Gold luminescence border (`.is-elite`) with subtle golden glow.
  - *Weak Slot (<65 Fit):* Warm amber border (`.is-weak`) alerting manager to replacement urgency.
  - *Locked Slot:* Distinct lock indicator (`🔒 Locked`) preventing optimizer override.

### 2.2 Shortlist Bench Tray
- Glassmorphism drawer below the pitch displaying all shortlisted candidate cards.
- Quick status pills showing assigned vs unassigned status (`●` assigned in lime, `○` bench in subtle gray).
- Provides instant situational awareness without scrolling through separate lists.

### 2.3 Squad DNA & Analytical Matrix (`#squad-dna`)
- High-density KPI cards (`stat-card`) with glowing top accents: Total Fit, Mean Coverage %, Scored Slots.
- Lineup breakdown list showing per-slot fitness evaluations, verified footballer uniqueness, and PlayStyle coverage.
- Tactical profile alternatives matrix with 1-click profile application (`Apply HIGH_PRESS`, `Apply POSSESSION`).

### 2.4 Smart Upgrade Studio (`#upgrade-studio`)
- Dual-card visual diff comparing Current Item vs Proposed Replacement.
- Highlighted fitness delta (`Total Fit Gain: +0.142`) in vivid pitch lime.
- Full context explanations preserving mathematical honesty (zero simulated stats).
- High-impact "Apply replacements" trigger and 1-click "Undo last edit" restore action.

---

## 3. Responsive & Accessibility Validation

- **Desktop (1440px - 1600px):** 3-column tactical workspace (Left: Tactical Rules & Shortlist -> Center: Stadium Pitch & Assignment Selectors -> Right: Squad Intelligence & Saving).
- **Tablet (1024px):** Responsive 2-column layout with stacked intelligence drawer.
- **Mobile (360px - 390px):** Single-column stacked pitch with touch-optimized slot targets (minimum 48px hit areas), verified with zero horizontal overflow.
- **Keyboard Navigation:** Slot buttons activate on `Enter`/`Space` and immediately focus the corresponding assignment selector (`Assign [Slot]`).
