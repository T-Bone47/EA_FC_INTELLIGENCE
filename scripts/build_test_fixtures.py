#!/usr/bin/env python3
"""
Build clearly-labelled SYNTHETIC test fixtures (never production data):

  data/fixtures/fictional_ut_cards.csv      63 synthetic UT cards
                                            (60 valid + 3 deliberately invalid)
                                            rarities: gold 32 / silver 20 / totw 7 / bronze 4
  data/real_player_identities.csv           20 real-world identity facts used by
                                            identity-resolution tests; 19 unambiguous,
                                            1 ambiguous 'Ronaldo' case (REVIEW_REQUIRED)

Identity facts are taken from the FC26 foundation (EA-published real-world facts:
name, nationality, DOB, position) — no fabricated identities.
"""
from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "data" / "fixtures"
FIX.mkdir(parents=True, exist_ok=True)
FOUNDATION = ROOT / "data" / "fc26_real_foundation" / "players.csv"

# ---------------------------------------------------------------- synthetic cards
POSITIONS = ["ST", "LW", "RW", "CAM", "CM", "CDM", "LM", "RM", "LB", "RB", "CB", "GK"]
PLAYSTYLES = [
    "Finesse Shot", "Power Shot", "Technical", "First Touch", "Quick Step", "Rapid",
    "Incisive Pass", "Pinged Pass", "Tiki Taka", "Whipped Pass", "Jockey", "Anticipate",
    "Intercept", "Block", "Bruiser", "Slide Tackle", "Aerial Fortress", "Acrobatic",
    "Relentless", "Press Proven", "Trickster", "Inventive", "Enforcer", "Dead Ball",
]
RARITY_PLAN = (["gold"] * 32) + (["silver"] * 20) + (["totw"] * 7) + (["bronze"] * 4)
RATING_BAND = {"gold": (75, 89), "silver": (65, 74), "bronze": (55, 64), "totw": (80, 91)}

rng = random.Random(26093)  # deterministic fixtures


def make_cards() -> pd.DataFrame:
    rows = []
    for i, rarity in enumerate(RARITY_PLAN):
        lo, hi = RATING_BAND[rarity]
        pos = POSITIONS[i % len(POSITIONS)]
        base = rng.randint(lo, hi)
        n_ps = rng.choice([1, 2, 2, 3])
        ps = rng.sample(PLAYSTYLES, n_ps)
        psp = [ps[0]] if (rarity in ("gold", "totw") and rng.random() < 0.35) else []
        rows.append({
            "card_id": f"synth-fc26-{i+1:03d}",
            "source_card_id": f"SYNTH-{i+1:04d}",
            "source": "SYNTHETIC_TEST",
            "game_version": "FC26",
            "data_status": "SYNTHETIC_TEST",
            "player_name": f"Fixture Player {i+1:02d}",
            "position": pos,
            "rarity": rarity,
            "overall_rating": base,
            "pace": max(30, min(99, base + rng.randint(-8, 8))),
            "shooting": max(20, min(99, base + rng.randint(-10, 8))),
            "passing": max(20, min(99, base + rng.randint(-10, 8))),
            "dribbling": max(20, min(99, base + rng.randint(-8, 8))),
            "defending": max(15, min(99, base + rng.randint(-12, 6))),
            "physicality": max(25, min(99, base + rng.randint(-8, 8))),
            "playstyles": ",".join(ps),
            "playstyles_plus": ",".join(psp),
            "price_coins": rng.choice([800, 1200, 2400, 5200, 11000, 24000, 58000]),
        })

    # 3 deliberately invalid cases (validation-failure fixtures, documented in handoff)
    # rarities intentionally untouched so the documented distribution
    # (gold 32 / silver 20 / totw 7 / bronze 4) is preserved.
    rows[0].update(player_name="Broken Rating Case", overall_rating="NOT_A_NUMBER",
                   card_id="synth-fc26-invalid-001")
    rows[1].update(player_name="Missing Rating Case", overall_rating=None,
                   card_id="synth-fc26-invalid-002")
    rows[2].update(player_name="Too Many Plus Case",
                   playstyles="Finesse Shot,Power Shot,Technical",
                   playstyles_plus="Finesse Shot,Power Shot",  # exceeds FC26 cap of 1
                   card_id="synth-fc26-invalid-003")

    df = pd.DataFrame(rows)
    df.to_csv(FIX / "fictional_ut_cards.csv", index=False)
    return df


