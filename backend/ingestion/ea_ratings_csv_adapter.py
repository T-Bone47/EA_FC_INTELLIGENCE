"""Adapter for CSV exports of EA's public ratings API (Phase 22).

Written for the FC27 Kaggle snapshot `mikedpad/ea-sports-fc27-player-ratings`
(players.csv, 60 columns, snapshot 2026-09-12). The layout differs from the
FC26 foundation CSV that LocalFileAdapter reads, so it gets its own adapter
rather than a branch inside that one:

  * detailed attributes carry EA group prefixes (`attacking_crossing`, ...)
    and are mapped to canonical names by an explicit, closed table;
  * `alternate_positions` is space separated;
  * PlayStyles live in one comma-separated column; a trailing `+` marks a
    PlayStyle+ and the source wording is preserved otherwise;
  * `edition` ("fc27") is the per-row game-version marker.

Fail-closed rules:
  * the header must be exactly the expected 60 columns -- an added, removed
    or renamed column stops the run instead of being silently dropped;
  * every row's edition must equal the adapter's game version, otherwise the
    whole file is refused (version wall, same policy as LocalFileAdapter);
  * for goalkeepers the six outfield-named face-stat columns carry EA's GK
    face stats (measured: pace == goalkeeping_diving, shooting ==
    goalkeeping_handling, passing == goalkeeping_kicking, dribbling ==
    goalkeeping_reflexes, physicality == goalkeeping_positioning on 2,204 of
    2,204 GK rows and on 0 of 17,585 outfield rows; EA's own ratings page
    shows GKs under the same PAC..PHY headers). They are NOT outfield
    facades, so they are not mapped to pace..physicality. The raw values are
    kept in `extras['unmapped_source_values']` for the observation record.
"""
from __future__ import annotations

import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from backend.domain.evidence_model import SourceRecord
from backend.ingestion.adapter import (
    BaseAdapter,
    RawCardRecord,
    RawPlayerRecord,
    RawPlayStyleRecord,
    RawPriceRecord,
    SnapshotMetadata,
)

EXPECTED_COLUMNS: tuple[str, ...] = (
    "player_id", "common_name", "first_name", "last_name", "overall_rating",
    "position", "alternate_positions", "club", "league", "nationality", "gender",
    "preferred_foot", "skill_moves", "weak_foot", "height_cm", "weight_kg",
    "birthdate", "playstyles", "pace", "shooting", "passing", "dribbling",
    "defending", "physicality", "attacking_crossing", "attacking_finishing",
    "attacking_heading_accuracy", "attacking_short_passing", "attacking_volleys",
    "skill_dribbling", "skill_curve", "skill_fk_accuracy", "skill_long_passing",
    "skill_ball_control", "movement_acceleration", "movement_sprint_speed",
    "movement_agility", "movement_reactions", "movement_balance",
    "power_shot_power", "power_jumping", "power_stamina", "power_strength",
    "power_long_shots", "mentality_aggression", "mentality_interceptions",
    "mentality_positioning", "mentality_vision", "mentality_penalties",
    "mentality_composure", "defending_awareness", "defending_standing_tackle",
    "defending_sliding_tackle", "goalkeeping_diving", "goalkeeping_handling",
    "goalkeeping_kicking", "goalkeeping_positioning", "goalkeeping_reflexes",
    "edition", "snapshot_date",
)

FACADE_COLUMNS: tuple[str, ...] = (
    "pace", "shooting", "passing", "dribbling", "defending", "physicality")

# Source column -> canonical attribute. Closed table; every entry was checked
# against the source README column descriptions and against cross-version
# value agreement for the 12,026 EA ids present in both FC26 and FC27
# (docs/FC26_FC27_ATTRIBUTE_SCHEMA_DIFF.md).
ATTRIBUTE_COLUMN_MAP: dict[str, str] = {
    "attacking_crossing": "crossing",
    "attacking_finishing": "finishing",
    "attacking_heading_accuracy": "heading_accuracy",
    "attacking_short_passing": "short_passing",
    "attacking_volleys": "volleys",
    "skill_dribbling": "dribbling_detail",
    "skill_curve": "curve",
    "skill_fk_accuracy": "free_kick_accuracy",
    "skill_long_passing": "long_passing",
    "skill_ball_control": "ball_control",
    "movement_acceleration": "acceleration",
    "movement_sprint_speed": "sprint_speed",
    "movement_agility": "agility",
    "movement_reactions": "reactions",
    "movement_balance": "balance",
    "power_shot_power": "shot_power",
    "power_jumping": "jumping",
    "power_stamina": "stamina",
    "power_strength": "strength",
    "power_long_shots": "long_shots",
    "mentality_aggression": "aggression",
    "mentality_interceptions": "interceptions",
    "mentality_positioning": "positioning",
    "mentality_vision": "vision",
    "mentality_penalties": "penalties",
    "mentality_composure": "composure",
    "defending_awareness": "defensive_awareness",
    "defending_standing_tackle": "standing_tackle",
    "defending_sliding_tackle": "sliding_tackle",
    "goalkeeping_diving": "gk_diving",
    "goalkeeping_handling": "gk_handling",
    "goalkeeping_kicking": "gk_kicking",
    "goalkeeping_positioning": "gk_positioning",
    "goalkeeping_reflexes": "gk_reflexes",
}

