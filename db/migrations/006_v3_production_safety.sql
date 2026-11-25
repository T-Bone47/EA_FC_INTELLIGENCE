-- Migration 006: V3 production safety.
--
-- Three independent fixes, each addressing a defect proven in
-- IMPLEMENTATION_BASELINE.md / FC26_DATA_QUALITY_SPEC.md:
--
--   1. Synthetic firewall defense-in-depth. The application-layer SQL bug in
--      candidate_repository._load_cards is fixed in code (see that file's
--      comment), but a CHECK constraint makes the two synthetic markers
--      impossible to desynchronise at the row level, independent of any
--      future query change, and a production view gives callers a single
--      object that cannot forget to filter.
--
--   2. field_provenance -- attributes must trace back to a source
--      observation (FC26_PROVENANCE_SPEC.md S2). Every claim gets a row,
--      including losers ('SUPERSEDED'), so the table can explain a
--      decision, not just restate it.
--
--   3. reference_distribution -- the frozen, versioned, universe-tagged
--      P10/P50/P90 table the v3 evidence interval reads
--      (FC26_REFERENCE_DISTRIBUTION_SPEC.md S2). The engine loads this from
--      a JSON artifact at runtime (never a live query during scoring); this
--      table is an optional durable mirror for querying/auditing releases,
--      not on the scoring hot path.

BEGIN;

-- ---------------------------------------------------------------------
-- 1. Synthetic firewall
-- ---------------------------------------------------------------------

ALTER TABLE ut_card
    ADD CONSTRAINT synthetic_status_consistent
    CHECK ( (is_synthetic = TRUE) = (data_status = 'SYNTHETIC_TEST') );

-- game_player has no separate is_synthetic column -- is_synthetic is derived
-- as `data_status == SYNTHETIC_TEST` (domain/card_model.py,
-- Candidate.from_game_player), so there are no two markers to desynchronise
-- there and no constraint is needed on this table.

CREATE OR REPLACE VIEW ut_card_production AS
    SELECT * FROM ut_card
    WHERE is_synthetic = FALSE AND data_status <> 'SYNTHETIC_TEST';

CREATE OR REPLACE VIEW game_player_production AS
    SELECT * FROM game_player
    WHERE data_status = 'CANONICAL';

COMMENT ON VIEW ut_card_production IS
    'Production read path for UT cards. Callers should query this view, not '
    'ut_card directly, so a future query cannot reintroduce the synthetic '
    'leak proven in IMPLEMENTATION_BASELINE.md.';

-- ---------------------------------------------------------------------
-- 2. Field-level provenance
-- ---------------------------------------------------------------------

CREATE TABLE field_provenance (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_entity_type TEXT NOT NULL,
    canonical_entity_id   UUID NOT NULL,
    canonical_field       TEXT NOT NULL,
    source_id             TEXT NOT NULL,
    source_record_id      TEXT,
    source_observation_id UUID REFERENCES source_observation(id),
    observed_value        TEXT,
    normalized_value      TEXT,
    observed_at           TIMESTAMPTZ,
    retrieved_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_authority      INT NOT NULL,
    resolution_status     TEXT NOT NULL
        CHECK (resolution_status IN ('ACCEPTED', 'SUPERSEDED', 'REJECTED', 'CONFLICT', 'UNRESOLVED')),
    resolution_reason     TEXT NOT NULL,
    dataset_release_id    TEXT NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_fp_entity_field ON field_provenance (canonical_entity_type, canonical_entity_id, canonical_field);
CREATE INDEX ix_fp_unresolved ON field_provenance (resolution_status) WHERE resolution_status IN ('CONFLICT', 'UNRESOLVED');
CREATE INDEX ix_fp_release ON field_provenance (dataset_release_id);

COMMENT ON TABLE field_provenance IS
    'Answers "why do we believe this card/player has value X for field Y?" '
    'Every competing claim gets a row, including SUPERSEDED losers -- a '
    'table that stores only winners can restate a decision but not explain it.';

-- ---------------------------------------------------------------------
-- 3. Reference distribution (durable mirror; engine reads the frozen JSON
--    artifact at runtime, never this table, during scoring)
-- ---------------------------------------------------------------------

CREATE TABLE reference_distribution (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version        TEXT NOT NULL,
    game_version   TEXT NOT NULL,
    universe       TEXT NOT NULL CHECK (universe IN ('RATINGS_SITE_PLAYERS', 'UT_CARDS', 'UT_CARDS_BASE_ONLY')),
    position_group TEXT NOT NULL,
    attribute_code TEXT NOT NULL,
    n              INT NOT NULL CHECK (n >= 50),
    p10            NUMERIC(6,2) NOT NULL,
    p50            NUMERIC(6,2) NOT NULL,
    p90            NUMERIC(6,2) NOT NULL,
    dataset_release_id TEXT NOT NULL,
    content_hash   TEXT NOT NULL,
    generated_at   TIMESTAMPTZ NOT NULL,
    UNIQUE (version, position_group, attribute_code)
);

COMMENT ON COLUMN reference_distribution.universe IS
    'RATINGS_SITE_PLAYERS distributions must never be applied to ut_card '
    'scoring (FC26_DATA_TO_V3_MAPPING.md contradiction C-1): a FUT card '
    'universe (TOTW/promo/Icon/Hero) is a materially different, '
    'upward-shifted population. Enforced in code by '
    'ReferenceDistribution.applies_to(), not by this constraint alone.';

COMMIT;
