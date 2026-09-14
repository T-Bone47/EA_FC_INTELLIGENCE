"""PRODUCTION foundation CSV loader (backend/data_access — NOT a test module).

Loads the canonical FC26 foundation CSVs directly into domain Candidates.
Used by benchmarks and DB-less tooling; the API serves candidates from the
CandidateRepository (PostgreSQL). This is the production replacement for the historical
test-module data-loading coupling (§14).
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from backend.domain.card_model import (
    ALL_ATTRS, Candidate, DataStatus, GameVersionCode, PlayerAttributes,
)

DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
FOUNDATION_DIR = DATA_ROOT / "fc26_real_foundation"


def foundation_paths(game_version: str = "FC26") -> tuple[Path, Path]:
    if game_version.upper() != "FC26":
        raise FileNotFoundError(
            f"No foundation dataset exists for {game_version}. Only FC26 has a real "
            "foundation; other versions must be ingested from legitimate sources — "
            "nothing is fabricated or copied across versions.")
    return FOUNDATION_DIR / "players.csv", FOUNDATION_DIR / "player_playstyles.csv"


def _int_or_none(v):
    if v is None or v == "":
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def load_playstyles(path: Path) -> tuple[dict[str, dict[str, list[str]]], set[str]]:
    by_player: dict[str, dict[str, list[str]]] = {}
    published: set[str] = set()
    if not path.exists():
        return by_player, published
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            key = row["player_id"].strip()
            bucket = by_player.setdefault(key, {"base": [], "plus": []})
            tier = row.get("tier", "base").strip() or "base"
            name = row["playstyle"].strip()
            if name and name not in bucket[tier]:
                bucket[tier].append(name)
            published.add(key)
    return by_player, published


def load_foundation_candidates(game_version: str = "FC26",
                               positions: Optional[set[str]] = None) -> list[Candidate]:
    players_path, ps_path = foundation_paths(game_version)
    gv = GameVersionCode.parse(game_version)
    ps_by_player, published = load_playstyles(ps_path)

    candidates: list[Candidate] = []
    with open(players_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if (row.get("game_version") or gv.value) != gv.value:
                raise ValueError("game-version contamination in foundation CSV")
            pos = (row.get("position_primary") or "").strip().upper()
            if positions and pos not in {p.upper() for p in positions}:
                # still consider alternates below
                alt = {p.strip().upper() for p in
                       (row.get("alternate_positions") or "").split(",") if p.strip()}
                if not (alt & {p.upper() for p in positions}):
                    continue
            key = row["player_id"].strip()
            attrs = PlayerAttributes()
            for code in ALL_ATTRS:
                attrs.set(code, _int_or_none(row.get(code)))
            ps = ps_by_player.get(key, {"base": [], "plus": []})
            display = (row.get("common_name") or
                       f"{row.get('first_name') or ''} {row.get('last_name') or ''}").strip() \
                or "Unknown"
            candidates.append(Candidate(
                entity_type="game_player",
                entity_id=_stable_uuid(gv.value, key),
                game_version=gv,
                name=display,
                position_primary=pos,
                secondary_positions=[p.strip().upper() for p in
                                     (row.get("alternate_positions") or "").split(",")
                                     if p.strip()],
                overall_rating=_int_or_none(row.get("overall_rating")),
                attributes=attrs,
                playstyles_base=ps["base"], playstyles_plus=ps["plus"],
                playstyle_data_published=key in published,
                nation=row.get("nation") or None,
                club=row.get("club") or None,
                league=row.get("league") or None,
                data_status=DataStatus.CANONICAL,
                extra={"source_player_id": _int_or_none(key),
                       "position_type": row.get("position_type") or None,
                       "preferred_foot": row.get("preferred_foot") or None},
            ))
    return candidates


def _stable_uuid(game_version: str, source_player_id: str):
    from backend.ingestion.normalizer import NAME_NAMESPACE
    import uuid
    return uuid.uuid5(NAME_NAMESPACE, f"foundation|{game_version}|{source_player_id}")
