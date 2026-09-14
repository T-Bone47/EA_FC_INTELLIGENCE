-- ============================================================================
-- EA FC PLAYER INTELLIGENCE — DATABASE_SCHEMA_V1.sql
-- Base schema: the 29 documented core tables.
-- Conventions:
--   * UUID primary keys for canonical entities; source ids preserved alongside.
--   * game_version scoping everywhere versionable. NEVER mix FC26 and FC27.
--   * Provenance: every ingested fact can be traced to source_registry +
--     source_observation.
--   * Synthetic data firewall: ut_card.is_synthetic + data_status columns.
--   * NULL means UNKNOWN. No default-zero coercion for factual fields.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;      -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pg_trgm;       -- name search

-- 1. game_version -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS game_version (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code            TEXT NOT NULL UNIQUE,            -- 'FC26', 'FC27', ...
    display_name    TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE','PLANNED','RETIRED','NO_DATA')),
    config          JSONB NOT NULL DEFAULT '{}'::jsonb,  -- version-aware rules:
                                                         -- positions, facades, caps...
    released_on     DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. source_registry ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS source_registry (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id       TEXT NOT NULL UNIQUE,            -- stable machine id
    name            TEXT NOT NULL,
    source_type     TEXT NOT NULL
                    CHECK (source_type IN ('OFFICIAL_PAGE','CARRIER_DATASET','COMMUNITY_DB',
                                           'HISTORICAL_DATASET','COMMUNITY_EVIDENCE',
                                           'SYNTHETIC_FIXTURE','MARKET_FEED','OTHER')),
    authority_tier  INT  NOT NULL CHECK (authority_tier BETWEEN 1 AND 5),
    url             TEXT,
    license         TEXT,
    usage_status    TEXT NOT NULL DEFAULT 'UNKNOWN'
                    CHECK (usage_status IN ('OFFICIAL','AUTHORIZED','LICENSED',
                                            'PUBLIC_REFERENCE','RESEARCH_ONLY',
                                            'SYNTHETIC_TEST','UNKNOWN','NOT_PERMITTED')),
    -- runtime legal gate: fetch operations blocked unless CLEARED / NOT_REQUIRED
    legal_gate      TEXT NOT NULL DEFAULT 'REQUIRED'
                    CHECK (legal_gate IN ('REQUIRED','CLEARED','NOT_REQUIRED')),
    cleared_by      TEXT,
    cleared_at      TIMESTAMPTZ,
    canonical_fields TEXT[] NOT NULL DEFAULT '{}',   -- fields this source is authority for
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. real_player ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS real_player (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name       TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    nationality     TEXT,
    date_of_birth   DATE,
    position_hint   TEXT,
    identity_status TEXT NOT NULL DEFAULT 'RESOLVED'
                    CHECK (identity_status IN ('RESOLVED','REVIEW_REQUIRED','UNRESOLVED')),
    data_status     TEXT NOT NULL DEFAULT 'CANONICAL'
                    CHECK (data_status IN ('CANONICAL','PENDING_REVIEW','SYNTHETIC_TEST')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_real_player_norm ON real_player (normalized_name);

-- 4. real_player_name_variant ---------------------------------------------------
CREATE TABLE IF NOT EXISTS real_player_name_variant (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    real_player_id  UUID NOT NULL REFERENCES real_player(id) ON DELETE CASCADE,
    variant         TEXT NOT NULL,
    normalized_variant TEXT NOT NULL,
    variant_type    TEXT NOT NULL DEFAULT 'ALIAS'
                    CHECK (variant_type IN ('ALIAS','COMMON_NAME','EA_REGISTERED',
                                            'TRANSLITERATION','SHORT')),
    source_id       TEXT REFERENCES source_registry(source_id),
    UNIQUE (real_player_id, normalized_variant)
);
CREATE INDEX IF NOT EXISTS ix_name_variant_norm ON real_player_name_variant (normalized_variant);

-- 5. club ------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS club (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    league_name     TEXT,
    nation          TEXT,
    UNIQUE (normalized_name, league_name)
);
CREATE INDEX IF NOT EXISTS ix_club_norm ON club (normalized_name);

-- 6. club_affiliation (game-version scoped; supports freshness/history) -----------
CREATE TABLE IF NOT EXISTS club_affiliation (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    club_id          UUID NOT NULL REFERENCES club(id),
    game_version_id  UUID NOT NULL REFERENCES game_version(id),
    game_player_id   UUID NOT NULL,          -- FK added after game_player exists
    valid_from       DATE,
    valid_to         DATE,
    source_id        TEXT REFERENCES source_registry(source_id),
    UNIQUE (game_player_id, game_version_id)
);

-- 7. game_player -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS game_player (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_version_id   UUID NOT NULL REFERENCES game_version(id),
    real_player_id    UUID REFERENCES real_player(id),
    source_id         TEXT NOT NULL REFERENCES source_registry(source_id),
    source_player_id  BIGINT NOT NULL,          -- EA player id from source
    first_name        TEXT,
    last_name         TEXT,
    common_name       TEXT,
    display_name      TEXT NOT NULL,
    normalized_name   TEXT NOT NULL,
    nation            TEXT,
    position_primary  TEXT NOT NULL,
    position_type     TEXT,
    overall_rating    INT NOT NULL CHECK (overall_rating BETWEEN 1 AND 99),
    date_of_birth     DATE,
    height_cm         SMALLINT,
    weight_kg         SMALLINT,
    preferred_foot    TEXT CHECK (preferred_foot IN ('Right','Left')),
    weak_foot_stars   SMALLINT CHECK (weak_foot_stars BETWEEN 1 AND 5),
    skill_moves_stars SMALLINT CHECK (skill_moves_stars BETWEEN 1 AND 5),
    gender            TEXT,
    source_rank       INT,
    identity_status   TEXT NOT NULL DEFAULT 'RESOLVED'
                      CHECK (identity_status IN ('RESOLVED','REVIEW_REQUIRED','UNRESOLVED')),
    data_status       TEXT NOT NULL DEFAULT 'CANONICAL'
                      CHECK (data_status IN ('CANONICAL','PENDING_REVIEW','SYNTHETIC_TEST')),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (game_version_id, source_id, source_player_id)
);
CREATE INDEX IF NOT EXISTS ix_gp_version_pos   ON game_player (game_version_id, position_primary);
CREATE INDEX IF NOT EXISTS ix_gp_version_ovr   ON game_player (game_version_id, overall_rating DESC);
CREATE INDEX IF NOT EXISTS ix_gp_name_trgm     ON game_player USING gin (display_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_gp_norm          ON game_player (game_version_id, normalized_name);
CREATE INDEX IF NOT EXISTS ix_gp_nation        ON game_player (game_version_id, nation);
CREATE INDEX IF NOT EXISTS ix_gp_real          ON game_player (real_player_id);

ALTER TABLE club_affiliation
    DROP CONSTRAINT IF EXISTS fk_affiliation_game_player,
    ADD  CONSTRAINT fk_affiliation_game_player
    FOREIGN KEY (game_player_id) REFERENCES game_player(id) ON DELETE CASCADE;

-- 8. game_player_position_secondary --------------------------------------------------
CREATE TABLE IF NOT EXISTS game_player_position_secondary (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_player_id  UUID NOT NULL REFERENCES game_player(id) ON DELETE CASCADE,
    position        TEXT NOT NULL,
    sort_order      SMALLINT NOT NULL DEFAULT 0,
    UNIQUE (game_player_id, position)
);

-- 9. game_player_attributes (wide, typed; one row per game_player) ---------------------
CREATE TABLE IF NOT EXISTS game_player_attributes (
    game_player_id      UUID PRIMARY KEY REFERENCES game_player(id) ON DELETE CASCADE,
    -- facades
    pace SMALLINT CHECK (pace BETWEEN 1 AND 99),
    shooting SMALLINT CHECK (shooting BETWEEN 1 AND 99),
    passing SMALLINT CHECK (passing BETWEEN 1 AND 99),
    dribbling SMALLINT CHECK (dribbling BETWEEN 1 AND 99),
    defending SMALLINT CHECK (defending BETWEEN 1 AND 99),
    physicality SMALLINT CHECK (physicality BETWEEN 1 AND 99),
    -- outfield details
    acceleration SMALLINT CHECK (acceleration BETWEEN 1 AND 99),
    sprint_speed SMALLINT CHECK (sprint_speed BETWEEN 1 AND 99),
    finishing SMALLINT CHECK (finishing BETWEEN 1 AND 99),
    shot_power SMALLINT CHECK (shot_power BETWEEN 1 AND 99),
    long_shots SMALLINT CHECK (long_shots BETWEEN 1 AND 99),
    volleys SMALLINT CHECK (volleys BETWEEN 1 AND 99),
    penalties SMALLINT CHECK (penalties BETWEEN 1 AND 99),
    positioning SMALLINT CHECK (positioning BETWEEN 1 AND 99),
    vision SMALLINT CHECK (vision BETWEEN 1 AND 99),
    crossing SMALLINT CHECK (crossing BETWEEN 1 AND 99),
    short_passing SMALLINT CHECK (short_passing BETWEEN 1 AND 99),
    long_passing SMALLINT CHECK (long_passing BETWEEN 1 AND 99),
    curve SMALLINT CHECK (curve BETWEEN 1 AND 99),
    free_kick_accuracy SMALLINT CHECK (free_kick_accuracy BETWEEN 1 AND 99),
    dribbling_detail SMALLINT CHECK (dribbling_detail BETWEEN 1 AND 99),
    ball_control SMALLINT CHECK (ball_control BETWEEN 1 AND 99),
    agility SMALLINT CHECK (agility BETWEEN 1 AND 99),
    balance SMALLINT CHECK (balance BETWEEN 1 AND 99),
    reactions SMALLINT CHECK (reactions BETWEEN 1 AND 99),
    composure SMALLINT CHECK (composure BETWEEN 1 AND 99),
    defensive_awareness SMALLINT CHECK (defensive_awareness BETWEEN 1 AND 99),
    interceptions SMALLINT CHECK (interceptions BETWEEN 1 AND 99),
    standing_tackle SMALLINT CHECK (standing_tackle BETWEEN 1 AND 99),
    sliding_tackle SMALLINT CHECK (sliding_tackle BETWEEN 1 AND 99),
    heading_accuracy SMALLINT CHECK (heading_accuracy BETWEEN 1 AND 99),
    strength SMALLINT CHECK (strength BETWEEN 1 AND 99),
    stamina SMALLINT CHECK (stamina BETWEEN 1 AND 99),
    aggression SMALLINT CHECK (aggression BETWEEN 1 AND 99),
    jumping SMALLINT CHECK (jumping BETWEEN 1 AND 99),
    -- GK-specific (real values for GKs; EA-published low values for outfield)
    gk_diving SMALLINT CHECK (gk_diving BETWEEN 1 AND 99),
    gk_handling SMALLINT CHECK (gk_handling BETWEEN 1 AND 99),
    gk_kicking SMALLINT CHECK (gk_kicking BETWEEN 1 AND 99),
    gk_positioning SMALLINT CHECK (gk_positioning BETWEEN 1 AND 99),
    gk_reflexes SMALLINT CHECK (gk_reflexes BETWEEN 1 AND 99)
);

-- 10. attribute_conflict_log -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS attribute_conflict_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_version_id UUID NOT NULL REFERENCES game_version(id),
    entity_type     TEXT NOT NULL,           -- 'game_player' | 'ut_card'
    entity_id       UUID NOT NULL,
    field_name      TEXT NOT NULL,
    value_a         TEXT,
    source_a        TEXT REFERENCES source_registry(source_id),
    value_b         TEXT,
    source_b        TEXT REFERENCES source_registry(source_id),
    resolution      TEXT NOT NULL DEFAULT 'UNRESOLVED'
                    CHECK (resolution IN ('UNRESOLVED','SOURCE_A_WINS','SOURCE_B_WINS',
                                          'MANUAL','DEFERRED')),
    resolution_note TEXT,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_conflict_entity ON attribute_conflict_log (entity_type, entity_id);

-- 11. role_definition -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS role_definition (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_version_id UUID NOT NULL REFERENCES game_version(id),
    role_code       TEXT NOT NULL,
    role_name       TEXT NOT NULL,
    description     TEXT,
    applicable_positions TEXT[] NOT NULL DEFAULT '{}',
    data_status     TEXT NOT NULL DEFAULT 'NOT_INGESTED'
                    CHECK (data_status IN ('CANONICAL','NOT_INGESTED','SYNTHETIC_TEST')),
    source_id       TEXT REFERENCES source_registry(source_id),
    UNIQUE (game_version_id, role_code)
);

-- 12. game_player_role_familiarity ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS game_player_role_familiarity (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_player_id  UUID NOT NULL REFERENCES game_player(id) ON DELETE CASCADE,
    role_definition_id UUID NOT NULL REFERENCES role_definition(id),
    familiarity     NUMERIC(4,3) CHECK (familiarity BETWEEN 0 AND 1),
    support_levels  TEXT[] NOT NULL DEFAULT '{}',
    evidence_id     UUID,
    UNIQUE (game_player_id, role_definition_id)
);

-- 13. playstyle_definition ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS playstyle_definition (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_version_id UUID NOT NULL REFERENCES game_version(id),
    playstyle_name  TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    category        TEXT,
    description     TEXT,
    data_status     TEXT NOT NULL DEFAULT 'CANONICAL'
                    CHECK (data_status IN ('CANONICAL','NOT_INGESTED','SYNTHETIC_TEST')),
    UNIQUE (game_version_id, normalized_name)
);

-- player-level playstyles (long format, mirrors foundation CSV)
CREATE TABLE IF NOT EXISTS game_player_playstyle (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_player_id  UUID NOT NULL REFERENCES game_player(id) ON DELETE CASCADE,
    playstyle_definition_id UUID NOT NULL REFERENCES playstyle_definition(id),
    tier            TEXT NOT NULL CHECK (tier IN ('base','plus')),
    UNIQUE (game_player_id, playstyle_definition_id)
);
CREATE INDEX IF NOT EXISTS ix_gpp_player ON game_player_playstyle (game_player_id);

-- 14. card_rarity ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS card_rarity (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_version_id UUID NOT NULL REFERENCES game_version(id),
    rarity_code     TEXT NOT NULL,
    rarity_name     TEXT NOT NULL,
    is_promo        BOOLEAN NOT NULL DEFAULT FALSE,
    data_status     TEXT NOT NULL DEFAULT 'CANONICAL'
                    CHECK (data_status IN ('CANONICAL','NOT_INGESTED','SYNTHETIC_TEST')),
    UNIQUE (game_version_id, rarity_code)
);

-- 15. ut_card ---------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ut_card (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_version_id UUID NOT NULL REFERENCES game_version(id),
    game_player_id  UUID REFERENCES game_player(id),
    source_id       TEXT NOT NULL REFERENCES source_registry(source_id),
    source_card_id  TEXT NOT NULL,
    card_name       TEXT NOT NULL,
    rarity_id       UUID REFERENCES card_rarity(id),
    position        TEXT NOT NULL,
    overall_rating  INT CHECK (overall_rating BETWEEN 1 AND 99),
    release_group   TEXT,
    -- SYNTHETIC DATA FIREWALL: production queries MUST filter is_synthetic = FALSE
    is_synthetic    BOOLEAN NOT NULL DEFAULT FALSE,
    data_status     TEXT NOT NULL DEFAULT 'CANONICAL'
                    CHECK (data_status IN ('CANONICAL','PENDING_REVIEW',
                                           'SYNTHETIC_TEST','REJECTED')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_id, source_card_id, game_version_id)
);
CREATE INDEX IF NOT EXISTS ix_utcard_prod ON ut_card (game_version_id) WHERE is_synthetic = FALSE;
CREATE INDEX IF NOT EXISTS ix_utcard_player ON ut_card (game_player_id);

-- 16. ut_card_attribute_override ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ut_card_attribute_override (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ut_card_id      UUID NOT NULL REFERENCES ut_card(id) ON DELETE CASCADE,
    attribute_code  TEXT NOT NULL,
    value           SMALLINT CHECK (value BETWEEN 1 AND 99),
    UNIQUE (ut_card_id, attribute_code)
);

-- 17. ut_card_playstyle -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ut_card_playstyle (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ut_card_id      UUID NOT NULL REFERENCES ut_card(id) ON DELETE CASCADE,
    playstyle_name  TEXT NOT NULL,
    tier            TEXT NOT NULL CHECK (tier IN ('base','plus')),
    UNIQUE (ut_card_id, playstyle_name, tier)
);

-- 18. playstyle_plus_cap ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS playstyle_plus_cap (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_version_id UUID NOT NULL REFERENCES game_version(id),
    scope           TEXT NOT NULL DEFAULT 'player_base'
                    CHECK (scope IN ('player_base','card')),
    max_plus        SMALLINT NOT NULL CHECK (max_plus >= 0),
    evidence_note   TEXT,
    UNIQUE (game_version_id, scope)
);

-- 19. card_price ---------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS card_price (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ut_card_id      UUID NOT NULL REFERENCES ut_card(id) ON DELETE CASCADE,
    platform        TEXT NOT NULL DEFAULT 'UNKNOWN',   -- 'playstation'|'xbox'|'pc'|'UNKNOWN'
    price_coins     BIGINT CHECK (price_coins >= 0),   -- NULL = UNKNOWN, never default 0
    observed_at     TIMESTAMPTZ NOT NULL,
    source_observation_id UUID,
    confidence      NUMERIC(4,3) CHECK (confidence BETWEEN 0 AND 1)
);
CREATE INDEX IF NOT EXISTS ix_card_price_time ON card_price (ut_card_id, observed_at DESC);

-- 20. source_observation -----------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS source_observation (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id       TEXT NOT NULL REFERENCES source_registry(source_id),
    game_version_id UUID REFERENCES game_version(id),
    entity_type     TEXT NOT NULL,
    entity_source_id TEXT,
    observed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    snapshot_date   DATE,
    raw_payload     JSONB,
    retrieval_context TEXT
);
CREATE INDEX IF NOT EXISTS ix_obs_entity ON source_observation (entity_type, entity_source_id);

-- 21. claim --------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS claim (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_observation_id UUID NOT NULL REFERENCES source_observation(id),
    subject_type    TEXT NOT NULL,
    subject_id      UUID,
    field_name      TEXT NOT NULL,
    claimed_value   TEXT,
    claim_status    TEXT NOT NULL DEFAULT 'ACCEPTED'
                    CHECK (claim_status IN ('ACCEPTED','REJECTED','SUPERSEDED','PENDING')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 22. experiment -----------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS experiment (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL UNIQUE,
    hypothesis      TEXT,
    engine_config   JSONB NOT NULL DEFAULT '{}'::jsonb,
    status          TEXT NOT NULL DEFAULT 'DRAFT'
                    CHECK (status IN ('DRAFT','RUNNING','COMPLETED','ABANDONED')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 23. experiment_result ------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS experiment_result (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id   UUID NOT NULL REFERENCES experiment(id) ON DELETE CASCADE,
    variant         TEXT NOT NULL,
    metrics         JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 24. experiment_result_card ---------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS experiment_result_card (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_result_id UUID NOT NULL REFERENCES experiment_result(id) ON DELETE CASCADE,
    entity_type     TEXT NOT NULL CHECK (entity_type IN ('ut_card','game_player')),
    entity_id       UUID NOT NULL,
    score           NUMERIC(8,5),
    rank            INT
);

-- 25. evidence --------------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS evidence (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_class  TEXT NOT NULL
                    CHECK (evidence_class IN ('FACT','SUPPORTED','COMMUNITY_CONSENSUS',
                                              'INFERENCE','HYPOTHESIS','UNKNOWN')),
    statement       TEXT NOT NULL,
    source_observation_id UUID REFERENCES source_observation(id),
    url             TEXT,
    confidence      NUMERIC(4,3) CHECK (confidence BETWEEN 0 AND 1),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 26. confidence_score ---------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS confidence_score (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type     TEXT NOT NULL,
    entity_id       UUID NOT NULL,
    dimension       TEXT NOT NULL,          -- 'attributes'|'identity'|'price'|'recommendation'
    score           NUMERIC(4,3) NOT NULL CHECK (score BETWEEN 0 AND 1),
    inputs          JSONB NOT NULL DEFAULT '{}'::jsonb,
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_conf_entity ON confidence_score (entity_type, entity_id, dimension);

-- 27. user_profile ---------------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_profile (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,               -- bcrypt; plaintext NEVER stored
    display_name    TEXT,
    role            TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user','admin')),
    preferred_game_version TEXT,
    preferences     JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at   TIMESTAMPTZ
);

-- 28. user_squad_slot (squad header table added in migration 004) -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_squad_slot (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_profile_id UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    formation       TEXT NOT NULL,
    slot_index      SMALLINT NOT NULL,
    slot_position   TEXT NOT NULL,
    game_player_id  UUID REFERENCES game_player(id),
    ut_card_id      UUID REFERENCES ut_card(id),
    UNIQUE (user_profile_id, formation, slot_index)
);

-- 29. user_recommendation_feedback ----------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_recommendation_feedback (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_profile_id UUID REFERENCES user_profile(id) ON DELETE SET NULL,
    game_version_id UUID REFERENCES game_version(id),
    request_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    recommendation_id TEXT,
    entity_type     TEXT NOT NULL CHECK (entity_type IN ('game_player','ut_card')),
    entity_id       UUID,
    action          TEXT NOT NULL
                    CHECK (action IN ('SHOWN','SELECTED','REJECTED',
                                      'ALTERNATIVE_SELECTED','SAVED')),
    reason          TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_feedback_user ON user_recommendation_feedback (user_profile_id, created_at DESC);
