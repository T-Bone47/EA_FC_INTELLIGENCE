# Phase 43 Personal Meta & Closed-Loop Feedback Intelligence

## 1. Strict User, Edition & Patch Partitioning
`PersonalMetaService` (`backend/services/personal_meta_service.py`) constructs `PersonalMetaProfile` keyed strictly by `(user_id, game_version, game_patch)`:
- Excludes all `SYNTHETIC_FIXTURE` records cleanly (`synthetic_excluded_count`).
- Prevents merging `FC26` and `FC27` records or mixing gameplay patches.
- Never modifies frozen `V3.2.1` card weights (`frozen_v321_weights_altered = False`).

## 2. Structured Meta Breakdown (`phase43_personal_meta`)
- `preferred_formations` & `formation_breakdown` (wins/draws/losses, transition exposure, compactness)
- `effective_player_role_combinations` (extracted from user's verified snapshots, tracking `ROLE_PLUS`/`ROLE_PLUS_PLUS` frequency)
- `successful_partnerships` (paired synergy highlights >= `0.65`)
- `experiment_history` (all user trial outcomes & status)
- `patch_dependent_behaviour` (explicit per-patch match breakdowns highlighted side-by-side without cross-patch pooling)
- `confidence_and_evidence_maturity` (`PRELIMINARY`, `EMERGING`, `VALIDATED` tier with calibrated maturity confidence)

## 3. Closed-Loop Recommendation Feedback Ledger (`phase43_recommendation_feedback`)
Implemented in `Migration 020` + `PersonalMetaService.record_feedback` / `GET & POST /api/phase43/feedback`:
- Links `recommendation_id` + `recommendation_type` -> `user_action` (`ACCEPTED`, `MODIFIED`, `REJECTED`, `IGNORED`, `DEFERRED`, `COMPLETED`) -> `snapshot_id` -> `experiment_id` -> `observation_id` -> `estimated_effect`, `uncertainty_summary`, and `model_version`.
