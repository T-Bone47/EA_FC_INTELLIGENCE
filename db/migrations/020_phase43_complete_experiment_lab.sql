-- Phase 43 Complete Tactical Experimentation Lab, Formation Intelligence & Closed-Loop Schema
-- Adds versioned experiment protocols, assignment adherence, observation records,
-- analysis snapshots, formation fit tracking, replacement studies, and closed-loop feedback.

ALTER TABLE phase43_tactical_snapshot
    ADD COLUMN IF NOT EXISTS mid_match_changes_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS notes TEXT NOT NULL DEFAULT '';

ALTER TABLE phase43_experiment
    DROP CONSTRAINT IF EXISTS phase43_experiment_status_check;

ALTER TABLE phase43_experiment
    ADD CONSTRAINT phase43_experiment_status_check CHECK (
        status IN (
            'DRAFT',
            'READY',
            'ACTIVE',
            'COLLECTING_EVIDENCE',
            'READY_FOR_ANALYSIS',
            'COMPLETED',
            'INCONCLUSIVE',
            'INSUFFICIENT_EVIDENCE',
            'PAUSED',
            'CANCELLED',
            'ARCHIVED'
        )
    );

ALTER TABLE phase43_experiment
    ADD COLUMN IF NOT EXISTS protocol_version INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS design_type TEXT NOT NULL DEFAULT 'MATCHED_COMPARISON',
    ADD COLUMN IF NOT EXISTS minimum_meaningful_improvement DOUBLE PRECISION NOT NULL DEFAULT 0.15,
    ADD COLUMN IF NOT EXISTS planned_observations INTEGER NOT NULL DEFAULT 10,
    ADD COLUMN IF NOT EXISTS required_coverage_pct DOUBLE PRECISION NOT NULL DEFAULT 0.65,
    ADD COLUMN IF NOT EXISTS stopping_criteria_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS confounders_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS random_seed INTEGER NOT NULL DEFAULT 43,
    ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS phase43_experiment_protocol_version (
    protocol_id UUID PRIMARY KEY,
    experiment_id TEXT NOT NULL REFERENCES phase43_experiment(experiment_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL CHECK (version_number >= 1),
    hypothesis TEXT NOT NULL,
    design_type TEXT NOT NULL DEFAULT 'MATCHED_COMPARISON',
    primary_metric TEXT NOT NULL,
    secondary_metrics JSONB NOT NULL DEFAULT '[]'::jsonb,
    minimum_meaningful_improvement DOUBLE PRECISION NOT NULL DEFAULT 0.15,
    planned_observations INTEGER NOT NULL DEFAULT 10 CHECK (planned_observations >= 2),
    required_coverage_pct DOUBLE PRECISION NOT NULL DEFAULT 0.65,
    stopping_criteria_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    confounder_controls_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    baseline_snapshot_id TEXT NOT NULL REFERENCES phase43_tactical_snapshot(snapshot_id) ON DELETE RESTRICT,
    variant_snapshot_id TEXT NOT NULL REFERENCES phase43_tactical_snapshot(snapshot_id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (experiment_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_phase43_protocol_exp
    ON phase43_experiment_protocol_version (experiment_id, version_number DESC);

CREATE TABLE IF NOT EXISTS phase43_experiment_assignment (
    assignment_id UUID PRIMARY KEY,
    experiment_id TEXT NOT NULL REFERENCES phase43_experiment(experiment_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    block_index INTEGER NOT NULL DEFAULT 1 CHECK (block_index >= 1),
    sequence_index INTEGER NOT NULL CHECK (sequence_index >= 1),
    assigned_arm TEXT NOT NULL CHECK (assigned_arm IN ('A', 'B')),
    assigned_snapshot_id TEXT NOT NULL REFERENCES phase43_tactical_snapshot(snapshot_id) ON DELETE RESTRICT,
    observed_match_id TEXT,
    observed_snapshot_id TEXT,
    observed_arm TEXT CHECK (observed_arm IS NULL OR observed_arm IN ('A', 'B')),
    adherent BOOLEAN,
    deviation_reason TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'COMPLETED', 'DEVIATED', 'SKIPPED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (experiment_id, sequence_index)
);

CREATE INDEX IF NOT EXISTS idx_phase43_assignment_exp
    ON phase43_experiment_assignment (experiment_id, user_id, sequence_index);

CREATE TABLE IF NOT EXISTS phase43_experiment_observation (
    observation_id UUID PRIMARY KEY,
    experiment_id TEXT NOT NULL REFERENCES phase43_experiment(experiment_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    assignment_id UUID REFERENCES phase43_experiment_assignment(assignment_id) ON DELETE SET NULL,
    match_id TEXT NOT NULL,
    arm TEXT NOT NULL CHECK (arm IN ('A', 'B')),
    snapshot_id TEXT REFERENCES phase43_tactical_snapshot(snapshot_id) ON DELETE SET NULL,
    game_version TEXT NOT NULL CHECK (game_version IN ('FC26', 'FC27')),
    game_patch TEXT NOT NULL DEFAULT 'current',
    gameplay_mode TEXT NOT NULL DEFAULT 'ONLINE',
    opponent_archetype TEXT,
    metric_values JSONB NOT NULL DEFAULT '{}'::jsonb,
    coverage_pct DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    confounder_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
    adherent BOOLEAN NOT NULL DEFAULT TRUE,
    model_version TEXT NOT NULL DEFAULT 'phase43.stats.v1',
    excluded_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (experiment_id, match_id)
);

CREATE INDEX IF NOT EXISTS idx_phase43_observation_exp
    ON phase43_experiment_observation (experiment_id, user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS phase43_experiment_analysis (
    analysis_id UUID PRIMARY KEY,
    experiment_id TEXT NOT NULL REFERENCES phase43_experiment(experiment_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    protocol_version INTEGER NOT NULL DEFAULT 1,
    verdict TEXT NOT NULL,
    estimated_effect DOUBLE PRECISION,
    relative_improvement DOUBLE PRECISION,
    ci_low DOUBLE PRECISION,
    ci_high DOUBLE PRECISION,
    p_value DOUBLE PRECISION,
    posterior_prob_meaningful DOUBLE PRECISION,
    confidence_score DOUBLE PRECISION,
    adherence_rate DOUBLE PRECISION,
    sample_counts_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    confounder_warnings_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    full_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_version TEXT NOT NULL DEFAULT 'phase43.stats.v1',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_phase43_analysis_exp
    ON phase43_experiment_analysis (experiment_id, user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS phase43_formation_fit_observation (
    fit_obs_id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    game_version TEXT NOT NULL CHECK (game_version IN ('FC26', 'FC27')),
    game_patch TEXT NOT NULL DEFAULT 'current',
    formation TEXT NOT NULL,
    theoretical_fit DOUBLE PRECISION NOT NULL,
    observed_performance DOUBLE PRECISION,
    controlled_experiment_evidence DOUBLE PRECISION,
    overall_suitability DOUBLE PRECISION NOT NULL,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    sample_matches INTEGER NOT NULL DEFAULT 0,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_phase43_formation_fit_user
    ON phase43_formation_fit_observation (user_id, game_version, game_patch, created_at DESC);

CREATE TABLE IF NOT EXISTS phase43_replacement_experiment (
    replacement_id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    snapshot_id TEXT REFERENCES phase43_tactical_snapshot(snapshot_id) ON DELETE SET NULL,
    game_version TEXT NOT NULL CHECK (game_version IN ('FC26', 'FC27')),
    position TEXT NOT NULL,
    outgoing_card_id TEXT,
    candidate_card_id TEXT,
    verdict TEXT NOT NULL,
    no_coin_tactical_alternative_viable BOOLEAN NOT NULL DEFAULT FALSE,
    market_price_status TEXT NOT NULL DEFAULT 'MARKET_PRICE_UNAVAILABLE',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_phase43_replacement_user
    ON phase43_replacement_experiment (user_id, game_version, created_at DESC);

CREATE TABLE IF NOT EXISTS phase43_recommendation_feedback (
    feedback_id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    recommendation_id TEXT NOT NULL,
    recommendation_type TEXT NOT NULL,
    game_version TEXT NOT NULL CHECK (game_version IN ('FC26', 'FC27')),
    game_patch TEXT NOT NULL DEFAULT 'current',
    user_action TEXT NOT NULL CHECK (user_action IN ('ACCEPTED', 'MODIFIED', 'REJECTED', 'IGNORED', 'DEFERRED', 'COMPLETED')),
    snapshot_id TEXT REFERENCES phase43_tactical_snapshot(snapshot_id) ON DELETE SET NULL,
    experiment_id TEXT REFERENCES phase43_experiment(experiment_id) ON DELETE SET NULL,
    observation_id UUID REFERENCES phase43_experiment_observation(observation_id) ON DELETE SET NULL,
    estimated_effect DOUBLE PRECISION,
    uncertainty_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_version TEXT NOT NULL DEFAULT 'phase43.v1',
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_phase43_feedback_user
    ON phase43_recommendation_feedback (user_id, game_version, created_at DESC);
