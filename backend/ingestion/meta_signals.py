"""META_SIGNAL pipeline (§18/§19) — schema + storage adapter, data-ready.

HARD FIREWALL by construction:
* meta signals are stored ONLY in `meta_signal` — never in ut_card,
  game_player, card_version, card_price or any canonical table;
* a meta signal can never overwrite canonical EA data: there is no code path
  from this module to a canonical write;
* community/competitive sources are stored as RESEARCH_ONLY and every
  consumer must label them as perception, not fact;
* signal_strength/sample_size stay NULL when the source does not publish
  them — never 0, never estimated;
* sources still pass the same legal gate as canonical ingestion
  (fetch_permitted), and production-permission rules apply to how the signal
  may be USED, recorded via data_status.

No FC26 meta source is currently permitted/adopted; this module makes the
pipeline ready the moment one is cleared (§18: schema and adapters first).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.domain.evidence_model import SourceRecord

VALID_SIGNAL_TYPES = {
    "popular_in_competitive_play", "community_favorite", "reported_strength",
    "reported_weakness", "market_demand", "tactical_trend", "frequently_used",
}
VALID_ENTITY_TYPES = {"ut_card", "game_player"}


class MetaSignalRejected(ValueError):
    pass


def validate_signal(sig: dict) -> None:
    stype = sig.get("signal_type")
    if stype not in VALID_SIGNAL_TYPES:
        raise MetaSignalRejected(
            f"unknown signal_type {stype!r} — permitted: "
            f"{sorted(VALID_SIGNAL_TYPES)}")
    if sig.get("entity_type") not in VALID_ENTITY_TYPES:
        raise MetaSignalRejected(
            f"entity_type must be one of {sorted(VALID_ENTITY_TYPES)}")
    strength = sig.get("signal_strength")
    if strength is not None and not (0.0 <= float(strength) <= 1.0):
        raise MetaSignalRejected("signal_strength must be within 0..1 or NULL")
    sample = sig.get("sample_size")
    if sample is not None and int(sample) <= 0:
        raise MetaSignalRejected("sample_size must be > 0 or NULL (never 0)")


def store_meta_signals(source: SourceRecord, game_version: str,
                       signals: list[dict],
                       observation_id: Optional[uuid.UUID] = None) -> dict:
    """Persist a batch of meta signals. Returns counts; rejects bad rows into
    `rejected` instead of silently dropping or silently fixing them."""
    from backend.core.db import execute, query_one

    if not source.fetch_permitted:
        raise MetaSignalRejected(
            f"source {source.source_id} legal_gate={source.legal_gate} — "
            "meta ingestion is gated exactly like canonical ingestion (§54)")

    gv_row = query_one("SELECT id FROM game_version WHERE code = %s",
                       (str(game_version).upper(),))
    if gv_row is None:
        raise MetaSignalRejected(
            f"game_version {game_version} not registered — refusing (§25)")
    gv_id = gv_row["id"]

    # usage -> data_status: only production-permitted sources may store
    # CANONICAL-status meta rows; everything else is RESEARCH_ONLY. This is
    # the status of the SIGNAL RECORD, never of canonical data.
    data_status = ("CANONICAL" if source.production_permitted
                   else "RESEARCH_ONLY" if source.usage_status.value in
                   ("PUBLIC_REFERENCE", "RESEARCH_ONLY")
                   else "RESEARCH_ONLY")

    stored = rejected = 0
    for sig in signals:
        try:
            validate_signal(sig)
        except MetaSignalRejected as e:
            rejected += 1
            execute(
                """INSERT INTO ingestion_quarantine
                     (run_id, source_id, game_version, entity_kind,
                      source_row_id, reason, raw_payload)
                   VALUES (NULL,%s,%s,'meta_signal',%s,%s,%s::jsonb)""",
                (source.source_id, str(game_version).upper(),
                 str(sig.get("entity_id")), str(e),
                 json.dumps(sig, default=str)[:20000]))
            continue
        execute(
            """INSERT INTO meta_signal
                 (game_version_id, source_id, signal_type, entity_type,
                  entity_id, position, tactical_context, signal_strength,
                  sample_size, confidence, observed_at, payload, data_status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
            (gv_id, source.source_id, sig["signal_type"], sig["entity_type"],
             sig.get("entity_id"), sig.get("position"),
             sig.get("tactical_context"), sig.get("signal_strength"),
             sig.get("sample_size"), sig.get("confidence"),
             sig.get("observed_at") or datetime.now(timezone.utc),
             json.dumps(sig.get("payload") or {}, default=str)[:100000],
             data_status))
        stored += 1
    return {"stored": stored, "rejected": rejected,
            "data_status": data_status,
            "observation_id": str(observation_id) if observation_id else None}


def meta_watermark(game_version: str) -> str:
    """§28: meta data version — separate from card/price/chemistry watermarks."""
    from backend.core.db import query_one
    row = query_one(
        """SELECT count(*) AS n, coalesce(max(m.observed_at), 'epoch') AS mo
           FROM meta_signal m
           JOIN game_version g ON g.id = m.game_version_id
           WHERE g.code = %s""", (str(game_version).upper(),))
    return f"meta:{row['n']}@{row['mo']}"


def signals_for(entity_type: str, entity_id: uuid.UUID,
                signal_type: Optional[str] = None) -> list[dict]:
    """Read path for consumers. Output is ALWAYS labelled as perception."""
    from backend.core.db import query
    sql = """SELECT m.signal_type, m.signal_strength, m.sample_size,
                    m.confidence, m.observed_at, m.data_status, m.source_id,
                    m.tactical_context, m.payload
             FROM meta_signal m
             WHERE m.entity_type = %s AND m.entity_id = %s"""
    params: list = [entity_type, entity_id]
    if signal_type:
        sql += " AND m.signal_type = %s"
        params.append(signal_type)
    sql += " ORDER BY m.observed_at DESC LIMIT 50"
    out = []
    for r in query(sql, tuple(params)):
        out.append({
            "kind": "META_SIGNAL",           # never presented as canonical fact
            "is_canonical": False,
            "signal_type": r["signal_type"],
            "signal_strength": (float(r["signal_strength"])
                                if r["signal_strength"] is not None else None),
            "sample_size": r["sample_size"],
            "confidence": float(r["confidence"]) if r["confidence"] is not None else None,
            "observed_at": r["observed_at"].isoformat() if r["observed_at"] else None,
            "data_status": r["data_status"],
            "source_id": r["source_id"],
            "tactical_context": r["tactical_context"],
            "payload": r["payload"],
        })
    return out
