# Phase 43 Baseline & Defect Audit

## 1. Repository & Service Health Snapshot
- **Repository:** `https://github.com/T-Bone47/EA_FC_INTELLIGENCE.git` (`main` branch, HEAD `014d8d4` synced cleanly before uncommitted Phase 43 workspace work).
- **Local Services:** Embedded PostgreSQL 16.16 (`127.0.0.1:5432`), FastAPI + Uvicorn (`0.0.0.0:8000`), and Vite dev server (`http://localhost:5173`).
- **Database Migration Integrity:** Checked `scripts/setup_database.py` sha256 tracking over `db/migrations/001`–`019`. Added `db/migrations/020_phase43_complete_experiment_lab.sql` and reversible rollback `db/migrations/rollback/020_phase43_complete_experiment_lab_down.sql`. Applied twice cleanly with zero errors (`skip (applied): 020_phase43_complete_experiment_lab.sql`).

## 2. Resolved Defects Identified in Phase 42 / Early Phase 43 Audit
1. **`test_phase30_card_lab.py` Starlette 0.37 TestClient Fixture Error (`2 errors`):**
   - Root cause: `TestClient(create_app(), base_url="http://127.0.0.1", client=("127.0.0.1", 53002))` failed because Starlette `0.37` removed the `client=` keyword argument on `TestClient.__init__`.
   - Fix applied: Added local ASGI wrapper `_with_client_addr(app, "127.0.0.1", 53002)` setting `scope["client"]` (matching `backend/tests/test_zero_budget_research.py`), resolving both setup errors (`backend/tests/test_phase30_card_lab.py`: `6 passed`).
2. **`TACTICAL_LAB` Comparison Intent Collision (`PersonalCoachOrchestrator.classify_intent`):**
   - Root cause: Queries containing `"compare "` or `" vs "` matched `TaskIntent.PLAYER_COMPARISON` before reaching `TACTICAL_LAB` / formation comparison checks.
   - Fix applied: Prioritized `TACTICAL_RECOMMENDATION` and `compare_formations` / `compare_tactical_configurations` selection when `source_route` is `TACTICAL_LAB` or query compares tactical formations/configurations without 2 selected player cards.
3. **FastAPI Route Ordering Shadowing `/experiments/suggest` & `/experiments/sample-size`:**
   - Root cause: `/experiments/{experiment_id}` intercepted `GET /api/phase43/experiments/suggest` returning `404`.
   - Fix applied: Reordered `/experiments/suggest`, `/experiments/preview`, and `/experiments/sample-size` ahead of `/experiments/{experiment_id}` in `backend/api/routes/phase43_tactical_lab.py`.
4. **`PersonalFormationEngine` Cross-Repository Lookups:**
   - Replaced erroneous `p40_repo.list_football_iq` with `Phase41Repository.list_decision_windows` + `FootballIQEngine.compute_profile`, and added optional `game_version` filtering to `Phase43Repository.list_fingerprints`.
5. **Pre-existing Legacy/Threshold Failures (Preserved Honestly Unaltered):**
   - `backend/tests/test_engine_adversarial_phase7.py` (`9 failed`): legacy Phase 7 V2 assertions superseded by frozen V3.2.1 math.
   - `backend/tests/test_engine_v3_real_data.py` (`4 failed`): `TestRD3OvrCorrelationBand[CB/ST/CM]` and `TestRD4TacticalResponsiveness[CB]` empirical frozen V3.2.1 threshold probes. Frozen `recommendation_engine_v3.py` and `v3_config.py` remain strictly untouched.
