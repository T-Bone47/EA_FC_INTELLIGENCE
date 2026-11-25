"""Pinned owner-supplied observations. Nothing in this module publishes catalogue data."""
from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zipfile import ZipFile

from backend.ingestion.ea_ratings_csv_adapter import (
    ATTRIBUTE_COLUMN_MAP, EXPECTED_COLUMNS, FACADE_COLUMNS, FIELD_COLUMN_MAP, parse_playstyles,
)
from backend.ingestion.fc27_research_profile import KAGGLE_URL, POSITION_VOCABULARY, SOURCE_ID

OCTOBER = tuple("""base_id stats_id first_name last_name nation_name league_name club_name full_name common_name
position position_alt position_alt_2 position_alt_3 rating height acceleration aggression agility positioning
balance ball_control composure crossing curve dribbling finishing free_kick_accuracy gk_diving gk_handling
gk_kicking gk_one_on_one gk_positioning gk_reflexes heading interceptions jumping long_passing long_shots marking
penalties potential reactions short_passing shot_power sliding_tackle sprint_speed stamina standing_tackle
strength def_awareness vision volleys ball_skills shooting_skills set_pieces_skills passing_skills aerial_skills
defending_skills physical_mobility physical_power growth pac sho pas dri def phy skill_moves weak_foot foot accelerate""".split())
ITEMS = tuple("""eaId player_name full_name overall rarity positions nation league club age height weight
preferred_foot weak_foot skill_moves accelerate_type body_type face_pace face_shooting face_passing face_dribbling
face_defending face_physicality playstyles_plus playstyles_base fc_iq_roles stat_acceleration stat_sprint_speed
stat_positioning stat_finishing stat_shot_power stat_long_shots stat_volleys stat_penalties stat_vision
stat_crossing stat_free_kick_accuracy stat_short_passing stat_long_passing stat_curve stat_dribbling stat_agility
stat_balance stat_reactions stat_ball_control stat_composure stat_interceptions stat_heading_accuracy
stat_defensive_awareness stat_standing_tackle stat_sliding_tackle stat_jumping stat_stamina stat_strength
stat_aggression""".split())
ALT = ("position_alt", "position_alt_2", "position_alt_3")
PLAYER_FIELDS = {**FIELD_COLUMN_MAP, **ATTRIBUTE_COLUMN_MAP, **{key: key for key in FACADE_COLUMNS}}
OCTOBER_ATTRS = {k: k for k in OCTOBER if k in ATTRIBUTE_COLUMN_MAP.values()}
OCTOBER_ATTRS.update(dict(zip(("pac", "sho", "pas", "dri", "def", "phy"), FACADE_COLUMNS)))
OCTOBER_ATTRS.update(heading="heading_accuracy", dribbling="dribbling_detail", def_awareness="defensive_awareness")
CARD_ATTRS = {k: k.removeprefix("stat_").removeprefix("face_") for k in ITEMS if k.startswith(("stat_", "face_"))}
CARD_ATTRS["stat_dribbling"] = "dribbling_detail"
COMMON = {"full_name": "full_name", "height": "height_cm", "weak_foot": "weak_foot_stars",
          "skill_moves": "skill_moves_stars"}
OCTOBER_FIELDS = {**COMMON, **OCTOBER_ATTRS, "base_id": "source_base_id", "stats_id": "source_item_id",
                  "rating": "overall_rating", "position": "position_primary", "foot": "preferred_foot",
                  "club_name": "club", "league_name": "league", "nation_name": "nation", "accelerate": "accelerate_type",
                  **{k: "observed_positions" for k in ALT}, **{k: k for k in ("first_name", "last_name", "common_name")}}
CARD_FIELDS = {**COMMON, **CARD_ATTRS, "eaId": "source_item_id", "overall": "overall_rating",
               "positions": "observed_positions", "weight": "weight_kg", "fc_iq_roles": "unverified_editorial_role_fit",
               **{k: k for k in ("player_name", "rarity", "nation", "league", "club", "age", "preferred_foot",
                                  "accelerate_type", "body_type", "playstyles_base", "playstyles_plus")}}


