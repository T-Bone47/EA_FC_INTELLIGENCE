-- Migration 008: FC27 research-only firewall (Phase 22).
--
-- Migration 007 made RESEARCH_ONLY a legal data_status on game_player and
-- real_player. Its comment states that the production read paths exclude
-- such rows "by the same data_status = 'CANONICAL' filter" -- Phase 22
-- reconnaissance measured that this was NOT true for candidate_repository,
-- player_repository or the readiness endpoint (all filtered only
-- `<> 'SYNTHETIC_TEST'`). Those code paths are fixed in the same change;
-- this migration adds the database-level backstops so the guarantee does
-- not depend on every future query remembering the filter:
--
--   1. playstyle_definition may carry RESEARCH_ONLY. PlayStyle names
--      observed only in a research-only source (the FC27 Kaggle snapshot)
--      are version-scoped vocabulary, not canonical reference data.
--
--   2. A trigger makes it impossible to write a game_player row whose
--      source is registered usage_status='RESEARCH_ONLY' with any
--      data_status other than RESEARCH_ONLY. Promotion to CANONICAL
--      therefore requires a documented change to the source registry
--      entry first (a licence change), never a silent UPDATE of rows.

BEGIN;

ALTER TABLE playstyle_definition DROP CONSTRAINT IF EXISTS playstyle_definition_data_status_check;
ALTER TABLE playstyle_definition ADD CONSTRAINT playstyle_definition_data_status_check
    CHECK (data_status IN ('CANONICAL','NOT_INGESTED','SYNTHETIC_TEST','RESEARCH_ONLY'));

CREATE OR REPLACE FUNCTION enforce_research_only_game_player() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    src_usage TEXT;
BEGIN
    SELECT usage_status INTO src_usage FROM source_registry WHERE source_id = NEW.source_id;
    IF src_usage = 'RESEARCH_ONLY' AND NEW.data_status <> 'RESEARCH_ONLY' THEN
        RAISE EXCEPTION
            'game_player % from RESEARCH_ONLY source % must have data_status RESEARCH_ONLY (got %)',
            NEW.source_player_id, NEW.source_id, NEW.data_status
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_research_only_game_player ON game_player;
CREATE TRIGGER trg_research_only_game_player
    BEFORE INSERT OR UPDATE OF data_status, source_id ON game_player
    FOR EACH ROW EXECUTE FUNCTION enforce_research_only_game_player();

COMMENT ON FUNCTION enforce_research_only_game_player() IS
    'Phase 22 firewall: rows from a source registered RESEARCH_ONLY can only '
    'ever be RESEARCH_ONLY. Excluded from every production read path, which '
    'filters data_status = ''CANONICAL''.';

COMMIT;
