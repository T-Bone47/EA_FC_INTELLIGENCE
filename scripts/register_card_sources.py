#!/usr/bin/env python3
"""Register Phase 3 card-data source research findings (§22/§24/§54).

Records the license/permission/API-terms research per source in
source_registry. NO data is fetched or ingested here — every source stays
behind its legal gate until a human clears it. Availability != permission.

Research date: 2026-09-14 (see docs/CARD_DATA_ACQUISITION.md for the full
per-source table and evidence).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.db import close_pool, execute, query  # noqa: E402

RESEARCH_DATE = "2026-09-14"

# source_id, name, type, tier, url, license, usage_status, legal_gate, notes
SOURCES = [
    ("ea_official_fut_database",
     "EA SPORTS official FUT Database (historical)",
     "OFFICIAL_PAGE", 1,
     "https://www.ea.com/games/ea-sports-fc/ultimate-team/fut/database",
     "EA proprietary", "UNKNOWN", "REQUIRED",
     f"Researched {RESEARCH_DATE}: URL returns 404 — the official downloadable "
     "FUT database was discontinued after FIFA 23. EA's current ratings pages "
     "(ea.com/games/ea-sports-fc/ratings) publish BASE player ratings only, are "
     "JS-gated and carry no card/promo/pricing feed. No official machine-"
     "accessible UT card source exists. Re-check each title update."),
    ("kaggle_flynn28_eafc26_player_db",
     "Kaggle: EAFC26 Player Database (flynn28)",
     "CARRIER_DATASET", 4,
     "https://www.kaggle.com/datasets/flynn28/eafc26-player-database",
     "GPL-3", "RESEARCH_ONLY", "REQUIRED",
     f"Researched {RESEARCH_DATE}: 20,933-row FC26 player ratings CSV incl. "
     "play styles + a 'card' column and an api.msmc.cc endpoint. GPL-3 applies "
     "to the compilation; underlying ratings originate from EA pages (scraped). "
     "Overlaps the already-ingested CC0 justdhia player set; adds no verified "
     "PROMO CARD data. Schema research only — never auto-activate."),
    ("kaggle_flynn28_fc26_rating_cards_images",
     "Kaggle: Complete EA FC26 Rating Cards Database (flynn28)",
     "CARRIER_DATASET", 4,
     "https://www.kaggle.com/datasets/flynn28/complete-ea-fc26-rating-cards-database",
     "CC BY 4.0 (claimed)", "RESEARCH_ONLY", "REQUIRED",
     f"Researched {RESEARCH_DATE}: 17,873 .webp card ARTWORK images (593 MB), "
     "not structured data. Uploader's CC BY claim over EA-copyrighted card art "
     "is legally doubtful; redistributing the artwork is NOT assumed permitted. "
     "Base rating cards only — no promo cards, no prices. Unusable as canonical "
     "attribute data (OCR of artwork would be fabrication-adjacent). Reference "
     "for rarity/card-type vocabulary research only."),
    ("futdatabase_com",
     "Futdatabase.com (FutDB) commercial API",
     "OTHER", 3,
     "https://www.futdatabase.com/",
     "proprietary ToS (not reviewed)", "UNKNOWN", "REQUIRED",
     f"Researched {RESEARCH_DATE}: advertises FC26 players/prices/card-types "
     "JSON API. 'Free' tier is a funnel: player stats and prices require "
     "premium (~EUR 79/month) via a checkout provider. Data provenance "
     "unstated (community sites of this kind typically crawl EA's private "
     "web-app API — unauthorized). Redistribution terms unknown. NOT ingested: "
     "payment + ToS review + provenance verification are human decisions."),
    ("futdb_app",
     "futdb.app third-party FUT API",
     "OTHER", 3,
     "https://futdb.app/",
     "unknown", "UNKNOWN", "REQUIRED",
     f"Researched {RESEARCH_DATE}: mentioned in community threads as a FUT "
     "data API. License/terms/provenance not verifiable without registration. "
     "Availability != permission — stays gated."),
]

# Community tracker sites: scraping violates their ToS (established earlier).
NOT_PERMITTED_NOTES = (
    f"Re-confirmed {RESEARCH_DATE}: card data obtainable only by scraping "
    "against ToS and/or via EA's private web-app API — NOT_PERMITTED for "
    "ingestion. May inform schema/vocabulary research from public docs only."
)


def main() -> None:
    for (sid, name, stype, tier, url, lic, status, gate, notes) in SOURCES:
        execute(
            """INSERT INTO source_registry
                 (source_id, name, source_type, authority_tier, url, license,
                  usage_status, legal_gate, canonical_fields, notes)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'{}',%s)
               ON CONFLICT (source_id) DO UPDATE SET
                 name = EXCLUDED.name, url = EXCLUDED.url,
                 license = EXCLUDED.license, usage_status = EXCLUDED.usage_status,
                 legal_gate = EXCLUDED.legal_gate, notes = EXCLUDED.notes""",
            (sid, name, stype, tier, url, lic, status, gate, notes))
        print(f"registered {sid:42s} {status}")

    for sid in ("futbin", "futwiz", "futgg", "wefut"):
        row = query("SELECT usage_status, notes FROM source_registry WHERE source_id=%s",
                    (sid,))
        if not row:
            continue
        if row[0]["usage_status"] not in ("NOT_PERMITTED",):
            execute("UPDATE source_registry SET usage_status='NOT_PERMITTED' WHERE source_id=%s",
                    (sid,))
        note = row[0]["notes"] or ""
        if "Re-confirmed" not in note:
            execute("UPDATE source_registry SET notes = %s WHERE source_id=%s",
                    (f"{note} | {NOT_PERMITTED_NOTES}".strip(" |"), sid))
        print(f"re-confirmed {sid:40s} NOT_PERMITTED")

    rows = query("SELECT source_id, usage_status, legal_gate FROM source_registry "
                 "ORDER BY source_id")
    print("\nsource_registry now:")
    for r in rows:
        print(f"  {r['source_id']:44s} {r['usage_status']:16s} gate={r['legal_gate']}")
    close_pool()


if __name__ == "__main__":
    main()