@dataclass(frozen=True)
class Source:
    archive: str
    member: str
    sha: str
    rows: int
    columns: tuple
    key: str
    source_id: str
    name: str
    schema: str
    claimed: str | None = None
    url: str | None = None
    rights: str = "UNKNOWN"


SOURCES = (
    Source("archive (3).zip", "players.csv",
           "e2fe9d848fa21b04f0b76d851a94ad2d44b8a8c695bc202d4e0f1f5843db1264", 19789,
           EXPECTED_COLUMNS, "player_id", SOURCE_ID, "FC27 player ratings v4", "player-ratings-v1",
           "2026-09-12", KAGGLE_URL, "RESEARCH_ONLY"),
    Source("EA_FC_ANALYSIS-main.zip", "EA_FC_ANALYSIS-main/EA_FC_PLAYERS_DATASET_AND_ DASHBOARD/data/players.csv",
           "18ed434e5bb90f9afa72363d14438005c785eb4b8872a64c89c75bb38e14e911", 19789,
           EXPECTED_COLUMNS, "player_id", "ea_fc_analysis_fc27", "EA FC Analysis snapshot copy",
           "player-ratings-v1", "2026-09-12", "https://github.com/LakshmiKanth11/EA_FC_ANALYSIS"),
    Source("archive (4).zip", "fc27-players-2026-10-11.csv",
           "1abaebe45d9ee7448667638c0fa96e8b4f2af710fe608cd0a6ba9b1bb4817eeb", 10762,
           OCTOBER, "stats_id", "owner_fc27_october", "Owner-supplied October item table", "october-item-v1",
           "2026-10-11"),
    Source("archive (5).zip", "fc27_players_database.csv",
           "c472b9b3b9362cc6928ae3e9351b9a84418d396c49734017e03adb231e062ebe", 9962,
           ITEMS, "eaId", "owner_fc27_card_items", "Owner-supplied card item table", "card-item-v1"),
)


def date_value(value):
    if not value:
        return None
    parsed = datetime.strptime(value, "%d-%m-%Y").date() if value[2:3] == "-" else date.fromisoformat(value)
    return parsed.isoformat()


def number(value, low, high):
    if not re.fullmatch(r"[0-9]+(?:\.0+)?", value):
        raise ValueError("Expected an integer observation")
    n = int(value.split(".")[0])
    if not low <= n <= high:
        raise ValueError("Observed value is out of range")
    return n


def read_snapshot(directory: Path, spec: Source):
    path = directory / spec.archive
    with ZipFile(path) as archive:
        if archive.testzip() or archive.namelist().count(spec.member) != 1:
            raise ValueError(f"Invalid ZIP or missing/duplicate member: {spec.archive}")
        raw = archive.read(spec.member)
    if hashlib.sha256(raw).hexdigest() != spec.sha:
        raise ValueError(f"Hash mismatch: {spec.archive}")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
    if tuple(reader.fieldnames or ()) != spec.columns:
        raise ValueError(f"Schema mismatch: {spec.archive}")
    rows = list(reader)
    if len(rows) != spec.rows or any(None in r or None in r.values() for r in rows):
        raise ValueError(f"Incorrect row count or malformed rows: {spec.archive}")
    ids = [row[spec.key] for row in rows]
    if len(set(ids)) != len(rows) or any(key != str(number(key, 1, 2**63 - 1)) for key in ids):
        raise ValueError(f"Duplicate or invalid source key: {spec.archive}")
    return hashlib.sha256(path.read_bytes()).hexdigest(), rows


