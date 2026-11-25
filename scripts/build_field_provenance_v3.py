#!/usr/bin/env python
"""Populate field_provenance for one game version's ingested player data.

Answers, for any served attribute value: "why do we believe this?" with a
trace to the exact source_observation, source_registry entry and dataset
release that produced it (FC26_PROVENANCE_SPEC.md). This closes the measured
gap in DATA_ARCHITECTURE_CURRENT_STATE.md: source_observation_id existed on
some tables but was discarded before reaching individual attributes.

Granularity: one source_observation per (source, ingestion batch) already
exists (created by the ingestion pipeline). This script writes one
field_provenance row per (player, field) with a non-NULL value, linked to
that batch observation -- honest at the granularity the source actually
supports (one dataset retrieval, not one fetch per attribute).

Each version has its own source, data status and dataset release. FC27
uses the pinned snapshot observation referenced by reviewed release
membership.

    FC26: the 40 served attributes, exactly as before (unchanged output).
    FC27: the served attributes AND non-attribute fields (rating, positions,
          PlayStyles, names, links, foot, stars, DOB, division), with the
          as-published source value and source column recorded, and every
          stored value re-checked against the raw file.

Idempotent: safe to re-run (the release's rows are replaced).

Usage:
    python scripts/build_field_provenance_v3.py                   # FC26
    python scripts/build_field_provenance_v3.py --game-version FC27
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.db import close_pool, get_catalogue_conn, get_conn, query
from backend.domain.card_model import DETAIL_ATTRS, FACADE_ATTRS, GK_ATTRS
from backend.ingestion import fc27_research_profile as fc27

ROOT = Path(__file__).resolve().parents[1]

VERSION_PROFILES = {
    "FC26": {
        "source_id": "kaggle_justdhia_ea_fc26_player_ratings",
        "data_status": "CANONICAL",
        "dataset_release_id": "fc26-foundation-2026-09-r1",
        "resolution_reason": "FC26 foundation ingestion snapshot (see release registry for usage rights)",
    },
    "FC27": {
        "source_id": fc27.SOURCE_ID,
        "data_status": fc27.DATA_STATUS,
        "dataset_release_id": fc27.DATASET_RELEASE_ID,
        "resolution_reason": ("single RESEARCH_ONLY source (not production-permitted); "
                              "no competing claim; source column {col}"),
    },
}

_COPY_COLS = ("canonical_entity_type, canonical_entity_id, canonical_field, source_id, "
              "source_record_id, source_observation_id, observed_value, normalized_value, "
              "source_authority, resolution_status, resolution_reason, dataset_release_id")


class ProvenanceRefused(SystemExit):
    pass


def select_observation(game_version: str, source_id: str) -> str:
    if game_version == fc27.GAME_VERSION:
        with get_catalogue_conn(local_fc27_research=True) as conn:
            obs = conn.execute("""
                SELECT DISTINCT so.id FROM catalogue_serving.member m
                JOIN source_observation so ON so.id = m.source_observation_id
                WHERE m.entity_scope = 'game_player' AND m.dataset_version = %s
                  AND so.source_id = %s AND so.entity_type = 'snapshot'
                  AND so.snapshot_date = %s
                  AND so.raw_payload->'raw_files'->'raw/extracted/players.csv'->>'sha256' = %s
            """, (fc27.REFERENCE_DISTRIBUTION_VERSION, source_id,
                  fc27.SNAPSHOT_DATE, fc27.PLAYERS_CSV_SHA256)).fetchall()
        if len(obs) != 1:
            raise ProvenanceRefused("ERROR: expected one pinned FC27 release observation. Run ingestion first.")
        return obs[0]["id"]

    obs = query("""
        SELECT so.id FROM source_observation so
        JOIN game_version gv ON gv.id = so.game_version_id
        WHERE so.entity_type = 'snapshot' AND so.source_id = %s AND gv.code = %s
        ORDER BY so.observed_at DESC LIMIT 1""", (source_id, game_version))
    if not obs:
        raise ProvenanceRefused(f"ERROR: no {game_version} snapshot observation for "
                                f"{source_id}. Run ingestion first.")
    return obs[0]["id"]


def _write(rows: list[tuple], release: str) -> int:
    if not rows:
        raise ProvenanceRefused(f"ERROR: no evidence for {release}. Existing provenance was preserved.")
    with get_conn() as conn:
        conn.execute("DELETE FROM field_provenance WHERE dataset_release_id=%s", (release,))
        with conn.cursor() as cur:
            with cur.copy(f"COPY field_provenance ({_COPY_COLS}) FROM STDIN") as copy:
                for r in rows:
                    copy.write_row(r)
        conn.commit()
    return len(rows)


# ---------------------------------------------------------------------- FC26
def build_fc26(profile: dict, observation_id, authority: int) -> dict:
    cols = list(FACADE_ATTRS) + list(DETAIL_ATTRS) + list(GK_ATTRS)
    select_cols = ", ".join(f"a.{c}" for c in cols)
    rows = query(f"""
        SELECT gp.id AS entity_id, {select_cols}
        FROM game_player gp
        JOIN game_version gv ON gv.id = gp.game_version_id
        LEFT JOIN game_player_attributes a ON a.game_player_id = gp.id
        WHERE gv.code = 'FC26' AND gp.data_status = %s AND gp.source_id = %s""",
        (profile["data_status"], profile["source_id"]))
    print(f"Writing field_provenance for {len(rows)} players x up to {len(cols)} attributes "
          f"(non-NULL values only) linked to observation {observation_id} ({profile['source_id']})")
    out = []
    for r in rows:
        for attr in cols:
            v = r[attr]
            if v is None:
                continue
            out.append(("game_player", r["entity_id"], attr, profile["source_id"],
                        str(r["entity_id"]), observation_id, str(v), str(v), authority,
                        "ACCEPTED", profile["resolution_reason"],
                        profile["dataset_release_id"]))
    return {"written": _write(out, profile["dataset_release_id"])}


# ---------------------------------------------------------------------- FC27
def _fc27_field_sources():
    """canonical field -> source column. Imported lazily so the FC26 path has
    no dependency on the FC27 adapter."""
    from backend.ingestion.ea_ratings_csv_adapter import (
        ATTRIBUTE_COLUMN_MAP,
        FACADE_COLUMNS,
    )
    attr_src = {canon: col for col, canon in ATTRIBUTE_COLUMN_MAP.items()}
    attr_src.update({c: c for c in FACADE_COLUMNS})       # outfield rows only
    scalar_src = {
        "overall_rating": "overall_rating", "position_primary": "position",
        "nation": "nationality", "date_of_birth": "birthdate",
        "preferred_foot": "preferred_foot", "weak_foot_stars": "weak_foot",
        "skill_moves_stars": "skill_moves", "gender": "gender",
        "first_name": "first_name", "last_name": "last_name",
        "common_name": "common_name", "club": "club", "league": "league",
    }
    return attr_src, scalar_src


def build_fc27(profile: dict, observation_id, authority: int) -> dict:
    from backend.ingestion.ea_ratings_csv_adapter import (
        file_sha256,
        parse_playstyles,
        read_rows,
    )

    if file_sha256(fc27.RAW_PLAYERS_CSV) != fc27.PLAYERS_CSV_SHA256:
        raise ProvenanceRefused("FC27 raw file hash does not match the manifest")
    _, raw_rows = read_rows(fc27.RAW_PLAYERS_CSV)
    raw = {r["player_id"].strip(): r for r in raw_rows}
    attr_src, scalar_src = _fc27_field_sources()

    attr_cols = list(FACADE_ATTRS) + list(DETAIL_ATTRS) + list(GK_ATTRS)
    sql = f"""
        SELECT gp.id AS entity_id, gp.source_player_id, gp.overall_rating, gp.position_primary,
               gp.nation, gp.date_of_birth, gp.preferred_foot, gp.weak_foot_stars,
               gp.skill_moves_stars, gp.gender, gp.first_name, gp.last_name, gp.common_name,
               gp.display_name, c.name AS club, c.league_name AS league,
               {", ".join(f"a.{c}" for c in attr_cols)},
               (SELECT string_agg(sp.position, ' ' ORDER BY sp.sort_order)
                  FROM game_player_position_secondary sp
                 WHERE sp.game_player_id = gp.id) AS secondary_positions,
               (SELECT string_agg(pd.playstyle_name, ', ' ORDER BY pd.playstyle_name)
                  FROM game_player_playstyle gpp
                  JOIN playstyle_definition pd ON pd.id = gpp.playstyle_definition_id
                 WHERE gpp.game_player_id = gp.id AND gpp.tier = 'base') AS playstyles,
               (SELECT string_agg(pd.playstyle_name, ', ' ORDER BY pd.playstyle_name)
                  FROM game_player_playstyle gpp
                  JOIN playstyle_definition pd ON pd.id = gpp.playstyle_definition_id
                 WHERE gpp.game_player_id = gp.id AND gpp.tier = 'plus') AS playstyles_plus
        FROM game_player gp
        JOIN game_version gv ON gv.id = gp.game_version_id
        LEFT JOIN game_player_attributes a ON a.game_player_id = gp.id
        LEFT JOIN club_affiliation ca ON ca.game_player_id = gp.id
                 AND ca.game_version_id = gp.game_version_id
        LEFT JOIN club c ON c.id = ca.club_id
        WHERE gv.code = 'FC27' AND gp.data_status = %s AND gp.source_id = %s
          AND EXISTS (SELECT 1 FROM catalogue_serving.member m
                      WHERE m.entity_scope = 'game_player' AND m.entity_id = gp.id
                        AND m.game_version_id = gp.game_version_id AND m.source_id = gp.source_id
                        AND m.dataset_version = %s AND m.source_observation_id = %s)
    """
    with get_catalogue_conn(local_fc27_research=True) as conn:
        rows = conn.execute(sql, (profile["data_status"], profile["source_id"],
                                  fc27.REFERENCE_DISTRIBUTION_VERSION, observation_id)).fetchall()
    if {str(row["source_player_id"]) for row in rows} != raw.keys() or len(rows) != len(raw):
        raise ProvenanceRefused("ERROR: FC27 release membership differs from the pinned player CSV.")
    print(f"Writing FC27 field_provenance for {len(rows)} players linked to observation "
          f"{observation_id} ({profile['source_id']})")

    reason = profile["resolution_reason"]
    out: list[tuple] = []
    per_field: dict[str, dict] = {}
    mismatches: list[dict] = []

    def add(r, field, stored, observed, col, equal):
        st = per_field.setdefault(field, {"served": 0, "covered": 0, "value_mismatch": 0,
                                          "source_column": col})
        st["served"] += 1
        if not equal:
            st["value_mismatch"] += 1
            if len(mismatches) < 50:
                mismatches.append({"source_player_id": r["source_player_id"], "field": field,
                                   "stored": stored, "published": observed})
        out.append(("game_player", r["entity_id"], field, profile["source_id"],
                    f"players.csv#player_id={r['source_player_id']}", observation_id,
                    observed, None if stored is None else str(stored), authority,
                    "ACCEPTED", reason.format(col=col), profile["dataset_release_id"]))
        st["covered"] += 1

    for r in rows:
        src = raw[str(r["source_player_id"])]
        for attr in attr_cols:
            v = r[attr]
            if v is None:
                continue
            col = attr_src[attr]
            pub = (src.get(col) or "").strip()
            add(r, attr, v, pub, col, pub.isdigit() and int(pub) == v)
        for field, col in scalar_src.items():
            v = r[field]
            if v is None:
                continue
            pub = (src.get(col) or "").strip()
            add(r, field, v, pub, col, str(v)[:10] == pub if field == "date_of_birth"
                else str(v) == pub)
        pub_name = (src.get("common_name") or "").strip() or \
            f"{(src.get('first_name') or '').strip()} {(src.get('last_name') or '').strip()}".strip()
        add(r, "display_name", r["display_name"], pub_name, "common_name|first_name+last_name",
            r["display_name"] == pub_name)
        if r["secondary_positions"] is not None:
            pub = " ".join((src.get("alternate_positions") or "").split())
            add(r, "secondary_positions", r["secondary_positions"], pub, "alternate_positions",
                r["secondary_positions"] == pub)
        base, plus, _ = parse_playstyles(src.get("playstyles"))
        pub_ps = (src.get("playstyles") or "").strip()
        if r["playstyles"] is not None:
            add(r, "playstyles", r["playstyles"], pub_ps, "playstyles",
                r["playstyles"] == ", ".join(sorted(base)))
        if r["playstyles_plus"] is not None:
            add(r, "playstyles_plus", r["playstyles_plus"], pub_ps, "playstyles",
                r["playstyles_plus"] == ", ".join(sorted(plus)))

    mismatch_count = sum(s["value_mismatch"] for s in per_field.values())
    if mismatch_count:
        raise ProvenanceRefused(f"ERROR: {mismatch_count} FC27 fields differ from the pinned source. "
                                f"Examples: {json.dumps(mismatches[:3], default=str)}")
    written = _write(out, profile["dataset_release_id"])
    served = sum(s["served"] for s in per_field.values())
    covered = sum(s["covered"] for s in per_field.values())
    return {"written": written, "players": len(rows), "players_missing_in_raw_file": 0,
            "total_served_fields": served, "provenance_covered_fields": covered,
            "missing_provenance": served - covered,
            "value_mismatches": mismatch_count,
            "mismatch_examples": mismatches, "per_field": per_field}


def cross_version_checks() -> dict:
    """Provenance may never cross the version wall in either direction."""
    return query("""
        SELECT
          count(*) FILTER (WHERE gp_gv.code <> obs_gv.code)::int AS rows_with_observation_of_other_version,
          count(*) FILTER (WHERE gp_gv.code = 'FC27' AND fp.source_id <> 'kaggle_fc27_player_ratings')::int
              AS fc27_fields_from_non_fc27_source,
          count(*) FILTER (WHERE gp_gv.code = 'FC26' AND fp.source_id = 'kaggle_fc27_player_ratings')::int
              AS fc26_fields_from_fc27_source,
          count(*) FILTER (WHERE gp_gv.code = 'FC26' AND fp.dataset_release_id LIKE 'fc27%%')::int
              AS fc26_fields_in_fc27_release,
          count(*) FILTER (WHERE gp_gv.code = 'FC27' AND fp.dataset_release_id LIKE 'fc26%%')::int
              AS fc27_fields_in_fc26_release
        FROM field_provenance fp
        JOIN game_player gp ON gp.id = fp.canonical_entity_id
        JOIN game_version gp_gv ON gp_gv.id = gp.game_version_id
        JOIN source_observation so ON so.id = fp.source_observation_id
        JOIN game_version obs_gv ON obs_gv.id = so.game_version_id""")[0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game-version", default="FC26", choices=sorted(VERSION_PROFILES))
    ap.add_argument("--report", default=None, help="write a JSON coverage report here")
    args = ap.parse_args()
    profile = VERSION_PROFILES[args.game_version]
    observation_id = select_observation(args.game_version, profile["source_id"])
    authority = query("SELECT authority_tier FROM source_registry WHERE source_id=%s",
                      (profile["source_id"],))
    source_authority = authority[0]["authority_tier"] if authority else 5

    if args.game_version == "FC26":
        result = build_fc26(profile, observation_id, source_authority)
    else:
        result = build_fc27(profile, observation_id, source_authority)
    result["cross_version_checks"] = cross_version_checks()
    result.update({"game_version": args.game_version, "source_id": profile["source_id"],
                   "observation_id": str(observation_id),
                   "dataset_release_id": profile["dataset_release_id"]})
    print(f"Wrote {result['written']} field_provenance rows")
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ("per_field", "mismatch_examples")}, indent=2, default=str))
    if args.report:
        Path(args.report).write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    finally:
        close_pool()
