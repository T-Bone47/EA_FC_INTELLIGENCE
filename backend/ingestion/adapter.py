"""Provider-neutral data source adapter protocol + raw record shapes.

Raw records are intentionally source-shaped; canonicalization happens in the
normalizer, so the domain layer never knows where data came from.

Legal gate: adapters constructed from a SourceRecord with legal_gate=REQUIRED
and no clearance raise LegalGateError on any fetch operation. No bypass.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Protocol, runtime_checkable

from backend.domain.evidence_model import SourceRecord


class LegalGateError(RuntimeError):
    """Raised when a fetch is attempted on a source without required clearance."""


@dataclass
class RawPlayerRecord:
    """Source-shaped player row (pre-normalization)."""
    source_player_id: Any
    names: dict[str, Any] = field(default_factory=dict)      # first/last/common/display
    nation: Optional[str] = None
    club: Optional[str] = None
    league: Optional[str] = None
    position_raw: Optional[str] = None
    alternate_positions_raw: Optional[str] = None
    overall_rating: Any = None
    attributes: dict[str, Any] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class RawCardRecord:
    source_card_id: Any
    card_name: Optional[str] = None
    position_raw: Optional[str] = None
    rarity_raw: Optional[str] = None
    overall_rating: Any = None
    attributes: dict[str, Any] = field(default_factory=dict)
    playstyles_raw: Optional[str] = None
    playstyles_plus_raw: Optional[str] = None
    price_coins: Any = None
    source_player_ref: Any = None
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class RawPlayStyleRecord:
    source_player_id: Any
    playstyle: str
    tier: str                          # 'base' | 'plus'


@dataclass
class RawPriceRecord:
    source_card_id: Any
    platform: str
    price_coins: Any
    observed_at: Optional[datetime] = None


@dataclass
class SnapshotMetadata:
    source_id: str
    game_version: str
    retrieved_at: datetime
    snapshot_date: Optional[str] = None
    record_counts: dict[str, int] = field(default_factory=dict)
    license: Optional[str] = None
    notes: Optional[str] = None


@runtime_checkable
class DataSourceAdapter(Protocol):
    source: SourceRecord

    def fetch_players(self) -> list[RawPlayerRecord]: ...
    def fetch_cards(self) -> list[RawCardRecord]: ...
    def fetch_card(self, source_card_id: str) -> Optional[RawCardRecord]: ...
    def fetch_playstyles(self) -> list[RawPlayStyleRecord]: ...
    def fetch_prices(self) -> list[RawPriceRecord]: ...
    def get_snapshot_metadata(self) -> SnapshotMetadata: ...


class BaseAdapter:
    """Shared legal-gate enforcement for all adapters."""

    def __init__(self, source: SourceRecord, game_version: str):
        self.source = source
        self.game_version = game_version

    def _assert_gate(self, operation: str) -> None:
        if not self.source.fetch_permitted:
            raise LegalGateError(
                f"source {self.source.source_id!r} is blocked by the legal gate "
                f"(legal_gate={self.source.legal_gate}, usage_status="
                f"{self.source.usage_status.value}). Operation {operation!r} "
                "refused. Clearance must be recorded before any fetch.")

    # convenience for subclasses
    def gate(self, operation: str) -> None:
        self._assert_gate(operation)
