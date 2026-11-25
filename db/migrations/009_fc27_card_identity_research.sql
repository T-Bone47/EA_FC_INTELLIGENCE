-- Migration 009: FC27 card identity / reference layer (RESEARCH_ONLY, quarantined).  Phase 24.
--
-- Source: independent GLM research package FC27_CARD_DATASET v0.1.0-research (fut.gg snapshot
-- snap-20260930T0728Z), independently audited (see artifacts/phase24/FC27_CARD_PACKAGE_AUDIT_REPORT.md).
--
-- DESIGN RULES (fail closed):
--  * ut_card / card_rarity / role_definition are NOT touched: ut_card.position is NOT NULL and the
--    package has no per-card position/OVR/rarity; inventing them would be fabrication, and widening
--    those CHECKs would expose research rows to every card read path. Research rows live in their own
--    fc27_* tables that no production module reads.
--  * Registry: `futgg` stays NOT_PERMITTED (unchanged). This package is registered under a NEW
--    source id with usage_status RESEARCH_ONLY and legal_gate REQUIRED (NOT cleared). Registering
--    it is a policy decision the owner must approve BEFORE this migration is run on a real database.
--  * Version wall in the database: every row must belong to game_version FC27 (trigger).
--  * data_status can only ever be RESEARCH_ONLY (CHECK); promotion needs a new migration.
--  * No price/market columns exist or may be added here (prices are absent by design).
BEGIN;

INSERT INTO source_registry (source_id, name, source_type, authority_tier, url, license,
                             usage_status, legal_gate, canonical_fields, notes)
VALUES ('futgg_fc27_identity_research',
        'fut.gg FC27 identity/reference snapshot (GLM research package v0.1.0-research)',
        'COMMUNITY_DB', 4, 'https://www.fut.gg/',
        'Stormstrike ToS: no redistribution, no commercial use, no ML training without written consent; storage UNKNOWN; EA underlying rights.',
        'RESEARCH_ONLY', 'REQUIRED', '{}',
        'Research copy only. The registry entry `futgg` remains NOT_PERMITTED. Automated acquisition legality is PARTIAL (robots/sitemap signal vs ToS). Requires owner sign-off + Stormstrike/EA written position before any production use.')
ON CONFLICT (source_id) DO NOTHING;

CREATE OR REPLACE FUNCTION enforce_fc27_card_research_firewall() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE gv_code TEXT; src_usage TEXT;
BEGIN
    SELECT code INTO gv_code FROM game_version WHERE id = NEW.game_version_id;
    IF gv_code IS DISTINCT FROM 'FC27' THEN
        RAISE EXCEPTION 'table % accepts only game_version FC27 (got %): FC26/earlier card data must never be mixed',
            TG_TABLE_NAME, COALESCE(gv_code, 'NULL') USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.data_status IS DISTINCT FROM 'RESEARCH_ONLY' THEN
        RAISE EXCEPTION 'table % rows must be data_status RESEARCH_ONLY (got %)', TG_TABLE_NAME, NEW.data_status
            USING ERRCODE = 'check_violation';
    END IF;
    SELECT usage_status INTO src_usage FROM source_registry WHERE source_id = NEW.source_id;
    IF src_usage IS DISTINCT FROM 'RESEARCH_ONLY' THEN
        RAISE EXCEPTION 'source % must be registered RESEARCH_ONLY for table % (is %)', NEW.source_id, TG_TABLE_NAME, COALESCE(src_usage, 'UNREGISTERED')
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

CREATE TABLE card_source_snapshot (
    snapshot_id              TEXT PRIMARY KEY,
    game_version_id          UUID NOT NULL REFERENCES game_version(id),
    source_id                TEXT NOT NULL,
    package_name             TEXT NOT NULL,
    package_version          TEXT NOT NULL,
    declared_window_start    TIMESTAMPTZ,
    declared_window_end      TIMESTAMPTZ,
    license_note             TEXT NOT NULL,
    retrieved_at_semantics   TEXT NOT NULL,
    audit_status             TEXT NOT NULL,
    ingested_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    data_status              TEXT NOT NULL DEFAULT 'RESEARCH_ONLY' CHECK (data_status = 'RESEARCH_ONLY')
);

