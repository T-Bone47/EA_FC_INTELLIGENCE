-- 004: Squads + saved players (additive).

CREATE TABLE IF NOT EXISTS user_squad (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_profile_id UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    formation       TEXT NOT NULL,
    game_version_id UUID NOT NULL REFERENCES game_version(id),
    tactics         JSONB NOT NULL DEFAULT '{}'::jsonb,   -- tactical profile, custom prefs
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_profile_id, name)
);

ALTER TABLE user_squad_slot
    ADD COLUMN IF NOT EXISTS squad_id UUID REFERENCES user_squad(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS ix_slot_squad ON user_squad_slot (squad_id);
-- per-squad slot uniqueness (full unique index, not partial: ON CONFLICT cannot
-- target a partial index without repeating its predicate in every writer)
CREATE UNIQUE INDEX IF NOT EXISTS uq_slot_squad_index ON user_squad_slot (squad_id, slot_index);

CREATE TABLE IF NOT EXISTS user_saved_player (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_profile_id UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    game_version_id UUID NOT NULL REFERENCES game_version(id),
    entity_type     TEXT NOT NULL CHECK (entity_type IN ('game_player','ut_card')),
    entity_id       UUID NOT NULL,
    note            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_profile_id, entity_type, entity_id)
);
