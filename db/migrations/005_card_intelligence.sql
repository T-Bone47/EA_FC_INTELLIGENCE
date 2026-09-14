-- 005: Phase 3 — Card Intelligence (additive; no destructive change).
-- Adds card identity/lifecycle columns, card roles, evolutions, availability,
-- meta-signal firewall, ingestion run tracking + quarantine, and retrieval
-- indexes. Everything here is DATA-READY scaffolding: absent production data
-- stays UNKNOWN, never fabricated.

-- ---------------------------------------------------------------------------
-- 1. Card identity & lifecycle (§4, §7, §47)
--    source_card_id already exists and is unique per (source, version).
--    canonical_card_id is the cross-source deterministic identity: the same
--    real card seen via two sources resolves to one canonical id.
-- ---------------------------------------------------------------------------
ALTER TABLE ut_card ADD COLUMN IF NOT EXISTS canonical_card_id UUID;
ALTER TABLE ut_card ADD COLUMN IF NOT EXISTS card_type TEXT;
ALTER TABLE ut_card ADD COLUMN IF NOT EXISTS rarity_raw TEXT;
ALTER TABLE ut_card ADD COLUMN IF NOT EXISTS release_date DATE;
ALTER TABLE ut_card ADD COLUMN IF NOT EXISTS valid_from TIMESTAMPTZ;
ALTER TABLE ut_card ADD COLUMN IF NOT EXISTS valid_to TIMESTAMPTZ;
ALTER TABLE ut_card ADD COLUMN IF NOT EXISTS identity_status TEXT NOT NULL
    DEFAULT 'UNRESOLVED'
    CHECK (identity_status IN ('RESOLVED','REVIEW_REQUIRED','UNRESOLVED'));
ALTER TABLE ut_card ADD COLUMN IF NOT EXISTS identity_rule TEXT;
ALTER TABLE ut_card ADD COLUMN IF NOT EXISTS playstyle_data_published BOOLEAN
    NOT NULL DEFAULT FALSE;

CREATE UNIQUE INDEX IF NOT EXISTS ux_utcard_canonical
    ON ut_card (game_version_id, canonical_card_id)
    WHERE canonical_card_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_utcard_identity ON ut_card (identity_status);

