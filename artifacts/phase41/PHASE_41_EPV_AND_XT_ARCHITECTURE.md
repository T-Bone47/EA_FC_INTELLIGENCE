# PHASE 41F/41G: Expected Possession Value, Markov xT & Risk-Adjusted Utility Architecture

**Modules:** `backend/services/passing_intelligence.py`, `backend/services/possession_value_engine.py`

## 1. Passing Physics (`PassingIntelligenceEngine`)
- **Corridor Clearance:** Computes minimum Euclidean point-to-segment distance from all pre-action opponents onto pass ray $A \to B$.
- **Dynamic Interception Margin:** Evaluates $M = t_{\text{opp}}(C) - t_{\text{ball}}(C)$ along segment closest point $C$ incorporating opponent reaction lag ($0.25\text{s}$), current velocity vector projection toward $C$, and bounded sprint speed.
- **Pass-Speed Sensitivity:** Computes $M$ and open/contested/blocked status simultaneously across four speeds: `GROUND_PASS` ($16.5\text{ m/s}$), `DRIVEN_PASS` ($22.5\text{ m/s}$), `THROUGH_BALL` ($14.5\text{ m/s}$), `LONG_SWITCH` ($21.0\text{ m/s}$ loft-adjusted).

## 2. Three-Stage Valuation Boundary
1. **Stage 1 — `HeuristicPossessionValue`:** Combines corridor interception margin $M$, receiver space radius, rest-defense multiplier, and turnover exposure. Explicitly sets `is_calibrated_probability = False`.
2. **Stage 2 — `ExpectedThreatEngine`:** Iterative Bellman solver on $12\times 8$ (or custom $R\times C$) zones initialized from Karun Singh xT prior or empirical Dirichlet-smoothed transition matrices $T_{z\to z'}$ and shot rates $s(z)$. Explicitly marks non-probability threat value until fitted on calibrated match transitions.
3. **Stage 3 — `CalibratedEPVInterface`:** Future $V(s) = P(\text{score}\mid s) - P(\text{concede}\mid s)$ gated strictly behind $\ge 25$ calibrated EA FC matches AND Brier $\le 0.20$. Currently returns `calibrated_ready = False` honestly.

## 3. Dual Reward / Risk Exposure Decomposition
Every scored action exposes `reward_component` and `risk_component` separately inside `PossessionValueBreakdown` alongside `risk_adjusted_utility = reward - risk` so gamers never confuse aggressive risk-taking with safe conservative resets.
