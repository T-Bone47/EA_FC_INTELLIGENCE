#!/usr/bin/env python3
"""Ingest the FC27 Kaggle ratings snapshot as RESEARCH_ONLY data (Phase 22).

Same production architecture as scripts/ingest_fc26_foundation.py:

    raw CSV (hash-verified) -> EARatingsCsvAdapter (legal-gated)
      -> snapshot validation (whole file, before any write)
      -> Normalizer -> DataQualityValidator (FC27 research profile)
      -> IdentityResolver (real_player index) -> PostgresCanonicalRepository
      -> source_observation (snapshot date + hashes)

Refuses to run unless: the raw file matches data/fc27_research/MANIFEST.json,
the source is registered usage_status=RESEARCH_ONLY, and the snapshot
validation verdict is PASS. After the write it verifies that every FC27 row
is RESEARCH_ONLY and that the FC26 fingerprint did not change.

Idempotent: deterministic UUIDs + upserts. Each run appends a record to
fc27_ingestion_report.json. The report compares consecutive observations
from the same database.

Usage:
    python scripts/register_fc27_research_source.py
    python scripts/ingest_fc27_research.py            # run twice to prove idempotency
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.db import close_pool, query
from backend.domain.card_model import RealPlayer
from backend.domain.evidence_model import SourceRecord, UsageStatus
from backend.ingestion import fc27_research_profile as P
from backend.ingestion.data_quality import DataQualityValidator
from backend.ingestion.ea_ratings_csv_adapter import (
    FACADE_COLUMNS,
    EARatingsCsvAdapter,
    file_sha256,
    read_rows,
)
from backend.ingestion.identity_resolver import IdentityIndex
from backend.ingestion.normalizer import Normalizer
from backend.ingestion.pipeline import IngestionPipeline
from backend.ingestion.snapshot_validation import validate_snapshot
from backend.repositories.postgres_canonical_repository import (
    PostgresCanonicalRepository,
)
from backend.services.scoring_config import ScoringConfig

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "phase22"


class IngestionRefused(SystemExit):
    pass


def verify_raw_files() -> dict:
    manifest = json.loads(P.MANIFEST_PATH.read_text(encoding="utf-8"))
    base = P.MANIFEST_PATH.parent
    out = {}
    for rel, meta in manifest["raw_files"].items():
        path = base / rel
        if not path.exists():
            raise IngestionRefused(f"raw file missing: {path} -- re-acquire from "
                                   f"{manifest['source']['url']} and verify hashes")
        digest = file_sha256(path)
        if digest != meta["sha256"]:
            raise IngestionRefused(f"hash mismatch for {rel}: {digest} != {meta['sha256']}")
        out[rel] = {"sha256": digest, "bytes": path.stat().st_size}
    return out


def source_record() -> SourceRecord:
    rows = query("SELECT * FROM source_registry WHERE source_id=%s", (P.SOURCE_ID,))
    if not rows:
        raise IngestionRefused(f"{P.SOURCE_ID} not registered -- run "
                               "scripts/register_fc27_research_source.py first")
    r = rows[0]
    src = SourceRecord(
        source_id=r["source_id"], name=r["name"], source_type=r["source_type"],
        authority_tier=r["authority_tier"], url=r["url"], license=r["license"],
        usage_status=UsageStatus(r["usage_status"]), legal_gate=r["legal_gate"],
        canonical_fields=list(r["canonical_fields"] or []), notes=r["notes"])
    if src.usage_status != UsageStatus.RESEARCH_ONLY or src.legal_gate not in {"CLEARED", "NOT_REQUIRED"}:
        raise IngestionRefused(
            f"{P.SOURCE_ID} usage_status is {src.usage_status.value}, expected "
            "RESEARCH_ONLY -- this script never ingests FC27 as production data")
    return src


def identity_index() -> IdentityIndex:
    idx = IdentityIndex()
    for r in query("SELECT * FROM real_player"):
        idx.add(RealPlayer(
            id=r["id"], full_name=r["full_name"], normalized_name=r["normalized_name"],
            nationality=r["nationality"],
            date_of_birth=str(r["date_of_birth"]) if r["date_of_birth"] else None,
            position_hint=r["position_hint"], name_variants=[]))
    return idx


def fingerprint(code: str) -> dict:
    """Order-independent content fingerprint of one version's player data."""
    row = query("""
        SELECT count(*)::int AS n,
               md5(coalesce(string_agg(t.txt, '|' ORDER BY t.k), '')) AS h
        FROM (
          SELECT gp.source_id || ':' || gp.source_player_id AS k,
                 concat_ws(',', gp.source_player_id, gp.overall_rating, gp.position_primary,
                           gp.data_status, gp.display_name, gp.real_player_id,
                           gp.nation, gp.gender, row_to_json(a)::jsonb - 'game_player_id',
                           (SELECT string_agg(sp.position, ' ' ORDER BY sp.position)
                              FROM game_player_position_secondary sp
                             WHERE sp.game_player_id = gp.id),
                           (SELECT string_agg(pd.playstyle_name || '/' || gpp.tier, ' '
                                              ORDER BY pd.playstyle_name)
                              FROM game_player_playstyle gpp
                              JOIN playstyle_definition pd ON pd.id = gpp.playstyle_definition_id
                             WHERE gpp.game_player_id = gp.id)) AS txt
          FROM game_player gp
          JOIN game_version gv ON gv.id = gp.game_version_id
          LEFT JOIN game_player_attributes a ON a.game_player_id = gp.id
          WHERE gv.code = %s) t""", (code,))[0]
    return {"rows": row["n"], "md5": row["h"]}