CREATE TABLE fc27_rarity_catalogue (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_version_id  UUID NOT NULL REFERENCES game_version(id),
    futgg_rarity_id  INTEGER NOT NULL,
    ea_rarity_id     INTEGER NOT NULL,
    rarity_name      TEXT NOT NULL,
    slug             TEXT NOT NULL,
    card_count       INTEGER NOT NULL CHECK (card_count >= 0),   -- as published at snapshot; drifts over time
    is_pseudo_rarity BOOLEAN NOT NULL,                           -- negative EA id (Concepts *)
    source_id        TEXT NOT NULL,
    snapshot_id      TEXT NOT NULL REFERENCES card_source_snapshot(snapshot_id),
    package_retrieved_at TIMESTAMPTZ NOT NULL,                   -- as published; NOT the fetch time
    acquired_from    TIMESTAMPTZ NOT NULL,                       -- from provenance/request_log.csv
    acquired_to      TIMESTAMPTZ NOT NULL,
    data_status      TEXT NOT NULL DEFAULT 'RESEARCH_ONLY' CHECK (data_status = 'RESEARCH_ONLY'),
    UNIQUE (game_version_id, futgg_rarity_id)
);

CREATE TABLE fc27_card_identity (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_version_id     UUID NOT NULL REFERENCES game_version(id),
    source_player_id    TEXT NOT NULL,          -- EA player id (package "game_player_id"); = game_player.source_player_id
    source_card_id      TEXT NOT NULL,          -- fut.gg item id (package "card_id")
    game_player_id      UUID REFERENCES game_player(id),   -- resolved FC27 game_player; NULL when not in our player data
    player_slug         TEXT NOT NULL,
    card_url            TEXT NOT NULL,
    is_base_style       BOOLEAN NOT NULL,       -- derived fact: card id = player id
    sitemap_lastmod     DATE,
    sitemap_row_count   INTEGER NOT NULL DEFAULT 1 CHECK (sitemap_row_count >= 1),  -- 2 = duplicated in source sitemap
    source_id           TEXT NOT NULL,
    snapshot_id         TEXT NOT NULL REFERENCES card_source_snapshot(snapshot_id),
    package_retrieved_at TIMESTAMPTZ NOT NULL,
    acquired_from       TIMESTAMPTZ NOT NULL,
    acquired_to         TIMESTAMPTZ NOT NULL,
    data_status         TEXT NOT NULL DEFAULT 'RESEARCH_ONLY' CHECK (data_status = 'RESEARCH_ONLY'),
    UNIQUE (game_version_id, source_card_id),
    UNIQUE (game_version_id, source_player_id, source_card_id)
);
CREATE INDEX idx_fc27_card_identity_player ON fc27_card_identity (game_version_id, source_player_id);
CREATE INDEX idx_fc27_card_identity_gp ON fc27_card_identity (game_player_id);

CREATE TABLE fc27_role_reference (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_version_id        UUID NOT NULL REFERENCES game_version(id),
    position_page          TEXT NOT NULL,
    role_position_id       INTEGER NOT NULL,
    role_futgg_id          INTEGER NOT NULL,
    role_slug              TEXT NOT NULL,
    role_name              TEXT NOT NULL,
    role_plus_ea_id        INTEGER,
    role_plus_plus_ea_id   INTEGER,
    focus_name             TEXT NOT NULL,
    source_id              TEXT NOT NULL,
    snapshot_id            TEXT NOT NULL REFERENCES card_source_snapshot(snapshot_id),
    package_retrieved_at   TIMESTAMPTZ NOT NULL,
    acquired_from          TIMESTAMPTZ NOT NULL,
    acquired_to            TIMESTAMPTZ NOT NULL,
    data_status            TEXT NOT NULL DEFAULT 'RESEARCH_ONLY' CHECK (data_status = 'RESEARCH_ONLY'),
    UNIQUE (game_version_id, position_page, role_futgg_id, focus_name)
);
COMMENT ON TABLE fc27_role_reference IS 'No base role EA id column: the source carries only plusEaId/plusPlusEaId (verified in raw role pages).';

