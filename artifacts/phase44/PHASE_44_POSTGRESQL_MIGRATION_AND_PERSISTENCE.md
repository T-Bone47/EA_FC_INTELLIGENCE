# Phase 44 PostgreSQL Migration & Dual-Mode Persistence

## 1. Schema Migration `021_phase44_gamer_dna_v2.sql`
Applied idempotently to PostgreSQL 16.16 via `C:\Python315\python.exe scripts/setup_database.py` (with full rollback at `db/migrations/rollback/021_phase44_gamer_dna_v2_down.sql`), provisioning **14 tables**:
- `phase44_professional_reference_source`
- `phase44_professional_gamer_reference`
- `phase44_professional_reference_rights`
- `phase44_reference_match`
- `phase44_style_feature_definition`
- `phase44_gamer_style_profile_version`
- `phase44_style_feature_observation`
- `phase44_professional_style_profile_version`
- `phase44_style_archetype_model`
- `phase44_style_similarity_run`
- `phase44_style_similarity_result`
- `phase44_elite_skill_gap`
- `phase44_style_evolution_snapshot`
- `phase44_style_recommendation_feedback`

## 2. Repository & Live FK Fix (`backend/repositories/phase44_repository.py`)
- Enforces user ownership via `user_id::uuid` matching `public.user_profile(id)` on all personal tables and cascade deletes cleanly on `/api/phase44/reset`.
- Live E2E testing caught a PostgreSQL FK violation when `/api/phase44/similarity` inserted `phase44_style_similarity_run` before persisting the referenced `profile_version_id`. Fixed by persisting `save_gamer_profile(prof)` idempotently (`ON CONFLICT (profile_version_id) DO NOTHING`) both in `GET /api/phase44/profile` (`persist=True` default) and before `save_similarity_run(rep)`.
