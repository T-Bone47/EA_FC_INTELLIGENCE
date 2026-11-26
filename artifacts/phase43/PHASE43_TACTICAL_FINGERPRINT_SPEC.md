# Phase 43C Tactical Fingerprint Engine Specification

## 1. Nominal vs Observed Phase Separation
Real EA FC matches rarely maintain a static pre-match formation diagram across attacking and defensive phases. `TacticalFingerprintEngine` (`backend/services/tactical_fingerprint_engine.py`) extracts `TacticalFingerprint` records keyed uniquely per `(user_id, match_id, snapshot_id)` while keeping nominal formation labels (`nominal_formation`) strictly separated from observed shapes (`observed_in_possession_shape`, `observed_out_of_possession_shape`).

## 2. Four-Phase Tactical Metrics (`PhaseMetricBlock`)
Every `TacticalFingerprint` records four distinct phase blocks:
1. **`IN_POSSESSION`:** `possession_share`, `central_progression` (or `central_progression_share`), `wing_utilization`, `passing_risk`, `chance_creation_xt_proxy`, and `width_proxy_m` (`round(wing_utilization * 62.0, 2)` when supported).
2. **`OUT_OF_POSSESSION`:** `defensive_compactness`, `pressing_intensity`, `tactical_discipline`, `def_to_mid_gap_m`.
3. **`ATTACKING_TRANSITION`:** `attacking_directness`, `passing_tempo`.
4. **`DEFENSIVE_TRANSITION`:** `transition_opportunities`, `exposed_transitions`, opportunity-normalized `conceded_transition_rate` (`exposed_transitions / transition_opportunities` whenever denominator `> 0`), `defensive_transition_management`.

## 3. Spatial Shape Inference & Calibration Coverage Gate
- **Adequacy Threshold (`cov >= 35.0%`):** Matches with tracking coverage below `35.0%` retain `observed_in_possession_shape = "UNKNOWN_INSUFFICIENT_SPATIAL_DATA"` and `observed_out_of_possession_shape = "UNKNOWN_INSUFFICIENT_SPATIAL_DATA"` with an explicit uncertainty warning rather than guessing geometry.
- **Calibration State Grading:** Derived from telemetry (`MODERATE` when `cov >= 70%`, `COARSE` when `cov >= 40%`, else `INSUFFICIENT`).
- **Observed In-Possession Classification:** `WIDE_3_2_5_OR_OVERLAPPING_WING_SHAPE` (`wing_utilization >= 0.65`), `CENTRAL_BOX_OVERLOAD_SHAPE` (`central_progression >= 0.65`), or `BALANCED_BUILD_UP_SHAPE`.
- **Observed Out-of-Possession Classification:** `STRETCHED_HIGH_PRESS_WITH_CENTRAL_GAP` (`pressing_intensity >= 0.65` and `defensive_compactness < 0.55`), `COMPACT_HIGH_PRESS_4_4_2_OR_4_2_3_1` (`pressing_intensity >= 0.65`), `COMPACT_MID_LOW_BLOCK` (`defensive_compactness >= 0.62`), or `LOOSE_MID_BLOCK`.

## 4. Intended vs Observed Drift Auditing (`IntendedVsObservedDelta`)
When linked to a `TacticalConfigurationSnapshot`, the engine evaluates three alignment checks (`ALIGNED` vs `DRIFTED`):
- `press_intensity_vs_line_height`: Compares observed `pressing_intensity` against normalized `line_height / 100.0` (drifted if `|delta| > 0.16`).
- `wing_utilization_vs_width_setting`: Compares observed `wing_utilization` against `width_setting / 100.0` (drifted if `|delta| > 0.16`).
- `press_rest_defense_cost`: Flags `DRIFTED` on `HIGH_PRESS` / `PRESSING` snapshots when opportunity-normalized `conceded_transition_rate > 0.28`.

## 5. Missing-Data & Synthetic Provenance Discipline
- Unsupported metrics remain Python `None` (`null` in JSON) and are enumerated explicitly in per-phase and top-level `unsupported_metrics`.
- `SYNTHETIC_FIXTURE` records receive an explicit warning noting demo-only status and are excluded automatically from real tactical experimentation pools.
