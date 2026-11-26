-- 019: Phase 43 — Personal Tactical Experimentation Lab, Immutable Snapshots,
-- Phase-Separated Fingerprints, Match-Level Experiments, and Personal Meta Profiles.
-- Reversible via db/migrations/rollback/019_phase43_tactical_experimentation_down.sql.

BEGIN;

ALTER TABLE public.phase40_match_record
    ADD COLUMN IF NOT EXISTS tactical_snapshot_id TEXT DEFAULT NULL;

CREATE TABLE IF NOT EXISTS public.phase43_tactical_snapshot (
    snapshot_id             TEXT PRIMARY KEY,
    user_id                 UUID NOT NULL REFERENCES public.user_profile(id) ON DELETE CASCADE,
    label                   TEXT NOT NULL DEFAULT '',
    game_version            TEXT NOT NULL CHECK (game_version IN ('FC26', 'FC27')),
    game_patch              TEXT NOT NULL DEFAULT 'PATCH_1.04',
    gameplay_mode           TEXT NOT NULL DEFAULT 'COMPETITIVE_RIVALS',
    source_squad_id         UUID REFERENCES public.user_squad(id) ON DELETE SET NULL,
    formation               TEXT NOT NULL,
    tactical_profile        TEXT NOT NULL DEFAULT 'BALANCED',
    build_up_style          TEXT DEFAULT NULL,
    defensive_approach      TEXT DEFAULT NULL,
    line_height             INTEGER DEFAULT NULL,
    width_setting           INTEGER DEFAULT NULL,
    tactical_instructions   JSONB NOT NULL DEFAULT '{}'::jsonb,
    slots                   JSONB NOT NULL DEFAULT '[]'::jsonb,
    chemistry_summary       JSONB DEFAULT NULL,
    cohesion_summary        JSONB DEFAULT NULL,
    partnership_summary     JSONB DEFAULT NULL,
    unknown_fields          JSONB NOT NULL DEFAULT '[]'::jsonb,
    config_hash             TEXT NOT NULL,
    version_number          INTEGER NOT NULL DEFAULT 1,
    parent_snapshot_id      TEXT DEFAULT NULL,
    is_immutable            BOOLEAN NOT NULL DEFAULT TRUE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_p43_snapshot_user
    ON public.phase43_tactical_snapshot (user_id, game_version, game_patch, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_p43_snapshot_hash
    ON public.phase43_tactical_snapshot (user_id, config_hash);

CREATE TABLE IF NOT EXISTS public.phase43_tactical_fingerprint (
    fingerprint_id          TEXT PRIMARY KEY,
    fingerprint_key         TEXT NOT NULL,
    user_id                 UUID NOT NULL REFERENCES public.user_profile(id) ON DELETE CASCADE,
    match_id                TEXT NOT NULL,
    snapshot_id             TEXT REFERENCES public.phase43_tactical_snapshot(snapshot_id) ON DELETE SET NULL,
    game_version            TEXT NOT NULL CHECK (game_version IN ('FC26', 'FC27')),
    game_patch              TEXT NOT NULL DEFAULT 'PATCH_1.04',
    formation               TEXT NOT NULL,
    provenance              TEXT NOT NULL CHECK (provenance IN (
                                'REAL_VIDEO_DECODED',
                                'IMPORTED_MATCH_TRACE',
                                'MANUAL_ANNOTATION',
                                'SYNTHETIC_FIXTURE'
                            )),
    in_possession_metrics   JSONB NOT NULL DEFAULT '{}'::jsonb,
    out_of_possession_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    attacking_transition_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    defensive_transition_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    observed_shapes         JSONB NOT NULL DEFAULT '{}'::jsonb,
    intended_vs_observed_deltas JSONB NOT NULL DEFAULT '[]'::jsonb,
    coverage_pct            DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    calibration_state       TEXT NOT NULL DEFAULT 'UNKNOWN',
    uncertainty_notes       JSONB NOT NULL DEFAULT '[]'::jsonb,
    unsupported_metrics     JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, fingerprint_key)
);

CREATE INDEX IF NOT EXISTS ix_p43_fp_user_match
    ON public.phase43_tactical_fingerprint (user_id, match_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.phase43_experiment (
    experiment_id           TEXT PRIMARY KEY,
    user_id                 UUID NOT NULL REFERENCES public.user_profile(id) ON DELETE CASCADE,
    title                   TEXT NOT NULL,
    hypothesis              TEXT NOT NULL,
    experiment_type         TEXT NOT NULL CHECK (experiment_type IN (
                                'FORMATION_COMPARISON',
                                'TACTICAL_PRESET_COMPARISON',
                                'PLAYER_ROLE_FOCUS_COMPARISON',
                                'DEFENSIVE_HEIGHT_PRESS_COMPARISON',
                                'BUILD_UP_STYLE_COMPARISON',
                                'PLAYER_PARTNERSHIP_COMPARISON',
                                'SINGLE_POSITION_REPLACEMENT',
                                'PERSONAL_PLAYSTYLE_COMPATIBILITY'
                            )),
    game_version            TEXT NOT NULL CHECK (game_version IN ('FC26', 'FC27')),
    baseline_patch          TEXT NOT NULL DEFAULT 'PATCH_1.04',
    gameplay_mode           TEXT NOT NULL DEFAULT 'COMPETITIVE_RIVALS',
    baseline_snapshot_id    TEXT NOT NULL REFERENCES public.phase43_tactical_snapshot(snapshot_id) ON DELETE RESTRICT,
    variant_snapshot_id     TEXT NOT NULL REFERENCES public.phase43_tactical_snapshot(snapshot_id) ON DELETE RESTRICT,
    primary_metric          TEXT NOT NULL DEFAULT 'conceded_transition_rate',
    secondary_metrics       JSONB NOT NULL DEFAULT '[]'::jsonb,
    target_min_matches_per_arm INTEGER NOT NULL DEFAULT 3 CHECK (target_min_matches_per_arm BETWEEN 1 AND 50),
    assignment_design       TEXT NOT NULL DEFAULT 'MATCH_PAIRED_OR_RANDOMIZED_ABBA',
    status                  TEXT NOT NULL DEFAULT 'DRAFT' CHECK (
                                status IN ('DRAFT', 'ACTIVE', 'COMPLETED', 'INCONCLUSIVE', 'PAUSED', 'ARCHIVED')
                            ),
    analysis_cache          JSONB DEFAULT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_p43_experiment_user
    ON public.phase43_experiment (user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS public.phase43_experiment_match_link (
    link_id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id           TEXT NOT NULL REFERENCES public.phase43_experiment(experiment_id) ON DELETE CASCADE,
    user_id                 UUID NOT NULL REFERENCES public.user_profile(id) ON DELETE CASCADE,
    match_id                TEXT NOT NULL,
    arm                     TEXT NOT NULL CHECK (arm IN ('BASELINE_A', 'VARIANT_B')),
    snapshot_id             TEXT REFERENCES public.phase43_tactical_snapshot(snapshot_id) ON DELETE SET NULL,
    game_version            TEXT NOT NULL CHECK (game_version IN ('FC26', 'FC27')),
    game_patch              TEXT NOT NULL DEFAULT 'PATCH_1.04',
    gameplay_mode           TEXT NOT NULL DEFAULT 'COMPETITIVE_RIVALS',
    opponent_archetype      TEXT DEFAULT NULL,
    match_order             INTEGER NOT NULL DEFAULT 0,
    weight                  DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    excluded_reason         TEXT DEFAULT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (experiment_id, match_id)
);

CREATE INDEX IF NOT EXISTS ix_p43_exp_link_user
    ON public.phase43_experiment_match_link (experiment_id, arm, match_order ASC);

CREATE TABLE IF NOT EXISTS public.phase43_personal_meta (
    meta_id                 TEXT PRIMARY KEY,
    user_id                 UUID NOT NULL REFERENCES public.user_profile(id) ON DELETE CASCADE,
    game_version            TEXT NOT NULL CHECK (game_version IN ('FC26', 'FC27')),
    game_patch              TEXT NOT NULL,
    profile_payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    eligible_match_count    INTEGER NOT NULL DEFAULT 0,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, game_version, game_patch)
);

CREATE INDEX IF NOT EXISTS ix_p43_meta_user
    ON public.phase43_personal_meta (user_id, game_version, game_patch);

COMMIT;
