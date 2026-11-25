# Phase 36 Development Handoff Specification
**Project:** EA FC Intelligence — Stadium 3.0  
**Delivering Milestone:** Phase 35 Complete  
**Receiving Milestone:** Phase 36 — Live Empirical Ingestion & Advanced Interactive Pitch Intelligence  
**Author:** Principal AI/ML Research & Full-Stack Engineering Team  
**Date:** November 24, 2026  

---

## 1. System State & Certified Assets

Phase 35 leaves the repository in an impeccably verified, zero-regression state. Every component, formula, and visual control has been certified through automated unit tests, build verifications, performance benchmarks, and headless browser visual inspections.

### Certified Test Baseline:
- **Backend:** 109 passed, 4 skipped across 10 certified modules in 4.80s (`FULL_BACKEND_TEST_RESULTS.json`).
- **Frontend:** 92 passed, 3 skipped in 6.83s (`FRONTEND_TEST_RESULTS.json`).
- **TypeScript:** 0 type errors via `npx tsc --noEmit`.
- **Production Bundle:** Clean 1.45s compilation via `npm run build`.
- **Browser E2E:** 11 screenshots verified across desktop and mobile (`BROWSER_E2E_RESULTS.json`, `VISUAL_INSPECTION.md`).
- **Computational Latency:** Sub-millisecond evaluations (0.022 ms Whole-XI synergy, 0.050 ms Partnership V2).
- **External Budget Consumed:** ₹0.00.

---

## 2. Inherited Infrastructure & Capabilities

Phase 36 inherits the following completed subsystems:

1. **Frozen V3.2.1 Deterministic Core:**
   - Files: `backend/services/card_squad_lab.py`, `backend/services/v3_config.py`, `backend/tests/fixtures/v3_2_golden_fixtures.json`.
   - Invariant: Zero modification permitted to existing heuristic weights or golden outputs.
2. **Empirical Observation Schema & Integrity Ledger:**
   - Files: `backend/domain/empirical_observation.py`, `artifacts/phase35/EMPIRICAL_OBSERVATION_SCHEMA.md`.
   - Capabilities: 6 review states (`DRAFT` through `SUPERSEDED`), SHA-256 digest hashing, quality gating.
3. **Partnership Intelligence V2 Engine:**
   - Files: `backend/services/partnership_intelligence.py`, `backend/tests/test_partnership_intelligence.py`.
   - Capabilities: 5 tactical couplings, harmonic mean capability complementarity, responsibility overlap, and friction deductions.
4. **Recommendation Stability Lab:**
   - Files: `backend/services/recommendation_stability.py`, `backend/tests/test_recommendation_stability.py`.
   - Capabilities: 14 systematic perturbation scenarios, candidate rank volatility ($\sigma_R$), and sensitivity classification.
5. **Whole-XI Multi-Slot Counterfactual Engine:**
   - Files: `backend/services/squad_synergy.py`, `verification/run_phase35_counterfactuals.py`.
   - Capabilities: Alignment index $I_{\text{align}}$, dispersion penalty ($0.5\sigma_r$), unrounded double-precision delta policy ($\Delta I$).
6. **Empirical Evaluator & Hypothesis Testing:**
   - Files: `backend/services/empirical_evaluator.py`, `backend/tests/test_empirical_evaluator.py`.
   - Capabilities: Exact paired Student's $t$-test and Wilcoxon signed-rank test.
7. **Stadium 3.0 UI/UX Implementation:**
   - Files: `frontend/src/pages/CardSquadLab.tsx`, `frontend/src/pages/PerformanceEvidenceLab.tsx`, `frontend/src/pages/CardSquadLab.css`.
   - Capabilities: Interactive `PARTNERSHIPS` and `STABILITY` tabs, Epistemic Honesty status banner, custom form controls.

---

## 3. High-Priority Directives for Phase 36

### Directive 1: Live Match Observation Ingestion
- **Objective:** Begin ingesting real, human-verified FC27 match records under Protocol `EXP-ST-PRESS-001` (Dembélé vs Mbappé).
- **Power Target:** Collect at least $N = 30$ accepted paired match sessions (15 with Dembélé, 15 with Mbappé in identical High Press setups).
- **Tooling:** Utilize the Observation Schema in `empirical_observation.py` with cryptographic SHA-256 verification.

### Directive 2: Statistical Power Evaluation & V3.3 Gate Verification
- **Objective:** Run the Empirical Evaluator against populated staging data.
- **Criteria:** Check whether Dembélé's defensive turnover rate ($t_{\text{won}} + \text{int}$) exceeds Mbappé's by $\Delta \ge +1.50/\text{90}$ at $p < 0.05$.
- **Gating:** If and only if all 5 promotion criteria in [V3_3_RESEARCH_READINESS.md](file:///c:/Users/dream/Downloads/EA_FC_INTELLIGENCE_COMPLETE_PHASE24-25/PROJECT/EA_FC_INTELLIGENCE-main/artifacts/phase35/V3_3_RESEARCH_READINESS.md) are satisfied ($N \ge 100$ overall), consider packaging V3.3 research candidate weights. Otherwise, keep V3.2.1 frozen.

### Directive 3: Interactive 2D/3D Pitch Visualization
- **Objective:** Enhance Stadium 3.0 with dynamic player positioning vectors, passing network arrows between high-synergy partners, and pressing heat zones.
- **Visual Design:** Strictly preserve the Stadium 3.0 dark palette (`--field-bg: #172536`, `--field-border: #344A60`, `--field-focus: #B8F57A`).

### Directive 4: Expanded Partnership Dynamics
- **Objective:** Extend Partnership Intelligence V2 with:
  1. **Goalkeeper + Center-Back (GK + CB):** Sweeper-keeper distribution vs backline depth.
  2. **Inverted Fullback + Central Midfielder (IFB + CM):** Underlapping box presence vs midfield coverage.

---

## 4. Key Developer Commands & Reference Paths

### Running Certified Backend Regression:
```powershell
Set-Location "PROJECT\EA_FC_INTELLIGENCE-main"
$env:PYTHONPATH="."
pytest backend/tests/test_squad_synergy.py backend/tests/test_partnership_intelligence.py backend/tests/test_recommendation_stability.py backend/tests/test_empirical_evaluator.py backend/tests/test_phase30_card_lab.py backend/tests/test_striker_pilot.py backend/tests/test_v3_2_config.py backend/tests/test_golden_fixtures_v3_2.py backend/tests/test_fastapi_app.py backend/tests/test_phase28_formation.py -v
```

### Running Frontend Tests & Typecheck:
```powershell
Set-Location "PROJECT\EA_FC_INTELLIGENCE-main\frontend"
npx tsc --noEmit
npm test -- --run
npm run build
```

### Running Browser E2E Inspection:
```powershell
Set-Location "PROJECT\EA_FC_INTELLIGENCE-main"
# 1. Start mock server (in separate terminal or background):
node verification/mock_backend.js
# 2. Start Vite server (in separate terminal or background):
cd frontend && npm run dev
# 3. Run inspection script:
$env:NODE_PATH="frontend/node_modules"
node verification/run_phase35_browser_inspection.js
```

### Key Policy Invariants:
1. **Zero External Budget:** Do not use paid third-party APIs or cloud endpoints.
2. **Epistemic Honesty:** Never report synthetic matches as real gameplay evidence.
3. **Frozen Golden Baseline:** Keep V3.2.1 golden fixtures bit-exact.
