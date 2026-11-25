-- Migration 007: RESEARCH_ONLY data_status for player-scope tables.
--
-- FC26_LEGAL_SOURCE_MATRIX.md and the Phase 20/21/22 source reviews have
-- used "RESEARCH_ONLY" as a classification term since the original data
-- audit (applied to flynn28/eafc26-player-database and the rovnez sofifa
-- dataset). It already exists as a valid data_status on meta_signal
-- (migration 005) but was never enabled on game_player or real_player,
-- which is where a real, well-documented, but explicitly non-commercial
-- dataset (e.g. a Kaggle FC27 snapshot whose own licence text says
-- "unofficial, non-commercial... for analysis and education") actually
-- needs to live: real data, genuinely useful for engineering and
-- validation, structurally excluded from every production read path
-- (game_player_production view, candidate_repository) by the same
-- "data_status = 'CANONICAL'" filter that already excludes
-- PENDING_REVIEW and SYNTHETIC_TEST rows.
--
-- Using PENDING_REVIEW instead would misstate the situation: this data
-- is not awaiting a review that might approve it for production -- its
-- own terms already say non-commercial, permanently, unless a separate
-- licence is obtained. RESEARCH_ONLY says what is actually true.

BEGIN;

ALTER TABLE real_player DROP CONSTRAINT real_player_data_status_check;
ALTER TABLE real_player ADD CONSTRAINT real_player_data_status_check
    CHECK (data_status IN ('CANONICAL','PENDING_REVIEW','SYNTHETIC_TEST','RESEARCH_ONLY'));

ALTER TABLE game_player DROP CONSTRAINT game_player_data_status_check;
ALTER TABLE game_player ADD CONSTRAINT game_player_data_status_check
    CHECK (data_status IN ('CANONICAL','PENDING_REVIEW','SYNTHETIC_TEST','RESEARCH_ONLY'));

COMMENT ON COLUMN game_player.data_status IS
    'CANONICAL rows are the only ones served by game_player_production and '
    'candidate_repository. RESEARCH_ONLY rows are real, ingested, provenance-'
    'tracked data whose source terms explicitly preclude production/commercial '
    'use (e.g. a dataset licensed for non-commercial analysis and education '
    'only) -- they exist for engineering validation, schema/version-wall '
    'testing, and reference, and must never be promoted to CANONICAL without '
    'a documented licence change.';

COMMIT;