def player_index(rows):
    normalized = {}
    for row in rows:
        claimed = date_value(row["snapshot_date"])
        if row["edition"].casefold() != "fc27" or claimed != "2026-09-12":
            raise ValueError("Unexpected version or snapshot date")
        if row["position"] not in POSITION_VOCABULARY:
            raise ValueError("Unrecognized player position")
        for key in ("overall_rating", *ATTRIBUTE_COLUMN_MAP, *FACADE_COLUMNS):
            if row[key]:
                number(row[key], 1, 99)
        normalized[row["player_id"]] = {**row, "snapshot_date": claimed, "birthdate": date_value(row["birthdate"])}
    return normalized


def normalize_item(row, *, october):
    mapping, attrs = (OCTOBER_FIELDS, OCTOBER_ATTRS) if october else (CARD_FIELDS, CARD_ATTRS)
    data = {target: row[source] or None for source, target in mapping.items() if source not in attrs and source not in ALT}
    primary = [row["position"], *(row[k] for k in ALT)] if october else row["positions"].replace(",", " ").split()
    positions = [p for p in dict.fromkeys(primary) if p in POSITION_VOCABULARY]
    if positions and positions[0] == "GK":
        positions = ["GK"]
    issues = [{"field": "positions", "value": p} for p in dict.fromkeys(primary) if p and p not in positions]
    data["observed_positions"] = positions
    data["position_primary"] = positions[0] if positions else None
    data["unmapped"] = {k: v or None for k, v in row.items() if k not in mapping}
    data["attributes"] = {}
    for source, target in attrs.items():
        value = row[source]
        if positions == ["GK"] and (target in FACADE_COLUMNS or not october):
            data["unmapped"][source] = value or None
            continue
        try:
            data["attributes"][target] = number(value, 1, 99) if value else None
        except ValueError:
            data["attributes"][target] = None
            issues.append({"field": source, "reason": "invalid rating"})
    data["overall_rating"] = number(row["rating" if october else "overall"], 1, 99)
    if october:
        number(row["base_id"], 1, 2**63 - 1)
    for field, unit, low, high in (("height_cm", "cm", 100, 250), ("weight_kg", "kg", 30, 220),
                                   ("weak_foot_stars", "", 1, 5), ("skill_moves_stars", "", 1, 5), ("age", "", 14, 75)):
        if value := data.get(field):
            match = re.fullmatch(r"([0-9]+)(?:" + unit + r" \([^)]*\))?" if unit else r"([0-9]+)", value)
            try:
                data[field] = number(match[1], low, high) if match else None
            except ValueError:
                data[field] = None
            if data[field] is None:
                issues.append({"field": field, "reason": "invalid observation"})
    if data.get("preferred_foot") not in {None, "Left", "Right"}:
        data["preferred_foot"] = None
        issues.append({"field": "preferred_foot", "reason": "unknown vocabulary"})
    if not october:
        base, _, base_issues = parse_playstyles(row["playstyles_base"])
        plus, marked, plus_issues = parse_playstyles(row["playstyles_plus"])
        plus = plus + marked
        data["playstyles"] = {"base": [p for p in base if p not in plus], "plus": plus}
        data["official_role_eligibility"] = None
        data["role_observation_kind"] = "EDITORIAL_ROLE_FIT_UNVERIFIED" if row["fc_iq_roles"] else None
        issues.extend(base_issues + plus_issues)
    data["issues"] = issues
    return data


def name_key(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value).casefold() if c.isalnum())