-- Deterministic canonical identity (§4): a card is NOT "name + OVR".
-- Rule (documented in docs/CARD_IDENTITY.md):
--   canonical_card_id = uuid5(ID_NAMESPACE,
--       "canonical_card|<game_version>|<real_player_id|source_player_id>
--        |<card_type|rarity_code|'BASE'>|<position>|<release_group|''>")
-- Distinct promos/upgrades of one player therefore stay distinct rows, and the
-- same card arriving from two sources collapses to one canonical id.

-- ---------------------------------------------------------------------------
-- 2. Card-level PlayStyles: source reference + published flag (§6)
--    Base and plus stay distinct rows; the contextual engine remains
--    authoritative — no "more PlayStyles = better" bonus anywhere.
-- ---------------------------------------------------------------------------
ALTER TABLE ut_card_playstyle ADD COLUMN IF NOT EXISTS source_observation_id UUID
    REFERENCES source_observation(id);
ALTER TABLE ut_card_playstyle ADD COLUMN IF NOT EXISTS observed_at TIMESTAMPTZ;

-- ---------------------------------------------------------------------------
-- 3. Card Roles (§9) — architecture ready, production data UNKNOWN for FC26.
--    Roles are game-defined; archetypes stay engine-derived. Both are kept.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ut_card_role (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ut_card_id      UUID NOT NULL REFERENCES ut_card(id) ON DELETE CASCADE,
    role_definition_id UUID REFERENCES role_definition(id),
    role_name       TEXT NOT NULL,
    familiarity     TEXT CHECK (familiarity IN ('ROLE','ROLE_PLUS','UNFAMILIAR')),
    is_primary      BOOLEAN NOT NULL DEFAULT FALSE,
    source_observation_id UUID REFERENCES source_observation(id),
    observed_at     TIMESTAMPTZ,
    data_status     TEXT NOT NULL DEFAULT 'CANONICAL'
                    CHECK (data_status IN ('CANONICAL','PENDING_REVIEW',
                                           'SYNTHETIC_TEST','REJECTED')),
    UNIQUE (ut_card_id, role_name)
);
CREATE INDEX IF NOT EXISTS ix_utcard_role_card ON ut_card_role (ut_card_id);
CREATE INDEX IF NOT EXISTS ix_utcard_role_name ON ut_card_role (role_name);

-- ---------------------------------------------------------------------------
-- 4. Evolutions (§8) — base card -> evolution -> result card.
--    Rules are never invented: with no verified data this table stays empty
--    and Evolution status is UNKNOWN.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS card_evolution (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_version_id UUID NOT NULL REFERENCES game_version(id),
    source_id       TEXT NOT NULL REFERENCES source_registry(source_id),
    source_evolution_id TEXT NOT NULL,
    evolution_name  TEXT NOT NULL,
    source_card_id  UUID REFERENCES ut_card(id) ON DELETE SET NULL,
    result_card_id  UUID REFERENCES ut_card(id) ON DELETE SET NULL,
    requirements    JSONB NOT NULL DEFAULT '{}'::jsonb,
    attribute_changes JSONB NOT NULL DEFAULT '{}'::jsonb,
    playstyle_changes JSONB NOT NULL DEFAULT '{}'::jsonb,
    position_changes JSONB NOT NULL DEFAULT '{}'::jsonb,
    role_changes    JSONB NOT NULL DEFAULT '{}'::jsonb,
    eligibility     JSONB NOT NULL DEFAULT '{}'::jsonb,
    starts_at       TIMESTAMPTZ,
    ends_at         TIMESTAMPTZ,
    source_observation_id UUID REFERENCES source_observation(id),
    data_status     TEXT NOT NULL DEFAULT 'CANONICAL'
                    CHECK (data_status IN ('CANONICAL','PENDING_REVIEW',
                                           'SYNTHETIC_TEST','REJECTED')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_id, source_evolution_id, game_version_id)
);
CREATE INDEX IF NOT EXISTS ix_evo_source_card ON card_evolution (source_card_id);
CREATE INDEX IF NOT EXISTS ix_evo_result_card ON card_evolution (result_card_id);

-- ---------------------------------------------------------------------------
-- 5. Availability (§3) — in packs / SBC / objective / market only.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS card_availability (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ut_card_id      UUID NOT NULL REFERENCES ut_card(id) ON DELETE CASCADE,
    channel         TEXT NOT NULL,     -- 'pack'|'sbc'|'objective'|'market'|'evolution'
    available       BOOLEAN,           -- NULL = UNKNOWN, never default FALSE
    observed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_observation_id UUID REFERENCES source_observation(id),
    notes           TEXT,
    UNIQUE (ut_card_id, channel)
);

-- ---------------------------------------------------------------------------
-- 6. Price observations (§13, §48): provenance + validity window.
--    card_price already stores observed_at/confidence; add authority + window.
-- ---------------------------------------------------------------------------
ALTER TABLE card_price ADD COLUMN IF NOT EXISTS source_id TEXT
    REFERENCES source_registry(source_id);
ALTER TABLE card_price ADD COLUMN IF NOT EXISTS currency TEXT NOT NULL DEFAULT 'COINS';
ALTER TABLE card_price ADD COLUMN IF NOT EXISTS valid_from TIMESTAMPTZ;
ALTER TABLE card_price ADD COLUMN IF NOT EXISTS valid_to TIMESTAMPTZ;
ALTER TABLE card_price ADD COLUMN IF NOT EXISTS source_authority INT;
CREATE INDEX IF NOT EXISTS ix_card_price_observed ON card_price (observed_at DESC);

-- ---------------------------------------------------------------------------
-- 7. Chemistry (§15): rules are verified or they do not exist.
--    No row => chemistry UNKNOWN. Structural fit stays a separate concept.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chemistry_rule (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_version_id UUID NOT NULL REFERENCES game_version(id),
    rule_code       TEXT NOT NULL,
    link_type       TEXT CHECK (link_type IN ('club','league','nation','manager',
                                              'position','formation')),
    contribution    JSONB NOT NULL DEFAULT '{}'::jsonb,
    threshold       JSONB NOT NULL DEFAULT '{}'::jsonb,
    verified        BOOLEAN NOT NULL DEFAULT FALSE,
    evidence_note   TEXT,
    source_observation_id UUID REFERENCES source_observation(id),
    data_status     TEXT NOT NULL DEFAULT 'CANONICAL'
                    CHECK (data_status IN ('CANONICAL','NOT_INGESTED',
                                           'SYNTHETIC_TEST','REJECTED')),
    UNIQUE (game_version_id, rule_code)
);

-- ---------------------------------------------------------------------------
-- 8. Meta signals (§18, §19) — HARD FIREWALL from canonical data.
--    Community/competitive signals live here and may never overwrite an
--    official attribute. Presentation must label them as perception.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS meta_signal (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_version_id UUID NOT NULL REFERENCES game_version(id),
    source_id       TEXT NOT NULL REFERENCES source_registry(source_id),
    signal_type     TEXT NOT NULL,     -- 'popular_in_competitive_play',
                                       -- 'community_favorite', 'reported_strength',
                                       -- 'reported_weakness', 'market_demand',
                                       -- 'tactical_trend', 'frequently_used'
    entity_type     TEXT NOT NULL CHECK (entity_type IN ('ut_card','game_player')),
    entity_id       UUID,
    position        TEXT,
    tactical_context TEXT,
    signal_strength NUMERIC(5,4),      -- NULL = UNKNOWN
    sample_size     INT,               -- NULL = UNKNOWN, never 0
    confidence      NUMERIC(4,3),
    observed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    data_status     TEXT NOT NULL DEFAULT 'CANONICAL'
                    CHECK (data_status IN ('CANONICAL','RESEARCH_ONLY',
                                           'SYNTHETIC_TEST','REJECTED')),
    CONSTRAINT meta_never_canonical CHECK (data_status <> 'CANONICAL'
                                           OR signal_type IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS ix_meta_entity ON meta_signal (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS ix_meta_type ON meta_signal (game_version_id, signal_type);

-- ---------------------------------------------------------------------------
-- 9. Ingestion runs + quarantine (§26, §27): RAW -> STAGING -> VALIDATED ->
--    PRODUCTION, atomically, with an auditable record.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ingestion_run (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id       TEXT NOT NULL REFERENCES source_registry(source_id),
    game_version_id UUID NOT NULL REFERENCES game_version(id),
    dataset_version TEXT,
    source_hash     TEXT,
    stage           TEXT NOT NULL DEFAULT 'RAW'
                    CHECK (stage IN ('RAW','STAGING','VALIDATED','PRODUCTION',
                                     'FAILED','ROLLED_BACK')),
    rows_raw        INT NOT NULL DEFAULT 0,
    rows_accepted   INT NOT NULL DEFAULT 0,
    rows_rejected   INT NOT NULL DEFAULT 0,
    rows_quarantined INT NOT NULL DEFAULT 0,
    conflicts       INT NOT NULL DEFAULT 0,
    warnings        INT NOT NULL DEFAULT 0,
    activation_status TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK (activation_status IN ('PENDING','ACTIVE','REJECTED',
                                                 'ROLLED_BACK')),
    report          JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_ingestion_run_src ON ingestion_run (source_id, started_at DESC);

CREATE TABLE IF NOT EXISTS ingestion_quarantine (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID REFERENCES ingestion_run(id) ON DELETE CASCADE,
    source_id       TEXT NOT NULL,
    game_version    TEXT NOT NULL,
    entity_kind     TEXT NOT NULL,     -- 'player'|'card'|'price'|'playstyle'|'role'
    source_row_id   TEXT,
    reason          TEXT NOT NULL,
    raw_payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_quarantine_run ON ingestion_quarantine (run_id);

-- ---------------------------------------------------------------------------
-- 10. Retrieval indexes (§49, §50)
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS ix_utcard_pos ON ut_card (game_version_id, position)
    WHERE is_synthetic = FALSE;
CREATE INDEX IF NOT EXISTS ix_utcard_ovr ON ut_card (game_version_id, overall_rating DESC)
    WHERE is_synthetic = FALSE;
CREATE INDEX IF NOT EXISTS ix_utcard_rarity ON ut_card (rarity_id);
CREATE INDEX IF NOT EXISTS ix_utcard_name_trgm ON ut_card USING gin (card_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_utcard_playstyle ON ut_card_playstyle (playstyle_name);
CREATE INDEX IF NOT EXISTS ix_cardversion_card ON card_version (ut_card_id, is_current);
CREATE INDEX IF NOT EXISTS ix_gp_updated ON game_player (updated_at);
CREATE INDEX IF NOT EXISTS ix_utcard_updated ON ut_card (updated_at);
CREATE INDEX IF NOT EXISTS ix_gp_club ON club_affiliation (club_id);
