"""Provider license evidence evaluator (Phase 21 S9).

Mechanical only. This module performs NO legal interpretation beyond the
project's own documented policy (SILENT != ALLOWED, AMBIGUOUS != ALLOWED,
UNKNOWN behaves as RED). It answers exactly one question per dimension:
"does explicit, documented evidence exist that this right was granted?"

It never infers one right from another (Phase 21 S1: "DO NOT... infer
redistribution rights from 'commercial API'... infer storage rights from
API access... infer derived-data rights from API access"). Each of the
eight dimensions is evaluated independently, from its own evidence only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RightsAnswer(str, Enum):
    EXPLICITLY_ALLOWED = "EXPLICITLY_ALLOWED"
    EXPLICITLY_PROHIBITED = "EXPLICITLY_PROHIBITED"
    CONDITIONAL = "CONDITIONAL"
    SILENT = "SILENT"
    AMBIGUOUS = "AMBIGUOUS"


class RightsDimension(str, Enum):
    ACCESS = "ACCESS"
    AUTOMATION = "AUTOMATION"
    STORAGE = "STORAGE"
    DERIVATION = "DERIVATION"
    COMMERCIAL = "COMMERCIAL"
    DISPLAY = "DISPLAY"
    REDISTRIBUTION = "REDISTRIBUTION"
    RETENTION = "RETENTION"
    ATTRIBUTION = "ATTRIBUTION"


# The dimensions required for the MINIMUM production clearance profile
# (Phase 21 S11): automated access, storage, derived analytics, commercial
# use, user-facing serving. Redistribution of RAW data is deliberately
# excluded -- the product serves derived recommendations, not a raw-data
# mirror, so raw-redistribution rights are not required (S11: "do not
# require raw redistribution rights if the actual product does not need
# to redistribute the raw dataset").
MINIMUM_PRODUCTION_DIMENSIONS = (
    RightsDimension.ACCESS,
    RightsDimension.AUTOMATION,
    RightsDimension.STORAGE,
    RightsDimension.DERIVATION,
    RightsDimension.COMMERCIAL,
    RightsDimension.DISPLAY,
)


@dataclass(frozen=True)
class DimensionEvidence:
    dimension: RightsDimension
    answer: RightsAnswer
    evidence_reference: str      # e.g. a terms-of-service section, or "NO_EVIDENCE"
    evidence_timestamp: Optional[str] = None
    notes: str = ""


@dataclass(frozen=True)
class ClearanceResult:
    provider_id: str
    cleared_dimensions: tuple[RightsDimension, ...]
    not_cleared_dimensions: tuple[RightsDimension, ...]
    minimum_production_clearance: bool
    raw_redistribution_cleared: bool
    derived_intelligence_potentially_allowed: bool
    per_dimension: dict[str, DimensionEvidence]


# Only these two answers count as a granted right. Every other answer
# (PROHIBITED, CONDITIONAL, SILENT, AMBIGUOUS) is NOT_CLEARED. CONDITIONAL
# is deliberately excluded from "cleared" -- a condition that has not been
# separately verified as met is not a clearance, it is a requirement to
# verify something else first.
_CLEARED_ANSWERS = frozenset({RightsAnswer.EXPLICITLY_ALLOWED})


def is_cleared(evidence: DimensionEvidence) -> bool:
    return evidence.answer in _CLEARED_ANSWERS


def evaluate_provider_clearance(
    provider_id: str,
    evidence: dict[RightsDimension, DimensionEvidence],
) -> ClearanceResult:
    """Evaluate a provider's clearance across all supplied dimensions.
    Missing dimensions (no DimensionEvidence supplied at all) are treated
    identically to SILENT -- absence of an answer is not a granted right."""
    per_dimension: dict[str, DimensionEvidence] = {}
    cleared: list[RightsDimension] = []
    not_cleared: list[RightsDimension] = []

    for dim in RightsDimension:
        ev = evidence.get(dim)
        if ev is None:
            ev = DimensionEvidence(dim, RightsAnswer.SILENT, "NO_EVIDENCE_SUPPLIED",
                                    notes="dimension was never asked or never answered")
        per_dimension[dim.value] = ev
        if is_cleared(ev):
            cleared.append(dim)
        else:
            not_cleared.append(dim)

    minimum_ok = all(d in cleared for d in MINIMUM_PRODUCTION_DIMENSIONS)
    raw_redist_ok = RightsDimension.REDISTRIBUTION in cleared

    # S11's explicit distinction: if raw redistribution is NOT permitted but
    # derivation + display + commercial + storage + access + automation ARE
    # all explicitly permitted, derived intelligence may still be possible.
    # This is "potentially allowed", never "allowed" outright -- it still
    # requires the minimum profile to be separately, fully cleared.
    derived_potentially_ok = minimum_ok and not raw_redist_ok

    return ClearanceResult(
        provider_id=provider_id,
        cleared_dimensions=tuple(cleared),
        not_cleared_dimensions=tuple(not_cleared),
        minimum_production_clearance=minimum_ok,
        raw_redistribution_cleared=raw_redist_ok,
        derived_intelligence_potentially_allowed=derived_potentially_ok,
        per_dimension=per_dimension,
    )


def overall_provider_status(clearance: ClearanceResult,
                            any_dimension_explicitly_prohibited: bool) -> str:
    """VERIFIED / PARTIAL / UNVERIFIED / BLOCKED, per Phase 20/21's shared
    vocabulary (data_license_gate.DataLicenseStatus values, reused here as
    plain strings to avoid a hard dependency on that module's dataset-scoped
    semantics -- provider status and dataset status are related but
    distinct concepts kept separately)."""
    if any_dimension_explicitly_prohibited:
        return "BLOCKED"
    if clearance.minimum_production_clearance:
        return "VERIFIED"
    if clearance.cleared_dimensions:
        return "PARTIAL"
    return "UNVERIFIED"
