"""FitValue — the missing-data-aware score primitive of engine V2.

A fit component result is never a bare float. It carries:
  * value  — 0.0..1.0 when KNOWN, else None
  * status — KNOWN | UNKNOWN | INSUFFICIENT_EVIDENCE
  * reason / evidence — deterministic, explainable provenance

Policy (§19): unknown means unknown. Missing data is NOT converted into 0,
penalty, False or empty. The engine redistributes unknown component weight
across known components instead of punishing candidates for absent data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class FitStatus(str, Enum):
    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass(frozen=True)
class FitValue:
    value: Optional[float]
    status: FitStatus
    reason: Optional[str] = None
    evidence: tuple[str, ...] = field(default_factory=tuple)

    # ---- constructors -------------------------------------------------------
    @classmethod
    def known(cls, value: float, evidence: tuple[str, ...] = (), reason: Optional[str] = None) -> "FitValue":
        v = max(0.0, min(1.0, float(value)))
        return cls(value=v, status=FitStatus.KNOWN, reason=reason, evidence=tuple(evidence))

    @classmethod
    def unknown(cls, reason: str, evidence: tuple[str, ...] = ()) -> "FitValue":
        """No data exists to evaluate this component; carries no penalty."""
        return cls(value=None, status=FitStatus.UNKNOWN, reason=reason, evidence=tuple(evidence))

    @classmethod
    def insufficient(cls, reason: str, evidence: tuple[str, ...] = ()) -> "FitValue":
        """Data exists but is too partial/unverified to score honestly."""
        return cls(value=None, status=FitStatus.INSUFFICIENT_EVIDENCE,
                   reason=reason, evidence=tuple(evidence))

    # ---- helpers --------------------------------------------------------------
    @property
    def is_known(self) -> bool:
        return self.status == FitStatus.KNOWN and self.value is not None

    def to_dict(self) -> dict:
        return {
            "value": round(self.value, 5) if self.value is not None else None,
            "status": self.status.value,
            "reason": self.reason,
            "evidence": list(self.evidence),
        }