# Non-attribute source columns -> canonical GamePlayer field (or the
# metadata role they play). `edition`/`snapshot_date` are validated and kept
# on the observation, not stored per player.
FIELD_COLUMN_MAP: dict[str, str] = {
    "player_id": "source_player_id",
    "common_name": "common_name",
    "first_name": "first_name",
    "last_name": "last_name",
    "overall_rating": "overall_rating",
    "position": "position_primary",
    "alternate_positions": "secondary_positions",
    "club": "club",
    "league": "league",
    "nationality": "nation",
    "gender": "gender",
    "preferred_foot": "preferred_foot",
    "skill_moves": "skill_moves_stars",
    "weak_foot": "weak_foot_stars",
    "height_cm": "height_cm",
    "weight_kg": "weight_kg",
    "birthdate": "date_of_birth",
    "playstyles": "playstyles_base/playstyles_plus",
    "edition": "(game_version marker, validated per row)",
    "snapshot_date": "(observation snapshot_date, validated per row)",
}

GK_POSITION = "GK"


class SourceSchemaMismatch(ValueError):
    """The file's header is not the exact expected column set."""


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_rows(path: Path) -> tuple[list[str], list[dict]]:
    """Header + rows exactly as published (no stripping of internal text)."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        header = list(reader.fieldnames or [])
        rows = [dict(r) for r in reader]
    return header, rows


def check_header(header: list[str]) -> None:
    missing = [c for c in EXPECTED_COLUMNS if c not in header]
    unexpected = [c for c in header if c not in EXPECTED_COLUMNS]
    if missing or unexpected or len(header) != len(EXPECTED_COLUMNS):
        raise SourceSchemaMismatch(
            f"source header does not match the audited 60-column layout: "
            f"missing={missing} unexpected={unexpected} n={len(header)}. "
            "Columns are never silently dropped or guessed -- update the "
            "mapping (and the schema-diff document) deliberately.")


def parse_playstyles(raw: str | None) -> tuple[list[str], list[str], list[str]]:
    """-> (base, plus, issues). Source wording kept verbatim; only the single
    trailing '+' marker is interpreted. Malformed tokens are reported, never
    repaired or guessed."""
    base: list[str] = []
    plus: list[str] = []
    issues: list[str] = []
    if raw is None or raw.strip() == "":
        return base, plus, issues
    for token in raw.split(","):
        t = token.strip()
        if not t:
            issues.append("empty PlayStyle token")
            continue
        if t.endswith("+"):
            name = t[:-1].strip()
            if not name or name.endswith("+"):
                issues.append(f"malformed PlayStyle+ token {t!r}")
                continue
            target = plus
        else:
            name = t
            target = base
        if "+" in name:
            issues.append(f"'+' inside PlayStyle name {t!r}")
            continue
        if name in base or name in plus:
            issues.append(f"duplicate PlayStyle {name!r}")
            continue
        target.append(name)
    return base, plus, issues


_FOOT_VALUES = {"Right", "Left"}
_STAR_VALUES = {"1", "2", "3", "4", "5"}


def _checked(value: str | None, ok: bool, field: str, issues: list[str]) -> str | None:
    """Keep a published value only if it is valid for its canonical column.
    An invalid value becomes NULL (UNKNOWN) and is reported -- never
    corrected to a plausible value."""
    if value is None or ok:
        return value
    issues.append(f"{field}={value!r} invalid; stored as UNKNOWN")
    return None


def _iso_date_ok(value: str | None) -> bool:
    if value is None:
        return True
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


class EARatingsCsvAdapter(BaseAdapter):
    def __init__(self, source: SourceRecord, game_version: str, players_path: Path):
        super().__init__(source, game_version)
        self.players_path = Path(players_path)
        self.expected_edition = str(game_version).strip().lower()
        self.playstyle_issues: dict[str, list[str]] = {}
        self.field_issues: dict[str, list[str]] = {}
        self._rows: list[dict] | None = None

    # ------------------------------------------------------------- source rows
    def source_rows(self) -> list[dict]:
        if self._rows is None:
            header, rows = read_rows(self.players_path)
            check_header(header)
            bad = [r.get("player_id") for r in rows
                   if (r.get("edition") or "").strip().lower() != self.expected_edition]
            if bad:
                raise ValueError(
                    f"game-version contamination: {len(bad)} row(s) (e.g. player_id "
                    f"{bad[:3]}) are not edition {self.expected_edition!r}; the whole "
                    "file is refused, rows are never mixed across versions")
            self._rows = rows
        return self._rows

    # ------------------------------------------------------------- players
    def fetch_players(self) -> list[RawPlayerRecord]:
        self.gate("fetch_players")
        out: list[RawPlayerRecord] = []
        self.field_issues = {}
        for r in self.source_rows():
            pid = (r.get("player_id") or "").strip()
            issues: list[str] = []
            dob = (r.get("birthdate") or "").strip() or None
            dob = _checked(dob, _iso_date_ok(dob), "birthdate", issues)
            foot = (r.get("preferred_foot") or "").strip() or None
            foot = _checked(foot, foot in _FOOT_VALUES, "preferred_foot", issues)
            wf = (r.get("weak_foot") or "").strip() or None
            wf = _checked(wf, wf in _STAR_VALUES, "weak_foot", issues)
            sm = (r.get("skill_moves") or "").strip() or None
            sm = _checked(sm, sm in _STAR_VALUES, "skill_moves", issues)
            if issues:
                self.field_issues[pid] = issues
            is_gk = (r.get("position") or "").strip().upper() == GK_POSITION
            attrs: dict[str, str | None] = {}
            for col, canon in ATTRIBUTE_COLUMN_MAP.items():
                attrs[canon] = (r.get(col) or "").strip() or None
            unmapped: dict[str, str | None] = {}
            for col in FACADE_COLUMNS:
                v = (r.get(col) or "").strip() or None
                if is_gk:
                    unmapped[col] = v          # GK face stat, not an outfield facade
                else:
                    attrs[col] = v
            alternates = " ".join((r.get("alternate_positions") or "").split())
            out.append(RawPlayerRecord(
                source_player_id=pid,
                names={"first": (r.get("first_name") or "").strip() or None,
                       "last": (r.get("last_name") or "").strip() or None,
                       "common": (r.get("common_name") or "").strip() or None},
                nation=(r.get("nationality") or "").strip() or None,
                club=(r.get("club") or "").strip() or None,
                league=(r.get("league") or "").strip() or None,
                position_raw=(r.get("position") or "").strip() or None,
                # canonical separator for normalizer.parse_alternate_positions
                alternate_positions_raw=",".join(alternates.split()) or None,
                overall_rating=(r.get("overall_rating") or "").strip() or None,
                attributes=attrs,
                extras={
                    "game_version": self.game_version,
                    "date_of_birth": dob,
                    "height_cm": (r.get("height_cm") or "").strip() or None,
                    "weight_kg": (r.get("weight_kg") or "").strip() or None,
                    "preferred_foot": foot,
                    "weak_foot_stars": wf,
                    "skill_moves_stars": sm,
                    "gender": (r.get("gender") or "").strip() or None,
                    "position_type": None,       # not published by this source
                    "source_rank": None,         # not published by this source
                    "snapshot_date": (r.get("snapshot_date") or "").strip() or None,
                    "unmapped_source_values": unmapped,
                },
            ))
        return out

    # ------------------------------------------------------------- playstyles
    def fetch_playstyles(self) -> list[RawPlayStyleRecord]:
        """One record per (player, PlayStyle). Players with an empty cell emit
        nothing; the pipeline then marks their PlayStyle data unpublished
        (UNKNOWN), which is the same reading applied to FC26 (D-4)."""
        self.gate("fetch_playstyles")
        out: list[RawPlayStyleRecord] = []
        self.playstyle_issues = {}
        for r in self.source_rows():
            pid = (r.get("player_id") or "").strip()
            base, plus, issues = parse_playstyles(r.get("playstyles"))
            if issues:
                self.playstyle_issues[pid] = issues
            out.extend(RawPlayStyleRecord(pid, n, "base") for n in base)
            out.extend(RawPlayStyleRecord(pid, n, "plus") for n in plus)
        return out

    # ------------------------------------------------------------- no card data
    def fetch_cards(self) -> list[RawCardRecord]:
        self.gate("fetch_cards")
        return []      # base-player ratings only; UT-card scope stays disabled

    def fetch_card(self, source_card_id: str) -> RawCardRecord | None:
        return None

    def fetch_prices(self) -> list[RawPriceRecord]:
        self.gate("fetch_prices")
        return []      # no price data in this source; UNKNOWN stays UNKNOWN

    # ------------------------------------------------------------- metadata
    def get_snapshot_metadata(self) -> SnapshotMetadata:
        rows = self.source_rows()
        dates = sorted({(r.get("snapshot_date") or "").strip() for r in rows})
        return SnapshotMetadata(
            source_id=self.source.source_id,
            game_version=self.game_version,
            retrieved_at=datetime.now(timezone.utc),
            snapshot_date=dates[0] if len(dates) == 1 else None,
            record_counts={"players": len(rows)},
            license=self.source.license,
            notes=f"file={self.players_path.name} sha256={file_sha256(self.players_path)} "
                  f"snapshot_dates={dates}",
        )
