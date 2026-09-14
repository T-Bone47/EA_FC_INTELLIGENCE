#!/usr/bin/env python3
"""
Build the canonical FC26 real foundation dataset from raw source CSVs.

Source: Kaggle 'justdhia/ea-sports-fc-26-player-ratings' (CC0 1.0 Public Domain),
a scrape of the official EA SPORTS FC Ratings page (ea.com/games/ea-sports-fc/ratings),
men's universe, scraped March 2026, retrieved 2026-09-14.

Normalization policy (documented in docs/DATASET_FORENSICS_FC26.md):
  * Split files (outfield / goalkeepers) are the base: ISO dates, no GK facade mirroring.
  * GK rows: outfield detailed attributes + facades are NULL (UNKNOWN). The combined
    file's GK facades are mirrors of GK attributes (EA UI mapping), NOT outfield ability.
  * Outfield rows: retain EA-published GK attributes (real values, semantically unused
    for outfield fit) from the combined file.
  * preferredFoot 1->Right, 2->Left (verified against known players: Messi/Salah/Haaland=2
    left-footed, De Bruyne/Kane=1 right-footed). Mapping classified SUPPORTED.
  * gender='male' — source-documented scope of this dataset (men's ratings).
  * PlayStyles exploded to long format: tier='base' from playStyles, tier='plus' from
    playStylesPlus (trailing '+' stripped). EA lists plus separately from base; the
    player's effective PlayStyle set is the union (documented).
  * UNKNOWN stays UNKNOWN: empty source values become empty output values (never 0).
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT.parent / "data_acquisition" / "raw"
OUT = ROOT / "data" / "fc26_real_foundation"
DOCS = ROOT / "docs"

GAME_VERSION = "FC26"
SOURCE_ID = "kaggle_justdhia_ea_fc26_player_ratings"
SOURCE_URL = "https://www.kaggle.com/datasets/justdhia/ea-sports-fc-26-player-ratings"
UPSTREAM_URL = "https://www.ea.com/games/ea-sports-fc/ratings"
RETRIEVED = "2026-09-14"

FACADES = {
    "pac": "pace", "sho": "shooting", "pas": "passing",
    "dri": "dribbling", "def": "defending", "phy": "physicality",
}
DETAILS = {
    "acceleration": "acceleration", "sprintSpeed": "sprint_speed",
    "finishing": "finishing", "shotPower": "shot_power",
    "longShots": "long_shots", "volleys": "volleys", "penalties": "penalties",
    "positioning": "positioning", "vision": "vision", "crossing": "crossing",
    "shortPassing": "short_passing", "longPassing": "long_passing",
    "curve": "curve", "freeKickAccuracy": "free_kick_accuracy",
    "dribbling": "dribbling_detail", "ballControl": "ball_control",
    "agility": "agility", "balance": "balance", "reactions": "reactions",
    "composure": "composure", "interceptions": "interceptions",
    "defensiveAwareness": "defensive_awareness",
    "standingTackle": "standing_tackle", "slidingTackle": "sliding_tackle",
    "headingAccuracy": "heading_accuracy", "aggression": "aggression",
    "jumping": "jumping", "stamina": "stamina", "strength": "strength",
}
GK_ATTRS = {
    "gkDiving": "gk_diving", "gkHandling": "gk_handling",
    "gkKicking": "gk_kicking", "gkPositioning": "gk_positioning",
    "gkReflexes": "gk_reflexes",
}
PREFERRED_FOOT = {1: "Right", 2: "Left"}

FOUNDATION_COLUMNS = [
    "player_id", "game_version", "first_name", "last_name", "common_name",
    "nation", "club", "league", "position_primary", "position_type",
    "date_of_birth", "height_cm", "weight_kg", "overall_rating", "source_rank",
    "weak_foot_stars", "skill_moves_stars", "preferred_foot",
    "pace", "shooting", "passing", "dribbling", "defending", "physicality",
    "acceleration", "sprint_speed", "finishing", "shot_power", "long_shots",
    "volleys", "penalties", "positioning", "vision", "crossing",
    "short_passing", "long_passing", "curve", "free_kick_accuracy",
    "dribbling_detail", "ball_control", "agility", "balance",
    "defensive_awareness", "interceptions", "standing_tackle", "sliding_tackle",
    "heading_accuracy", "strength", "stamina", "aggression", "jumping",
    "reactions", "composure",
    "gk_diving", "gk_handling", "gk_kicking", "gk_positioning", "gk_reflexes",
    "gender", "alternate_positions",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(v):
    """Preserve NaN as missing; strip strings."""
    if pd.isna(v):
        return None
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


def normalize_split(raw_row: dict, is_gk: bool) -> dict:
    out = {
        "player_id": int(raw_row["id"]),
        "game_version": GAME_VERSION,
        "first_name": clean(raw_row.get("firstName")),
        "last_name": clean(raw_row.get("lastName")),
        "common_name": clean(raw_row.get("commonName")),
        "nation": clean(raw_row.get("nationality")),
        "club": clean(raw_row.get("team")),
        "league": clean(raw_row.get("leagueName")),
        "position_primary": clean(raw_row.get("position")),
        "position_type": clean(raw_row.get("positionType")),
        "date_of_birth": clean(raw_row.get("birthdate")),
        "height_cm": clean(raw_row.get("height")),
        "weight_kg": clean(raw_row.get("weight")),
        "overall_rating": clean(raw_row.get("overallRating")),
        "source_rank": clean(raw_row.get("rank")),
        "weak_foot_stars": clean(raw_row.get("weakFootAbility")),
        "skill_moves_stars": clean(raw_row.get("skillMoves")),
        "gender": "male",  # source-documented scope (men's ratings)
        "alternate_positions": clean(raw_row.get("alternatePositions")),
    }
    pf = clean(raw_row.get("preferredFoot"))
    out["preferred_foot"] = PREFERRED_FOOT.get(pf) if pf is not None else None

    if not is_gk:
        for src, dst in FACADES.items():
            out[dst] = clean(raw_row.get(src))
        for src, dst in DETAILS.items():
            out[dst] = clean(raw_row.get(src))
    else:
        # GK outfield facades/details are UNKNOWN — combined-file facades are
        # mirrors of GK attributes (EA UI mapping), not outfield ability.
        for dst in list(FACADES.values()) + list(DETAILS.values()):
            out[dst] = None

    for src, dst in GK_ATTRS.items():
        out[dst] = clean(raw_row.get(src))
    return out


def explode_playstyles(players: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in players.iterrows():
        pid = int(r["player_id"])
        base = r.get("playstyles_raw")
        plus = r.get("playstylesplus_raw")
        if isinstance(base, str) and base.strip():
            for name in base.split(","):
                name = name.strip().rstrip("+")
                if name:
                    rows.append((pid, name, "base"))
        if isinstance(plus, str) and plus.strip():
            for name in plus.split(","):
                name = name.strip().rstrip("+")
                if name:
                    rows.append((pid, name, "plus"))
    ps = pd.DataFrame(rows, columns=["player_id", "playstyle", "tier"])
    ps["game_version"] = GAME_VERSION
    # a plus tier supersedes a duplicate base row for the same (player, playstyle)
    ps = ps.sort_values("tier", ascending=False)  # 'plus' > 'base' alphabetically? no: base<plus, ascending=False -> plus first
    ps = ps.drop_duplicates(subset=["player_id", "playstyle"], keep="first")
    return ps.sort_values(["player_id", "tier", "playstyle"]).reset_index(drop=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    outfield = pd.read_csv(RAW / "ea_fc26_outfield.csv")
    goalkeepers = pd.read_csv(RAW / "ea_fc26_goalkeepers.csv")
    combined = pd.read_csv(RAW / "ea_fc26_players.csv", encoding="utf-8-sig")
    combined.columns = [c.strip().lstrip("\ufeff") for c in combined.columns]

    raw_hashes = {f.name: sha256(f) for f in sorted(RAW.glob("*.csv"))}

    # Outfield GK attributes (EA-published, from combined file)
    comb_gk = combined.set_index("id")[list(GK_ATTRS.keys())]

    records = []
    ps_raw = []
    for df, is_gk in ((outfield, False), (goalkeepers, True)):
        for _, r in df.iterrows():
            raw_row = r.to_dict()
            rec = normalize_split(raw_row, is_gk)
            if not is_gk:
                pid = rec["player_id"]
                for src, dst in GK_ATTRS.items():
                    v = comb_gk.at[pid, src] if pid in comb_gk.index else None
                    rec[dst] = clean(v)
            records.append(rec)
            ps_raw.append({
                "player_id": rec["player_id"],
                "playstyles_raw": raw_row.get("playStyles"),
                "playstylesplus_raw": raw_row.get("playStylesPlus"),
            })

    players = pd.DataFrame(records, columns=FOUNDATION_COLUMNS)

    # ---- validation gate: reject invalid production data ----
    assert players["player_id"].is_unique, "duplicate player_id"
    assert len(players) == 16228, f"unexpected row count {len(players)}"
    assert players["overall_rating"].between(1, 99).all(), "OVR out of range"
    assert players["position_primary"].notna().all(), "missing position"
    attr_cols = [c for c in FOUNDATION_COLUMNS
                 if c not in ("player_id", "game_version", "first_name", "last_name",
                              "common_name", "nation", "club", "league",
                              "position_primary", "position_type", "date_of_birth",
                              "preferred_foot", "gender", "alternate_positions",
                              "source_rank", "height_cm", "weight_kg")]
    for c in attr_cols:
        s = pd.to_numeric(players[c], errors="coerce")
        bad = players[c].notna() & (s.isna() | (s < 1) | (s > 99))
        assert not bad.any(), f"invalid values in {c}"
    rank = pd.to_numeric(players["source_rank"], errors="coerce")
    assert (players["source_rank"].isna() | (rank >= 1)).all(), "invalid source_rank"
    assert (players["game_version"] == GAME_VERSION).all(), "version contamination"

    players.to_csv(OUT / "players.csv", index=False)

    ps_df = explode_playstyles(pd.DataFrame(ps_raw))
    ps_df.to_csv(OUT / "player_playstyles.csv", index=False)

    manifest = {
        "dataset": "FC26 real foundation (canonical)",
        "game_version": GAME_VERSION,
        "generated_utc": str(date.today()),
        "generator": "scripts/build_foundation.py",
        "source": {
            "source_id": SOURCE_ID,
            "carrier": "Kaggle dataset (Tier-3 carrier of Tier-1 official EA field values)",
            "source_url": SOURCE_URL,
            "upstream_url": UPSTREAM_URL,
            "license": "CC0 1.0 Public Domain",
            "usage_status": "PRODUCTION_DATA",
            "scope": "men's ratings universe (source-documented)",
            "scraped_by_source": "March 2026",
            "retrieved": RETRIEVED,
            "raw_file_sha256": raw_hashes,
        },
        "outputs": {
            "players.csv": {
                "sha256": sha256(OUT / "players.csv"),
                "rows": int(len(players)),
                "columns": len(FOUNDATION_COLUMNS),
            },
            "player_playstyles.csv": {
                "sha256": sha256(OUT / "player_playstyles.csv"),
                "rows": int(len(ps_df)),
                "unique_players": int(ps_df["player_id"].nunique()),
                "unique_playstyles": int(ps_df["playstyle"].nunique()),
                "tier_counts": ps_df["tier"].value_counts().to_dict(),
            },
        },
        "policy_notes": [
            "GK rows: outfield facades/details NULL (combined-file GK facades are mirrors of GK attributes).",
            "Outfield rows: retain EA-published GK attributes (real values; unused for outfield fit).",
            "preferredFoot 1->Right 2->Left (SUPPORTED mapping, verified vs known players).",
            "Empty source values remain NULL — never coerced to 0.",
            "gender='male' is a source-stated scope fact, not an inference per row.",
        ],
    }
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest["outputs"], indent=2))
    print("Foundation built OK:", OUT)


if __name__ == "__main__":
    main()
