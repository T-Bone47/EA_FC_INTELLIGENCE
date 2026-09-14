-- ============================================================================
-- seed_reference_data.sql — version-aware reference data.
-- Idempotent. Rarities / positions / caps are REFERENCE TABLES, not hardcoded
-- engine constants, so FC27+ can be added without code changes.
-- ============================================================================

-- game versions ----------------------------------------------------------------
INSERT INTO game_version (code, display_name, status, released_on, config) VALUES
  ('FC26', 'EA SPORTS FC 26', 'ACTIVE', DATE '2025-09-26', '{
     "positions": ["GK","CB","LB","RB","CDM","CM","CAM","LM","RM","LW","RW","ST"],
     "position_types": {"Defense":["GK","CB","LB","RB"],"Midfielder":["CDM","CM","CAM","LM","RM"],"Attack":["LW","RW","ST"]},
     "facades": ["pace","shooting","passing","dribbling","defending","physicality"],
     "gk_attributes": ["gk_diving","gk_handling","gk_kicking","gk_positioning","gk_reflexes"],
     "playstyle_plus_available": true,
     "roles_available": false,
     "market_data_available": false,
     "chemistry_rules_verified": false,
     "women_universe_included": false
   }'::jsonb),
  ('FC27', 'EA SPORTS FC 27', 'NO_DATA', NULL, '{
     "positions": [],
     "facades": ["pace","shooting","passing","dribbling","defending","physicality"],
     "playstyle_plus_available": null,
     "roles_available": null,
     "market_data_available": false,
     "chemistry_rules_verified": false,
     "data_acquisition_status": "BLOCKED_TECHNICAL_AND_ACCESS",
     "note": "Architecture supports FC27; zero records acquired. Nothing fabricated."
   }'::jsonb)
ON CONFLICT (code) DO UPDATE
  SET display_name = EXCLUDED.display_name,
      status = EXCLUDED.status,
      released_on = EXCLUDED.released_on,
      config = EXCLUDED.config;

-- source registry --------------------------------------------------------------
INSERT INTO source_registry
  (source_id, name, source_type, authority_tier, url, license, usage_status,
   legal_gate, cleared_by, cleared_at, canonical_fields, notes)