def crosswalk(players, alternate, cards):
    index = {row["stats_id"]: row for row in alternate}
    for card in cards:
        item_id = card["eaId"]
        item = index.get(item_id)
        direct = players.get(item_id)
        base_id = item["base_id"] if item else None
        same_rating = bool(item and card["overall"] == item["rating"])
        conflict = bool(direct and card["overall"] != direct["overall_rating"])
        name = name_key(card["full_name"])
        same_name = bool(item and name and name == name_key(item["full_name"]))
        if conflict or (item and not same_rating):
            status = "CONFLICTED"
        elif item and base_id in players and same_name:
            status = "PROVISIONAL"
        elif item or direct:
            status = "AMBIGUOUS"
        else:
            status = "UNMATCHED"
        yield {"source_item_id": item_id, "status": status,
               "alternate_stats_id": item["stats_id"] if item else None, "candidate_base_id": base_id,
               "item_rating_agrees": same_rating, "direct_player_id_rating_conflict": conflict,
               "names_agree": same_name, "rarity": card["rarity"],
               "item_rating": int(card["overall"]), "direct_rating": int(direct["overall_rating"]) if direct else None,
               "item_positions": card["positions"], "alternate_position": item["position"] if item else None,
               "club_agrees": bool(item and card["club"] and name_key(card["club"]) == name_key(item["club_name"])),
               "league_agrees": bool(item and card["league"] and name_key(card["league"]) == name_key(item["league_name"]))}


def audit(directory: Path, received: date):
    files = [read_snapshot(directory, source) for source in SOURCES]
    players = player_index(files[0][1])
    if players != player_index(files[1][1]):
        raise ValueError("Player copies differ after date normalization")
    october, items = files[2][1], files[3][1]
    reviews = list(crosswalk(players, october, items))
    counts = {"distinct_csv_tables": 3, "duplicate_player_rows": len(players),
              "player_divisions": dict(Counter(r["gender"] for r in players.values())),
              "goalkeepers": sum(r["position"] == "GK" for r in players.values()),
              "october_distinct_base_ids": len({r["base_id"] for r in october}),
              "october_distinct_item_ids": len(october),
              "october_item_differs_from_base": sum(r["base_id"] != r["stats_id"] for r in october),
              "matched_item_ids": sum(r["alternate_stats_id"] is not None for r in reviews),
              "matched_item_ratings": sum(r["item_rating_agrees"] for r in reviews),
              "direct_id_conflicts": sum(r["direct_player_id_rating_conflict"] for r in reviews),
              "identity_status": dict(Counter(r["status"] for r in reviews)),
              "rarities": dict(Counter(r["rarity"] for r in items))}
    expected = {"goalkeepers": 2204, "october_distinct_base_ids": 9907, "october_item_differs_from_base": 880,
                "matched_item_ids": 7698, "matched_item_ratings": 7698, "direct_id_conflicts": 14,
                "player_divisions": {"Men's Football": 17849, "Women's Football": 1940}}
    if any(counts[key] != value for key, value in expected.items()):
        raise ValueError("Source comparison differs from audit baseline")
    manifest, missing, observations = [], {}, {}
    for index, (source, (archive_hash, rows)) in enumerate(zip(SOURCES, files)):
        sid = "fc27-" + source.sha
        manifest.append({"snapshot_id": sid, "source_id": source.source_id, "source_name": source.name,
            "source_url": source.url, "game_version": "FC27", "claimed_snapshot_date": source.claimed,
            "acquisition_date": received.isoformat(), "sha256": source.sha, "archive_sha256": archive_hash,
            "schema_version": source.schema, "row_count": len(rows), "field_count": len(source.columns),
            "source_rights_status": source.rights, "production_reuse_scope": "NONE",
            "raw_file_path": f"{source.archive}::{source.member}", "validation_status": "PASS",
            "ingestion_status": ("EXISTING_RESEARCH", "DUPLICATE_EVIDENCE", "STAGING_ONLY", "STAGING_ONLY")[index],
            "duplicate_of": manifest[0]["snapshot_id"] if index == 1 else None,
            "approval_evidence_id": "phase22-local-research" if index == 0 else None})
        missing[source.source_id] = {c: sum(not row[c].strip() for row in rows) for c in source.columns}
        if index >= 2:
            observations[sid] = [(row[source.key], n, row, normalize_item(row, october=index == 2),
                                  reviews[n - 2] if index == 3 else None) for n, row in enumerate(rows, 2)]
    return manifest, missing, observations, reviews, counts
