-- 018: Phase 42 — Universal Co-Pilot Context, Coaching Preferences, Adaptive Training Metadata
-- Reversible via db/migrations/rollback/018_phase42_copilot_training_loop_down.sql.

BEGIN;

ALTER TABLE public.phase40_coach_session
    ADD COLUMN IF NOT EXISTS source_route TEXT NOT NULL DEFAULT '/coach',
    ADD COLUMN IF NOT EXISTS context_envelope JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS last_context_freshness_ts TIMESTAMPTZ DEFAULT NULL;

ALTER TABLE public.phase41_5_provider_usage_log
    ADD COLUMN IF NOT EXISTS ttft_ms DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    ADD COLUMN IF NOT EXISTS tools_sent_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS fallback_used BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS public.phase42_user_coach_preferences (
    user_id                     UUID PRIMARY KEY REFERENCES public.user_profile(id) ON DELETE CASCADE,
    preferred_formation         TEXT,
    preferred_tactical_profile  TEXT,
    preferred_provider          TEXT NOT NULL DEFAULT 'AUTO',
    coach_style                 TEXT NOT NULL DEFAULT 'CONCISE_TACTICAL',
    consent_saved_default       BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.phase40_training_attempt
    ADD COLUMN IF NOT EXISTS scenario_id TEXT DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS window_id TEXT DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS decision_category TEXT NOT NULL DEFAULT 'GENERAL',
    ADD COLUMN IF NOT EXISTS confidence_tier TEXT NOT NULL DEFAULT 'MODERATE',
    ADD COLUMN IF NOT EXISTS outcome_revealed_after BOOLEAN NOT NULL DEFAULT TRUE;

CREATE TABLE IF NOT EXISTS public.phase42_cv_checkpoint (
    checkpoint_id       TEXT PRIMARY KEY,
    architecture        TEXT NOT NULL,
    dataset_manifest    TEXT NOT NULL,
    onnx_path           TEXT,
    map_50              DOUBLE PRECISION,
    precision_score     DOUBLE PRECISION,
    recall_score        DOUBLE PRECISION,
    idf1                DOUBLE PRECISION,
    hota_proxy          DOUBLE PRECISION,
    fps_rtx3050         DOUBLE PRECISION,
    peak_vram_mb        DOUBLE PRECISION,
    license_name        TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'REGISTERED',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
