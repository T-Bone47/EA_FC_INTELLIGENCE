# Phase 43D/E Tactical Experiment Engine & Statistical Inference Report

## 1. Eight Supported N-of-1 Tactical Experiment Workflows (`ExperimentType`)
Managed by `TacticalExperimentEngine` (`backend/services/tactical_experiment_engine.py`) with PostgreSQL persistence in `phase43_experiment` and `phase43_experiment_match_link`:
1. `FORMATION_COMPARISON` (enforces distinct `snap_a.formation != snap_b.formation`)
2. `TACTICAL_PRESET_COMPARISON`
3. `PLAYER_ROLE_FOCUS_COMPARISON`
4. `DEFENSIVE_HEIGHT_PRESS_COMPARISON`
5. `BUILD_UP_STYLE_COMPARISON`
6. `PLAYER_PARTNERSHIP_COMPARISON`
7. `SINGLE_POSITION_REPLACEMENT`
8. `PERSONAL_PLAYSTYLE_COMPATIBILITY`

Supported counterbalanced block schedules (`get_recommended_schedule`) output `["BASELINE_A", "VARIANT_B", "VARIANT_B", "BASELINE_A"]` ABBA sequences to mitigate fatigue and session-order drift.

## 2. Primary Metric & Opportunity-Normalized Denominator Registry
`SUPPORTED_PRIMARY_METRICS` enforces metric directionality and opportunity normalization:
- `conceded_transition_rate` (`higher_is_better=False`, numerator=`exposed_transitions`, denominator=`transition_opportunities`)
- `risky_central_pass_rate` (`higher_is_better=False`, numerator=`risky_central_passes`, denominator=`central_pass_opportunities`)
- Scalar higher-is-better metrics: `defensive_compactness`, `defensive_transition_management`, `central_progression`, `chance_creation`, `possession_share`, `pressing_intensity`.

## 3. Match-Clustered Statistical & Bayesian Inference (`ExperimentAnalysisService`)
`backend/services/experiment_analysis_service.py` enforces strict methodological safeguards:
- **Unit of Analysis:** Always `MATCH_CLUSTER_AGGREGATE` (one scalar summary per verified match; video frames are never pooled as independent replicates).
- **Automatic Firewall Filtering:** Excludes `SYNTHETIC_FIXTURE` matches (`SYNTHETIC_FIXTURE_EXCLUDED`) and `game_version` mismatches before statistical estimation.
- **Confounder Audits (`ConfounderReport`):** Detects `patch_drift_detected`, `mode_mismatch_detected`, `opponent_imbalance_detected`, low coverage (`<40%`), and synthetic exclusions.
- **Frequentist & Effect Size Inference:**
  - Descriptive per-arm distributions (`mean`, `median`, `sd`, `iqr`, `opportunity_normalized_rate`).
  - `scipy.stats.ttest_rel` (when balanced replicates differ non-trivially) or `scipy.stats.ttest_ind(..., equal_var=False)` Welch test.
  - Bias-corrected Hedges' `g` (`_hedges_g` with small-sample `1 - 3/(4*df - 1)` factor).
  - Non-parametric percentile `95%` bootstrap CI (`scipy.stats.bootstrap(..., n_resamples=1500, random_state=42)`).
- **Analytical Normal-Normal Conjugate Bayesian Posterior:** Computes posterior mean, SD, `95%` credible interval, and `P(Variant B better)` (`bayesian_posterior_prob_b_better` clamped to `[0.001, 0.999]`) using `prior_sd = 0.25`.
- **Sensitivity & Honest Abstention:**
  - Leave-one-match-out (LOO) sign-stability check (`sensitivity_leave_one_out_stable`).
  - Automatically assigns `INSUFFICIENT_EVIDENCE` when `<2` eligible matches per arm, and `INCONCLUSIVE` / `OBSERVED_ASSOCIATION` when patch drift, mode mismatch, LOO sign flip, or under-target replicate counts (`< target_min_matches_per_arm`) occur.

## 4. Verified Benchmark & Test Measurement
- In both `test_phase43b_to_e_snapshots_fingerprints_and_experiment_statistics` and `verification/benchmark_phase43_tactical_lab.py` (3 verified Arm A `4-3-3` matches vs 3 verified Arm B `4-2-3-1` matches + 1 synthetic fixture):
  - Synthetic exclusion verified (`synthetic_excluded_count = 1`).
  - Benchmark output (`EXP-0598f9f9`): `arm_a_mean=0.4445`, `arm_b_mean=0.1667`, `hedges_g=-6.5343`, `p_value=0.0098`, `bootstrap_ci_95=[-0.3333, -0.25]`, `bayesian_p_b_better=0.999`, `loo_stable=true`, verdict `SUPPORTED_IMPROVEMENT`, grade `CONTROLLED_EXPERIMENT_EVIDENCE`.
- In live Playwright browser QA (0-match new user creating `EXP-d5d2f80b`), the service cleanly reported `INSUFFICIENT_EVIDENCE` / `THEORETICAL_SUITABILITY`.