def measure() -> dict:
    q1 = lambda sql, p=None: query(sql, p)
    by_status = {r["k"]: r["n"] for r in q1("""
        SELECT gv.code || ':' || gp.data_status AS k, count(*)::int AS n
        FROM game_player gp JOIN game_version gv ON gv.id = gp.game_version_id
        GROUP BY 1 ORDER BY 1""")}
    fc27 = """FROM game_player gp JOIN game_version gv ON gv.id = gp.game_version_id
              WHERE gv.code = 'FC27'"""
    return {
        "game_player_by_version_status": by_status,
        "fc27_distinct_ids": q1(f"SELECT count(DISTINCT gp.id)::int n {fc27}")[0]["n"],
        "fc27_distinct_source_player_ids": q1(
            f"SELECT count(DISTINCT gp.source_player_id)::int n {fc27}")[0]["n"],
        "fc27_by_gender": {r["gender"]: r["n"] for r in q1(
            f"SELECT gp.gender, count(*)::int n {fc27} GROUP BY 1 ORDER BY 1")},
        "fc27_gk": q1(f"SELECT count(*)::int n {fc27} AND gp.position_primary='GK'")[0]["n"],
        "fc27_by_position": {r["position_primary"]: r["n"] for r in q1(
            f"SELECT gp.position_primary, count(*)::int n {fc27} GROUP BY 1 ORDER BY 1")},
        "fc27_identity_status": {r["identity_status"]: r["n"] for r in q1(
            f"SELECT gp.identity_status, count(*)::int n {fc27} GROUP BY 1 ORDER BY 1")},
        "fc27_linked_real_player": q1(
            f"SELECT count(*)::int n {fc27} AND gp.real_player_id IS NOT NULL")[0]["n"],
        "fc27_attribute_rows": q1(f"""SELECT count(*)::int n {fc27}
            AND EXISTS (SELECT 1 FROM game_player_attributes a WHERE a.game_player_id = gp.id)""")[0]["n"],
        "fc27_secondary_position_rows": q1("""SELECT count(*)::int n
            FROM game_player_position_secondary sp JOIN game_player gp ON gp.id = sp.game_player_id
            JOIN game_version gv ON gv.id = gp.game_version_id WHERE gv.code='FC27'""")[0]["n"],
        "fc27_playstyle_links": {r["tier"]: r["n"] for r in q1("""
            SELECT gpp.tier, count(*)::int n FROM game_player_playstyle gpp
            JOIN game_player gp ON gp.id = gpp.game_player_id
            JOIN game_version gv ON gv.id = gp.game_version_id
            WHERE gv.code='FC27' GROUP BY 1 ORDER BY 1""")},
        "fc27_players_with_playstyles": q1("""
            SELECT count(DISTINCT gpp.game_player_id)::int n FROM game_player_playstyle gpp
            JOIN game_player gp ON gp.id = gpp.game_player_id
            JOIN game_version gv ON gv.id = gp.game_version_id WHERE gv.code='FC27'""")[0]["n"],
        "playstyle_definition_by_version_status": {r["k"]: r["n"] for r in q1("""
            SELECT gv.code || ':' || pd.data_status AS k, count(*)::int n
            FROM playstyle_definition pd JOIN game_version gv ON gv.id = pd.game_version_id
            GROUP BY 1 ORDER BY 1""")},
        "fc27_club_affiliations": q1("""SELECT count(*)::int n FROM club_affiliation ca
            JOIN game_version gv ON gv.id = ca.game_version_id WHERE gv.code='FC27'""")[0]["n"],
        "source_observations_for_source": q1(
            "SELECT count(*)::int n FROM source_observation WHERE source_id=%s",
            (P.SOURCE_ID,))[0]["n"],
        "field_provenance_by_release": {r["dataset_release_id"]: r["n"] for r in q1("""
            SELECT dataset_release_id, count(*)::int n FROM field_provenance GROUP BY 1 ORDER BY 1""")},
        "ut_card_by_status": {r["k"]: r["n"] for r in q1("""
            SELECT is_synthetic::text || ':' || data_status AS k, count(*)::int n
            FROM ut_card GROUP BY 1 ORDER BY 1""")},
        "real_player": q1("SELECT count(*)::int n FROM real_player")[0]["n"],
    }


