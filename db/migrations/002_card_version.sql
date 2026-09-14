-- 002: CardVersion concept (additive, per UT_CANONICAL_DATA_CONTRACT_V1).
-- A stable card identity (ut_card) can have changing stats over time;
-- static cards have one version, dynamic/upgradeable cards have multiple.
-- Version IDs incorporate a content hash -> deterministic idempotent ingestion.

CREATE TABLE IF NOT EXISTS card_version (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ut_card_id      UUID NOT NULL REFERENCES ut_card(id) ON DELETE CASCADE,
    version_number  INT  NOT NULL DEFAULT 1,
    content_hash    TEXT NOT NULL,             -- sha256 of canonical stat payload
    overall_rating  INT  CHECK (overall_rating BETWEEN 1 AND 99),
    attributes      JSONB NOT NULL DEFAULT '{}'::jsonb,  -- snapshot at this version
    playstyles      JSONB NOT NULL DEFAULT '{}'::jsonb,
    valid_from      TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_to        TIMESTAMPTZ,
    is_current      BOOLEAN NOT NULL DEFAULT TRUE,
    source_observation_id UUID REFERENCES source_observation(id),
    UNIQUE (ut_card_id, content_hash)
);
CREATE INDEX IF NOT EXISTS ix_card_version_current ON card_version (ut_card_id) WHERE is_current;
