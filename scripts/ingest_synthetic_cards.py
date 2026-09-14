#!/usr/bin/env python3
"""Ingest SYNTHETIC test cards (data/fixtures/fictional_ut_cards.csv).

Purpose: exercise the card pipeline + validation gate end-to-end.
Expected: 60 persisted with is_synthetic=TRUE / data_status=SYNTHETIC_TEST,
3 rejected (Broken Rating Case, Missing Rating Case, Too Many Plus Case).

These rows are FIREWALLED: production read paths filter them out (§13).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.db import close_pool, query  # noqa: E402
from backend.domain.evidence_model import SourceRecord, UsageStatus  # noqa: E402
from backend.ingestion.local_file_adapter import LocalFileAdapter  # noqa: E402
from backend.ingestion.pipeline import IngestionPipeline  # noqa: E402
from backend.repositories.postgres_canonical_repository import (  # noqa: E402
    PostgresCanonicalRepository,
)

ROOT = Path(__file__).resolve().parents[1]
CARDS_CSV = ROOT / "data" / "fixtures" / "fictional_ut_cards.csv"
SOURCE_ID = "synthetic_fixtures"


def main() -> None:
    rows = query("SELECT * FROM source_registry WHERE source_id=%s", (SOURCE_ID,))
    r = rows[0]
    src = SourceRecord(
        source_id=r["source_id"], name=r["name"], source_type=r["source_type"],
        authority_tier=r["authority_tier"], url=r["url"], license=r["license"],
        usage_status=UsageStatus(r["usage_status"]), legal_gate=r["legal_gate"],
        canonical_fields=[], notes=r["notes"])
    adapter = LocalFileAdapter(src, "FC26", cards_path=CARDS_CSV)
    repo = PostgresCanonicalRepository(SOURCE_ID, "FC26")
    pipeline = IngestionPipeline(adapter, repo)
    report = pipeline.run_cards()
    counts = repo.flush(observation_note="synthetic card fixture ingestion")
    print(json.dumps({"report": report.to_dict(), "db_counts": counts},
                     indent=2, default=str))


if __name__ == "__main__":
    try:
        main()
    finally:
        close_pool()
