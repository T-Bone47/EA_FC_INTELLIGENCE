BEGIN;

-- A licence registry decision authorizes a release, never every row in a game.
-- No historical rows are enrolled. Membership requires a reviewed observation.
CREATE TABLE catalogue_release_member (
    entity_scope text NOT NULL CHECK (entity_scope IN ('game_player','ut_card')),
    entity_id uuid NOT NULL,
    dataset_version text NOT NULL CHECK (length(dataset_version) > 0),
    game_version_id uuid NOT NULL REFERENCES game_version(id),
    source_id text NOT NULL REFERENCES source_registry(source_id),
    source_observation_id uuid NOT NULL REFERENCES source_observation(id) ON DELETE CASCADE,
    PRIMARY KEY (entity_scope, entity_id, dataset_version)
);
CREATE INDEX catalogue_members_by_release ON catalogue_release_member (game_version_id, entity_scope, dataset_version);
CREATE INDEX catalogue_members_by_observation ON catalogue_release_member (source_observation_id);

CREATE SCHEMA catalogue_serving;
CREATE VIEW catalogue_serving.member AS
SELECT m.*
FROM public.catalogue_release_member m
JOIN public.game_version gv ON gv.id = m.game_version_id
JOIN public.source_observation o ON o.id = m.source_observation_id
    AND o.source_id = m.source_id AND o.game_version_id = m.game_version_id
JOIN public.source_registry s ON s.source_id = m.source_id
WHERE m.dataset_version = (NULLIF(current_setting('eafc.catalogue_releases', true), '')::jsonb
                            -> gv.code ->> m.entity_scope)
  AND s.legal_gate IN ('CLEARED', 'NOT_REQUIRED')
  AND (s.usage_status IN ('OFFICIAL', 'AUTHORIZED', 'LICENSED')
       OR (s.usage_status = 'RESEARCH_ONLY'
           AND current_setting('eafc.catalogue_mode', true) = 'research'));

CREATE VIEW catalogue_serving.game_player AS
SELECT gp.* FROM public.game_player gp
WHERE (gp.data_status = 'CANONICAL'
       OR (gp.data_status = 'RESEARCH_ONLY'
           AND current_setting('eafc.catalogue_mode', true) = 'research'))
AND EXISTS (SELECT 1 FROM catalogue_serving.member m
             WHERE m.entity_scope = 'game_player' AND m.entity_id = gp.id
               AND m.game_version_id = gp.game_version_id AND m.source_id = gp.source_id);

CREATE VIEW catalogue_serving.ut_card AS
SELECT uc.* FROM public.ut_card uc
WHERE uc.data_status = 'CANONICAL' AND NOT uc.is_synthetic
AND EXISTS (SELECT 1 FROM catalogue_serving.member m
             WHERE m.entity_scope = 'ut_card' AND m.entity_id = uc.id
               AND m.game_version_id = uc.game_version_id AND m.source_id = uc.source_id);

CREATE VIEW catalogue_serving.card_price AS
SELECT p.* FROM public.card_price p
JOIN catalogue_serving.ut_card c ON c.id = p.ut_card_id
JOIN catalogue_serving.member m ON m.entity_scope = 'ut_card' AND m.entity_id = c.id
    AND m.source_observation_id = p.source_observation_id;

CREATE VIEW catalogue_serving.card_version AS
SELECT v.* FROM public.card_version v
JOIN catalogue_serving.ut_card c ON c.id = v.ut_card_id
JOIN catalogue_serving.member m ON m.entity_scope = 'ut_card' AND m.entity_id = c.id
    AND m.source_observation_id = v.source_observation_id;

CREATE VIEW catalogue_serving.source_observation AS
SELECT o.* FROM public.source_observation o
WHERE EXISTS (SELECT 1 FROM catalogue_serving.member m WHERE m.source_observation_id = o.id);

-- Any later edit invalidates the membership of the affected row.
CREATE FUNCTION invalidate_catalogue_entity() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, public AS $$
DECLARE previous_id uuid; incoming_id uuid;
BEGIN
    IF TG_OP <> 'INSERT' THEN previous_id := (to_jsonb(OLD) ->> TG_ARGV[1])::uuid; END IF;
    IF TG_OP <> 'DELETE' THEN incoming_id := (to_jsonb(NEW) ->> TG_ARGV[1])::uuid; END IF;
    IF EXISTS (SELECT 1 FROM catalogue_release_member
               WHERE entity_scope = TG_ARGV[0] AND entity_id IN (previous_id, incoming_id)) THEN
        DELETE FROM catalogue_release_member
         WHERE entity_scope = TG_ARGV[0] AND entity_id IN (previous_id, incoming_id);
    END IF;
    RETURN NULL;
