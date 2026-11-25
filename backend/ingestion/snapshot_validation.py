"""Dataset-level validation of a raw ratings-API snapshot (Phase 22).

`DataQualityValidator` checks one normalized GamePlayer at a time. This
module checks the file as a whole, on the rows exactly as published, before
anything reaches the database: header, row count, duplicate ids, version
markers, position vocabulary, attribute ranges, PlayStyle syntax, GK shape,
gender distribution. It produces a machine-readable report in which every
REJECT and FLAG carries its reason. Nothing is repaired here.

Outcomes per row:
    ACCEPT  -- no issue
    FLAG    -- ingested, issue recorded (e.g. a field stored as UNKNOWN)
    REJECT  -- not ingested; reason recorded
"""
from __future__ import annotations

import collections
from collections.abc import Callable
from datetime import date, datetime

from backend.ingestion.ea_ratings_csv_adapter import (
    ATTRIBUTE_COLUMN_MAP,
    EXPECTED_COLUMNS,
    FACADE_COLUMNS,
    GK_POSITION,
    parse_playstyles,
)

GK_FACE_MIRROR_PAIRS: tuple[tuple[str, str], ...] = (
    ("pace", "goalkeeping_diving"),
    ("shooting", "goalkeeping_handling"),
    ("passing", "goalkeeping_kicking"),
    ("dribbling", "goalkeeping_reflexes"),
    ("physicality", "goalkeeping_positioning"),
)
GK_ATTRIBUTE_COLUMNS = tuple(c for c in ATTRIBUTE_COLUMN_MAP if c.startswith("goalkeeping_"))
OUTFIELD_DETAIL_COLUMNS = tuple(c for c in ATTRIBUTE_COLUMN_MAP if not c.startswith("goalkeeping_"))
NAME_COLUMNS = ("common_name", "first_name", "last_name")


def _int(v: str | None) -> int | None:
    s = (v or "").strip()
    if not s or not s.lstrip("-").isdigit():
        return None
    return int(s)


