# Phase 43G/H Behavior-First Replacement Triage & Tactical Counterfactual Spec

## 1. Behavior- & Tactics-First Replacement Triage (`ReplacementExperimentService`)
`backend/services/replacement_experiment_service.py` enforces a five-level diagnostic cascade before suggesting coin expenditure or card replacement on a slot (`evaluate_replacement`):
1. **`INSUFFICIENT_MATCH_EVIDENCE`:** Returned immediately whenever the user has `0` non-synthetic matches (`purchase_justified=False`), advising logging 2+ matches in Gameplay Studio first.
2. **`DECISION_PRACTICE_FIRST`:** Triggered when `PersonalGameplayFitService.diagnose_intervention` identifies decision habits (`GAMEPLAY_PRACTICE`) as primary cause (`purchase_justified=False`).
3. **`TACTICAL_OR_ROLE_ADJUSTMENT_FIRST`:** Triggered when tactical spacing, line height, or role focus explain observed exposure without justifying market spending (`purchase_justified=False`); proposes concrete Role/Focus tests first (e.g., `Holding` / `Deep-Lying Playmaker` over 3 matches).
4. **`TEST_REPLACEMENT_EXPERIMENT`:** Only when behavioral/tactical triage flags a genuine player capability bottleneck (`purchase_justified=True`), candidate upgrades are fetched read-only from `PersonalGameplayFitService.recommend_for_gamer(...)`.
5. **Single-Position Experimental Protocol (`proposed_experiment_design`):** Generates an explicit `SINGLE_POSITION_REPLACEMENT` design holding formation and all 10 other slots constant across `>=3` matches per arm.

- **Frozen V3.2.1 & Price Honesty Invariants:** Every `ReplacementTriageReport` enforces `frozen_v321_untouched=True` and `market_price_status="MARKET_PRICE_UNAVAILABLE"` (no invented coin prices).

## 2. Pre-Match Hypothetical Counterfactual Engine (`TacticalCounterfactualService`)
`backend/services/tactical_counterfactual_service.py` (`compare_snapshots`) evaluates two immutable `TacticalConfigurationSnapshot` records before playing live matches:
- **Edition Wall:** Raises `ValueError` if `snap_a.game_version != snap_b.game_version`.
- **Modeled Deltas Computed:**
  - Configuration diffs across `formation`, `tactical_profile`, `build_up_style`, `defensive_approach`, `line_height`, `width_setting`.
  - `rest_defense_risk_delta`: `(press_b - press_a) * 0.45 - (double_pivot_b - double_pivot_a) * 0.14`.
  - `progression_lane_delta`: Directness and width shifts from `PROFILE_DIMENSIONS` + `width_setting`.
  - `cohesion_delta` & `partnership_delta`: Whole-XI alignment and central pivot synergy shifts.
  - `role_familiarity_gaps`: Explicit callouts for variant slots assigned a role at `BASE` or `UNKNOWN` familiarity.
- **Strict Epistemic Label:** Always returns `evidence_grade=EvidenceGrade.THEORETICAL_SUITABILITY` so users never confuse pre-match modeled comparisons with empirical match results.
- **Benchmark Verification:** In `benchmark_phase43_tactical_lab.py` (comparing High-Press `4-3-3` line=76 vs Double-Pivot `4-2-3-1` line=52), reported `grade=THEORETICAL_SUITABILITY` and `rest_defense_risk_delta=-0.248`.
