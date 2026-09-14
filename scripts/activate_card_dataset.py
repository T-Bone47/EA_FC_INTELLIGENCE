#!/usr/bin/env python3
"""ONE-COMMAND card dataset activation (§26/§27).

    python3 scripts/activate_card_dataset.py \
        --source-id <registry id> --game-version FC26 --cards <file.csv> \
        [--dataset-version vN] [--dry-run]

Chain (every step auditable via the ingestion_run row):

    legal gate -> forensics (REJECT verdict aborts) -> ingestion_run(RAW)
    -> fetch -> normalize (version firewall, deterministic ids)
    -> validate (REJECT -> quarantine, REVIEW -> flagged)
    -> dedup/identity (canonical ids; conflicts logged)
    -> STAGING -> VALIDATED -> atomic promote (single DB transaction:
       ut_card + attributes + playstyles + roles + versions + prices +
       source_observation) -> watermark refresh -> cache invalidate
    -> integrity checks -> golden regression -> report

Atomicity: promotion is one transaction inside PostgresCanonicalRepository
.flush(); a failure there leaves the database exactly as before and the run
is marked FAILED. The golden regression runs after promotion as an integrity
gate — card activation only writes card tables (ut_card/card_version/
card_price/...), never game_player, so legacy player goldens are structurally
unaffected; a golden failure here therefore signals a real defect and the run
is flagged ROLLED_BACK for investigation (data restored from the pre-run
counts is a human decision — no silent auto-deletion).

Dry-run: forensics + normalize + validate only; nothing is persisted.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.core.db import close_pool, query  # noqa: E402
from backend.domain.evidence_model import SourceRecord, UsageStatus  # noqa: E402
from backend.ingestion.forensics import analyze_rows, source_fingerprint, to_markdown  # noqa: E402
from backend.ingestion.local_file_adapter import LocalFileAdapter  # noqa: E402
from backend.ingestion.pipeline import IngestionPipeline  # noqa: E402
from backend.ingestion.run_tracker import IngestionRunTracker  # noqa: E402
from backend.repositories.postgres_canonical_repository import (  # noqa: E402
    PostgresCanonicalRepository,
)

REPORT_DIR = ROOT / "data_acquisition" / "activation_reports"
FORENSICS_DIR = ROOT / "data_acquisition" / "forensics"


def load_source(source_id: str) -> SourceRecord:
    rows = query("SELECT * FROM source_registry WHERE source_id=%s", (source_id,))
    if not rows:
        raise SystemExit(f"source {source_id!r} not registered — register it "
                         "with its license/permission research first (§22)")
    r = rows[0]
    return SourceRecord(
        source_id=r["source_id"], name=r["name"], source_type=r["source_type"],
        authority_tier=r["authority_tier"], url=r["url"], license=r["license"],
        usage_status=UsageStatus(r["usage_status"]), legal_gate=r["legal_gate"],
        canonical_fields=list(r["canonical_fields"] or []), notes=r["notes"])


def known_playstyles(game_version: str) -> set[str]:
    rows = query(
        """SELECT pd.playstyle_name AS name FROM playstyle_definition pd
           JOIN game_version gv ON gv.id = pd.game_version_id
           WHERE gv.code = %s""", (game_version,))
    return {r["name"] for r in rows}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source-id", required=True)
    ap.add_argument("--game-version", required=True)
    ap.add_argument("--cards", required=True, type=Path)
    ap.add_argument("--dataset-version", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    gv = args.game_version.upper()
    src = load_source(args.source_id)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    FORENSICS_DIR.mkdir(parents=True, exist_ok=True)

    # ---- 1. legal gate (§54) -------------------------------------------------
    if not src.fetch_permitted:
        print(f"REFUSED: source {src.source_id} legal_gate={src.legal_gate} — "
              "human clearance required before any fetch (§22/§54).")
        return 2
    if src.usage_status not in (UsageStatus.OFFICIAL, UsageStatus.AUTHORIZED,
                                UsageStatus.LICENSED) and not args.dry_run:
        print(f"REFUSED: usage_status={src.usage_status.value} — production "
              "activation requires OFFICIAL/AUTHORIZED/LICENSED (§54). "
              "Use --dry-run for forensics-only analysis.")
        return 2

    raw_bytes = args.cards.read_bytes()
    fingerprint = source_fingerprint(raw_bytes)

    # ---- 2. forensics (§23) ---------------------------------------------------
    with args.cards.open(newline="", encoding="utf-8-sig") as f:
        raw_rows = [dict(r) for r in csv.DictReader(f)]
    stats = analyze_rows(raw_rows, entity="card", game_version=gv,
                         id_column="source_card_id",
                         known_playstyles=known_playstyles(gv) or None)
    md = to_markdown(stats, source_label=f"{src.source_id} ({args.cards.name})")
    fpath = FORENSICS_DIR / f"{src.source_id}_{gv}_{stamp}.md"
    fpath.write_text(md)
    (FORENSICS_DIR / f"{src.source_id}_{gv}_{stamp}.json").write_text(
        json.dumps(stats, indent=2, default=str))
    print(f"forensics: verdict={stats['verdict']} rows={stats['row_count']} "
          f"-> {fpath.relative_to(ROOT)}")
    if stats["verdict"] == "REJECT" and not args.dry_run:
        print("ABORTED: REJECT-level forensic findings — fix or quarantine the "
              "dataset before activation (§23).")
        return 3

    # ---- 3. run tracking + pipeline -------------------------------------------
    tracker = IngestionRunTracker(src.source_id, gv,
                                  dataset_version=args.dataset_version,
                                  source_hash=fingerprint)
    adapter = LocalFileAdapter(src, gv, cards_path=args.cards)
    repo = PostgresCanonicalRepository(src.source_id, gv)
    pipeline = IngestionPipeline(adapter, repo)

    if args.dry_run:
        report = pipeline.run_cards()   # stages into repo buffers only
        print(json.dumps({"dry_run": True, "report": report.to_dict(),
                          "forensics_verdict": stats["verdict"]},
                         indent=2, default=str))
        return 0

    tracker.start(rows_raw=len(raw_rows))
    tracker.advance("STAGING")
    try:
        report = pipeline.run_cards()
    except Exception as e:                     # noqa: BLE001
        tracker.fail(f"pipeline error: {e}")
        raise
    tracker.advance("VALIDATED")

    # quarantine every rejected row with reason + raw payload (§26)
    raw_by_id = {str(r.get("source_card_id") or r.get("card_id")): r
                 for r in raw_rows}
    for rej in report.rejections:
        sid = str(rej.get("source_card_id"))
        tracker.quarantine("card", json.dumps(rej.get("reasons") or rej.get("reason")),
                           raw_by_id.get(sid, {"source_card_id": sid}),
                           source_row_id=sid)

    # ---- 4. atomic promote (§27) ----------------------------------------------
    try:
        db_counts = repo.flush(observation_note=(
            f"activation {stamp} dataset={args.dataset_version} "
            f"sha256={fingerprint[:16]}"))
    except Exception as e:                     # noqa: BLE001
        tracker.fail(f"promotion failed (transaction rolled back): {e}")
        print(f"PROMOTION FAILED — database unchanged: {e}")
        return 4
    tracker.advance("PRODUCTION")

    # ---- 5. watermark + cache invalidation (§28/§31) ---------------------------
    from backend.data_access.candidate_repository import CandidateRepository
    local_repo = CandidateRepository()
    local_repo.invalidate()   # in-process; API processes refresh via card
                              # watermark + TTL on their next load (§31)

    # ---- 6. integrity checks ----------------------------------------------------
    integrity = {}
    integrity["synthetic_in_production"] = query(
        """SELECT count(*) AS n FROM ut_card c
           JOIN game_version g ON g.id = c.game_version_id
           WHERE g.code = %s AND c.is_synthetic = TRUE
             AND c.data_status <> 'SYNTHETIC_TEST'""", (gv,))[0]["n"]
    integrity["cross_version_leak"] = query(
        """SELECT count(*) AS n FROM ut_card c
           JOIN game_version g ON g.id = c.game_version_id
           WHERE g.code <> %s AND c.source_id = %s""", (gv, src.source_id))[0]["n"]
    integrity["current_versions_per_card_ok"] = query(
        """SELECT count(*) AS n FROM (
             SELECT ut_card_id FROM card_version
             WHERE is_current GROUP BY ut_card_id HAVING count(*) > 1) x""")[0]["n"]
    integrity["prices_without_observation"] = query(
        """SELECT count(*) AS n FROM card_price
           WHERE source_observation_id IS NULL""")[0]["n"]
    integrity_ok = (integrity["synthetic_in_production"] == 0
                    and integrity["cross_version_leak"] == 0
                    and integrity["current_versions_per_card_ok"] == 0
                    and integrity["prices_without_observation"] == 0)

    # ---- 7. golden regression (§57) ----------------------------------------------
    goldens = subprocess.run([sys.executable, str(ROOT / "scripts" / "verify_goldens.py")],
                             capture_output=True, text=True, timeout=900)
    golden_ok = goldens.returncode == 0

    final_report = {
        "source_id": src.source_id,
        "game_version": gv,
        "dataset_version": args.dataset_version,
        "source_sha256": fingerprint,
        "activated_at": datetime.now(timezone.utc).isoformat(),
        "forensics_verdict": stats["verdict"],
        "forensics_report": str(fpath.relative_to(ROOT)),
        "pipeline": report.to_dict(),
        "db_counts": db_counts,
        "integrity": integrity,
        "integrity_ok": integrity_ok,
        "golden_regression_ok": golden_ok,
        "activation": "ACTIVE" if (integrity_ok and golden_ok) else "ROLLED_BACK",
    }
    tracker.finish(final_report,
                   stage="PRODUCTION" if final_report["activation"] == "ACTIVE" else "ROLLED_BACK",
                   activation_status=final_report["activation"])
    rpath = REPORT_DIR / f"{src.source_id}_{gv}_{stamp}.json"
    rpath.write_text(json.dumps(final_report, indent=2, default=str))
    print(json.dumps({k: final_report[k] for k in
                      ("forensics_verdict", "db_counts", "integrity_ok",
                       "golden_regression_ok", "activation")}, indent=2, default=str))
    print(f"report -> {rpath.relative_to(ROOT)}")
    if not golden_ok:
        print("GOLDEN REGRESSION FAILED after promotion — STOP and investigate "
              "(§57). Run flagged ROLLED_BACK; do not edit the baseline.")
        return 5
    if not integrity_ok:
        print("INTEGRITY CHECKS FAILED — investigate before serving this data.")
        return 5
    print("ACTIVATION COMPLETE: production card data is live; readers pick it "
          "up via the card watermark (no stale reads).")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        close_pool()