VALUES
  ('ea_official_ratings', 'EA SPORTS FC Ratings (official)', 'OFFICIAL_PAGE', 1,
   'https://www.ea.com/games/ea-sports-fc/ratings', 'EA proprietary', 'OFFICIAL',
   'REQUIRED', NULL, NULL,
   ARRAY['overall_rating','pace','shooting','passing','dribbling','defending','physicality',
         'position_primary','nation','club'],
   'Canonical authority for the fields EA publishes. Bulk table data is not exposed to a standard page fetch (JS-rendered / undocumented endpoints) so direct bulk ingestion is NOT performed. Accessed only for field-level schema confirmation.'),

  ('kaggle_justdhia_ea_fc26_player_ratings', 'EA Sports FC 26 Player Ratings (Kaggle carrier)', 'CARRIER_DATASET', 3,
   'https://www.kaggle.com/datasets/justdhia/ea-sports-fc-26-player-ratings', 'CC0 1.0 Public Domain',
   'LICENSED', 'CLEARED', 'project-owner-license-review', TIMESTAMPTZ '2026-09-14 00:00:00+00',
   ARRAY['overall_rating','pace','shooting','passing','dribbling','defending','physicality',
         'position_primary','position_secondary','nation','club','league','date_of_birth',
         'height_cm','weight_kg','preferred_foot','weak_foot_stars','skill_moves_stars',
         'gk_diving','gk_handling','gk_kicking','gk_positioning','gk_reflexes',
         'playstyles','playstyles_plus','detailed_attributes'],
   'CC0-licensed carrier of values scraped from the official EA ratings page (men''s universe, scraped March 2026). CC0 permits commercial use and redistribution. 16,228 players; forensics in docs/DATASET_FORENSICS_FC26.md. Authority is derived from EA; conflicts defer to ea_official_ratings.'),

  ('synthetic_fixtures', 'Synthetic test fixtures (project-generated)', 'SYNTHETIC_FIXTURE', 5,
   NULL, 'project-internal', 'SYNTHETIC_TEST', 'NOT_REQUIRED', NULL, NULL, ARRAY[]::TEXT[],
   'FICTIONAL UT cards and generated test data. MUST NEVER enter production queries. Firewall: ut_card.is_synthetic = TRUE and data_status = SYNTHETIC_TEST.'),

  ('futbin', 'FUTBIN', 'COMMUNITY_DB', 4, 'https://www.futbin.com', 'proprietary; scraping prohibited',
   'PUBLIC_REFERENCE', 'REQUIRED', NULL, NULL, ARRAY[]::TEXT[],
   'Not ingested. Reference-only for card-structure/schema discovery. No scraping performed.'),

  ('futgg', 'FUT.GG', 'COMMUNITY_DB', 4, 'https://www.fut.gg', 'proprietary', 'UNKNOWN', 'REQUIRED',
   NULL, NULL, ARRAY[]::TEXT[], 'Not ingested. No access attempted.'),

  ('futwiz', 'FUTWIZ', 'COMMUNITY_DB', 4, 'https://www.futwiz.com', 'proprietary', 'UNKNOWN',
   'REQUIRED', NULL, NULL, ARRAY[]::TEXT[], 'Not ingested. No access attempted.'),

  ('wefut', 'WeFUT', 'COMMUNITY_DB', 4, 'https://www.wefut.com', 'proprietary', 'UNKNOWN',
   'REQUIRED', NULL, NULL, ARRAY[]::TEXT[], 'Not ingested. No access attempted.'),

  ('ut_market_feed', 'Live UT market feed (none available)', 'MARKET_FEED', 2, NULL, NULL,
   'NOT_PERMITTED', 'REQUIRED', NULL, NULL, ARRAY[]::TEXT[],
   'No legitimate live market source is available. Prices remain UNKNOWN. NullBudgetProvider in use.')
ON CONFLICT (source_id) DO UPDATE
  SET name = EXCLUDED.name, source_type = EXCLUDED.source_type,
      authority_tier = EXCLUDED.authority_tier, url = EXCLUDED.url,
      license = EXCLUDED.license, usage_status = EXCLUDED.usage_status,
      legal_gate = EXCLUDED.legal_gate, canonical_fields = EXCLUDED.canonical_fields,
      notes = EXCLUDED.notes;

-- FC26 card rarities (reference table; card-level data still NOT ingested) -------
INSERT INTO card_rarity (game_version_id, rarity_code, rarity_name, is_promo, data_status)
SELECT gv.id, v.code, v.name, v.promo, 'NOT_INGESTED'
FROM game_version gv
CROSS JOIN (VALUES
  ('bronze','Bronze',FALSE), ('silver','Silver',FALSE), ('gold','Gold',FALSE),
  ('totw','Team of the Week',TRUE), ('icons','Icon',TRUE), ('hero','Hero',TRUE)
) AS v(code, name, promo)
WHERE gv.code = 'FC26'
ON CONFLICT (game_version_id, rarity_code) DO NOTHING;

-- PlayStyle+ cap: FC26 player_base = 1, evidence-based from dataset forensics
-- (max observed plus-per-player across all 119 PlayStyle+ holders is exactly 1).
INSERT INTO playstyle_plus_cap (game_version_id, scope, max_plus, evidence_note)
SELECT id, 'player_base', 1,
       'Observed maximum PlayStyle+ count per player = 1 across all 119 holders in the CC0 FC26 foundation (docs/DATASET_FORENSICS_FC26.md). Card-scope cap for promo cards is UNKNOWN and intentionally not seeded.'
FROM game_version WHERE code = 'FC26'
ON CONFLICT (game_version_id, scope) DO UPDATE SET max_plus = EXCLUDED.max_plus,
       evidence_note = EXCLUDED.evidence_note;

-- FC27 cap intentionally NOT seeded: unknown, must not be guessed.
