-- Rollback 018: Phase 42 schema additions
BEGIN;

DROP TABLE IF EXISTS public.phase42_cv_checkpoint;
DROP TABLE IF EXISTS public.phase42_user_coach_preferences;

ALTER TABLE public.phase40_training_attempt
    DROP COLUMN IF EXISTS outcome_revealed_after,
    DROP COLUMN IF EXISTS confidence_tier,
    DROP COLUMN IF EXISTS decision_category,
    DROP COLUMN IF EXISTS window_id,
    DROP COLUMN IF EXISTS scenario_id;

ALTER TABLE public.phase41_5_provider_usage_log
    DROP COLUMN IF EXISTS fallback_used,
    DROP COLUMN IF EXISTS tools_sent_count,
    DROP COLUMN IF EXISTS ttft_ms;

ALTER TABLE public.phase40_coach_session
    DROP COLUMN IF EXISTS last_context_freshness_ts,
    DROP COLUMN IF EXISTS context_envelope,
    DROP COLUMN IF EXISTS source_route;

COMMIT;
