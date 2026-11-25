#!/usr/bin/env python3
"""Audit the four input ZIPs, with optional immutable staging in a local PostgreSQL test database."""
import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.ingestion.fc27_source_evidence import audit, CARD_FIELDS, OCTOBER_FIELDS, PLAYER_FIELDS, SOURCES


def stage(conn, manifest, observations):
    from psycopg.types.json import Jsonb
    conn.execute("LOCK TABLE fc27_staging.snapshot IN SHARE ROW EXCLUSIVE MODE")
    inserted = rows_written = 0
    for snapshot in manifest:
        sid = snapshot["snapshot_id"]
        rows = observations.get(sid, [])
        fresh = conn.execute("""INSERT INTO fc27_staging.snapshot (snapshot_id,source_id,sha256,manifest)
                                  VALUES (%s,%s,%s,%s) ON CONFLICT (snapshot_id) DO NOTHING""",
                             (sid, snapshot["source_id"], snapshot["sha256"], Jsonb(snapshot))).rowcount
        if not fresh:
            old = conn.execute("""SELECT s.source_id,s.sha256,
                    (SELECT count(*) FROM fc27_staging.observation o WHERE o.snapshot_id=s.snapshot_id)
                    FROM fc27_staging.snapshot s WHERE s.snapshot_id=%s""", (sid,)).fetchone()
            if old != (snapshot["source_id"], snapshot["sha256"], len(rows)):
                raise ValueError("Stored snapshot differs from the audited input")
            continue
        inserted += 1
        if rows:
            with conn.cursor() as cursor, cursor.copy("""COPY fc27_staging.observation
                (snapshot_id,record_id,source_row_number,raw,normalized,identity_review) FROM STDIN""") as copy:
                for key, n, raw, normalized, review in rows:
                    copy.write_row((sid, key, n, Jsonb(raw), Jsonb(normalized), Jsonb(review) if review else None))
            rows_written += len(rows)
    return {"snapshots_inserted": inserted, "snapshots_reused": len(manifest) - inserted, "rows_written": rows_written}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", type=Path)
    parser.add_argument("--received", type=date.fromisoformat, required=True)
    parser.add_argument("--out", required=True, type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--stage", action="store_true")
    modes.add_argument("--verify-rollback", action="store_true")
    args = parser.parse_args()
    manifest, missing, observations, reviews, comparison = audit(args.archives, args.received)
    args.out.mkdir(parents=True, exist_ok=False)
    result = {"validation": "PASS", "public_memberships_created": 0, "database": "NOT_REQUESTED"}
    if args.stage or args.verify_rollback:
        import psycopg
        from backend.core.config import get_settings
        from backend.services.data_license_gate import Environment, environment_from_settings
        settings = get_settings()
        if (environment_from_settings(settings.environment) != Environment.LOCAL
                or urlparse(settings.database_url).hostname not in {"localhost", "127.0.0.1", "::1"}):
            parser.error("Select an isolated local PostgreSQL deployment for staging")
        with psycopg.connect(settings.database_url) as conn:
            result["database"] = stage(conn, manifest, observations)
            result["database"]["transaction"] = "ROLLED_BACK" if args.verify_rollback else "COMMITTED"
            if args.verify_rollback:
                conn.rollback()
    for name, payload in (("FC27_FILE_MANIFEST", manifest), ("FC27_MISSINGNESS_REPORT", missing),
                          ("FC27_SOURCE_COMPARISON", comparison), ("FC27_INGESTION_RESULTS", result)):
        (args.out / f"{name}.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with (args.out / "FC27_FIELD_MAPPING.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("schema", "source_field", "mapped_field", "policy"))
        for index, fields in [(0, PLAYER_FIELDS), (2, OCTOBER_FIELDS), (3, CARD_FIELDS)]:
            schema = SOURCES[index]
            for col in schema.columns:
                writer.writerow((schema.schema, col, fields.get(col),
                                 "EDITORIAL_ONLY" if col == "fc_iq_roles" else
                                 "RESEARCH_OBSERVATION" if col in fields else "UNMAPPED_RETAINED"))
    with (args.out / "FC27_IDENTITY_CONFLICTS.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=reviews[0].keys())
        writer.writeheader()
        writer.writerows(review for review in reviews if review["status"] in {"AMBIGUOUS", "CONFLICTED"})
    print(json.dumps({"comparison": comparison, **result}, indent=2))


if __name__ == "__main__":
    main()
