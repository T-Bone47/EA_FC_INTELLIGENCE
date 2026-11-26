# Phase 43 Statistical & Bayesian Inference Models

## 1. Match-Clustered Sampling Unit
- `ExperimentAnalysisService` (`backend/services/experiment_analysis_service.py`) strictly sets `unit_of_analysis = "MATCH_CLUSTER_AGGREGATE"`.
- Individual video frames are never treated as independent samples (avoiding intra-match temporal autocorrelation inflation).
- Matches tagged `SYNTHETIC_FIXTURE` or from another `game_version` (`FC26` vs `FC27`) are automatically excluded (`weight = 0.0`) before estimation.

## 2. Frequentist, Non-Parametric & Bayesian Estimators
Implemented using `scipy.stats` (`ttest_rel`, `ttest_ind`, `bootstrap`, `norm`) and `numpy`:
- **Arm Summaries:** `eligible_match_count`, `mean`, `median`, `sd`, `iqr`, and opportunity-normalized rate (`sum(num) / sum(denom)`).
- **Relative Improvement Zero Guard:** `relative_improvement = signed_improvement / abs(mean_a)` strictly guarded by `abs(mean_a) > 1e-6`, returning `None` when baseline mean is `0.0`.
- **Effect Size & Confidence:** Bias-corrected Hedges' `g`, 1500-resample 95% percentile bootstrap CI (`bootstrap_ci_95`), and leave-one-match-out sign stability check (`sensitivity_leave_one_out_stable`).
- **Normal-Normal Conjugate Bayesian Posterior:** Computes both:
  - `bayesian_posterior_prob_b_better`: `P(delta improves over baseline | data)`
  - `posterior_prob_meaningful`: `P(improvement >= minimum_meaningful_improvement | data)`
- **Confounder & Sample-Size Controls:** Flags `patch_drift_detected`, `mode_mismatch_detected`, `opponent_imbalance_detected`, downgrading confounded or LOO-unstable trials conservatively to `INCONCLUSIVE`. `estimate_required_sample_size` calculates recommended per-arm matches for target alpha/power.
