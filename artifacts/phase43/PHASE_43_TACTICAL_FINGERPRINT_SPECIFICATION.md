# Phase 43 Tactical Fingerprint Specification

## 1. Epistemic Design
- `TacticalFingerprintEngine` (`backend/services/tactical_fingerprint_engine.py`) separates observed gameplay geometry from pre-match nominal labels (`nominal_formation` vs `observed_in_possession_shape` and `observed_out_of_possession_shape`).
- Unmeasured or unobservable proxy metrics remain `None` (never defaulted to `0.0`).
- `SYNTHETIC_FIXTURE` sources are downgraded to `EvidenceGrade.UNSUPPORTED_CAUSAL_INFERENCE` and excluded from real tactical adaptation.

## 2. Four Football Phases & Supported Proxy Metrics
1. **IN_POSSESSION:** `possession_share`, `central_progression`, `wing_utilization`, `passing_risk`, `chance_creation_xt_proxy`, `attacking_depth`, `half_space_occupation`, `passing_outlet_availability`, `forward_support`, `overlapping_movement`, `width_proxy_m`.
2. **OUT_OF_POSSESSION:** `defensive_compactness`, `pressing_intensity`, `tactical_discipline`, `def_to_mid_gap_m`, `defensive_width`, `defensive_line_depth`, `central_coverage`, `recovery_positioning`, `defensive_overloads`.
3. **ATTACKING_TRANSITION:** `attacking_directness`, `passing_tempo`.
4. **DEFENSIVE_TRANSITION:** `transition_opportunities`, `exposed_transitions`, opportunity-normalized `conceded_transition_rate`, `defensive_transition_management`.

## 3. Per-Metric Provenance (`FingerprintMetricDetail`) & Abstention Guard
Every metric recorded in `metric_details` includes:
- `mathematical_definition`, `units`, `eligible_observation_criteria`
- `observation_count`, `match_count`, `coverage`, calibrated `confidence`
- `model_version` (`phase43.fingerprint.v1`), `evidence_references`, and `abstained_reason`

**Mandatory Visibility Abstention:**
If `visible_outfield_players < 14` or `calibration_state == "INSUFFICIENT"` or `tracking_coverage_pct < 35.0`:
- `team_compactness_abstained = True`
- Team-wide shape/compactness/width proxies (`defensive_compactness`, `defensive_width`, `defensive_line_depth`, `def_to_mid_gap_m`, `attacking_depth`, `half_space_occupation`, `width_proxy_m`) are nulled (`None`) with explicit `ABSTAINED_VISIBLE_PLAYERS_BELOW_14` or `ABSTAINED_INSUFFICIENT_COVERAGE_OR_CALIBRATION`.
