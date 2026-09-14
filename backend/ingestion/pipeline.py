"""Ingestion pipeline orchestration (§46 production data boundary):

    RAW SOURCE DATA -> validated -> normalized -> canonical -> persisted

Stages: fetch (adapter, legal-gated) -> normalize -> validate (reject invalid)
-> identity resolution (ambiguous -> REVIEW_REQUIRED) -> persist (repository
callbacks; idempotent deterministic IDs). Produces an IngestionReport.

The pipeline never fabricates: rejected rows stay rejected, ambiguous
identities stay in review, unknown fields stay None.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional, Protocol

from backend.domain.card_model import GamePlayer, IdentityStatus, UTCard
from backend.domain.evidence_model import SourceRecord
from backend.ingestion.adapter import (
    BaseAdapter, DataSourceAdapter, RawPlayStyleRecord, SnapshotMetadata,
)
from backend.ingestion.data_quality import DataQualityValidator, ValidationResult
from backend.ingestion.identity_resolver import IdentityResolver, IdentityIndex
from backend.ingestion.normalizer import Normalizer


class CanonicalRepository(Protocol):
    def upsert_game_player(self, gp: GamePlayer,
                           playstyles_base: list[str],
                           playstyles_plus: list[str],
                           playstyle_published: bool) -> None: ...
    def upsert_card(self, card: UTCard, version_payload: dict) -> None: ...


@dataclass
class IngestionReport:
    source_id: str
    game_version: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None
    players_fetched: int = 0
    players_persisted: int = 0
    players_rejected: int = 0
    players_review: int = 0
    cards_fetched: int = 0
    cards_persisted: int = 0
    cards_rejected: int = 0
    cards_review: int = 0
    playstyles_attached: int = 0
    identity_resolved: int = 0
    identity_review: int = 0
    identity_unresolved: int = 0
    rejections: list[dict] = field(default_factory=list)
    reviews: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["started_at"] = self.started_at.isoformat()
        d["finished_at"] = self.finished_at.isoformat() if self.finished_at else None
        return d


class IngestionPipeline:
    def __init__(self,
                 adapter: DataSourceAdapter,
                 repository: CanonicalRepository,
                 validator: Optional[DataQualityValidator] = None,
                 identity_index: Optional[IdentityIndex] = None):
        self.adapter = adapter
        self.repository = repository
        self.validator = validator or DataQualityValidator()
        source: SourceRecord = adapter.source  # type: ignore[attr-defined]
        self.normalizer = Normalizer(source.source_id, adapter.game_version)  # type: ignore[attr-defined]
        self.identity = IdentityResolver(identity_index or IdentityIndex())

    # ------------------------------------------------------------------ run
    def run_players(self, attach_playstyles: bool = True) -> IngestionReport:
        src = self.adapter.source
        report = IngestionReport(src.source_id, self.adapter.game_version)

        raw_players = self.adapter.fetch_players()
        report.players_fetched = len(raw_players)

        playstyles_by_player: dict[str, dict[str, list[str]]] = {}
        published_players: set[str] = set()
        if attach_playstyles:
            for ps in self.adapter.fetch_playstyles():
                key = str(ps.source_player_id)
                bucket = playstyles_by_player.setdefault(key, {"base": [], "plus": []})
                if ps.playstyle not in bucket[ps.tier]:
                    bucket[ps.tier].append(ps.playstyle)
                published_players.add(key)
            report.playstyles_attached = sum(
                len(v["base"]) + len(v["plus"]) for v in playstyles_by_player.values())

        for raw in raw_players:
            try:
                gp = self.normalizer.normalize_player(raw)
            except ValueError as e:
                report.players_rejected += 1
                report.rejections.append({"stage": "normalize",
                                          "source_player_id": str(raw.source_player_id),
                                          "reason": str(e)})
                continue

            ps = playstyles_by_player.get(str(raw.source_player_id), {"base": [], "plus": []})
            published = str(raw.source_player_id) in published_players
            gp.playstyles_base = ps["base"]
            gp.playstyles_plus = ps["plus"]
            gp.playstyle_data_published = published

            resolution = self.identity.resolve(gp)
            gp.identity_status = resolution.status
            if resolution.real_player is not None and resolution.status == IdentityStatus.RESOLVED:
                gp.real_player_id = resolution.real_player.id
            if resolution.status == IdentityStatus.RESOLVED:
                report.identity_resolved += 1
            elif resolution.status == IdentityStatus.REVIEW_REQUIRED:
                report.identity_review += 1
            else:
                report.identity_unresolved += 1

            result = self.validator.validate_player(gp)
            if result.rejected:
                gp.data_status = gp.data_status  # canonical object untouched
                report.players_rejected += 1
                report.rejections.append({
                    "stage": "validate", "source_player_id": str(raw.source_player_id),
                    "name": gp.display_name,
                    "reasons": [f"{i.rule}: {i.message}" for i in result.issues
                                if i.severity == "REJECT"]})
                continue
            if result.needs_review or gp.identity_status == IdentityStatus.REVIEW_REQUIRED:
                report.players_review += 1
                report.reviews.append({
                    "source_player_id": str(raw.source_player_id), "name": gp.display_name,
                    "reasons": [f"{i.rule}: {i.message}" for i in result.issues
                                if i.severity == "REVIEW"] +
                               ([f"identity: {resolution.reason}"]
                                if gp.identity_status == IdentityStatus.REVIEW_REQUIRED else [])})

            self.repository.upsert_game_player(gp, ps["base"], ps["plus"], published)
            report.players_persisted += 1

        report.finished_at = datetime.now(timezone.utc)
        return report

    def run_cards(self) -> IngestionReport:
        src = self.adapter.source
        report = IngestionReport(src.source_id, self.adapter.game_version)
        raw_cards = self.adapter.fetch_cards()
        report.cards_fetched = len(raw_cards)
        for raw in raw_cards:
            try:
                card = self.normalizer.normalize_card(raw)
            except ValueError as e:
                report.cards_rejected += 1
                report.rejections.append({"stage": "normalize",
                                          "source_card_id": str(raw.source_card_id),
                                          "reason": str(e)})
                continue
            result = self.validator.validate_card(card)
            if result.rejected:
                report.cards_rejected += 1
                report.rejections.append({
                    "stage": "validate", "source_card_id": card.source_card_id,
                    "name": card.card_name,
                    "reasons": [f"{i.rule}: {i.message}" for i in result.issues
                                if i.severity == "REJECT"]})
                continue
            if result.needs_review:
                report.cards_review += 1
                report.reviews.append({
                    "source_card_id": card.source_card_id, "name": card.card_name,
                    "reasons": [f"{i.rule}: {i.message}" for i in result.issues
                                if i.severity == "REVIEW"]})
            version = self.normalizer.card_version(card)
            self.repository.upsert_card(card, {
                "version_id": str(version.id),
                "content_hash": version.content_hash,
                "attributes": version.attributes,
                "playstyles": version.playstyles,
            })
            report.cards_persisted += 1
        report.finished_at = datetime.now(timezone.utc)
        return report