END $$;

CREATE TRIGGER catalogue_entity_change AFTER UPDATE OR DELETE ON game_player
    FOR EACH ROW EXECUTE FUNCTION invalidate_catalogue_entity('game_player','id');
CREATE TRIGGER catalogue_entity_change AFTER UPDATE OR DELETE ON ut_card
    FOR EACH ROW EXECUTE FUNCTION invalidate_catalogue_entity('ut_card','id');

DO $$ DECLARE t text; BEGIN
    FOREACH t IN ARRAY ARRAY['game_player_attributes','game_player_position_secondary',
        'game_player_playstyle','club_affiliation'] LOOP
        EXECUTE format('CREATE TRIGGER catalogue_fact_change AFTER INSERT OR UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION invalidate_catalogue_entity(''game_player'',''game_player_id'')', t);
    END LOOP;
    FOREACH t IN ARRAY ARRAY['ut_card_attribute_override','ut_card_playstyle','ut_card_role','card_version','card_price'] LOOP
        EXECUTE format('CREATE TRIGGER catalogue_fact_change AFTER INSERT OR UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION invalidate_catalogue_entity(''ut_card'',''ut_card_id'')', t);
    END LOOP;
END $$;

-- Shared definitions and identity links are reviewed with the parent release.
CREATE FUNCTION invalidate_catalogue_related() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, public AS $$
BEGIN
    CASE TG_TABLE_NAME
      WHEN 'club' THEN
        DELETE FROM catalogue_release_member m USING club_affiliation a
         WHERE m.entity_scope = 'game_player' AND m.entity_id = a.game_player_id AND a.club_id = OLD.id;
      WHEN 'playstyle_definition' THEN
        DELETE FROM catalogue_release_member m USING game_player_playstyle p
         WHERE m.entity_scope = 'game_player' AND m.entity_id = p.game_player_id
           AND p.playstyle_definition_id = OLD.id;
      WHEN 'real_player' THEN
        DELETE FROM catalogue_release_member m USING game_player p
         WHERE m.entity_scope = 'game_player' AND m.entity_id = p.id AND p.real_player_id = OLD.id;
      WHEN 'card_rarity' THEN
        DELETE FROM catalogue_release_member m USING ut_card c
         WHERE m.entity_scope = 'ut_card' AND m.entity_id = c.id AND c.rarity_id = OLD.id;
      WHEN 'source_observation' THEN
        DELETE FROM catalogue_release_member WHERE source_observation_id = OLD.id;
    END CASE;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;

DO $$ DECLARE t text; BEGIN
    FOREACH t IN ARRAY ARRAY['club','playstyle_definition','real_player','card_rarity','source_observation'] LOOP
        EXECUTE format('CREATE TRIGGER catalogue_related_change BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION invalidate_catalogue_related()', t);
    END LOOP;
END $$;

CREATE FUNCTION clear_catalogue_scope() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, public AS $$
BEGIN
    DELETE FROM catalogue_release_member WHERE entity_scope = TG_ARGV[0];
    RETURN NULL;
END $$;

DO $$ DECLARE t text; BEGIN
    FOREACH t IN ARRAY ARRAY['game_player','game_player_attributes','game_player_position_secondary',
        'game_player_playstyle','club_affiliation','club','playstyle_definition','real_player'] LOOP
        EXECUTE format('CREATE TRIGGER catalogue_truncated AFTER TRUNCATE ON %I FOR EACH STATEMENT EXECUTE FUNCTION clear_catalogue_scope(''game_player'')', t);
    END LOOP;
    FOREACH t IN ARRAY ARRAY['ut_card','ut_card_attribute_override','ut_card_playstyle','ut_card_role',
        'card_version','card_price','card_rarity'] LOOP
        EXECUTE format('CREATE TRIGGER catalogue_truncated AFTER TRUNCATE ON %I FOR EACH STATEMENT EXECUTE FUNCTION clear_catalogue_scope(''ut_card'')', t);
    END LOOP;
END $$;

CREATE TRIGGER catalogue_members_changed AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE ON catalogue_release_member
    FOR EACH STATEMENT EXECUTE FUNCTION advance_candidate_generation();
CREATE TRIGGER catalogue_sources_changed AFTER UPDATE OR DELETE OR TRUNCATE ON source_registry
    FOR EACH STATEMENT EXECUTE FUNCTION advance_candidate_generation();

COMMIT;
