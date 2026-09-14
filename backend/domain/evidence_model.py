"""Evidence, confidence and provenance domain model.

Evidence classes (from community/official research policy):
    FACT                  — directly published by an authoritative source
    SUPPORTED             — corroborated by >=2 independent observations
    COMMUNITY_CONSENSUS   — widespread community agreement, not ground truth
    INFERENCE             — derived by deterministic logic from evidence
    HYPOTHESIS            — plausible, unverified
    UNKNOWN               — no evidence available

Community opinion must never be promoted into canonical ratings; the class
travels with every claim so downstream consumers can weight it.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class EvidenceClass(str, Enum):
    FACT = "FACT"
    SUPPORTED = "SUPPORTED"
    COMMUNITY_CONSENSUS = "COMMUNITY_CONSENSUS"
    INFERENCE = "INFERENCE"
    HYPOTHESIS = "HYPOTHESIS"
    UNKNOWN = "UNKNOWN"


# Base trust applied when aggregating confidence from evidence.
EVIDENCE_TRUST: dict[EvidenceClass, float] = {
    EvidenceClass.FACT: 1.0,
    EvidenceClass.SUPPORTED: 0.9,
    EvidenceClass.COMMUNITY_CONSENSUS: 0.55,
    EvidenceClass.INFERENCE: 0.6,
    EvidenceClass.HYPOTHESIS: 0.25,
    EvidenceClass.UNKNOWN: 0.0,
}


class UsageStatus(str, Enum):
    OFFICIAL = "OFFICIAL"
    AUTHORIZED = "AUTHORIZED"
    LICENSED = "LICENSED"
    PUBLIC_REFERENCE = "PUBLIC_REFERENCE"
    RESEARCH_ONLY = "RESEARCH_ONLY"
    SYNTHETIC_TEST = "SYNTHETIC_TEST"
    UNKNOWN = "UNKNOWN"
    NOT_PERMITTED = "NOT_PERMITTED"


# Only these may feed production data without explicit project/legal approval.
PRODUCTION_PERMITTED = {UsageStatus.OFFICIAL, UsageStatus.AUTHORIZED, UsageStatus.LICENSED}


@dataclass
class SourceRecord:
    """Provenance for a data source. Persisted in source_registry."""
    source_id: str
    name: str
    source_type: str
    authority_tier: int
    url: Optional[str] = None
    license: Optional[str] = None
    usage_status: UsageStatus = UsageStatus.UNKNOWN
    legal_gate: str = "REQUIRED"
    canonical_fields: list[str] = field(default_factory=list)
    notes: Optional[str] = None

    @property
    def production_permitted(self) -> bool:
        return self.usage_status in PRODUCTION_PERMITTED

    @property
    def fetch_permitted(self) -> bool:
        """Runtime legal gate: blocked until clearance state is present."""
        return self.legal_gate in ("CLEARED", "NOT_REQUIRED")


@dataclass
class Observation:
    """A single retrieval event from a source."""
    source_id: str
    entity_type: str
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    snapshot_date: Optional[str] = None
    game_version: Optional[str] = None
    entity_source_id: Optional[str] = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    retrieval_context: Optional[str] = None


@dataclass
class Evidence:
    statement: str
    evidence_class: EvidenceClass
    source_id: Optional[str] = None
    url: Optional[str] = None
    confidence: Optional[float] = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)

    def trust(self) -> float:
        base = EVIDENCE_TRUST[self.evidence_class]
        if self.confidence is not None:
            return base * max(0.0, min(1.0, self.confidence))
        return base


@dataclass
class ConflictRecord:
    """Sources disagreeing on a field. Never silently overwritten."""
    entity_type: str
    entity_id: str
    field_name: str
    value_a: Any
    source_a: str
    value_b: Any
    source_b: str
    game_version: Optional[str] = None
    resolution: str = "UNRESOLVED"
    resolution_note: Optional[str] = None
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def values_agree(self) -> bool:
        return str(self.value_a).strip().lower() == str(self.value_b).strip().lower()
