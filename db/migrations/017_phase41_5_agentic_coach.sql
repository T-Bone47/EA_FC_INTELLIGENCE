-- 017: Phase 41.5 — Hybrid Agentic Football Coach Sessions, Telemetry & Squad Proposals
-- Reversible via db/migrations/rollback/017_phase41_5_agentic_coach_down.sql.

BEGIN;

ALTER TABLE public.phase40_coach_session
    ADD COLUMN IF NOT EXISTS active_squad_id UUID,
    ADD COLUMN IF NOT EXISTS active_match_id TEXT,
    ADD COLUMN IF NOT EXISTS conversation_summary TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS user_preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS last_provider TEXT NOT NULL DEFAULT 'DETERMINISTIC',
    ADD COLUMN IF NOT EXISTS last_model TEXT NOT NULL DEFAULT 'deterministic-coach';

CREATE TABLE IF NOT EXISTS public.phase41_5_provider_usage_log (
    usage_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID REFERENCES public.user_profile(id) ON DELETE SET NULL,
    provider            TEXT NOT NULL,
    model               TEXT NOT NULL,
    intent_category     TEXT NOT NULL DEFAULT 'GENERAL',
    prompt_tokens       INTEGER NOT NULL DEFAULT 0,
    completion_tokens   INTEGER NOT NULL DEFAULT 0,
    provider_requests   INTEGER NOT NULL DEFAULT 1,
    reported_cost_usd   DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    status              TEXT NOT NULL DEFAULT 'OK',
    latency_ms          DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_p41_5_usage_created
    ON public.phase41_5_provider_usage_log (created_at DESC, provider);

CREATE TABLE IF NOT EXISTS public.phase41_5_squad_proposal (
    proposal_id         TEXT PRIMARY KEY,
    user_id             UUID NOT NULL REFERENCES public.user_profile(id) ON DELETE CASCADE,
    session_id          UUID REFERENCES public.phase40_coach_session(session_id) ON DELETE SET NULL,
    target_squad_id     UUID,
    game_version        TEXT NOT NULL CHECK (game_version IN ('FC26', 'FC27')),
    formation           TEXT NOT NULL,
    tactical_profile    TEXT NOT NULL DEFAULT 'BALANCED',
    proposal_payload    JSONB NOT NULL DEFAULT '{}'::jsonb,
    previous_snapshot   JSONB DEFAULT NULL,
    status              TEXT NOT NULL DEFAULT 'PENDING_CONFIRMATION' CHECK (
                            status IN ('PENDING_CONFIRMATION', 'CONFIRMED_APPLIED', 'ROLLED_BACK', 'DISMISSED')
                        ),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_p41_5_proposal_user
    ON public.phase41_5_squad_proposal (user_id, created_at DESC);

COMMIT;
