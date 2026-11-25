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

# FC26_CONFLICT_RESOLUTION_SPEC.md S5. Detail attributes/OVR/facades default
# to 0 tolerance (integers -- 91 != 92 is a real disagreement, not noise).
# Only fields that are genuinely time-varying get a nonzero tolerance.
FIELD_TOLERANCE: dict[str, float] = {
    "price_coins": 0.10,   # +/-10%, fractional
}


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

        # Numeric values within a field's declared tolerance are not a real
        # disagreement (e.g. two price observations minutes apart).
        tol = FIELD_TOLERANCE.get(field_name)
        if tol is not None and self._within_tolerance(winner.value, runner_up.value, tol):
            conflict = ConflictRecord(
                entity_type=entity_type, entity_id=entity_id, field_name=field_name,
                value_a=winner.value, source_a=winner.source.source_id,
                value_b=runner_up.value, source_b=runner_up.source.source_id,
                game_version=game_version, resolution="RESOLVED_TOLERANCE",
                resolution_note=(f"values within {tol:.0%} tolerance for {field_name}; "
                                  f"{winner.source.source_id} used as higher-authority"),
            )
            return Resolution(winner, conflict, conflict.resolution_note)

        # FIX (V2-defect: conflict_resolver could never emit UNRESOLVED, see
        # FC26_CONFLICT_RESOLUTION_SPEC.md S1 / IMPLEMENTATION_BASELINE.md).
        # If the top two claims tie on every ranking key EXCEPT the
        # deterministic source_id tiebreak (field authority, tier, recency
        # all equal) and their values genuinely differ, this is not a real
        # win for the alphabetically-first source_id -- it is a deadlock.
        # The old code always returned SOURCE_A_WINS here, silently settling
        # ties alphabetically and reporting them as authority-based wins.
        if self._tied_ignoring_source_id(winner, runner_up, field_name):
            conflict = ConflictRecord(
                entity_type=entity_type, entity_id=entity_id, field_name=field_name,
                value_a=winner.value, source_a=winner.source.source_id,
                value_b=runner_up.value, source_b=runner_up.source.source_id,
                game_version=game_version, resolution="UNRESOLVED",
                resolution_note=(
                    f"{winner.source.source_id} and {runner_up.source.source_id} "
                    f"tie on field-authority, tier and recency but disagree on "
                    f"{field_name} ({winner.value!r} vs {runner_up.value!r}); "
                    f"value is UNKNOWN rather than arbitrarily choosing one"),
            )
            return Resolution(None, conflict, conflict.resolution_note)

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

    @staticmethod
    def _within_tolerance(a: Any, b: Any, tol: float) -> bool:
        try:
            fa, fb = float(a), float(b)
        except (TypeError, ValueError):
            return False
        if fa == 0 and fb == 0:
            return True
        denom = max(abs(fa), abs(fb)) or 1.0
        return abs(fa - fb) / denom <= tol

    def _tied_ignoring_source_id(self, winner: "Claim_", runner_up: "Claim_",
                                  field_name: str) -> bool:
        def key3(c: Claim_):
            s = c.source
            return (
                0 if self._is_canonical_for(s, field_name) else 1,
                s.authority_tier,
                round(c.observed_at.timestamp(), 0) if c.observed_at else 0,
            )
        return key3(winner) == key3(runner_up)

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
