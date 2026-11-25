-- Rollback 017: Phase 41.5 Agentic Football Coach extensions

BEGIN;

DROP TABLE IF EXISTS public.phase41_5_squad_proposal;
DROP TABLE IF EXISTS public.phase41_5_provider_usage_log;

ALTER TABLE public.phase40_coach_session
    DROP COLUMN IF EXISTS last_model,
    DROP COLUMN IF EXISTS last_provider,
    DROP COLUMN IF EXISTS user_preferences,
    DROP COLUMN IF EXISTS conversation_summary,
    DROP COLUMN IF EXISTS active_match_id,
    DROP COLUMN IF EXISTS active_squad_id;

COMMIT;
