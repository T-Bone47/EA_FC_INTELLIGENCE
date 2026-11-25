BEGIN;
-- Statement triggers version every joined input. The counter advances only on commit.
CREATE TABLE candidate_cache_generation (
    singleton boolean PRIMARY KEY CHECK (singleton), generation bigint NOT NULL DEFAULT 0
);
INSERT INTO candidate_cache_generation(singleton) VALUES (true);
CREATE FUNCTION advance_candidate_generation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    UPDATE candidate_cache_generation SET generation = generation + 1 WHERE singleton;
    RETURN NULL;
END $$;
DO $$ DECLARE t text; BEGIN
    FOREACH t IN ARRAY ARRAY['game_player','game_player_attributes','game_player_playstyle',
        'playstyle_definition','game_player_position_secondary','club_affiliation','club','game_version'] LOOP
        EXECUTE format('CREATE TRIGGER candidate_input_change AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE ON %I FOR EACH STATEMENT EXECUTE FUNCTION advance_candidate_generation()', t);
    END LOOP;
END $$;

ALTER TABLE card_source_snapshot ADD COLUMN inventory_sha256 text;

CREATE OR REPLACE VIEW fc27_card_player_spine AS
SELECT i.game_version_id, i.source_player_id, min(i.player_slug) AS player_slug,
       count(*) AS fc27_card_count, bool_or(i.is_base_style) AS has_base_style_card,
       (array_agg(i.card_url ORDER BY i.source_card_id::bigint))[1] AS first_card_url_by_lowest_card_id,
       CASE WHEN count(DISTINCT i.game_player_id) = 1 THEN min(i.game_player_id::text)::uuid END AS game_player_id,
       count(DISTINCT i.game_player_id) > 1 AS conflicting_player_links
FROM fc27_card_identity i GROUP BY i.game_version_id, i.source_player_id;
COMMIT;
