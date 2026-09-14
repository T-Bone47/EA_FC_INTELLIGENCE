#!/usr/bin/env python3
"""Ingest the 20 real-world identity facts and resolve them against canonical
FC26 GamePlayers (conservative policy §38).

Expected outcome (documented in the handoff): 19 unique resolutions + 1
ambiguous 'Cristiano Ronaldo' case routed to REVIEW_REQUIRED (never merged).
"""
from __future__ import annotations

import csv
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.db import close_pool, execute, get_conn, query  # noqa: E402
from backend.domain.card_model import GamePlayer, GameVersionCode, IdentityStatus  # noqa: E402
from backend.ingestion.identity_resolver import IdentityResolver  # noqa: E402
from backend.ingestion.normalizer import normalize_name  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
IDENTITIES_CSV = ROOT / "data" / "real_player_identities.csv"
NS = uuid.UUID("6f1e2d3c-4b5a-4968-8776-655443322110")


def main() -> None:
    # 1. upsert RealPlayer identity records
    with open(IDENTITIES_CSV, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        rid = uuid.uuid5(NS, f"real_player|{normalize_name(r['full_name'])}")
        execute("""
            INSERT INTO real_player (id, full_name, normalized_name, nationality,
                                     date_of_birth, position_hint, identity_status)
            VALUES (%s,%s,%s,%s,%s,%s,'UNRESOLVED')
            ON CONFLICT (id) DO UPDATE SET
              full_name=EXCLUDED.full_name, normalized_name=EXCLUDED.normalized_name,
              nationality=EXCLUDED.nationality, date_of_birth=EXCLUDED.date_of_birth,
              position_hint=EXCLUDED.position_hint, updated_at=now()""",
            (str(rid), r["full_name"], normalize_name(r["full_name"]),
             r["nationality"] or None, r["date_of_birth"] or None,
             r["position"] or None))

    # 2. load canonical FC26 GamePlayers (production data only)
    gps = []
    for g in query("""
            SELECT gp.id, gp.display_name, gp.first_name, gp.last_name,
                   gp.common_name, gp.nation, gp.date_of_birth, gp.position_primary
            FROM game_player gp JOIN game_version gv ON gv.id = gp.game_version_id
            WHERE gv.code='FC26' AND gp.data_status <> 'SYNTHETIC_TEST'"""):
        gps.append(GamePlayer(
            id=g["id"], game_version=GameVersionCode.FC26, source_id="x",
            source_player_id=0, display_name=g["display_name"],
            first_name=g["first_name"], last_name=g["last_name"],
            common_name=g["common_name"],
            position_primary=g["position_primary"], overall_rating=None,
            nation=g["nation"],
            date_of_birth=str(g["date_of_birth"]) if g["date_of_birth"] else None))

    # 3. resolve each identity record conservatively
    resolver = IdentityResolver.__new__(IdentityResolver)   # index not needed for RP-side
    from backend.ingestion.identity_resolver import IdentityIndex
    resolver = IdentityResolver(IdentityIndex())
    summary = {"resolved": 0, "review": 0, "unresolved": 0, "details": []}
    for r in rows:
        rid = uuid.uuid5(NS, f"real_player|{normalize_name(r['full_name'])}")
        from backend.domain.card_model import RealPlayer
        rp = RealPlayer(id=rid, full_name=r["full_name"],
                        normalized_name=normalize_name(r["full_name"]),
                        nationality=r["nationality"] or None,
                        date_of_birth=r["date_of_birth"] or None,
                        position_hint=r["position"] or None)
        res = resolver.resolve_identity_record(rp, gps)
        status = res.status
        matched_id = res.matched_game_player.id if res.matched_game_player else None
        execute("UPDATE real_player SET identity_status=%s WHERE id=%s",
                (status.value, str(rid)))
        if status == IdentityStatus.RESOLVED and matched_id:
            execute("""UPDATE game_player SET real_player_id=%s, identity_status='RESOLVED',
                       updated_at=now() WHERE id=%s""", (str(rid), str(matched_id)))
            summary["resolved"] += 1
        elif status == IdentityStatus.REVIEW_REQUIRED:
            summary["review"] += 1
        else:
            summary["unresolved"] += 1
        summary["details"].append({"name": r["full_name"], "status": status.value,
                                   "reason": res.reason})
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    try:
        main()
    finally:
        close_pool()
