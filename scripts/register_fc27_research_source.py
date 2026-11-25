#!/usr/bin/env python3
"""Register the FC27 Kaggle ratings snapshot as a RESEARCH_ONLY source (Phase 22).

Evidence (retrieved 2026-09-29):
  * Kaggle API metadata for mikedpad/ea-sports-fc27-player-ratings:
    licenseName "Other (specified in description)", currentVersionNumber 4,
    lastUpdated 2026-09-14T08:02:25.99Z, totalBytes 5,037,812 (equal to the
    received players.csv + README.md byte sizes).
  * Source README, "Source and legal": "This is an unofficial, non-commercial
    snapshot for analysis and education"; "All player data and names belong
    to Electronic Arts."

Classification:
  usage_status = RESEARCH_ONLY  -> not in PRODUCTION_PERMITTED; the conflict
                                   resolver can never let it win a production
                                   field; every production read path filters
                                   data_status = 'CANONICAL'.
  legal_gate   = CLEARED, scope-limited: access/ingestion of the locally
                 supplied file for non-commercial research, as directed by the
                 project owner's Phase 22 instruction (2026-09-29). This is NOT
                 production clearance. Revoke by setting legal_gate='REQUIRED'.

Idempotent registration; existing owner clearance decisions are retained.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.db import close_pool, execute, query
from backend.ingestion import fc27_research_profile as P
from backend.ingestion.ea_ratings_csv_adapter import ATTRIBUTE_COLUMN_MAP

CARRIED_FIELDS = (
    ["overall_rating", "position_primary", "position_secondary", "nation", "club",
     "league", "date_of_birth", "preferred_foot", "weak_foot_stars",
     "skill_moves_stars", "gender", "playstyles", "playstyles_plus",
     "pace", "shooting", "passing", "dribbling", "defending", "physicality"]
    + sorted(ATTRIBUTE_COLUMN_MAP.values()))

NOTES = (
    f"RESEARCH_ONLY. Kaggle dataset v{P.KAGGLE_VERSION}, snapshot {P.SNAPSHOT_DATE}, "
    f"{P.EXPECTED_ROW_COUNT} rows x 60 columns (17,849 Men's Football / 1,940 Women's "
    f"Football / 2,204 GK). players.csv sha256 {P.PLAYERS_CSV_SHA256}. "
    "Values come from EA's public ratings API (per README). Licence text: "
    f"{P.LICENCE_TEXT} Allowed here: engineering, schema validation, version-wall "
    "tests, V3.1 research validation, reference-distribution experiments. NOT "
    "allowed: production serving, commercial release, commercial fine-tuning. "
    "legal_gate=CLEARED covers local research ingestion only (project-owner Phase 22 "
    "instruction 2026-09-29); production legal status is RED. canonical_fields lists "
    "the fields this source carries for the RESEARCH_ONLY universe; it is authority "
    "for no production field. GK rows: the six outfield-named face-stat columns hold "
    "GK face stats and are not mapped (docs/FC26_FC27_ATTRIBUTE_SCHEMA_DIFF.md)."
)


def main() -> None:
    execute(
        """INSERT INTO source_registry
             (source_id, name, source_type, authority_tier, url, license,
              usage_status, legal_gate, cleared_by, cleared_at, canonical_fields, notes)
           VALUES (%s,%s,'CARRIER_DATASET',4,%s,%s,'RESEARCH_ONLY','CLEARED',%s,
                   TIMESTAMPTZ '2026-09-29 00:00:00+00',%s,%s)
           ON CONFLICT (source_id) DO NOTHING""",
        (P.SOURCE_ID,
         "EA SPORTS FC 27 Player Ratings (Kaggle: mikedpad) -- research-only snapshot",
         P.KAGGLE_URL,
         "Other (specified in description): " + P.LICENCE_TEXT,
         "project-owner Phase 22 instruction 2026-09-29; scope = local non-commercial "
         "research ingestion ONLY; production NOT cleared",
         CARRIED_FIELDS, NOTES))
    row = query("SELECT source_id, usage_status, legal_gate, authority_tier "
                "FROM source_registry WHERE source_id=%s", (P.SOURCE_ID,))[0]
    print(f"registered {row['source_id']} usage={row['usage_status']} "
          f"gate={row['legal_gate']} tier={row['authority_tier']}")


if __name__ == "__main__":
    try:
        main()
    finally:
        close_pool()