# ---------------------------------------------------------------- identity fixture
IDENTITY_QUERIES = [
    # (full_name as real-world identity fact, expected resolution)
    ("Lionel Messi", "unique"),
    ("Mohamed Salah", "unique"),
    ("Kevin De Bruyne", "unique"),
    ("Harry Kane", "unique"),
    ("Erling Haaland", "unique"),
    ("Kylian Mbappé", "unique"),
    ("Virgil van Dijk", "unique"),
    ("Jude Bellingham", "unique"),
    ("Luka Modrić", "unique"),
    ("Heung Min Son", "unique"),
    ("Gianluigi Donnarumma", "unique"),
    ("Alisson Ramses Becker", "unique"),
    ("Thibaut Courtois", "unique"),
    ("Jan Oblak", "unique"),
    ("Ousmane Dembélé", "unique"),
    ("Vinícius José de Oliveira Júnior", "unique"),
    ("Robert Lewandowski", "check"),
    ("Bernardo Mota Carvalho e Silva", "check"),  # EA-registered name (name-variant case)
    ("Phil Foden", "check"),
    # The documented ambiguous case: real-world name 'Cristiano Ronaldo' does not
    # exactly match the EA-registered 'C. Ronaldo dos Santos Aveiro', and the
    # 'ronaldo' token overlaps multiple distinct players (Ronaldo Martínez,
    # Ronaldo Dejesús, Ronaldo Deaconu, Fábio Ronaldo Costa Conceição).
    # Conservative policy => REVIEW_REQUIRED, never auto-merged (§38).
    ("Cristiano Ronaldo", "review"),
]
# Real-world identity facts for the non-exact case (public knowledge, matches
# the foundation's EA-published facts for C. Ronaldo dos Santos Aveiro).
MANUAL_FACTS = {
    "Cristiano Ronaldo": ("Portugal", "1985-02-05", "ST"),
}


def make_identities() -> pd.DataFrame:
    players = pd.read_csv(FOUNDATION)
    players["full"] = (players["first_name"].fillna("") + " " + players["last_name"].fillna("")).str.strip()
    rows = []
    for i, (name, _) in enumerate(IDENTITY_QUERIES):
        m = players[players["full"] == name]
        if name in MANUAL_FACTS:
            nat, dob, pos = MANUAL_FACTS[name]
            rows.append({"id": i + 1, "full_name": name, "nationality": nat,
                         "date_of_birth": dob, "position": pos})
        elif len(m) == 1:
            r = m.iloc[0]
            rows.append({"id": i + 1, "full_name": name, "nationality": r["nation"],
                         "date_of_birth": r["date_of_birth"], "position": r["position_primary"]})
        else:
            print(f"  WARN identity not found in foundation: {name}")
            rows.append({"id": i + 1, "full_name": name, "nationality": None,
                         "date_of_birth": None, "position": None})
    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "data" / "real_player_identities.csv", index=False)
    return df


if __name__ == "__main__":
    cards = make_cards()
    print(f"fictional_ut_cards.csv: {len(cards)} rows")
    print("rarities:", cards["rarity"].value_counts().to_dict())
    ids = make_identities()
    print(f"real_player_identities.csv: {len(ids)} rows")
    missing = ids[ids["nationality"].isna() & (ids["full_name"] != "Ronaldo")]
    print("unresolved identities (will be checked):", missing["full_name"].tolist())
