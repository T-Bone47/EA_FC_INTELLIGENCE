"""FC27 research-only dataset profile (Phase 22).

Single place for the facts the FC27 ingestion, provenance, reference-
distribution and validation tooling share. Everything here is evidence-
backed; the evidence is cited next to each value.

This is deliberately NOT the production VersionConfig for FC27:
`scoring_config._FC27_FALLBACK` stays NO_DATA because FC27 has zero
production (CANONICAL) rows. `FC27_RESEARCH_VERSION_CONFIG` is used only to
validate the research snapshot during ingestion.
"""
from __future__ import annotations

from pathlib import Path

from backend.services.scoring_config import VersionConfig

GAME_VERSION = "FC27"
SOURCE_ID = "kaggle_fc27_player_ratings"
DATASET_RELEASE_ID = "fc27-research-2026-09-12-r1"
REFERENCE_DISTRIBUTION_VERSION = "fc27-players-2026-09-r1"
DATA_STATUS = "RESEARCH_ONLY"

KAGGLE_URL = "https://www.kaggle.com/datasets/mikedpad/ea-sports-fc27-player-ratings"
KAGGLE_VERSION = 4            # Kaggle API metadata, lastUpdated 2026-09-14T08:02:25.99Z
SNAPSHOT_DATE = "2026-09-12"  # `snapshot_date` column, identical on every row
LICENCE_TEXT = ("unofficial, non-commercial snapshot for analysis and education "
                "(source README; Kaggle licence field: 'Other (specified in description)'). "
                "All player data and names belong to Electronic Arts.")

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "fc27_research" / "raw"
RAW_ARCHIVE = RAW_DIR / "archive.zip"
RAW_PLAYERS_CSV = RAW_DIR / "extracted" / "players.csv"
RAW_README = RAW_DIR / "extracted" / "README.md"
MANIFEST_PATH = REPO_ROOT / "data" / "fc27_research" / "MANIFEST.json"

# Hashes of the file set received as the user's archive.zip. Kaggle's
# totalBytes for version 4 (5,037,812) equals players.csv (5,031,708) +
# README.md (6,104).
ARCHIVE_SHA256 = "fc1efc564629cbb43008225acd895fa825bb225155d58448be859cbdbdaede5b"
PLAYERS_CSV_SHA256 = "e2fe9d848fa21b04f0b76d851a94ad2d44b8a8c695bc202d4e0f1f5843db1264"
README_SHA256 = "ad4b9459236b7b69736e0817a0a930b5a29504350975f0c0b4cc2603cbc4c0d4"

# Documented independently three times: source README ("All 19,789
# players"), Kaggle subtitle, and EA's official ratings page ("Showing 19789
# results", viewed 2026-09-29).
EXPECTED_ROW_COUNT = 19789

# FC27 position labels. Evidence: all 12 labels appear on page 1 of EA's
# official FC27 ratings table (artifacts/phase22/ea_official_ratings_page1_2026-09-29.json);
# the set is identical to the FC26 reference table (schema comparison only).
# Validation against it is a closed-vocabulary check: an unseen label is
# rejected WITH a reason, never mapped.
POSITION_VOCABULARY: tuple[str, ...] = (
    "GK", "CB", "LB", "RB", "CDM", "CM", "CAM", "LM", "RM", "LW", "RW", "ST")

FC27_RESEARCH_VERSION_CONFIG = VersionConfig(
    code=GAME_VERSION,
    positions=POSITION_VOCABULARY,
    position_types={},            # not published by the source; not derived
    facades=("pace", "shooting", "passing", "dribbling", "defending", "physicality"),
    gk_attributes=("gk_diving", "gk_handling", "gk_kicking", "gk_positioning", "gk_reflexes"),
    playstyle_plus_caps={},       # observed max is reported, never promoted to a rule here
    roles_available=False,
    market_data_available=False,
    chemistry_rules_verified=False,
    women_universe_included=True,  # observed: 1,940 "Women's Football" rows
    data_status=DATA_STATUS,
)
