# Phase 43A Bugfix & Database Staging Remediation Report

## 1. Root Cause Analysis: `fc27_staging.observation` & Pre-Existing Test Failures

### 1.1 Resolved `fc27_staging.observation` Defect (`test_zero_budget_research.py`)
- **Symptom in Phase 42 Baseline:** `test_pinned_card_items_end_to_end` in `backend/tests/test_zero_budget_research.py` failed with HTTP `503` because `fc27_staging.observation` was absent in the local embedded PostgreSQL cluster.
- **Root Cause:** Migration `012_fc27_evidence_staging.sql` assumed pre-existing `fc27_staging.source_row` / schema staging state or had not completed against `fc27_staging.observation` cleanly in the embedded database runtime.
- **Non-Destructive Resolution:**
  - Reconstructed `fc27_staging.observation` cleanly from `fc27_staging.source_row` joined with `fc27_staging.identity_review`.
  - Verified exact row count: `20,724` rows in `fc27_staging.observation` (verified via PostgreSQL query).
  - Matched the exact pinned release `MEMBERS_DIGEST` (`7ea30715c31dc9effc47452b61b7a64b875efa852684d34bb6292d82c18780c1`) and attached `immutable_observation`.
  - Applied pending migrations `013`, `014`, `017`, and `018` and synchronized `public.schema_migrations`.
- **Verification:** `pytest backend/tests/test_zero_budget_research.py -v` -> **`9 passed in 12.53s`** (`0` failures), including `test_pinned_card_items_end_to_end`.

### 1.2 Pre-Existing Remaining Baseline Drift (Explicitly Tracked)
A full repository regression run recorded prior to Phase 43B-K modules (`task-7571`) established:
- `929 passed, 11 skipped, 13 failed, 2 errors`.
- **Transparent Classification of Non-Phase-43 Failures:**
  - `9` failures in `backend/tests/test_engine_adversarial_phase7.py`: pre-existing Phase 7 / V3 fixture drift.
  - `4` failures in `backend/tests/test_engine_v3_real_data.py`: pre-existing real-data catalog count/fixture drift.
  - `2` errors in `backend/tests/test_phase30_card_lab.py` (line 82): pre-existing Starlette `TestClient(..., client=...)` signature incompatibility.
  - None of the Phase 26–29, 31, or 37–42 regression tests failed.

### 1.3 Phase 43 Engine Integration Fixes Discovered During Testing
- **`compute_whole_xi_synergy` Signature Compatibility:** Updated `backend/services/tactical_snapshot_service.py` and `backend/services/coach_tools.py` (`evaluate_squad_cohesion`) to pass `cards_by_id` (`SimpleNamespace` card proxies keyed by `entity_id`) matching `compute_whole_xi_synergy(formation, tactical_profile, slots_data, cards_by_id)`.
- **`PartnershipIntelligenceEngine.evaluate_partnership` Unified Router:** Added static router method `evaluate_partnership(...)` in `backend/services/partnership_intelligence.py` routing slot pairs cleanly to `evaluate_cb_cb`, `evaluate_two_strikers`, `evaluate_st_cam`, `evaluate_winger_fullback`, or `evaluate_cm_cdm`.

## 2. Migration `019_phase43_tactical_experimentation.sql` & Rollback Verification
- **Forward Migration:** `db/migrations/019_phase43_tactical_experimentation.sql`
  - Extends `public.phase40_match_record` with `tactical_snapshot_id TEXT DEFAULT NULL`.
  - Creates user-owned tables:
    1. `public.phase43_tactical_snapshot` (indexes on `(user_id, game_version, game_patch, created_at DESC)` and `(user_id, config_hash)`)
    2. `public.phase43_tactical_fingerprint` (unique `(user_id, fingerprint_key)`)
    3. `public.phase43_experiment` (8 enforced `experiment_type` check constraint values; status `'DRAFT'`, `'ACTIVE'`, `'COMPLETED'`, `'INCONCLUSIVE'`, `'PAUSED'`, `'ARCHIVED'`)
    4. `public.phase43_experiment_match_link` (arms `'BASELINE_A'`, `'VARIANT_B'`, unique `(experiment_id, match_id)`, `excluded_reason`)
    5. `public.phase43_personal_meta` (unique `(user_id, game_version, game_patch)`)
- **Rollback Script:** `db/migrations/rollback/019_phase43_tactical_experimentation_down.sql` reverses all 5 tables and drops `tactical_snapshot_id`.
- **Idempotency Verification:** `python scripts/setup_database.py` exited `0` twice (`skip (applied): 019_phase43_tactical_experimentation.sql`, `Database setup complete.`).
