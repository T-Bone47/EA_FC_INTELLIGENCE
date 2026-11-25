# PHASE 41: Uncertainty Propagation & Sensitivity Analysis Specification

**Modules:** `backend/services/counterfactual_football_engine.py`, `backend/services/passing_intelligence.py`

## 1. Monte Carlo Perturbation Propagation (`_run_uncertainty_monte_carlo`)
- Generates reproducible seed from SHA-256 hash of `window_id` ($N=24$ default draws).
- Scales uncertainty width dynamically with inverse tracking coverage (`1 - coverage_pct / 100`) and calibration state (`GOOD` vs `PARTIAL` / `APPROXIMATE`).
- Outputs `[q_p10, q_p90]`, `q_std`, `[regret_p10, regret_p90]`, `rank_stability_rate` (% draws where top option stays `#1`), and `indistinguishable_from_best`.

## 2. Pass-Style Speed Sensitivity (`pass_speed_sensitivity`)
Evaluates every candidate passing lane across four distinct velocity profiles (`GROUND_PASS` $16.5\text{ m/s}$, `DRIVEN_PASS` $22.5\text{ m/s}$, `THROUGH_BALL` $14.5\text{ m/s}$, `LONG_SWITCH` $21.0\text{ m/s}$), allowing gamers and the Coach to see when a corridor flips from `BLOCKED` (ground pass) to `OPEN` (driven pass).
