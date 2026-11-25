-- 016: Phase 41 — Advanced Decision Intelligence, Counterfactual Evaluations,
-- Football IQ Profiles, Decision Training Scenarios, and Blind-Review Annotations.
-- Reversible via db/migrations/rollback/016_phase41_decision_intelligence_down.sql.

BEGIN;

CREATE TABLE IF NOT EXISTS public.phase41_decision_opportunity (
    window_id               TEXT PRIMARY KEY,
    match_id                TEXT NOT NULL,
    user_id                 UUID NOT NULL REFERENCES public.user_profile(id) ON DELETE CASCADE,
    video_id                TEXT,
    cluster_id              TEXT NOT NULL,
    decision_type           TEXT NOT NULL,
    status                  TEXT NOT NULL CHECK (status IN (
                                'EVALUATED',
                                'ABSTAINED_INSUFFICIENT_CONTEXT',
                                'SYNTHETIC_EXCLUDED_DIAGNOSTIC'
                            )),
    provenance              TEXT NOT NULL CHECK (provenance IN (
                                'REAL_VIDEO_DECODED',
                                'IMPORTED_MATCH_TRACE',
                                'MANUAL_ANNOTATION',
                                'SYNTHETIC_FIXTURE'
                            )),
    pre_action_cutoff_sec   DOUBLE PRECISION NOT NULL,
    action_timestamp_sec    DOUBLE PRECISION NOT NULL,
    observation_adequacy    TEXT NOT NULL CHECK (observation_adequacy IN (
                                'ADEQUATE',
                                'PARTIAL_WITH_UNCERTAINTY',
                                'INSUFFICIENT_ABSTAIN'
                            )),
    calibration_state       TEXT NOT NULL DEFAULT 'GOOD',
    coverage_pct            DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    pre_action_state        JSONB NOT NULL DEFAULT '{}'::jsonb,
    post_action_outcome     JSONB DEFAULT NULL,
    candidate_actions       JSONB NOT NULL DEFAULT '[]'::jsonb,
    counterfactual_comparison JSONB NOT NULL DEFAULT '{}'::jsonb,
    regret_estimate         DOUBLE PRECISION,
    normalized_regret        DOUBLE PRECISION,
    uncertainty_payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
    analysis_version        TEXT NOT NULL DEFAULT 'phase41.v1',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_p41_decision_user_match
    ON public.phase41_decision_opportunity (user_id, match_id, action_timestamp_sec ASC);
CREATE INDEX IF NOT EXISTS ix_p41_decision_regret
    ON public.phase41_decision_opportunity (user_id, regret_estimate DESC NULLS LAST);

CREATE TABLE IF NOT EXISTS public.phase41_football_iq_profile (
    user_id                 UUID PRIMARY KEY REFERENCES public.user_profile(id) ON DELETE CASCADE,
    eligible_match_count    INTEGER NOT NULL DEFAULT 0,
    eligible_decision_windows INTEGER NOT NULL DEFAULT 0,
    synthetic_excluded_count INTEGER NOT NULL DEFAULT 0,
    overall_football_iq     DOUBLE PRECISION,
    confidence              TEXT NOT NULL DEFAULT 'INSUFFICIENT',
    dimensions              JSONB NOT NULL DEFAULT '[]'::jsonb,
    top_regret_clusters     JSONB NOT NULL DEFAULT '[]'::jsonb,
    calibration_caveat      TEXT NOT NULL DEFAULT 'Heuristic Stage 1/2 valuation',
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.phase41_training_scenario (
    scenario_id             TEXT PRIMARY KEY,
    user_id                 UUID NOT NULL REFERENCES public.user_profile(id) ON DELETE CASCADE,
    match_id                TEXT NOT NULL,
    window_id               TEXT NOT NULL,
    skill_dimension         TEXT NOT NULL,
    provenance              TEXT NOT NULL CHECK (provenance IN (
                                'REAL_VIDEO_DECODED',
                                'IMPORTED_MATCH_TRACE',
                                'MANUAL_ANNOTATION',
                                'SYNTHETIC_FIXTURE'
                            )),
    payload                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_p41_scenario_user
    ON public.phase41_training_scenario (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.phase41_decision_annotation (
    annotation_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES public.user_profile(id) ON DELETE CASCADE,
    window_id               TEXT NOT NULL,
    match_id                TEXT NOT NULL,
    annotator_role          TEXT NOT NULL DEFAULT 'PLAYER_SELF',
    best_option_id          TEXT,
    defensible_option_ids   JSONB NOT NULL DEFAULT '[]'::jsonb,
    disagreement_note       TEXT NOT NULL DEFAULT '',
    blind_review_completed  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_p41_annotation_window
    ON public.phase41_decision_annotation (user_id, window_id);

COMMIT;
