"""V3 capability and evidence interval.

Implements INTELLIGENCE_MODEL_SPEC.md S3-S4. Replaces v2's weight
redistribution (measured to reward thin evidence -- a one-attribute
candidate outranked a fully documented one, see
CORE_INTELLIGENCE_ARCHITECTURE.md S1.3) with an evidence interval:

    covered      = D ∩ K(c)                       -- demanded AND published
    kappa        = sum(w_a for a in covered)       -- evidence coverage
    C_lo         = sum(w_a * s(v_a) for covered) + sum(w_a * s(q_lo(a)) for D\\K)
    C_hi         = sum(w_a * s(v_a) for covered) + sum(w_a * s(q_hi(a)) for D\\K)

Ranking uses C_lo (pessimistic under uncertainty). This makes missing a
demanded attribute strictly non-beneficial: publishing a value above the
frozen P10 raises C_lo, publishing one below it lowers C_lo. What NOT publishing
charges is the config's `missing_value_charge`:
    ZERO (V3.2, default)    unpublished earns nothing, so omission can never
                            raise C_lo (INV-5 holds for EVERY published value).
    P10  (V3.1, historical) unpublished is charged the P10 rate; Phase 23 (F-1)
                            measured that hiding a published value BELOW P10 then
                            RAISES C_lo, i.e. INV-5 held only for values >= P10.
(INV-5 in INTELLIGENCE_TEST_MATRIX.md; Phase 24: test_v3_2_missing_data.py.)

`overall_quality` and `position_fit` are deliberately NOT scored components
here (CORE_INTELLIGENCE_ARCHITECTURE.md S7): capability over the composed
demand vector already measures quality in the attributes that matter for
this request, and re-adding OVR as a parallel term is what let v2's ranking
degenerate to an OVR proxy under thin evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.services.engine_config import (
    DEFAULT_SATURATION_KNEE,
    SATURATION_EXCESS_FACTOR,
    SATURATION_KNEES,
)
from backend.services.reference_distribution import ReferenceDistribution
from backend.services.v3_config import DEFAULT_V3_CONFIG, MISSING_CHARGE_MODES


def saturate(value: float, attribute: str) -> float:
    """s(v, a): continuous, strictly increasing, bounded in [0,1]. Carried
    from v2 engine_config.py unchanged -- this is a MATH property (monotone,
    bounded piecewise-linear), not re-derived in this session. Always on in
    v3 (v2 gated it behind an opt-in flag)."""
    knee = SATURATION_KNEES.get(attribute, DEFAULT_SATURATION_KNEE)
    if value <= knee:
        return value / 99.0
    return (knee + (value - knee) * SATURATION_EXCESS_FACTOR) / 99.0


@dataclass(frozen=True)
class AttributeContribution:
    attribute: str
    weight: float
    value: Optional[float]          # None = UNKNOWN (not published)
    s_eff: Optional[float]          # saturated value, or None if unpublished
    contribution_lo: float
    contribution_hi: float
    covered: bool                   # True iff this demanded attribute was published


@dataclass(frozen=True)
class CapabilityResult:
    c_lo: float
    c_hi: float
    kappa: float                        # evidence coverage, sum of covered weight
    per_attribute: tuple[AttributeContribution, ...]
    missing_attributes: tuple[str, ...]
    reference_distribution_version: Optional[str]
    reference_distribution_universe: Optional[str]


MISSING_CHARGES = MISSING_CHARGE_MODES


def compute_capability(
    *,
    demand: dict[str, float],
    attributes: dict[str, Optional[float]],
    position: str,
    reference: Optional[ReferenceDistribution],
    missing_charge: str = DEFAULT_V3_CONFIG.missing_value_charge,
) -> CapabilityResult:
    """Compute C_lo, C_hi and coverage for one candidate against one demand
    vector. `attributes` maps attribute name -> published value or None.

    missing_charge selects what C_lo charges for an unpublished demanded
    attribute: "P10" (V3.1: frozen reference P10) or "ZERO" (strict: the
    unpublished share earns nothing). C_hi always charges P90. Measured in
    the Phase 23 lab: under P10, hiding a published value BELOW P10 raises
    C_lo (13% of FC27 CM probes, max +0.0296); under ZERO it never can."""
    if missing_charge not in MISSING_CHARGES:
        raise ValueError(f"missing_charge must be one of {MISSING_CHARGES}")
    contributions: list[AttributeContribution] = []
    missing: list[str] = []
    kappa = 0.0
    c_lo = 0.0
    c_hi = 0.0

    for attr, weight in demand.items():
        value = attributes.get(attr)
        if value is not None:
            s_eff = saturate(value, attr)
            contributions.append(AttributeContribution(
                attribute=attr, weight=weight, value=value, s_eff=s_eff,
                contribution_lo=weight * s_eff, contribution_hi=weight * s_eff,
                covered=True,
            ))
            kappa += weight
            c_lo += weight * s_eff
            c_hi += weight * s_eff
        else:
            missing.append(attr)
            q = reference.quantiles(position, attr) if reference is not None else None
            if q is not None:
                lo_s = 0.0 if missing_charge == "ZERO" else saturate(q.p10, attr)
                hi_s = saturate(q.p90, attr)
            else:
                # No reference evidence for this attribute either -- charge
                # the full plausible range. This never happens for the
                # 34 attributes covered by the shipped fc26-players
                # distribution but is handled explicitly rather than
                # crashing, per the project's UNKNOWN-never-crashes stance.
                lo_s, hi_s = 0.0, 1.0
            contributions.append(AttributeContribution(
                attribute=attr, weight=weight, value=None, s_eff=None,
                contribution_lo=weight * lo_s, contribution_hi=weight * hi_s,
                covered=False,
            ))
            c_lo += weight * lo_s
            c_hi += weight * hi_s

    return CapabilityResult(
        c_lo=round(c_lo, 10), c_hi=round(c_hi, 10), kappa=round(kappa, 10),
        per_attribute=tuple(contributions), missing_attributes=tuple(missing),
        reference_distribution_version=reference.version if reference else None,
        reference_distribution_universe=reference.universe if reference else None,
    )
