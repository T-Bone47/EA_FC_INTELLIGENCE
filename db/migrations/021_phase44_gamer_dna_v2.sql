-- Phase 44 Complete Schema: Professional Reference Governance, Gamer DNA V2,
-- Style Similarity, Archetypes, Elite Skill Gaps, Style Evolution & Closed-Loop Feedback.

CREATE TABLE IF NOT EXISTS phase44_professional_reference_source (
    source_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN (
        'OFFICIAL_RULES',
        'PUBLIC_COMPETITION_METADATA',
        'AUTHORIZED_CREATOR_CONTRIBUTION',
        'AUTHORIZED_PLAYER_CONTRIBUTION',
        'CONTROLLED_RESEARCH_DATASET',
        'UNKNOWN'
    )),
    source_url TEXT,
    license_or_terms TEXT NOT NULL DEFAULT 'UNKNOWN',
    attribution_required BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS phase44_professional_gamer_reference (
    reference_id TEXT PRIMARY KEY,
    public_alias TEXT NOT NULL,
    display_name TEXT,
    competition_affiliations JSONB NOT NULL DEFAULT '[]'::jsonb,
    applicable_editions JSONB NOT NULL DEFAULT '[]'::jsonb,
    dataset_version TEXT NOT NULL DEFAULT 'NONE',
    reference_match_count INTEGER NOT NULL DEFAULT 0 CHECK (reference_match_count >= 0),
    evidence_quality TEXT NOT NULL DEFAULT 'NONE' CHECK (evidence_quality IN ('HIGH', 'MODERATE', 'LOW', 'NONE')),
    profile_coverage DOUBLE PRECISION NOT NULL DEFAULT 0.0 CHECK (profile_coverage >= 0.0 AND profile_coverage <= 1.0),
    is_independent_unendorsed BOOLEAN NOT NULL DEFAULT TRUE,
    metadata_notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS phase44_professional_reference_rights (
    rights_id UUID PRIMARY KEY,
    reference_id TEXT NOT NULL UNIQUE REFERENCES phase44_professional_gamer_reference(reference_id) ON DELETE CASCADE,
    source_id TEXT REFERENCES phase44_professional_reference_source(source_id) ON DELETE SET NULL,
    rights_status TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK (rights_status IN (
        'RIGHTS_VERIFIED',
        'RESEARCH_ONLY',
        'METADATA_ONLY',
        'AWAITING_PERMISSION',
        'RESTRICTED',
        'UNKNOWN',
        'REVOKED'
    )),
    allow_local_research BOOLEAN NOT NULL DEFAULT FALSE,
    allow_feature_extraction BOOLEAN NOT NULL DEFAULT FALSE,
    allow_model_training BOOLEAN NOT NULL DEFAULT FALSE,
    allow_commercial_inference BOOLEAN NOT NULL DEFAULT FALSE,
    allow_public_profile_display BOOLEAN NOT NULL DEFAULT FALSE,
    allow_video_redistribution BOOLEAN NOT NULL DEFAULT FALSE,
    allow_derived_dataset_redistribution BOOLEAN NOT NULL DEFAULT FALSE,
    verified_by TEXT,
    revocation_reason TEXT,
    verified_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS phase44_reference_match (
    ref_match_id TEXT PRIMARY KEY,
    reference_id TEXT NOT NULL REFERENCES phase44_professional_gamer_reference(reference_id) ON DELETE CASCADE,
    source_id TEXT REFERENCES phase44_professional_reference_source(source_id) ON DELETE SET NULL,
    game_version TEXT NOT NULL CHECK (game_version IN ('FC26', 'FC27')),
    game_patch TEXT NOT NULL DEFAULT 'PATCH_1.04',
    competition_name TEXT NOT NULL DEFAULT 'METADATA_ONLY',
    gameplay_mode TEXT NOT NULL DEFAULT 'TOURNAMENT',
    formation TEXT,
    coverage_pct DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    feature_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    provenance TEXT NOT NULL DEFAULT 'METADATA_ONLY',
    is_invalidated BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_phase44_ref_match_ref
    ON phase44_reference_match (reference_id, game_version, is_invalidated);

CREATE TABLE IF NOT EXISTS phase44_style_feature_definition (
    feature_id TEXT PRIMARY KEY,
    feature_group TEXT NOT NULL,
    mathematical_definition TEXT NOT NULL,
    units TEXT NOT NULL,
    is_proficiency_only BOOLEAN NOT NULL DEFAULT FALSE,
    model_version TEXT NOT NULL DEFAULT 'phase44.v2',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS phase44_gamer_style_profile_version (
    profile_version_id TEXT PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    game_version TEXT NOT NULL CHECK (game_version IN ('FC26', 'FC27')),
    game_patch TEXT NOT NULL DEFAULT 'ALL',
    gameplay_mode TEXT NOT NULL DEFAULT 'ALL',
    eligible_match_count INTEGER NOT NULL DEFAULT 0,
    synthetic_excluded_count INTEGER NOT NULL DEFAULT 0,
    profile_maturity TEXT NOT NULL DEFAULT 'COLD_START',
    overall_coverage DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    primary_archetype TEXT NOT NULL DEFAULT 'Undetermined',
    secondary_archetype TEXT,
    scaler_fit_split TEXT NOT NULL DEFAULT 'NONE',
    feature_vectors_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    context_summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_version TEXT NOT NULL DEFAULT 'phase44.v2',
    is_invalidated BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_phase44_gamer_profile_user
    ON phase44_gamer_style_profile_version (user_id, game_version, game_patch, created_at DESC);

CREATE TABLE IF NOT EXISTS phase44_style_feature_observation (
    obs_id UUID PRIMARY KEY,
    profile_version_id TEXT NOT NULL REFERENCES phase44_gamer_style_profile_version(profile_version_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    feature_id TEXT NOT NULL REFERENCES phase44_style_feature_definition(feature_id) ON DELETE RESTRICT,
    game_version TEXT NOT NULL CHECK (game_version IN ('FC26', 'FC27')),
    game_patch TEXT NOT NULL,
    raw_value DOUBLE PRECISION,
    normalized_value DOUBLE PRECISION,
    opportunity_denominator DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    match_count INTEGER NOT NULL DEFAULT 0,
    coverage DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    uncertainty DOUBLE PRECISION,
    source_type TEXT NOT NULL,
    evidence_references JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS phase44_professional_style_profile_version (
    pro_profile_id TEXT PRIMARY KEY,
    reference_id TEXT NOT NULL REFERENCES phase44_professional_gamer_reference(reference_id) ON DELETE CASCADE,
    game_version TEXT NOT NULL CHECK (game_version IN ('FC26', 'FC27')),
    game_patch TEXT NOT NULL DEFAULT 'PATCH_1.04',
    dataset_version TEXT NOT NULL,
    eligible_ref_matches INTEGER NOT NULL DEFAULT 0,
    coverage DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    feature_vectors_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    distributions_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_version TEXT NOT NULL DEFAULT 'phase44.v2',
    is_invalidated BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS phase44_style_archetype_model (
    archetype_run_id UUID PRIMARY KEY,
    user_id UUID REFERENCES user_profile(id) ON DELETE CASCADE,
    layer TEXT NOT NULL CHECK (layer IN ('LAYER1_INTERPRETABLE_RULE', 'LAYER2_UNSUPERVISED_CLUSTERING')),
    algorithm TEXT NOT NULL,
    n_profiles INTEGER NOT NULL DEFAULT 0,
    n_clusters INTEGER NOT NULL DEFAULT 0,
    silhouette_score DOUBLE PRECISION,
    davies_bouldin_index DOUBLE PRECISION,
    bootstrap_stability DOUBLE PRECISION,
    primary_archetype TEXT,
    mixed_probabilities_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS phase44_style_similarity_run (
    similarity_run_id TEXT PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    profile_version_id TEXT NOT NULL REFERENCES phase44_gamer_style_profile_version(profile_version_id) ON DELETE CASCADE,
    game_version TEXT NOT NULL CHECK (game_version IN ('FC26', 'FC27')),
    game_patch TEXT NOT NULL,
    distance_metric TEXT NOT NULL DEFAULT 'WEIGHTED_RELIABILITY_EUCLIDEAN',
    abstained BOOLEAN NOT NULL DEFAULT FALSE,
    abstention_reason TEXT,
    eligible_references_count INTEGER NOT NULL DEFAULT 0,
    top_k_stability DOUBLE PRECISION,
    uncertainty_notes_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    model_version TEXT NOT NULL DEFAULT 'phase44.sim.v1',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS phase44_style_similarity_result (
    result_id UUID PRIMARY KEY,
    similarity_run_id TEXT NOT NULL REFERENCES phase44_style_similarity_run(similarity_run_id) ON DELETE CASCADE,
    reference_id TEXT NOT NULL REFERENCES phase44_professional_gamer_reference(reference_id) ON DELETE CASCADE,
    rank_position INTEGER NOT NULL,
    raw_distance DOUBLE PRECISION NOT NULL,
    interpretable_similarity_index DOUBLE PRECISION NOT NULL,
    feature_overlap_ratio DOUBLE PRECISION NOT NULL,
    confidence_band_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    group_similarities_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    top_similar_features_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    top_divergent_features_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    indistinguishable_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS phase44_elite_skill_gap (
    gap_run_id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    game_version TEXT NOT NULL CHECK (game_version IN ('FC26', 'FC27')),
    reference_scope TEXT NOT NULL,
    gaps_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    strengths_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    caveats_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    model_version TEXT NOT NULL DEFAULT 'phase44.gap.v1',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS phase44_style_evolution_snapshot (
    evolution_id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    game_version TEXT NOT NULL CHECK (game_version IN ('FC26', 'FC27')),
    window_label TEXT NOT NULL,
    match_count INTEGER NOT NULL DEFAULT 0,
    ewma_vector_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    shift_detected BOOLEAN NOT NULL DEFAULT FALSE,
    shift_attributed_to_experiment_id TEXT,
    stability_score DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS phase44_style_recommendation_feedback (
    feedback_id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    recommendation_id TEXT NOT NULL,
    recommendation_type TEXT NOT NULL,
    game_version TEXT NOT NULL CHECK (game_version IN ('FC26', 'FC27')),
    game_patch TEXT NOT NULL DEFAULT 'PATCH_1.04',
    user_action TEXT NOT NULL CHECK (user_action IN (
        'ACCEPTED', 'MODIFIED', 'REJECTED', 'IGNORED', 'DEFERRED', 'COMPLETED', 'WITHDRAWN'
    )),
    profile_version_id TEXT,
    similarity_run_id TEXT,
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_phase44_feedback_user
    ON phase44_style_recommendation_feedback (user_id, game_version, created_at DESC);
