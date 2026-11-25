# EA FC INTELLIGENCE — PHASE 35
# BASELINE REPOSITORY & ARCHITECTURE AUDIT

**Phase:** Phase 35 — Empirical Tactical Intelligence & Uncertainty-Aware Engineering  
**Baseline Engine Version:** V3.2.1 (Frozen Deterministic Baseline)  
**Card Research Dataset Release:** `fc27-card-items-local-r1`  
**Execution Environment:** Windows Server / Local Python 3.15.1 / Node 20+ / React 18.3.1  
**External Budget Consumed:** ₹0.00  
**Audit Date:** 2026-11-24  

---

## 1. Executive Summary

This document establishes the verified baseline of the EA FC Intelligence software repository as of the commencement of Phase 35. 

The preceding milestone, **Phase 34B**, formalized the **Experimental Tactical Alignment Index** ($I_{\text{align}}$), certified disjoint and complete channel partitioning across all 12 supported formations, eliminated unprincipled numerical clamping ($15\%–99\%$) and uncalibrated scaling factors ($0.88$), integrated an interactive 5-tab **Synergy Explanation Inspector** into the Stadium 3.0 Squad Lab, and resolved FastAPI route compatibility issues.

The primary objective of **Phase 35** is to advance EA FC Intelligence from deterministic attribute-based heuristic predictions into an **empirically evaluated, uncertainty-aware football decision-support platform** while rigorously maintaining the **frozen V3.2.1 deterministic core baseline**.

---

## 2. System Architecture & Inventory

### 2.1 Backend Services Directory (`PROJECT/EA_FC_INTELLIGENCE-main/backend/services`)
The backend architecture comprises 37 specialized service modules executing deterministic tactical scoring, slot demand composition, formation validation, and synergy auditing:

| Service Module | Purpose / Domain Responsibility | Baseline Status |
|:---|:---|:---|
| `scoring_config.py` & `v3_config.py` | Declares immutable V3.1 and V3.2 scoring weights, attributes, and baseline coefficients | **Frozen V3.2.1 Baseline** |
| `recommendation_engine_v3.py` | Deterministic ranking engine evaluating card-level suitability with confidence intervals | Active & Verified |
| `demand_composition.py` | Composes multi-dimensional tactical demand vectors per formation slot and tactical profile | Active & Verified |
| `formations.py` | Canonical definitions and slot metadata for all 12 supported formations | Certified Complete |
| `squad_synergy.py` | Computes Experimental Tactical Alignment Index, channel units, and tactical friction rules | Phase 34B Certified |
| `card_squad_lab.py` | Coordinates squad optimization, candidate filtering, and slot assignments | Active & Verified |
| `empirical_evaluator.py` | Evaluates match observations, statistical differences, and empirical evidence | Target for Phase 35 Enhancement |
| `fc27_card_research.py` | Resolves canonical card items from local research cohort (`TOP_100_BASE_CARDS.csv`) | Active & Verified |
| `reference_distribution.py` | Computes reference distributions for attribute percentile normalizations | Active & Verified |
| `card_value_service.py` | Computes value-for-money without fabricating price history or assuming free cards | Active & Verified |
| `chemistry_service.py` | Reports factual structural fit (nation/club/league); reports chemistry as UNKNOWN when unverified | Active & Verified |

### 2.2 Frontend Architecture (`PROJECT/EA_FC_INTELLIGENCE-main/frontend`)
The frontend client is built with React 18.3.1, TypeScript 5.6, Vite 6.0, and Tailwind CSS, adhering to Stadium 3.0 visual tokens:

- **Key Interfaces:**
  - `CardSquadLab.tsx`: Pitch visualizer, slot assignment controls, 5-tab Synergy Explanation Inspector (`Whole XI`, `Left Flank`, `Central Spine`, `Right Flank`, `Tactical Alerts`), Stadium 3.0 form controls.
  - `PerformanceEvidenceLab.tsx`: Empirical study tracking, observation verification, and model comparison.
  - `Intelligence.tsx` & `Recommend.tsx`: Player search, attribute weight customization, tactical profile selection, and ladder rankings.
  - `ComparePanel.tsx` & `WhatIfPanel.tsx`: Multi-player attribute comparison and tactical what-if evaluation.

---

## 3. Baseline Verification Status

Prior to initiating Phase 35 feature development, the full verification test suite was executed in the active repository environment:

### 3.1 Backend Pytest Regression
- **Command:** `python -m pytest backend/tests/test_squad_synergy.py backend/tests/test_empirical_evaluator.py backend/tests/test_phase30_card_lab.py backend/tests/test_striker_pilot.py backend/tests/test_v3_2_config.py backend/tests/test_golden_fixtures_v3_2.py backend/tests/test_engine_intelligence.py backend/tests/test_phase28_formation.py -v`
- **Result:** **100 Passed, 4 Skipped** (Skipped tests require live PostgreSQL service; see below)
- **Execution Time:** 28.57 seconds
- **Engine Invariants:**
  - Deterministic golden fixture receipts: 100% bit-exact match against committed baseline.
  - 12/12 formations mapped completely without channel overlap: Verified.
  - Tactical rule provenance and alignment index precision: Verified.

### 3.2 Frontend Vitest Regression
- **Command:** `npm test -- --run`
- **Result:** **92 Passed, 3 Skipped** (Skipped tests require live backend daemon)
- **Execution Time:** 60.74 seconds across 16 test suites
- **Component Coverage:**
  - Form controls, Data Quality panels, Card rendering, ComparePanel, WhatIfPanel, Route guards, and State management verified.

### 3.3 Database & Staging Evidence Status
- **PostgreSQL Database:** Offline during test runs; integration tests requiring live pool gracefully skip with documented reasons (`requires_db`).
- **Accepted Gameplay Match Observations (`fc27_staging`):** **0 records**.
- **Honest Data Assertion:** Because 0 accepted empirical match observation records currently exist in the database, all model rules and tactical weights are formally categorized as `MODELED_HEURISTIC` or `PENDING_EMPIRICAL_VALIDATION`. No fabricated match statistics or synthetic gameplay claims exist in production data.

---

## 4. Phase 35 Mandate & Constraints

1. **₹0 External Budget Consumed:** No third-party paid APIs, proprietary licensed feeds, or cloud services utilized.
2. **V3.2.1 Deterministic Engine Frozen:** Scoring weights, golden fixture outputs, and core recommendation algorithms remain completely immutable.
3. **Additive Research & Calibration Architecture:** All Phase 35 features (Empirical Observation Schema, Partnership Science, Stability Lab, Whole-XI Counterfactuals) are implemented additively without modifying existing production routes or breaking backwards compatibility.
4. **Epistemic Honesty:** Unobserved attributes remain `UNKNOWN`; zero chemistry is fabricated; all empirical conclusions are mathematically reconstructable.
