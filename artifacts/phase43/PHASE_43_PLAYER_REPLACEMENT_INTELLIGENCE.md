# Phase 43 Player Replacement & Counterfactual Intelligence

## 1. Behavior & Tactics Before Coin Spending (`ReplacementExperimentService`)
Before suggesting transfer purchases, `ReplacementExperimentService` (`backend/services/replacement_experiment_service.py`) executes a diagnostic triage hierarchy:
1. Insufficient match data (`< 1` non-synthetic match) -> `INSUFFICIENT_MATCH_EVIDENCE`
2. Recurring gamer decision pattern (`GAMEPLAY_PRACTICE`) -> `DECISION_PRACTICE_FIRST`
3. Tactical / FC IQ role focus mismatch -> `TACTICAL_OR_ROLE_ADJUSTMENT_FIRST`
4. Sustained capability gap -> `TEST_REPLACEMENT_EXPERIMENT` (holding other 10 players and tactics constant)

**Four-Option Comparison (`candidate_comparisons`):**
Outputs structured trade-offs across `CURRENT_PLAYER`, `NO_COIN_TACTICAL_ADJUSTMENT`, `CANDIDATE_ALT_A`, and `CANDIDATE_ALT_B` (via frozen V3.2.1 `PersonalGameplayFitService`). Coin prices are never guessed (`MARKET_PRICE_UNAVAILABLE`). Persistent studies log to `phase43_replacement_experiment`.

## 2. Hypothetical Counterfactual Configuration Lab (`TacticalCounterfactualService`)
Compares two immutable `TacticalConfigurationSnapshot` versions prior to live matches:
- **Spatial Zone Geometry Deltas (`zone_geometry_deltas`):** `passing_outlets_delta`, `zone14_overloads_delta`, `midfield_congestion_delta`, `attacking_width_delta_m`, `defensive_coverage_delta`, `transition_exposure_delta`, `role_conflicts_count`, and `spatial_occupation_shift`.
- **Epistemic Separation (`epistemic_classification`):** Explicitly tags `ACTUAL_OBSERVED`, `HYPOTHETICAL_MODELED`, `HEURISTIC_MOVEMENT`, and `UNSUPPORTED_ASSUMPTION`.
- **Parameter Sensitivity Sweep (`sensitivity_sweep`):** Evaluates a 3x3 perturbation grid (`line_height += {-10, 0, +10}`, `width_setting += {-10, 0, +10}`) so gamers see stability boundaries before testing live.
