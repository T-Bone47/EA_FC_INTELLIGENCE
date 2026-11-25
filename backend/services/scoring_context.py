"""V3 ScoringContext.

Implements INTELLIGENCE_MODEL_SPEC.md S9 and the P0 fix for the measured
V2-7 defect: v2's explanation_service read a static COMPONENT_WEIGHTS table
that did not match the redistributed weights that actually produced the
score (reported contribution 0.15 where scoring had used 0.50).

Contract: `reconstruct_score(context)` recomputes R from nothing but the
stored per-attribute contributions and modifiers, and must equal
context.r to within 1e-9. explanation_service_v3 is required to read
ONLY this object -- never a separate weight table.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional

from backend.services.capability_model import AttributeContribution, CapabilityResult
from backend.services.demand_composition import DemandStage
from backend.services.eligibility_gate import EligibilityResult


@dataclass(frozen=True)
class ModifierContribution:
    name: str
    raw: float
    capped: float
    cap: float
    reason: str


@dataclass(frozen=True)
class ScoringContext:
    """Immutable. One instance per (candidate, request). Everything
    explanation, sensitivity, counterfactuals and audit need, and nothing
    they should read instead."""
    # -- identity / versioning --
    request_id: uuid.UUID
    candidate_entity_id: uuid.UUID
    candidate_name: str
    entity_type: str                      # 'game_player' (only supported scope in v3.0)
    engine_version: str
    config_version: str
    data_version: Optional[str]
    reference_distribution_version: Optional[str]
    reference_distribution_universe: Optional[str]

    # -- request context --
    position: str
    tactical_profile: str
    secondary_tactical_profile: Optional[str]
    lam: float

    # -- demand --
    demand_stages: tuple[DemandStage, ...]
    demand_vector: dict[str, float]

    # -- capability / evidence --
    per_attribute: tuple[AttributeContribution, ...]
    coverage_kappa: float
    missing_attributes: tuple[str, ...]
    c_lo: float
    c_hi: float

    # -- modifiers --
    modifiers: tuple[ModifierContribution, ...]
    modifier_total: float                 # M, already clamped to [modifier_min, modifier_max]

    # -- final --
    r: float                              # R = C_lo * M -- the ranking quantity
    r_hi: float                           # C_hi * M -- optimistic bound, never used for ranking

    # -- eligibility (only present on the ELIGIBLE path; exclusions are
    #    represented separately, see recommendation_engine_v3.ExclusionRecord) --
    eligibility: Optional[EligibilityResult] = None

    # -- confidence (reporting only -- see V3_1_CALIBRATION_REPORT.md Phase 11:
    #    proven independent of R by construction, not merely by convention.
    #    Computed AFTER r/r_hi below and never fed back into either.) --
    confidence: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "request_id": str(self.request_id),
            "candidate_entity_id": str(self.candidate_entity_id),
            "candidate_name": self.candidate_name,
            "entity_type": self.entity_type,
            "engine_version": self.engine_version,
            "config_version": self.config_version,
            "data_version": self.data_version,
            "reference_distribution_version": self.reference_distribution_version,
            "reference_distribution_universe": self.reference_distribution_universe,
            "position": self.position,
            "tactical_profile": self.tactical_profile,
            "secondary_tactical_profile": self.secondary_tactical_profile,
            "lambda": self.lam,
            "demand_vector": self.demand_vector,
            "coverage_kappa": self.coverage_kappa,
            "missing_attributes": list(self.missing_attributes),
            "c_lo": self.c_lo,
            "c_hi": self.c_hi,
            "modifiers": [
                {"name": m.name, "raw": m.raw, "capped": m.capped, "cap": m.cap, "reason": m.reason}
                for m in self.modifiers
            ],
            "modifier_total": self.modifier_total,
            "r": self.r,
            "r_hi": self.r_hi,
            "per_attribute": [
                {
                    "attribute": a.attribute, "weight": a.weight, "value": a.value,
                    "s_eff": a.s_eff, "contribution_lo": a.contribution_lo,
                    "contribution_hi": a.contribution_hi, "covered": a.covered,
                }
                for a in sorted(self.per_attribute, key=lambda x: -x.contribution_lo)
            ],
        }


def reconstruct_score(context: ScoringContext) -> float:
    """Recompute R from nothing but the stored contributions and modifiers.
    Used by the INV-8 regression test (tolerance 1e-9) and available to any
    caller that wants to verify a context before trusting it (e.g. after
    deserialising one from a stored recommendation)."""
    c_lo = sum(a.contribution_lo for a in context.per_attribute)
    return round(c_lo * context.modifier_total, 10)


def reconstruct_score_hi(context: ScoringContext) -> float:
    c_hi = sum(a.contribution_hi for a in context.per_attribute)
    return round(c_hi * context.modifier_total, 10)
