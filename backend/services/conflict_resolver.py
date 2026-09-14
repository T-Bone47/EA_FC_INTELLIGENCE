"""Source conflict resolution (§11).

When sources disagree on a field, the conflict is RECORDED, never silently
overwritten. Resolution prefers the source that is canonical for that specific
field, then authority tier, then recency.

Default authority order:
    Official EA > Authorized/Licensed > Established community DB
    > Historical dataset > Community discussion
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from backend.domain.evidence_model import ConflictRecord, SourceRecord


@dataclass
class Claim_:
    source: SourceRecord
    value: Any
    observed_at: Optional[datetime] = None


@dataclass
class Resolution:
    winner: Optional[Claim_]
    conflict: Optional[ConflictRecord]
    reason: str
    exceptions_note: Optional[str] = None


class ConflictResolver:
    def __init__(self, sources: list[SourceRecord]):
        self.sources = {s.source_id: s for s in sources}

    def _is_canonical_for(self, src: SourceRecord, field_name: str) -> bool:
        return field_name in src.canonical_fields

    def resolve(self, entity_type: str, entity_id: str, field_name: str,
                claims: list[Claim_], game_version: Optional[str] = None) -> Resolution:
        usable = [c for c in claims if c.source.production_permitted
                  or c.source.usage_status.value == "PUBLIC_REFERENCE"]
        if not usable:
            return Resolution(None, None,
                              "no production-permitted claims for this field")

        distinct = {(str(c.value).strip().lower(), c.source.source_id) for c in usable}
        values = {v for v, _ in distinct}
        if len(values) <= 1:
            best = self._rank(usable, field_name)[0]
            return Resolution(best, None, "sources agree (or single claim)")

        ranked = self._rank(usable, field_name)
        winner = ranked[0]
        runner_up = ranked[1]
        conflict = ConflictRecord(
            entity_type=entity_type, entity_id=entity_id, field_name=field_name,
            value_a=winner.value, source_a=winner.source.source_id,
            value_b=runner_up.value, source_b=runner_up.source.source_id,
            game_version=game_version,
            resolution="SOURCE_A_WINS",
            resolution_note=(
                f"field-authority ranking: {winner.source.source_id} "
                f"(canonical={self._is_canonical_for(winner.source, field_name)}, "
                f"tier={winner.source.authority_tier}) beats "
                f"{runner_up.source.source_id} "
                f"(tier={runner_up.source.authority_tier})"),
        )
        return Resolution(winner, conflict, conflict.resolution_note)

    def _rank(self, claims: list[Claim_], field_name: str) -> list[Claim_]:
        def key(c: Claim_):
            s = c.source
            return (
                0 if self._is_canonical_for(s, field_name) else 1,  # field authority first
                s.authority_tier,                                   # then tier (1 = highest)
                -(c.observed_at.timestamp() if c.observed_at else 0),  # then recency
                s.source_id,                                        # deterministic tiebreak
            )
        return sorted(claims, key=key)
