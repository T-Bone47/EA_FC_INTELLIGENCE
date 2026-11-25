# EA FC INTELLIGENCE — PHASE 35
# V3.3 RESEARCH CANDIDATE SPECIFICATION & PROMOTION READINESS REPORT

**Document Version:** 1.0.0-phase35  
**Current Active Production Baseline:** Engine V3.2.1 (Frozen Deterministic Baseline)  
**Proposed Candidate:** Engine V3.3-RC1 (Evidence-Calibrated Non-Linear Weighting)  
**Promotion Decision:** **BLOCKED — INSUFFICIENT EMPIRICAL GAMEPLAY EVIDENCE**  
**Date:** 2026-11-24  

---

## 1. Executive Summary & Policy Mandate

The primary architectural principle of EA FC Intelligence is **epistemic integrity**:
> *"Never claim mathematical elegance or heuristic plausibility proves actual gameplay effectiveness. If verified empirical gameplay data is absent, the engine must refuse promotion, state the data deficiency honestly, and preserve the frozen baseline."*

In Phase 35, candidate architectural improvements for Engine V3.3 (such as dynamic tactical demand weighting calibrated by observed final-third turnovers and non-linear stamina decay curves) were developed in experimental isolation.

However, an exhaustive audit of `fc27_staging` confirms that **accepted gameplay match observation records currently stand at 0**. Consequently, in strict compliance with project governance:
1. **Engine V3.3 is NOT promoted to production.**
2. **Engine V3.2.1 remains the immutable, frozen active production engine.**
3. This report defines the immutable **Promotion Gate Criteria** that must be satisfied before any future V3.3 promotion can be considered.

---

## 2. Formal Promotion Gate Criteria for Engine V3.3

Before any candidate model can supersede V3.2.1, it must pass all five quantitative criteria:

| Gate Identifier | Evaluation Scope | Quantitative Threshold | Current Status |
|:---|:---|:---|:---|
| **`GATE-001-VOL`** | Minimum Empirical Volume | $\ge 100$ accepted match observation records in `fc27_staging` | **FAILED (0 / 100 records)** |
| **`GATE-002-OBS`** | Observer Diversity | $\ge 5$ independent observers with verified client signatures | **FAILED (0 / 5 observers)** |
| **`GATE-003-SIG`** | Statistical Significance | $p < 0.01$ on paired difference $t$-tests over V3.2.1 predictions | **PENDING DATA** |
| **`GATE-004-IRR`** | Inter-Rater Reliability | Cohen's $\kappa \ge 0.85$ on dual-annotated video verification | **PENDING DATA** |
| **`GATE-005-REG`** | Regression Invariance | 100% bit-exact pass rate on committed golden fixtures | **PASSED (100% on V3.2 goldens)** |

---

## 3. V3.3 Research Candidate Specification (In-Flight Innovations)

When empirical volume thresholds are satisfied, the V3.3 architecture introduces three evidence-calibrated enhancements:

### 3.1 Calibrated Tactical Elasticity ($\lambda_{\text{cal}}$)
In V3.2.1, tactical blend $\lambda = 0.65$ is a fixed scalar. In V3.3-RC1, $\lambda$ becomes context-elastic, dynamically shifting based on the empirical turnover yield observed for specific formation slots (e.g. higher tactical elasticity for wide pressing wingers, lower elasticity for central screening anchors).

### 3.2 Non-Linear Second-Half Stamina Decay
Based on pilot trial observations showing that pressing forwards suffer non-linear recovery decay when stamina drops below 75 after minute 65:
$$r_s(t) = r_s \cdot \left(1.0 - \alpha_{\text{decay}} \cdot \max(0.0, 75 - \text{Stamina}) \cdot \mathbb{I}(t > 65)\right)$$

### 3.3 Dynamic Partnership Multipliers
Directly incorporating Partnership Intelligence V2 ($S_{\text{part}}$) into slot-level suitability adjustments rather than reporting it as a separate squad dashboard index.

---

## 4. Current Blocker Report & Next Steps

1. **Current Blocker:** The transition from Modeled Heuristic to Empirically Supported is gated solely on physical match data acquisition. No software bugs or mathematical ambiguities block the pipeline.
2. **Action Item for Community / Operators:**
   - Deploy `EXP-ST-PRESS-001` to human volunteer observers using `MATCH_ANNOTATION_PROTOCOL.md`.
   - Log at least 50 paired sessions (100 matches) on `fc27_staging`.
   - Re-run `verification/run_empirical_evaluation.py` once records reach $N \ge 100$.
3. **Serving Invariant:** Until that condition is met, all API endpoints, frontend dashboards, and ladder rankings will continue serving frozen V3.2.1 intelligence with 100% determinism.
