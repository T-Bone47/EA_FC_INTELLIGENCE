"""LocalFileAdapter — reads canonical foundation CSVs and fixture CSVs.

Handles two shapes:
  * foundation players (data/fc26_real_foundation/players.csv + player_playstyles.csv)
  * UT card CSVs (data/fixtures/fictional_ut_cards.csv — SYNTHETIC_TEST only)

The adapter enforces the source legal gate like every other adapter.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.domain.evidence_model import SourceRecord, UsageStatus
from backend.domain.card_model import ALL_ATTRS
from backend.ingestion.adapter import (
    BaseAdapter, RawCardRecord, RawPlayerRecord, RawPlayStyleRecord,
    RawPriceRecord, SnapshotMetadata,
)


def _rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [{k.strip(): (v.strip() if isinstance(v, str) else v)
                 for k, v in row.items() if k} for row in csv.DictReader(f)]


class LocalFileAdapter(BaseAdapter):
    def __init__(self, source: SourceRecord, game_version: str,
                 players_path: Optional[Path] = None,
                 playstyles_path: Optional[Path] = None,
                 cards_path: Optional[Path] = None):
        super().__init__(source, game_version)
        self.players_path = Path(players_path) if players_path else None
        self.playstyles_path = Path(playstyles_path) if playstyles_path else None
        self.cards_path = Path(cards_path) if cards_path else None

    # ------------------------------------------------------------- players
    def fetch_players(self) -> list[RawPlayerRecord]:
        self.gate("fetch_players")
        if self.players_path is None:
            return []
        out = []
        for r in _rows(self.players_path):
            attrs = {k: v for k, v in r.items()
                     if k not in {"player_id", "game_version", "first_name", "last_name",
                                  "common_name", "nation", "club", "league",
                                  "position_primary", "position_type", "date_of_birth",
                                  "preferred_foot", "gender", "alternate_positions",
                                  "source_rank"}}
            gv = r.get("game_version") or self.game_version
            if gv != self.game_version:
                # never mix versions within one ingestion run (§3)
                raise ValueError(
                    f"game-version contamination: row {r.get('player_id')} is {gv} "
                    f"but adapter is bound to {self.game_version}")
            out.append(RawPlayerRecord(
                source_player_id=r["player_id"],
                names={"first": r.get("first_name"), "last": r.get("last_name"),
                       "common": r.get("common_name")},
                nation=r.get("nation") or None,
                club=r.get("club") or None,
                league=r.get("league") or None,
                position_raw=r.get("position_primary") or None,
                alternate_positions_raw=r.get("alternate_positions") or None,
                overall_rating=r.get("overall_rating") or None,
                attributes=attrs,
                extras={
                    "position_type": r.get("position_type") or None,
                    "date_of_birth": r.get("date_of_birth") or None,
                    "height_cm": r.get("height_cm") or None,
                    "weight_kg": r.get("weight_kg") or None,
                    "preferred_foot": r.get("preferred_foot") or None,
                    "weak_foot_stars": r.get("weak_foot_stars") or None,
                    "skill_moves_stars": r.get("skill_moves_stars") or None,
                    "gender": r.get("gender") or None,
                    "source_rank": r.get("source_rank") or None,
                    "game_version": gv,
                },
            ))
        return out

    # ------------------------------------------------------------- playstyles
    def fetch_playstyles(self) -> list[RawPlayStyleRecord]:
        self.gate("fetch_playstyles")
        if self.playstyles_path is None:
            return []
        out = []
        for r in _rows(self.playstyles_path):
            if (r.get("game_version") or self.game_version) != self.game_version:
                raise ValueError("game-version contamination in playstyles file")
            out.append(RawPlayStyleRecord(
                source_player_id=r["player_id"],
                playstyle=r["playstyle"],
                tier=r.get("tier", "base")))
        return out

    # ------------------------------------------------------------- cards
    def fetch_cards(self) -> list[RawCardRecord]:
        self.gate("fetch_cards")
        if self.cards_path is None:
            return []
        out = []
        for r in _rows(self.cards_path):
            gv = r.get("game_version") or self.game_version
            if gv != self.game_version:
                raise ValueError("game-version contamination in cards file")
            out.append(RawCardRecord(
                source_card_id=r.get("source_card_id") or r.get("card_id"),
                card_name=r.get("player_name") or r.get("card_name"),
                position_raw=r.get("position"),
                rarity_raw=r.get("rarity"),
                overall_rating=r.get("overall_rating"),
                attributes={k: r.get(k) for k in ALL_ATTRS
                            if r.get(k) not in (None, "")},
                playstyles_raw=r.get("playstyles"),
                playstyles_plus_raw=r.get("playstyles_plus"),
                price_coins=r.get("price_coins"),
                source_player_ref=(r.get("source_player_id") or r.get("player_ref")),
                extras={"data_status": r.get("data_status"),
                        "card_id": r.get("card_id"),
                        "source": r.get("source"),
                        "game_version": gv,
                        "card_type": r.get("card_type"),
                        "release_group": r.get("release_group"),
                        "release_date": r.get("release_date"),
                        "playstyles_published": r.get("playstyles_published")},
            ))
        return out

    def fetch_card(self, source_card_id: str) -> Optional[RawCardRecord]:
        for c in self.fetch_cards():
            if str(c.source_card_id) == str(source_card_id):
                return c
        return None

    # ------------------------------------------------------------- prices
    def fetch_prices(self) -> list[RawPriceRecord]:
        self.gate("fetch_prices")
        return []   # no local price data; UNKNOWN stays UNKNOWN

    # ------------------------------------------------------------- metadata
    def get_snapshot_metadata(self) -> SnapshotMetadata:
        counts = {}
        if self.players_path and self.players_path.exists():
            counts["players"] = sum(1 for _ in open(self.players_path)) - 1
        if self.playstyles_path and self.playstyles_path.exists():
            counts["playstyles"] = sum(1 for _ in open(self.playstyles_path)) - 1
        if self.cards_path and self.cards_path.exists():
            counts["cards"] = sum(1 for _ in open(self.cards_path)) - 1
        return SnapshotMetadata(
            source_id=self.source.source_id,
            game_version=self.game_version,
            retrieved_at=datetime.now(timezone.utc),
            license=self.source.license,
            record_counts=counts,
            notes=f"local files: players={self.players_path}, "
                  f"playstyles={self.playstyles_path}, cards={self.cards_path}",
        )
