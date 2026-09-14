#!/usr/bin/env python3
"""Ingest the real FC26 foundation into PostgreSQL via the production pipeline.

Flow (§46): raw CSV -> adapter (legal-gated) -> normalize -> validate ->
identity resolve -> canonical repository -> Postgres. Idempotent: re-running
produces no duplicates (deterministic UUIDs + upserts).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.db import close_pool, query  # noqa: E402
from backend.domain.evidence_model import SourceRecord, UsageStatus  # noqa: E402
from backend.ingestion.identity_resolver import IdentityIndex  # noqa: E402
from backend.ingestion.local_file_adapter import LocalFileAdapter  # noqa: E402
from backend.ingestion.pipeline import IngestionPipeline  # noqa: E402
from backend.repositories.postgres_canonical_repository import (  # noqa: E402
    PostgresCanonicalRepository,
)
from backend.domain.card_model import RealPlayer  # noqa: E402
from backend.ingestion.normalizer import normalize_name  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data" / "fc26_real_foundation"

SOURCE_ID = "kaggle_justdhia_ea_fc26_player_ratings"


def source_record() -> SourceRecord:
    rows = query("SELECT * FROM source_registry WHERE source_id=%s", (SOURCE_ID,))
    if not rows:
        raise SystemExit(f"source {SOURCE_ID} not registered — run setup_database first")
    r = rows[0]
    return SourceRecord(
        source_id=r["source_id"], name=r["name"], source_type=r["source_type"],
        authority_tier=r["authority_tier"], url=r["url"], license=r["license"],
        usage_status=UsageStatus(r["usage_status"]), legal_gate=r["legal_gate"],
        canonical_fields=list(r["canonical_fields"] or []), notes=r["notes"])


def identity_index() -> IdentityIndex:
    idx = IdentityIndex()
    for r in query("SELECT * FROM real_player"):
        idx.add(RealPlayer(
            id=r["id"], full_name=r["full_name"], normalized_name=r["normalized_name"],
            nationality=r["nationality"],
            date_of_birth=str(r["date_of_birth"]) if r["date_of_birth"] else None,
            position_hint=r["position_hint"],
            name_variants=[]))
    return idx


def main() -> None:
    src = source_record()
    adapter = LocalFileAdapter(
        src, "FC26",
        players_path=FOUNDATION / "players.csv",
        playstyles_path=FOUNDATION / "player_playstyles.csv")
    repo = PostgresCanonicalRepository(SOURCE_ID, "FC26")
    pipeline = IngestionPipeline(adapter, repo, identity_index=identity_index())

    report = pipeline.run_players(attach_playstyles=True)
    counts = repo.flush(observation_note="FC26 foundation ingestion")

    print(json.dumps({"report": report.to_dict(), "db_counts": counts},
                     indent=2, default=str))
    if report.players_rejected:
        print(f"WARNING: {report.players_rejected} rows rejected (see report)")


if __name__ == "__main__":
    try:
        main()
    finally:
        close_pool()