CREATE TABLE fc27_playstyle_page_reference (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_version_id         UUID NOT NULL REFERENCES game_version(id),
    slug                    TEXT NOT NULL,
    name_derived_from_slug  TEXT NOT NULL,
    sitemap_row_count       INTEGER NOT NULL CHECK (sitemap_row_count >= 1),   -- source sitemap lists duplicates (141 rows / 41 unique)
    version_scope           TEXT NOT NULL DEFAULT 'UNSCOPED_UNVERIFIED' CHECK (version_scope = 'UNSCOPED_UNVERIFIED'),
    source_id               TEXT NOT NULL,
    snapshot_id             TEXT NOT NULL REFERENCES card_source_snapshot(snapshot_id),
    package_retrieved_at    TIMESTAMPTZ NOT NULL,
    acquired_from           TIMESTAMPTZ NOT NULL,
    acquired_to             TIMESTAMPTZ NOT NULL,
    data_status             TEXT NOT NULL DEFAULT 'RESEARCH_ONLY' CHECK (data_status = 'RESEARCH_ONLY'),
    UNIQUE (game_version_id, slug)
);
COMMENT ON TABLE fc27_playstyle_page_reference IS 'URLs carry no game-version marker: FC27 membership NOT verified. Must not be joined into playstyle_definition.';

CREATE TABLE fc27_card_open_flag (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_version_id  UUID NOT NULL REFERENCES game_version(id),
    snapshot_id      TEXT NOT NULL REFERENCES card_source_snapshot(snapshot_id),
    source_id        TEXT NOT NULL,
    flag_type        TEXT NOT NULL,
    entity           TEXT NOT NULL,
    field            TEXT,
    source_a         TEXT, value_a TEXT, source_b TEXT, value_b TEXT,
    status           TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'NOTED', 'RESOLVED')),
    resolution       TEXT, resolved_by TEXT,
    raised_by        TEXT NOT NULL,
    details          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    data_status      TEXT NOT NULL DEFAULT 'RESEARCH_ONLY' CHECK (data_status = 'RESEARCH_ONLY'),
    CHECK (status <> 'RESOLVED' OR (resolution IS NOT NULL AND resolved_by IS NOT NULL))
);
CREATE UNIQUE INDEX uq_fc27_card_open_flag ON fc27_card_open_flag (snapshot_id, flag_type, entity, COALESCE(field, ''));

DO $$ DECLARE t TEXT; BEGIN
  FOREACH t IN ARRAY ARRAY['card_source_snapshot','fc27_rarity_catalogue','fc27_card_identity','fc27_role_reference','fc27_playstyle_page_reference','fc27_card_open_flag'] LOOP
    EXECUTE format('CREATE TRIGGER trg_%s_research_firewall BEFORE INSERT OR UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION enforce_fc27_card_research_firewall()', t, t);
  END LOOP;
END $$;

-- Player spine VIEW (not a copy): per-player aggregation of the card identity rows.
-- first_card_url_by_lowest_card_id uses an EXPLICIT rule; the package's own first_card_url is
-- "first in sitemap file order" (undocumented) and differs for some players.
CREATE VIEW fc27_card_player_spine AS
SELECT i.game_version_id, i.source_player_id, min(i.player_slug) AS player_slug,
       count(*) AS fc27_card_count, bool_or(i.is_base_style) AS has_base_style_card,
       (array_agg(i.card_url ORDER BY i.source_card_id::bigint))[1] AS first_card_url_by_lowest_card_id,
       max(i.game_player_id::text)::uuid AS game_player_id
FROM fc27_card_identity i GROUP BY i.game_version_id, i.source_player_id;

COMMIT;
