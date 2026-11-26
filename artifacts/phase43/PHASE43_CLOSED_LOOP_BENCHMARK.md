# Phase 43 Closed-Loop Empirical Benchmark

## 1. Benchmark Scope & Reproducibility
Executed via `python verification/benchmark_phase43_tactical_lab.py` against `Phase40Repository(force_memory=True)` + `Phase43Repository(force_memory=True)` to validate end-to-end execution across Modules 43B through 43K in a single deterministic run.

## 2. Exact Observed Benchmark Output (`elapsed_ms = 2987.5`)
- **Snapshots Created:**
  - Baseline Arm A (`4-3-3` HIGH_PRESS, line=76): `TSNP-4c31cd19`
  - Variant Arm B (`4-2-3-1` POSSESSION, line=52, `v2_hash=13f5e6d4122feb22`): `TSNP-e7fb42f2`
- **Pre-Match Counterfactual (`TacticalCounterfactualService`):**
  - `evidence_grade`: `THEORETICAL_SUITABILITY`
  - `rest_defense_risk_delta`: `-0.248`
- **Tactical Fingerprints Extracted:** `6` four-phase fingerprints across 6 real-provenance matches (`3` Arm A + `3` Arm B).
- **Match-Clustered Statistical Analysis (`EXP-0598f9f9`):**
  - `verdict`: `SUPPORTED_IMPROVEMENT`
  - `evidence_grade`: `CONTROLLED_EXPERIMENT_EVIDENCE`
  - `arm_a_mean`: `0.4445`
  - `arm_b_mean`: `0.1667`
  - `hedges_g`: `-6.5343`
  - `p_value`: `0.0098`
  - `bootstrap_ci_95`: `[-0.3333, -0.25]`
  - `bayesian_p_b_better`: `0.999`
  - `synthetic_excluded`: `1` (automatic exclusion of `BENCH-SYNTH` verified)
  - `loo_stable`: `true`
- **Personal Formation Recommendation (`PersonalFormationEngine`):**
  - Top system: `4-2-3-1` (`POSSESSION / BALANCED`), `theoretical_score = 0.8899`, `observed_match_count = 3`, `observed_avg_delta = 0.833`, `experiment_wins = 1`, `evidence_grade = CONTROLLED_EXPERIMENT_EVIDENCE`.
- **Replacement Triage (`ReplacementExperimentService`):**
  - `primary_recommendation`: `TACTICAL_OR_ROLE_ADJUSTMENT_FIRST`
  - `purchase_justified`: `false`
  - `market_price_status`: `MARKET_PRICE_UNAVAILABLE`
- **Personal Meta Profile (`PersonalMetaService`):**
  - Scope: `PATCH_1.04`, `6` eligible matches, `strongest = 4-2-3-1`, `frozen_v321_altered = false`.
- **CV Pipeline Probe:**
  - `onnx_status`: `NO_TRAINED_WEIGHTS_PRESENT`
  - `synthetic_proxy_ece`: `0.0817`, `synthetic_proxy_brier`: `0.0178`, `synthetic_proxy_map50`: `0.7712`, `real_clips_processed`: `2`.
- **Co-Pilot Closed-Loop Grounding Note:**
  - Querying `"Compare Arm A vs Arm B in my active tactical experiment"` from `TACTICAL_LAB` returned grounded output in `benchmark_phase43_tactical_lab.py`; notably, the `"Compare ..."` phrasing currently routes `PersonalCoachOrchestrator` intent classifier toward `PLAYER_COMPARISON` alongside mistake/meta/formation tools (`TACTICAL_LAB` sub-intent routing for comparison queries is tracked cleanly in Phase 43 limitations as a next improvement).
