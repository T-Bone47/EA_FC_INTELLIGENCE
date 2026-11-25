#!/usr/bin/env python
"""Build a frozen v3 reference distribution for ONE game version from the
ingested player rows and write it as a versioned JSON artifact.

This is an explicit, offline, human-triggered build step (per
FC26_REFERENCE_DISTRIBUTION_SPEC.md S1: "never live during recommendation
scoring", "regenerated only on explicit data release"). It is never invoked
by the engine or the API.

Version-aware (Phase 22):
  FC26 -> data/reference_distributions/fc26-players-2026-09-r1.json
          from data_status='CANONICAL' FC26 rows. The artifact is FROZEN:
          the script refuses to overwrite an existing file (use --verify to
          recompute and compare the content hash without writing).
  FC27 -> data/reference_distributions/research/fc27-players-2026-09-r1.json
          from data_status='RESEARCH_ONLY' FC27 rows only, tagged
          data_status=RESEARCH_ONLY. Lives outside the production artifact
          directory so the production loader cannot reach it by name.
Each version is built from its own rows only; nothing crosses the wall.

Usage:
    python scripts/build_reference_distribution_v3.py --game-version FC27
    python scripts/build_reference_distribution_v3.py --game-version FC26 --verify
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.db import close_pool, get_catalogue_conn
from backend.domain.card_model import DETAIL_ATTRS, GK_ATTRS
from backend.ingestion import fc27_research_profile as fc27
from backend.services.reference_distribution import (
    ReferenceDistributionUnavailable,
    Universe,
    build_from_rows,
    check_reference_compatible,
    default_artifact_path,
    load_reference_distribution,
    research_artifact_path,
)

PROFILES = {
    "FC26": {"version": "fc26-players-2026-09-r1", "data_status": "CANONICAL",
             "research_only": False, "source_id": "kaggle_justdhia_ea_fc26_player_ratings"},
    "FC27": {"version": fc27.REFERENCE_DISTRIBUTION_VERSION, "data_status": fc27.DATA_STATUS,
             "research_only": True, "source_id": fc27.SOURCE_ID,
             "dataset_release_id": fc27.DATASET_RELEASE_ID, "snapshot_date": fc27.SNAPSHOT_DATE},
}

# Backward-compatible module constants (FC26 was the only version before Phase 22).
VERSION = PROFILES["FC26"]["version"]
GAME_VERSION = "FC26"


def fetch_rows(game_version: str = GAME_VERSION, data_status: str = "CANONICAL") -> list[dict]:
    profile = PROFILES[game_version]
    select_cols = ", ".join(f"a.{c}" for c in DETAIL_ATTRS + GK_ATTRS)
    sql = f"""
        SELECT gp.position_primary, gp.gender, {select_cols}
        FROM game_player gp
        JOIN game_version gv ON gv.id = gp.game_version_id
        LEFT JOIN game_player_attributes a ON a.game_player_id = gp.id
        WHERE gv.code = %s AND gp.data_status = %s AND gp.source_id = %s
    """
    with get_catalogue_conn(local_fc27_research=profile["research_only"]) as conn:
        return conn.execute(sql, (game_version, data_status, profile["source_id"])).fetchall()


def build(game_version: str, generated_at: str):
    prof = PROFILES[game_version]
    rows = fetch_rows(game_version, prof["data_status"])
    if not rows:
        raise SystemExit(f"ERROR: no {prof['data_status']} {game_version} game_player rows. "
                         "Run the version's ingestion first.")
    if prof["research_only"] and len(rows) != fc27.EXPECTED_ROW_COUNT:
        raise SystemExit(f"ERROR: expected {fc27.EXPECTED_ROW_COUNT} release members, found {len(rows)}")
    dist = build_from_rows(
        rows,
        attribute_columns=list(DETAIL_ATTRS) + list(GK_ATTRS),
        position_field="position_primary",
        version=prof["version"],
        game_version=game_version,
        universe=Universe.RATINGS_SITE_PLAYERS,
        generated_at=generated_at,
    )
    if prof["research_only"]:
        divisions: dict[str, int] = {}
        for r in rows:
            key = r["gender"] or "UNKNOWN"
            divisions[key] = divisions.get(key, 0) + 1
        dist = replace(dist, data_status=prof["data_status"], provenance={
            "source_id": prof["source_id"],
            "dataset_release_id": prof["dataset_release_id"],
            "snapshot_date": prof["snapshot_date"],
            "built_from": f"{len(rows)} {game_version} game_player rows with "
                          f"data_status={prof['data_status']} (no other version, no synthetic rows)",
            "population_by_division": divisions,
            "population_note": ("all published ratings-site players of this version, both "
                                "divisions; the architecture has no division policy, so none "
                                "is imposed here"),
        })
    return dist, rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game-version", default="FC26", choices=sorted(PROFILES))
    ap.add_argument("--verify", action="store_true",
                    help="recompute and compare with the existing artifact; never writes")
    args = ap.parse_args()
    prof = PROFILES[args.game_version]
    out_dir = research_artifact_path() if prof["research_only"] else default_artifact_path()
    out_path = out_dir / f"{prof['version']}.json"

    dist, rows = build(args.game_version, dt.datetime.now(dt.timezone.utc).isoformat())
    print(f"Built {prof['version']} from {len(rows)} {args.game_version} rows "
          f"(data_status={prof['data_status']}); content_hash = {dist.content_hash}")

    if args.verify or out_path.exists():
        if not out_path.exists():
            raise SystemExit(f"nothing to verify: {out_path} does not exist")
        try:
            frozen = load_reference_distribution(prof["version"], artifact_dir=out_dir)
            check_reference_compatible(frozen, game_version=args.game_version, entity_type="game_player")
        except ReferenceDistributionUnavailable as exc:
            raise SystemExit(f"ERROR: {exc}") from exc
        same = (frozen.content_hash, frozen.data_status, frozen.provenance) == (
            dist.content_hash, dist.data_status, dist.provenance)
        print(f"frozen artifact {out_path.name}: content_hash {frozen.content_hash} "
              f"-> {'IDENTICAL' if same else 'DIFFERENT'}; not overwritten "
              "(a new data release needs a new version string)")
        sys.exit(0 if same else 1)

    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        with out_path.open("x", encoding="utf-8") as f:
            json.dump(dist.to_json(), f, indent=2, sort_keys=True)
    except FileExistsError as exc:
        raise SystemExit(f"ERROR: {out_path.name} already exists. Re-run with --verify.") from exc
    print(f"Wrote {out_path}")
    for group, attrs in dist.groups.items():
        print(f"  {group:4s}: {len(attrs)} attributes with n>=50  "
              f"(min n = {min((q.n for q in attrs.values()), default=0)})")
    print(f"UNIVERSE = {dist.universe}  data_status = {dist.data_status or 'CANONICAL'}")


if __name__ == "__main__":
    try:
        main()
    finally:
        close_pool()
