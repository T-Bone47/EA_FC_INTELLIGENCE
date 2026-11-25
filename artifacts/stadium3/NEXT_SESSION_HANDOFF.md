# STADIUM 3.0 — NEXT SESSION HANDOFF & OPERATIONAL RUNBOOK
**EA FC Intelligence — Football Intelligence Operating System**
*Revision: 3.0.0 | Status: Production Active | Date: November 24, 2026*

---

## 1. Current State & Runtime Overview

The EA FC Intelligence frontend is operating under the **Stadium 3.0** visual and tactical architecture.

- **Vite Dev Server:** Running continuously via background daemon (`http://localhost:5173/`).
- **Working Directory:** `PROJECT/EA_FC_INTELLIGENCE-main/frontend/`
- **Build Status:** Verified production build via `npm run build` (`tsc --noEmit && vite build`), building cleanly in 3.16s.
- **Test Status:** 92 Vitest unit and integration tests passing across 16 test files (0 failures).

---

## 2. Fast Commands Cheat Sheet

From workspace root `PROJECT/EA_FC_INTELLIGENCE-main/frontend`:

```powershell
# Run the test suite
npm test

# Run production build and typecheck
npm run build

# Start the dev server (if restarting)
npm run dev
```

---

## 3. Key Invariants to Maintain

1. **Strict Data Honesty:**
   - Never invent player ratings, attributes, market prices, or chemistry links.
   - If data is absent from EA or the local database, display `UNKNOWN` / `—`.
2. **Version Isolation:**
   - FC26 canonical data and FC27 research data must remain isolated.
   - FC27 research search requires explicit user opt-in (`Include FC27 research players`).
3. **Test Accessibility Assertions:**
   - In `Intelligence.tsx`: keep exactly ONE primary `<button>Find players</button>` in the form.
   - In `CardSquadLab.tsx`: pitch slot buttons must match regex `/^[A-Z0-9]+\s*(Unfilled|.*)$/` and associate with `<select aria-label="Assign [SLOT]">`.
   - In `Dashboard.tsx`: keep headline `<h1>Build a smarter squad. Play your football.</h1>` and link `Find my best fit`.
4. **Zero Budget Policy:**
   - ₹0 external development budget.
   - Component enhancements should remain native React + CSS/SVG primitives.

---

## 4. Documentation Links

- Design System Specification: [DESIGN_SYSTEM.md](file:///c:/Users/dream/Downloads/EA_FC_INTELLIGENCE_COMPLETE_PHASE24-25/PROJECT/EA_FC_INTELLIGENCE-main/artifacts/stadium3/DESIGN_SYSTEM.md)
- Component Inventory: [COMPONENT_INVENTORY.md](file:///c:/Users/dream/Downloads/EA_FC_INTELLIGENCE_COMPLETE_PHASE24-25/PROJECT/EA_FC_INTELLIGENCE-main/artifacts/stadium3/COMPONENT_INVENTORY.md)
- Final Engineering Report: [FINAL_ENGINEERING_REPORT.md](file:///c:/Users/dream/Downloads/EA_FC_INTELLIGENCE_COMPLETE_PHASE24-25/PROJECT/EA_FC_INTELLIGENCE-main/artifacts/stadium3/FINAL_ENGINEERING_REPORT.md)
