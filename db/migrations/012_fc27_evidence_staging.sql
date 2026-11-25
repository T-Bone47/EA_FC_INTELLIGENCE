BEGIN;
CREATE SCHEMA fc27_staging;
CREATE TABLE fc27_staging.snapshot (
    snapshot_id text PRIMARY KEY,
    source_id text NOT NULL,
    sha256 text UNIQUE NOT NULL CHECK (sha256 ~ '^[a-f0-9]{64}$'),
    manifest jsonb NOT NULL CHECK (manifest->>'game_version' = 'FC27'
        AND manifest->>'production_reuse_scope' = 'NONE' AND manifest ? 'source_rights_status')
);
CREATE TABLE fc27_staging.observation (
    snapshot_id text NOT NULL REFERENCES fc27_staging.snapshot,
    record_id text NOT NULL,
    source_row_number integer NOT NULL CHECK (source_row_number >= 2),
    raw jsonb NOT NULL,
    normalized jsonb NOT NULL,
    identity_review jsonb,
    PRIMARY KEY (snapshot_id, record_id),
    UNIQUE (snapshot_id, source_row_number)
);
CREATE FUNCTION fc27_staging.reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'FC27 source evidence is append-only';
END $$;
CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE OR TRUNCATE ON fc27_staging.snapshot
    FOR EACH STATEMENT EXECUTE FUNCTION fc27_staging.reject_mutation();
CREATE TRIGGER immutable_observation BEFORE UPDATE OR DELETE OR TRUNCATE ON fc27_staging.observation
    FOR EACH STATEMENT EXECUTE FUNCTION fc27_staging.reject_mutation();
COMMIT;
