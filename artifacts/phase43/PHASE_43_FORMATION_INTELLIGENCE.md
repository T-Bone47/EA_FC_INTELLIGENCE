# Phase 43 Formation Intelligence Specification

## 1. Full 12-Formation Coverage
`PersonalFormationEngine` (`backend/services/personal_formation_engine.py`) evaluates all 12 canonical formations in `FORMATION_SLOTS`:
`4-2-3-1`, `4-3-3`, `4-4-2`, `4-3-2-1`, `4-5-1`, `4-2-2-2`, `4-1-2-1-2`, `3-5-2`, `3-4-2-1`, `3-4-3`, `5-3-2`, and `5-2-1-2`.

## 2. Three Strictly Separated Evidentiary Signals
Each ranked `FormationSuitabilityItem` reports independent fields without conflation:
1. **`theoretical_fit`** (`EvidenceGrade.THEORETICAL_SUITABILITY`): Derived from Gamer DNA style/proficiency dimensions (`wing_utilization`, `central_progression`, `pressing_intensity`, `defensive_transition_management`), recurring transition weaknesses, Football IQ average, saved snapshot `ROLE_PLUS`/`ROLE_PLUS_PLUS` familiarity, and cold-start preference hints (strictly labeled non-empirical).
2. **`observed_performance`** (`EvidenceGrade.OBSERVED_ASSOCIATION`): Aggregated strictly from non-synthetic personal match rest-defense/compactness metrics and verified `TacticalFingerprint` records matching `(user_id, game_version, game_patch)`.
3. **`controlled_experiment_evidence`** (`EvidenceGrade.CONTROLLED_EXPERIMENT_EVIDENCE`): Updated only when Phase 43 match-clustered N-of-1 experiments finish with `SUPPORTED_IMPROVEMENT` or `SUPPORTED_REGRESSION`.

## 3. Side-by-Side Formation Comparison (`compare_formations`)
- Exposed via `GET /api/phase43/formations/compare?formation_a=...&formation_b=...`, `compare_formations` Co-Pilot tool, and the Tactical Lab `Formations, Optimizer & Triage` tab.
- Produces structural rest-defense comparisons, width vs central density differences, unique slot role deltas from `slots_for(...)`, evidence grade, and non-guaranteeing advisory disclaimer.
- Never mutates frozen V3.2.1 scoring weights (`frozen_v321_preserved=True`).
