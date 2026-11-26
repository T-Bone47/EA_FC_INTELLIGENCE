# Phase 44 Feature Definitions & Provenance Specification

## 1. Schema Contract (`StyleFeatureObservationV2`)
Every feature stored or returned by `GamerDNAV2Engine` (`backend/domain/phase44_models.py`) records:
- `feature_id`: Canonical key in `FEATURE_CATALOG_V2`
- `feature_group`: Enum (`POSSESSION_BUILDUP` .. `TECHNICAL_EXECUTION`)
- `mathematical_definition`: Human-auditable formula summary
- `units`: `ratio_0_1`
- `game_version` / `game_patch` / `gameplay_mode`: Context filters enforced before aggregation
- `raw_value` / `normalized_value`: Bounded `[0, 1]` weighted mean and leak-free robust z-score (`(w_mean - median) / iqr`)
- `eligible_observations`, `opportunity_denominator`, `match_count`, `coverage`: Sample counts and coverage ratio across eligible matches
- `uncertainty`: Conservative Kish effective-sample standard error (`max(0.02, std / sqrt(n_eff))`)
- `source_type`: `OBSERVED`, `INFERRED`, `INTERPOLATED`, `USER_REPORTED`, `CANDIDATE_MULTIMODAL_OBSERVATION_UNVERIFIED`, `SYNTHETIC_FIXTURE`, or `UNKNOWN`
- `is_proficiency_only`: Boolean enforcing Group G separation
- `evidence_references`: Verified `match:<match_id>` citations

## 2. Backward-Compatible Telemetry Mapping
`_extract_feature_from_match()` bridges Phase 40–43 telemetry (`possession_share`, `pass_accuracy`, `defensive_transition_management`, `central_progression`, `wing_utilization`, `attacking_directness`, `passing_tempo`, `passing_risk`, `pressing_intensity`, `defensive_compactness`, `tactical_discipline`) alongside direct `FEATURE_CATALOG_V2` keys and Phase 41 Decision Replay windows without altering Phase 40–43 storage formats.

## 3. Button / Input Guardrail
Controller button presses, analog stick angles, and skill-move triggers are never inferred or hallucinated when raw controller logs are absent; `defensive_player_selection_activity` reflects observable active-defender switch frequency proxies only when present in telemetry.
