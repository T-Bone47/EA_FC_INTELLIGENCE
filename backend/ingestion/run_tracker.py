"""Ingestion run tracking + quarantine (§26/§27).

RAW -> STAGING -> VALIDATED -> PRODUCTION must be auditable and atomic:
every run records counts, activation status and the full pipeline report;
invalid rows are quarantined with their raw payload and reason instead of
being silently dropped or silently fixed.

Activation is transactional at the repository level (single flush inside one
DB transaction); this tracker records the outcome. A failed promotion marks
the run FAILED — a dataset is never partially activated.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

STAGES = ("RAW", "STAGING", "VALIDATED", "PRODUCTION", "FAILED", "ROLLED_BACK")


class IngestionRunTracker:
    """Persists one `ingestion_run` row and its quarantine entries."""

    def __init__(self, source_id: str, game_version: str,
                 dataset_version: Optional[str] = None,
                 source_hash: Optional[str] = None):
        self.source_id = source_id
        self.game_version = str(game_version).upper()
        self.dataset_version = dataset_version
        self.source_hash = source_hash
        self.run_id: Optional[uuid.UUID] = None

    # ------------------------------------------------------------------ lifecycle
    def start(self, rows_raw: int = 0) -> uuid.UUID:
        from backend.core.db import query_one
        row = query_one(
            """INSERT INTO ingestion_run
                 (source_id, game_version_id, dataset_version, source_hash,
                  stage, rows_raw, activation_status)
               SELECT %s, gv.id, %s, %s, 'RAW', %s, 'PENDING'
               FROM game_version gv
               WHERE gv.code = %s
               RETURNING id""",
            (self.source_id, self.dataset_version, self.source_hash,
             int(rows_raw), self.game_version))
        if row is None:
            raise LookupError(
                f"game_version {self.game_version} not registered — ingestion "
                "refuses to run for unknown versions (§25)")
        self.run_id = row["id"]
        return self.run_id

    def advance(self, stage: str) -> None:
        if stage not in STAGES:
            raise ValueError(f"unknown ingestion stage {stage!r}")
        self._update("stage", stage)

    def quarantine(self, entity_kind: str, reason: str,
                   raw_payload: dict, source_row_id: Optional[str] = None) -> None:
        from backend.core.db import execute
        execute(
            """INSERT INTO ingestion_quarantine
                 (run_id, source_id, game_version, entity_kind, source_row_id,
                  reason, raw_payload)
               VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)""",
            (self.run_id, self.source_id, self.game_version, entity_kind,
             source_row_id, reason,
             json.dumps(raw_payload, default=str)[:20000]))

    def finish(self, report: dict, stage: str = "PRODUCTION",
               activation_status: str = "ACTIVE") -> None:
        counts = report.get("counts") or {}
        self._finalize(stage=stage, activation_status=activation_status,
                       accepted=int(counts.get("players", 0)) + int(counts.get("cards", 0)),
                       rejected=int(report.get("rejected", 0)),
                       quarantined=int(report.get("quarantined", 0)),
                       conflicts=int(report.get("conflicts", 0)),
                       warnings=int(report.get("warnings", 0)),
                       report=report)

    def fail(self, reason: str, report: Optional[dict] = None) -> None:
        self._finalize(stage="FAILED", activation_status="REJECTED",
                       accepted=0, rejected=0, quarantined=0, conflicts=0,
                       warnings=0, report={"failure": reason, **(report or {})})

    # ------------------------------------------------------------------ internals
    def _update(self, field: str, value: str) -> None:
        from backend.core.db import execute
        if self.run_id is None:
            return
        execute(f"UPDATE ingestion_run SET {field} = %s WHERE id = %s",
                (value, self.run_id))

    def _finalize(self, stage: str, activation_status: str, accepted: int,
                  rejected: int, quarantined: int, conflicts: int,
                  warnings: int, report: dict) -> None:
        from backend.core.db import execute
        if self.run_id is None:
            return
        execute(
            """UPDATE ingestion_run
               SET stage = %s, activation_status = %s, rows_accepted = %s,
                   rows_rejected = %s, rows_quarantined = %s, conflicts = %s,
                   warnings = %s, report = %s::jsonb, finished_at = %s
               WHERE id = %s""",
            (stage, activation_status, accepted, rejected, quarantined,
             conflicts, warnings, json.dumps(report, default=str)[:200000],
             datetime.now(timezone.utc), self.run_id))