def cross_version_identity() -> dict:
    row = query("""
        SELECT count(*)::int AS same_ea_id_pairs,
               count(*) FILTER (WHERE a.id = b.id)::int AS identical_game_player_ids,
               count(*) FILTER (WHERE a.real_player_id IS NOT NULL
                                  AND a.real_player_id = b.real_player_id)::int
                   AS pairs_linked_to_same_real_player
        FROM game_player a JOIN game_version ga ON ga.id = a.game_version_id AND ga.code='FC26'
        JOIN game_player b ON b.source_player_id = a.source_player_id
        JOIN game_version gb ON gb.id = b.game_version_id AND gb.code='FC27'""")[0]
    return dict(row)


def reference_playstyle_vocabulary() -> set[str]:
    """FC26 CANONICAL PlayStyle names -- used for schema COMPARISON only."""
    return {r["playstyle_name"] for r in query("""
        SELECT pd.playstyle_name FROM playstyle_definition pd
        JOIN game_version gv ON gv.id = pd.game_version_id
        WHERE gv.code='FC26' AND pd.data_status='CANONICAL'""")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate-only", action="store_true")
    ap.add_argument("--artifacts-dir", type=Path, default=ARTIFACTS,
                    help="directory for validation and ingestion reports")
    args = ap.parse_args()
    args.artifacts_dir.mkdir(parents=True, exist_ok=True)
    started = dt.datetime.now(dt.timezone.utc)

    raw = verify_raw_files()
    src = source_record()
    header, rows = read_rows(P.RAW_PLAYERS_CSV)
    norm = Normalizer(P.SOURCE_ID, P.GAME_VERSION)
    validation = validate_snapshot(
        header, rows, expected_edition=P.GAME_VERSION.lower(),
        expected_row_count=P.EXPECTED_ROW_COUNT,
        position_vocabulary=set(P.POSITION_VOCABULARY),
        reference_playstyle_vocabulary=reference_playstyle_vocabulary(),
        canonical_id_fn=norm.game_player_id,
        snapshot_reference_date=dt.date.fromisoformat(P.SNAPSHOT_DATE))
    validation = {"generated_at": started.isoformat(), "source_id": P.SOURCE_ID,
                  "game_version": P.GAME_VERSION, "data_status": P.DATA_STATUS,
                  "raw_files": raw, **validation}
    (args.artifacts_dir / "fc27_validation_report.json").write_text(
        json.dumps(validation, indent=2, default=str), encoding="utf-8")
    print(f"validation verdict={validation['verdict']} outcomes={validation['row_outcomes']}")
    if validation["verdict"] != "PASS":
        raise IngestionRefused(f"snapshot validation FAILED: {validation['blocking_reasons']}")
    if args.validate_only:
        return 0

    path = args.artifacts_dir / "fc27_ingestion_report.json"
    doc = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"runs": []}
    previous = query("""
        SELECT so.id::text AS id FROM source_observation so
        JOIN game_version gv ON gv.id = so.game_version_id
        WHERE so.source_id = %s AND gv.code = %s AND so.entity_type = 'snapshot'
          AND so.raw_payload->>'dataset_release_id' = %s
        ORDER BY so.observed_at DESC, so.id DESC LIMIT 1
    """, (P.SOURCE_ID, P.GAME_VERSION, P.DATASET_RELEASE_ID))
    before = measure()
    fc26_before = fingerprint("FC26")

    adapter = EARatingsCsvAdapter(src, P.GAME_VERSION, P.RAW_PLAYERS_CSV)
    repo = PostgresCanonicalRepository(P.SOURCE_ID, P.GAME_VERSION)
    validator = DataQualityValidator(ScoringConfig.with_versions([P.FC27_RESEARCH_VERSION_CONFIG]))
    pipeline = IngestionPipeline(adapter, repo, validator=validator,
                                 identity_index=identity_index())
    report = pipeline.run_players(attach_playstyles=True)
    gk_unmapped = {}
    for rec in adapter.fetch_players():
        vals = rec.extras.get("unmapped_source_values") or {}
        if vals:
            gk_unmapped[str(rec.source_player_id)] = vals
    counts = repo.flush(
        observation_note="FC27 research-only snapshot ingestion (Phase 22)",
        observation_meta={
            "snapshot_date": P.SNAPSHOT_DATE, "data_status": P.DATA_STATUS,
            "dataset_release_id": P.DATASET_RELEASE_ID, "kaggle_url": P.KAGGLE_URL,
            "kaggle_version": P.KAGGLE_VERSION, "raw_files": raw,
            "rows_in_file": len(rows),
            "unmapped_gk_face_stat_columns": list(FACADE_COLUMNS),
            "unmapped_gk_face_stats_by_player_id": gk_unmapped,
            "adapter_field_issues": adapter.field_issues,
            "adapter_playstyle_issues": adapter.playstyle_issues,
        },
        bind_fc27_research=True)

    after = measure()
    fc26_after = fingerprint("FC26")
    fc27_fp = fingerprint("FC27")
    identity = cross_version_identity()

    # ---- post-write assertions (fail loudly; never adjust)
    problems = []
    fc27_status = {k: v for k, v in after["game_player_by_version_status"].items()
                   if k.startswith("FC27:")}
    if set(fc27_status) - {"FC27:RESEARCH_ONLY"}:
        problems.append(f"FC27 rows with non-RESEARCH_ONLY status: {fc27_status}")
    if fc26_before != fc26_after:
        problems.append(f"FC26 fingerprint changed: {fc26_before} -> {fc26_after}")
    if identity["identical_game_player_ids"]:
        problems.append(f"{identity['identical_game_player_ids']} FC26/FC27 id collisions")
    val_rejected = {r["player_id"] for r in validation["rejected_rows"]}
    pipe_rejected = {r["source_player_id"] for r in report.rejections}
    if val_rejected != pipe_rejected:
        problems.append(f"validator/pipeline rejection sets differ: "
                        f"{sorted(val_rejected ^ pipe_rejected)[:20]}")
    expected_rows = len(rows) - len(val_rejected)
    if fc27_status.get("FC27:RESEARCH_ONLY", 0) != expected_rows:
        problems.append(f"FC27 rows {fc27_status} != file rows minus rejections {expected_rows}")

    pr = report.to_dict()
    run = {
        "started_at": started.isoformat(),
        "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "observation_id": str(repo.last_observation_id),
        "pipeline": {k: pr[k] for k in (
            "players_fetched", "players_persisted", "players_rejected", "players_review",
            "playstyles_attached", "identity_resolved", "identity_review",
            "identity_unresolved")},
        "pipeline_rejections": pr["rejections"],
        "pipeline_reviews": pr["reviews"],
        "repository_flush_counts": counts,
        "counts_before": before,
        "counts_after": after,
        "fc26_fingerprint_before": fc26_before,
        "fc26_fingerprint_after": fc26_after,
        "fc26_unchanged": fc26_before == fc26_after,
        "fc27_fingerprint_after": fc27_fp,
        "cross_version_identity": identity,
        "post_write_problems": problems,
    }

    doc["runs"].append(run)
    doc.update({"source_id": P.SOURCE_ID, "game_version": P.GAME_VERSION,
                "data_status": P.DATA_STATUS, "dataset_release_id": P.DATASET_RELEASE_ID})
    doc.pop("idempotency", None)
    if len(doc["runs"]) >= 2 and previous and doc["runs"][-2]["observation_id"] == previous[0]["id"]:
        a, b = doc["runs"][-2]["counts_after"], doc["runs"][-1]["counts_after"]
        keys = ("fc27_distinct_ids", "fc27_attribute_rows", "fc27_secondary_position_rows",
                "fc27_players_with_playstyles", "fc27_club_affiliations")
        doc["idempotency"] = {
            "first_run_counts": {k: a[k] for k in keys} | {
                "game_player_by_version_status": a["game_player_by_version_status"],
                "fc27_playstyle_links": a["fc27_playstyle_links"]},
            "second_run_counts": {k: b[k] for k in keys} | {
                "game_player_by_version_status": b["game_player_by_version_status"],
                "fc27_playstyle_links": b["fc27_playstyle_links"]},
            "duplicate_delta": {
                **{k: b[k] - a[k] for k in keys},
                "game_player_rows": sum(b["game_player_by_version_status"].values())
                - sum(a["game_player_by_version_status"].values()),
                "playstyle_links": sum(b["fc27_playstyle_links"].values())
                - sum(a["fc27_playstyle_links"].values()),
            },
            "fc27_fingerprint_identical": (doc["runs"][-2]["fc27_fingerprint_after"]
                                           == doc["runs"][-1]["fc27_fingerprint_after"]),
            "source_observation_rows_added_by_rerun": (
                b["source_observations_for_source"] - a["source_observations_for_source"]),
            "note": ("each run records one snapshot observation event; player, "
                     "attribute, position, PlayStyle and affiliation rows must not grow"),
        }
    path.write_text(json.dumps(doc, indent=2, default=str), encoding="utf-8")

    print(json.dumps({"pipeline": run["pipeline"], "fc26_unchanged": run["fc26_unchanged"],
                      "cross_version_identity": identity,
                      "idempotency": doc.get("idempotency", {}).get("duplicate_delta"),
                      "problems": problems}, indent=2))
    if problems:
        print("POST-WRITE CHECKS FAILED", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        close_pool()