def validate_snapshot(
    header: list[str],
    rows: list[dict],
    *,
    expected_edition: str,
    expected_row_count: int | None,
    position_vocabulary: set[str],
    reference_playstyle_vocabulary: set[str] | None,
    canonical_id_fn: Callable[[str], object],
    snapshot_reference_date: date | None = None,
) -> dict:
    outcomes: dict[str, dict] = {}
    rejected: list[dict] = []
    flagged: list[dict] = []

    def note(idx: int, pid: str, severity: str, reason: str) -> None:
        key = f"{idx}:{pid}"
        o = outcomes.setdefault(key, {"row_index": idx, "player_id": pid,
                                      "status": "ACCEPT", "reasons": []})
        o["reasons"].append(f"{severity}: {reason}")
        if severity == "REJECT" or o["status"] == "REJECT":
            o["status"] = "REJECT"
        else:
            o["status"] = "FLAG"

    # ---------------------------------------------------------------- dataset
    header_exact = list(header) == list(EXPECTED_COLUMNS)
    editions = collections.Counter((r.get("edition") or "").strip() for r in rows)
    snapshot_dates = collections.Counter((r.get("snapshot_date") or "").strip() for r in rows)

    # ---------------------------------------------------------------- identity
    ids = [(r.get("player_id") or "").strip() for r in rows]
    id_counts = collections.Counter(ids)
    duplicate_ids = sorted(k for k, v in id_counts.items() if v > 1)
    canonical_ids = collections.Counter()
    for i, pid in enumerate(ids):
        if not pid.isdigit():
            note(i, pid, "REJECT", f"player_id {pid!r} missing or not an integer")
            continue
        if id_counts[pid] > 1:
            note(i, pid, "REJECT", "duplicate source player_id -- no occurrence is "
                                   "chosen over another")
        canonical_ids[str(canonical_id_fn(pid))] += 1
    duplicate_canonical = sum(1 for v in canonical_ids.values() if v > 1)

    # ---------------------------------------------------------------- per row
    missing = {"overall_rating": 0, "position": 0, "name": 0}
    positions = collections.Counter()
    alt_tokens = collections.Counter()
    attr_stats = {c: {"blank": 0, "non_integer": 0, "out_of_range": 0,
                      "min": None, "max": None}
                  for c in list(ATTRIBUTE_COLUMN_MAP) + list(FACADE_COLUMNS)}
    gender = collections.Counter()
    gk_by_gender = collections.Counter()
    pos_by_gender: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    leagues_by_gender: dict[str, set] = collections.defaultdict(set)
    gk_rows = 0
    gk_missing_gk_attrs = 0
    gk_mirror = {f"{a}=={b}": 0 for a, b in GK_FACE_MIRROR_PAIRS}
    outfield_mirror = {f"{a}=={b}": 0 for a, b in GK_FACE_MIRROR_PAIRS}
    outfield_rows = 0
    outfield_missing_detail = 0
    outfield_missing_facade = 0
    base_vocab = collections.Counter()
    plus_vocab = collections.Counter()
    plus_per_player = collections.Counter()
    players_with_playstyles = 0
    malformed_playstyle_rows = 0
    foot = collections.Counter()
    stars = {"skill_moves": collections.Counter(), "weak_foot": collections.Counter()}
    invalid_birthdates = 0
    ages: list[int] = []
    height_published = sum(1 for r in rows if (r.get("height_cm") or "").strip())
    weight_published = sum(1 for r in rows if (r.get("weight_kg") or "").strip())

    for i, r in enumerate(rows):
        pid = (r.get("player_id") or "").strip()

        ovr = _int(r.get("overall_rating"))
        if not (r.get("overall_rating") or "").strip():
            missing["overall_rating"] += 1
            note(i, pid, "REJECT", "missing overall_rating")
        elif ovr is None or not 1 <= ovr <= 99:
            note(i, pid, "REJECT", f"overall_rating {r.get('overall_rating')!r} outside 1-99")

        pos = (r.get("position") or "").strip().upper()
        if not pos:
            missing["position"] += 1
            note(i, pid, "REJECT", "missing position")
        elif pos not in position_vocabulary:
            note(i, pid, "REJECT", f"position {pos!r} not in the FC27 position vocabulary")
        positions[pos] += 1

        alts = (r.get("alternate_positions") or "").split()
        for a in alts:
            alt_tokens[a] += 1
            if a.upper() not in position_vocabulary:
                note(i, pid, "REJECT", f"alternate position {a!r} not in vocabulary")
        if len(set(alts)) != len(alts):
            note(i, pid, "FLAG", f"duplicate alternate positions {alts}")
        if pos and pos in alts:
            note(i, pid, "FLAG", "primary position repeated among alternates")

        if not any((r.get(c) or "").strip() for c in NAME_COLUMNS):
            missing["name"] += 1
            note(i, pid, "REJECT", "no name published (common/first/last all blank)")

        is_gk = pos == GK_POSITION
        for c, st in attr_stats.items():
            raw = (r.get(c) or "").strip()
            if not raw:
                st["blank"] += 1
                continue
            v = _int(raw)
            if v is None:
                st["non_integer"] += 1
                note(i, pid, "REJECT", f"{c}={raw!r} is not an integer")
                continue
            if not 1 <= v <= 99:
                st["out_of_range"] += 1
                note(i, pid, "REJECT", f"{c}={v} outside 1-99")
            st["min"] = v if st["min"] is None else min(st["min"], v)
            st["max"] = v if st["max"] is None else max(st["max"], v)

        g = (r.get("gender") or "").strip()
        gender[g] += 1
        pos_by_gender[g][pos] += 1
        leagues_by_gender[g].add((r.get("league") or "").strip())
        if not g:
            note(i, pid, "FLAG", "gender/division not published")

        if is_gk:
            gk_rows += 1
            gk_by_gender[g] += 1
            if not all((r.get(c) or "").strip() for c in GK_ATTRIBUTE_COLUMNS):
                gk_missing_gk_attrs += 1
                note(i, pid, "FLAG", "goalkeeper without all five goalkeeping attributes")
            for a, b in GK_FACE_MIRROR_PAIRS:
                if (r.get(a) or "").strip() == (r.get(b) or "").strip():
                    gk_mirror[f"{a}=={b}"] += 1
        else:
            outfield_rows += 1
            if not all((r.get(c) or "").strip() for c in OUTFIELD_DETAIL_COLUMNS):
                outfield_missing_detail += 1
                note(i, pid, "FLAG", "outfield player without all 29 detailed attributes")
            if not all((r.get(c) or "").strip() for c in FACADE_COLUMNS):
                outfield_missing_facade += 1
                note(i, pid, "FLAG", "outfield player without all six face stats")
            for a, b in GK_FACE_MIRROR_PAIRS:
                if (r.get(a) or "").strip() == (r.get(b) or "").strip():
                    outfield_mirror[f"{a}=={b}"] += 1

        base, plus, ps_issues = parse_playstyles(r.get("playstyles"))
        if base or plus:
            players_with_playstyles += 1
        for n in base:
            base_vocab[n] += 1
        for n in plus:
            plus_vocab[n] += 1
        plus_per_player[len(plus)] += 1
        raw_ps = [t.strip() for t in (r.get("playstyles") or "").split(",") if t.strip()]
        if any(t.endswith("+") for t in raw_ps[:-1]):
            ps_issues.append("PlayStyle+ is not the last entry")
        if ps_issues:
            malformed_playstyle_rows += 1
            note(i, pid, "FLAG", f"PlayStyles: {ps_issues}")

        f = (r.get("preferred_foot") or "").strip()
        foot[f] += 1
        if f not in ("Right", "Left"):
            note(i, pid, "FLAG", f"preferred_foot {f!r} not Right/Left; stored as UNKNOWN")
        for col in ("skill_moves", "weak_foot"):
            s = (r.get(col) or "").strip()
            stars[col][s] += 1
            if s not in ("1", "2", "3", "4", "5"):
                note(i, pid, "FLAG", f"{col} {s!r} not 1-5; stored as UNKNOWN")

        bd = (r.get("birthdate") or "").strip()
        if bd:
            try:
                d = datetime.strptime(bd, "%Y-%m-%d").date()
                if snapshot_reference_date:
                    ages.append(snapshot_reference_date.year - d.year -
                                ((snapshot_reference_date.month, snapshot_reference_date.day)
                                 < (d.month, d.day)))
            except ValueError:
                invalid_birthdates += 1
                note(i, pid, "FLAG", f"birthdate {bd!r} not ISO YYYY-MM-DD; stored as UNKNOWN")

    for o in outcomes.values():
        (rejected if o["status"] == "REJECT" else flagged).append(o)
    rejected.sort(key=lambda o: o["row_index"])
    flagged.sort(key=lambda o: o["row_index"])

    new_names = unknown_ref = None
    observed = set(base_vocab) | set(plus_vocab)
    if reference_playstyle_vocabulary is not None:
        new_names = sorted(observed - reference_playstyle_vocabulary)
        unknown_ref = sorted(reference_playstyle_vocabulary - observed)

    divisions = [g for g in leagues_by_gender if g]
    league_overlap = sorted(set.intersection(*(leagues_by_gender[g] for g in divisions))) \
        if len(divisions) > 1 else []

    blocking: list[str] = []
    if not header_exact:
        blocking.append("header is not the exact audited 60-column layout")
    if set(editions) != {expected_edition}:
        blocking.append(f"edition values {dict(editions)} != {{{expected_edition!r}}}")
    if len(snapshot_dates) != 1:
        blocking.append(f"more than one snapshot_date in one file: {dict(snapshot_dates)}")
    if expected_row_count is not None and len(rows) != expected_row_count:
        blocking.append(f"row count {len(rows)} != documented {expected_row_count}")
    if duplicate_canonical:
        blocking.append(f"{duplicate_canonical} duplicate canonical game_player ids")

    return {
        "verdict": "PASS" if not blocking else "FAIL",
        "blocking_reasons": blocking,
        "dataset": {
            "row_count": len(rows),
            "expected_row_count": expected_row_count,
            "row_count_matches": (expected_row_count is None or len(rows) == expected_row_count),
            "column_count": len(header),
            "header_exact_match": header_exact,
            "editions": dict(editions),
            "snapshot_dates": dict(snapshot_dates),
        },
        "identity": {
            "duplicate_source_player_ids": duplicate_ids,
            "duplicate_canonical_ids": duplicate_canonical,
            "canonical_id_rule": ("uuid5(ns, 'game_player|<source_id>|<GAME_VERSION>|"
                                  "<source_player_id>') -- game_version is in the preimage"),
        },
        "required_fields_missing": missing,
        "positions": {
            "vocabulary_used": sorted(position_vocabulary),
            "primary": dict(sorted(positions.items())),
            "alternate_tokens": dict(sorted(alt_tokens.items())),
            "players_with_alternates": sum(1 for r in rows if (r.get("alternate_positions") or "").strip()),
        },
        "attributes": attr_stats,
        "enumerations": {
            "preferred_foot": dict(foot),
            "skill_moves": dict(sorted(stars["skill_moves"].items())),
            "weak_foot": dict(sorted(stars["weak_foot"].items())),
            "invalid_birthdates": invalid_birthdates,
            "age_at_snapshot_min": min(ages) if ages else None,
            "age_at_snapshot_max": max(ages) if ages else None,
            "height_cm_published": height_published,
            "weight_kg_published": weight_published,
        },
        "goalkeepers": {
            "gk_rows": gk_rows,
            "gk_missing_any_goalkeeping_attribute": gk_missing_gk_attrs,
            "gk_face_stat_mirrors_of_goalkeeping_attributes": gk_mirror,
            "outfield_rows_with_same_equalities": outfield_mirror,
            "interpretation": ("GK rows carry EA's GK face stats in the outfield-named "
                               "columns; they are not mapped to canonical pace..physicality"),
        },
        "outfield": {
            "outfield_rows": outfield_rows,
            "missing_any_detailed_attribute": outfield_missing_detail,
            "missing_any_face_stat": outfield_missing_facade,
        },
        "playstyles": {
            "players_with_any": players_with_playstyles,
            "coverage_fraction": round(players_with_playstyles / len(rows), 6) if rows else None,
            "distinct_base_names": len(base_vocab),
            "distinct_plus_names": len(plus_vocab),
            "base_counts": dict(sorted(base_vocab.items())),
            "plus_counts": dict(sorted(plus_vocab.items())),
            "plus_per_player": dict(sorted(plus_per_player.items())),
            "rows_with_malformed_playstyles": malformed_playstyle_rows,
            "names_not_in_reference_vocabulary": new_names,
            "reference_names_not_observed": unknown_ref,
        },
        "gender": {
            "distribution": dict(gender),
            "goalkeepers_by_division": dict(gk_by_gender),
            "positions_by_division": {g: dict(sorted(c.items())) for g, c in pos_by_gender.items()},
            "league_overlap_between_divisions": league_overlap,
        },
        "row_outcomes": {
            "accepted": len(rows) - len(rejected) - len(flagged),
            "flagged": len(flagged),
            "rejected": len(rejected),
        },
        "rejected_rows": rejected,
        "flagged_rows": flagged,
    }
