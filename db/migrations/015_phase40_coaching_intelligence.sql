-- 015: Phase 40 — Persistent Match Intelligence, Gamer DNA, Recurring Mistakes,
-- Football Knowledge, Coach Sessions, and Training Academy tables.
-- Reversible via db/migrations/rollback/015_phase40_coaching_intelligence_down.sql.

BEGIN;

CREATE TABLE IF NOT EXISTS public.phase40_match_squad_snapshot (
    snapshot_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES public.user_profile(id) ON DELETE CASCADE,
    game_version            TEXT NOT NULL CHECK (game_version IN ('FC26', 'FC27')),
    formation               TEXT NOT NULL,
    tactical_profile        TEXT NOT NULL DEFAULT 'BALANCED',
    tactical_instructions   JSONB NOT NULL DEFAULT '{}'::jsonb,
    slots                   JSONB NOT NULL DEFAULT '[]'::jsonb,
    snapshot_sha256         TEXT NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_p40_snapshot_user
    ON public.phase40_match_squad_snapshot (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.phase40_match_record (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id                TEXT NOT NULL UNIQUE,
    user_id                 UUID NOT NULL REFERENCES public.user_profile(id) ON DELETE CASCADE,
    video_id                TEXT,
    game_version            TEXT NOT NULL CHECK (game_version IN ('FC26', 'FC27')),
    game_patch              TEXT NOT NULL DEFAULT 'PATCH_1.02',
    gameplay_mode           TEXT NOT NULL DEFAULT 'COMPETITIVE_RIVALS',
    platform                TEXT NOT NULL DEFAULT 'PC',
    match_result            JSONB NOT NULL DEFAULT '{}'::jsonb,
    duration_seconds        DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    is_partial_match        BOOLEAN NOT NULL DEFAULT FALSE,
    formation               TEXT NOT NULL DEFAULT '4-3-3',
    tactical_instructions   JSONB NOT NULL DEFAULT '{}'::jsonb,
    player_roles            JSONB NOT NULL DEFAULT '[]'::jsonb,
    squad_snapshot_id       UUID REFERENCES public.phase40_match_squad_snapshot(snapshot_id) ON DELETE SET NULL,
    opponent_context        JSONB NOT NULL DEFAULT '{}'::jsonb,
    provenance              TEXT NOT NULL CHECK (provenance IN (
                                'REAL_VIDEO_DECODED',
                                'IMPORTED_MATCH_TRACE',
                                'MANUAL_ANNOTATION',
                                'SYNTHETIC_FIXTURE'
                            )),
    observation_quality     TEXT NOT NULL DEFAULT 'MODERATE' CHECK (observation_quality IN (
                                'HIGH', 'MODERATE', 'LOW', 'INSUFFICIENT'
                            )),
    tracking_coverage_pct   DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    telemetry_summary       JSONB NOT NULL DEFAULT '{}'::jsonb,
    feature_metrics         JSONB NOT NULL DEFAULT '{}'::jsonb,
    tactical_events         JSONB NOT NULL DEFAULT '[]'::jsonb,
    coaching_findings       JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_clips          JSONB NOT NULL DEFAULT '[]'::jsonb,
    analysis_version        TEXT NOT NULL DEFAULT 'phase40.v1',
    content_sha256          TEXT NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, content_sha256, analysis_version)
);

CREATE INDEX IF NOT EXISTS ix_p40_match_user_created
    ON public.phase40_match_record (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_p40_match_user_version
    ON public.phase40_match_record (user_id, game_version, game_patch, provenance);

CREATE TABLE IF NOT EXISTS public.phase40_gamer_profile (
    user_id                 UUID PRIMARY KEY REFERENCES public.user_profile(id) ON DELETE CASCADE,
    self_reported_style     JSONB NOT NULL DEFAULT '{}'::jsonb,
    observed_dna            JSONB NOT NULL DEFAULT '{}'::jsonb,
    archetype_assessment    JSONB NOT NULL DEFAULT '{}'::jsonb,
    pro_schema_preview      JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_version           TEXT NOT NULL DEFAULT 'gamer_dna.v1',
    eligible_match_count    INTEGER NOT NULL DEFAULT 0,
    synthetic_excluded_count INTEGER NOT NULL DEFAULT 0,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.phase40_recurring_mistake (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES public.user_profile(id) ON DELETE CASCADE,
    diagnostic_code         TEXT NOT NULL,
    game_version            TEXT NOT NULL DEFAULT 'ALL',
    game_patch              TEXT NOT NULL DEFAULT 'ALL',
    total_occurrences       INTEGER NOT NULL DEFAULT 0,
    total_opportunities     INTEGER NOT NULL DEFAULT 0,
    normalized_rate         DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    severity_score          DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    confidence_level        TEXT NOT NULL DEFAULT 'LOW',
    root_cause_hypotheses   JSONB NOT NULL DEFAULT '[]'::jsonb,
    supporting_clips        JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, diagnostic_code, game_version, game_patch)
);

CREATE TABLE IF NOT EXISTS public.phase40_training_plan (
    plan_id                 TEXT PRIMARY KEY,
    user_id                 UUID NOT NULL REFERENCES public.user_profile(id) ON DELETE CASCADE,
    game_version            TEXT NOT NULL DEFAULT 'FC27',
    objectives              JSONB NOT NULL DEFAULT '[]'::jsonb,
    exercises               JSONB NOT NULL DEFAULT '[]'::jsonb,
    bkt_states              JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_p40_training_user
    ON public.phase40_training_plan (user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS public.phase40_training_attempt (
    attempt_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES public.user_profile(id) ON DELETE CASCADE,
    plan_id                 TEXT REFERENCES public.phase40_training_plan(plan_id) ON DELETE SET NULL,
    exercise_id             TEXT NOT NULL,
    skill_code              TEXT NOT NULL,
    selected_option_id      TEXT NOT NULL,
    is_optimal_or_defensible BOOLEAN NOT NULL DEFAULT FALSE,
    feedback_summary        TEXT NOT NULL,
    prior_p_mastery         DOUBLE PRECISION NOT NULL DEFAULT 0.25,
    posterior_p_mastery     DOUBLE PRECISION NOT NULL DEFAULT 0.25,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_p40_attempt_user
    ON public.phase40_training_attempt (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.phase40_coach_session (
    session_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES public.user_profile(id) ON DELETE CASCADE,
    title                   TEXT NOT NULL DEFAULT 'Personal Coaching Session',
    game_version            TEXT NOT NULL DEFAULT 'FC27',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.phase40_coach_message (
    message_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id              UUID NOT NULL REFERENCES public.phase40_coach_session(session_id) ON DELETE CASCADE,
    user_id                 UUID NOT NULL REFERENCES public.user_profile(id) ON DELETE CASCADE,
    role                    TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content                 TEXT NOT NULL,
    structured_payload      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_p40_coach_msg_session
    ON public.phase40_coach_message (session_id, created_at ASC);

CREATE TABLE IF NOT EXISTS public.phase40_knowledge_entry (
    entry_id                TEXT PRIMARY KEY,
    source_title            TEXT NOT NULL,
    source_url              TEXT NOT NULL,
    game_version            TEXT NOT NULL,
    patch_version           TEXT NOT NULL,
    topic                   TEXT NOT NULL,
    mechanic                TEXT NOT NULL,
    publication_date        TEXT NOT NULL,
    verification_status     TEXT NOT NULL CHECK (verification_status IN (
                                'OFFICIAL_FACT', 'RESEARCH_METHODOLOGY', 'COMMUNITY_OBSERVATION', 'UNVERIFIED_CLAIM'
                            )),
    applicability           TEXT NOT NULL,
    factual_summary         TEXT NOT NULL,
    tags                    JSONB NOT NULL DEFAULT '[]'::jsonb
);

COMMIT;
