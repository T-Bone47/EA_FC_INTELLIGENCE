"""DATASET FORENSICS (§23) — mandatory pre-import analysis for any dataset.

Deterministic, read-only analysis of raw rows BEFORE anything is normalized
or persisted. Produces a stats dict + a markdown report. A dataset with
REJECT-level findings must not be promoted to production.

Never fabricates: counts and violations are computed from the rows given;
missing columns are reported as absent, not assumed empty.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

RATING_RANGE = range(1, 100)
KNOWN_POSITIONS = {"GK", "CB", "LB", "RB", "CDM", "CM", "CAM", "LM", "RM",
                   "LW", "RW", "ST"}
NUMERIC_RATING_COLUMNS = None       # resolved lazily from ALL_ATTRS


def _rating_columns() -> set[str]:
    global NUMERIC_RATING_COLUMNS
    if NUMERIC_RATING_COLUMNS is None:
        from backend.domain.card_model import ALL_ATTRS
        NUMERIC_RATING_COLUMNS = set(ALL_ATTRS) | {"overall_rating"}
    return NUMERIC_RATING_COLUMNS


def _to_int(v: Any) -> Optional[int]:
    try:
        if v is None or str(v).strip() == "":
            return None
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return None


def analyze_rows(rows: list[dict], *, entity: str, game_version: str,
                 id_column: str, known_playstyles: Optional[Iterable[str]] = None,
                 stale_after_days: int = 400) -> dict:
    """Full forensic pass over raw rows. `entity` = 'card' | 'player' | 'price'."""
    findings: list[dict] = []

    def finding(severity: str, code: str, message: str, count: int = 1) -> None:
        findings.append({"severity": severity, "code": code,
                         "message": message, "count": count})

    n = len(rows)
    columns = sorted({k for r in rows for k in r}) if rows else []
    stats: dict[str, Any] = {
        "entity": entity,
        "game_version": game_version,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "row_count": n,
        "column_count": len(columns),
        "columns": columns,
    }
    if n == 0:
        finding("WARN", "empty_dataset", "dataset contains zero rows")
        stats["findings"] = findings
        return stats

    # ---- null rate per column ------------------------------------------------
    nulls = {c: sum(1 for r in rows if r.get(c) in (None, "")) for c in columns}
    stats["null_rate"] = {c: round(nulls[c] / n, 4) for c in columns}

    # ---- duplicates -----------------------------------------------------------
    ids = [str(r.get(id_column) or "").strip() for r in rows]
    id_counts = Counter(x for x in ids if x)
    dupes = {k: v for k, v in id_counts.items() if v > 1}
    missing_ids = sum(1 for x in ids if not x)
    stats["duplicate_rate"] = round(sum(v - 1 for v in dupes.values()) / n, 4)
    stats["identity_coverage"] = round((n - missing_ids) / n, 4)
    if dupes:
        finding("REJECT" if entity in ("card", "player") else "WARN",
                "duplicate_identity",
                f"{len(dupes)} duplicated {id_column} values "
                f"(e.g. {list(dupes)[:3]})")
    if missing_ids:
        finding("REJECT", "missing_identity",
                f"{missing_ids} rows without {id_column}")

    # ---- version consistency --------------------------------------------------
    if "game_version" in columns:
        versions = Counter(str(r.get("game_version") or "").upper() for r in rows)
        wrong = sum(v for k, v in versions.items() if k != game_version.upper())
        stats["version_consistency"] = {k: v for k, v in versions.items()}
        if wrong:
            finding("REJECT", "version_contamination",
                    f"{wrong} rows carry a game_version other than {game_version}")

    # ---- numeric ranges ---------------------------------------------------------
    rating_cols = [c for c in columns if c in _rating_columns()]
    range_violations: dict[str, int] = {}
    for c in rating_cols:
        bad = 0
        for r in rows:
            v = _to_int(r.get(c))
            if v is not None and v not in RATING_RANGE:
                bad += 1
        if bad:
            range_violations[c] = bad
    stats["range_violations"] = range_violations
    if range_violations:
        finding("REJECT", "impossible_ratings",
                f"values outside 1-99: {range_violations}")
    # attribute completeness over the rating columns present
    if rating_cols:
        filled = sum(sum(1 for c in rating_cols if _to_int(r.get(c)) is not None)
                     for r in rows)
        stats["attribute_completeness"] = round(filled / (n * len(rating_cols)), 4)

    # ---- position enum -----------------------------------------------------------
    if "position" in columns:
        bad_pos = Counter(str(r.get("position") or "").strip().upper()
                          for r in rows
                          if str(r.get("position") or "").strip().upper()
                          not in KNOWN_POSITIONS
                          and r.get("position") not in (None, ""))
        stats["invalid_positions"] = dict(bad_pos)
        if bad_pos:
            finding("REJECT", "invalid_position",
                    f"positions outside the known set: {dict(bad_pos)}")

    # ---- playstyle vocabulary ------------------------------------------------------
    if known_playstyles is not None:
        known = {p.strip().lower() for p in known_playstyles}
        unknown_ps: Counter = Counter()
        plus_col = "playstyles_plus" if "playstyles_plus" in columns else None
        for r in rows:
            for col in ("playstyles", "playstyles_plus"):
                raw = r.get(col)
                if not raw:
                    continue
                for item in str(raw).split(","):
                    item = item.strip().rstrip("+").lower()
                    if item and item not in known:
                        unknown_ps[item] += 1
        stats["unknown_playstyles"] = dict(unknown_ps)
        if unknown_ps:
            finding("REJECT", "unknown_playstyle",
                    f"PlayStyles outside the version vocabulary: {dict(unknown_ps)}")
        ps_cols = [c for c in ("playstyles", "playstyles_plus") if c in columns]
        if ps_cols:
            with_ps = sum(1 for r in rows if any(r.get(c) for c in ps_cols))
            stats["playstyle_coverage"] = round(with_ps / n, 4)
        if plus_col:
            multi_plus = sum(1 for r in rows
                             if len([x for x in str(r.get(plus_col) or "").split(",")
                                     if x.strip()]) > 1)
            if multi_plus:
                stats["multi_plus_rows"] = multi_plus
                finding("REVIEW", "playstyle_plus_cap",
                        f"{multi_plus} rows list more than one PlayStyle+ "
                        "(cap is version-specific — verify)")

    # ---- prices -----------------------------------------------------------------------
    if "price_coins" in columns:
        neg = sum(1 for r in rows
                  if (_to_int(r.get("price_coins")) or 0) < 0)
        priced = sum(1 for r in rows if _to_int(r.get("price_coins")) is not None)
        stats["price_coverage"] = round(priced / n, 4)
        if neg:
            finding("REJECT", "negative_price", f"{neg} rows with negative price")

    # ---- timestamps --------------------------------------------------------------------
    ts_col = next((c for c in ("observed_at", "retrieved_at", "updated_at",
                               "snapshot_date") if c in columns), None)
    if ts_col:
        stale = 0
        parsed = 0
        for r in rows:
            raw = r.get(ts_col)
            if raw in (None, ""):
                continue
            try:
                dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                parsed += 1
                age = (datetime.now(timezone.utc) - dt).days
                if age > stale_after_days or age < -1:
                    stale += 1
            except ValueError:
                continue
        stats["timestamp_coverage"] = round(parsed / n, 4)
        if stale:
            finding("REVIEW", "stale_timestamps",
                    f"{stale} rows with timestamps older than {stale_after_days}d "
                    "or in the future")
    else:
        stats["timestamp_coverage"] = None
        finding("REVIEW", "no_timestamp_column",
                "dataset carries no observed/retrieved timestamp column — "
                "freshness will be UNKNOWN")

    # ---- data_status firewall -----------------------------------------------------------
    if "data_status" in columns:
        statuses = Counter(str(r.get("data_status") or "").upper() for r in rows)
        stats["data_statuses"] = dict(statuses)

    stats["findings"] = findings
    stats["verdict"] = ("REJECT" if any(f["severity"] == "REJECT" for f in findings)
                        else "REVIEW" if any(f["severity"] == "REVIEW" for f in findings)
                        else "PASS")
    return stats


def source_fingerprint(raw_bytes: bytes) -> str:
    return hashlib.sha256(raw_bytes).hexdigest()


def to_markdown(stats: dict, source_label: str = "dataset") -> str:
    """DATASET_FORENSICS_REPORT.md content for one dataset (§23)."""
    lines = [
        f"# DATASET FORENSICS — {source_label}",
        "",
        f"* entity: `{stats['entity']}` · game_version: `{stats['game_version']}`",
        f"* analyzed_at: {stats['analyzed_at']}",
        f"* rows: **{stats['row_count']}** · columns: {stats['column_count']}",
        f"* verdict: **{stats['verdict']}**",
        "",
        "## Metrics",
        "",
        "| metric | value |",
        "|---|---|",
    ]
    for key in ("duplicate_rate", "identity_coverage", "attribute_completeness",
                "playstyle_coverage", "price_coverage", "timestamp_coverage"):
        if key in stats:
            lines.append(f"| {key} | {stats[key]} |")
    for key in ("range_violations", "invalid_positions", "unknown_playstyles",
                "version_consistency", "data_statuses"):
        if stats.get(key):
            lines.append(f"| {key} | `{json.dumps(stats[key], default=str)}` |")
    lines += ["", "## Findings", ""]
    if stats["findings"]:
        for f in stats["findings"]:
            lines.append(f"* **{f['severity']}** `{f['code']}` — {f['message']}")
    else:
        lines.append("* none")
    lines += ["", "Raw stats: `json` block below.", "",
              "```json", json.dumps(stats, indent=2, default=str)[:20000], "```", ""]
    return "\n".join(lines)
