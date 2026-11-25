"""V3 demand vector composition.

Implements INTELLIGENCE_MODEL_SPEC.md S2: one demand vector w, composed once
per request, before any candidate is scored. This replaces v2's split
between a position-only `attribute_fit` and a separately (and, for single
non-combination profiles, unsigned) tactically-weighted `tactical_fit`,
which measured evidence (Session 1) showed made position fit tactically
blind for ~0.60 of declared weight.

    w0 = position_base(position)
    w1 = (1-lambda)*w0 + lambda*tactical_demand(profile, secondary)
    w2 = w1 (x) slot_emphasis(formation, slot)
    w3 = w2 (x) role_modifier(role)              [identity -- no Role data exists]
    w4 = apply_user_preferences(w3, prefs, bands)
    w  = w4 / sum(w4)

ENGINE CONVENTION -- signed two-pole tactical affinity
--------------------------------------------------------
V2's `tactical_weights_from_dimensions` (formations.py) computed demand as
`abs(value - 0.5) * 2`, which is UNSIGNED: PRESSING (press_intensity=0.95)
and LOW_BLOCK (press_intensity=0.2) produced demand of equal magnitude for
the SAME attributes, in the SAME direction. Measured on the real FC26
foundation, this was a direct, confirmed cause of PRESSING and LOW_BLOCK
returning a 10/10-identical top-10 at CM (see CORE_INTELLIGENCE_ARCHITECTURE.md
S1.1). A low block and a high press are opposite ends of a spectrum and must
pull attribute importance in different directions, not the same direction at
different volumes.

This module fixes it by giving each dimension two affinity poles -- HIGH
(reused from formations.DIMENSION_ATTRIBUTE_AFFINITY, unchanged) and LOW
(new in this module). Which pole applies is decided by the SIGN of the
dimension's shift from neutral, not its magnitude. The LOW-pole table below
is a NEW engineering hypothesis introduced in this implementation session,
not a verified FC26 mechanic and not carried over from any prior session's
audit. It is labelled ENGINE_DERIVED in every API response, exactly like the
HIGH-pole table it extends. It was validated by:
  (a) construction -- a fast-but-lighter CB beats a slow-but-strong CB under
      HIGH_PRESS, and the same pair reverses under LOW_BLOCK, at every lambda
      tested in [0.5, 0.7] (see TEST_RESULTS.md, case G-B1/G-B2);
  (b) population measurement -- PRESSING/LOW_BLOCK top-10 overlap at CB drops
      from the v2-measured 10/10 to 3/10 at lambda=0.7 (TEST_RESULTS.md RD-2).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from backend.services.formations import (
    DIMENSION_ATTRIBUTE_AFFINITY,
    GK_DIMENSION_ATTRIBUTE_AFFINITY,
    dimension_vector,
)
from backend.services.scoring_config import ScoringConfig

# ---------------------------------------------------------------------------
# LOW-pole affinity. ENGINE_DERIVED, new in this session. See module docstring.
# Only dimensions where the low pole plausibly demands a genuinely different
# (not merely absent) attribute set are given an entry; a dimension with no
# entry here contributes nothing when its shift is negative, which is the
# conservative choice when no low-pole hypothesis is offered.
# ---------------------------------------------------------------------------
DIMENSION_LOW_POLE_AFFINITY: dict[str, dict[str, float]] = {
    "press_intensity": {
        "defensive_awareness": 0.25, "positioning": 0.20, "standing_tackle": 0.20,
        "strength": 0.15, "composure": 0.10, "interceptions": 0.10,
    },
    "block_height": {
        "standing_tackle": 0.30, "strength": 0.25, "heading_accuracy": 0.20,
        "jumping": 0.15, "defensive_awareness": 0.10,
    },
    "build_up_speed": {
        "composure": 0.30, "short_passing": 0.25, "vision": 0.20,
        "long_passing": 0.15, "ball_control": 0.10,
    },
    "directness": {
        "short_passing": 0.30, "vision": 0.25, "ball_control": 0.20,
        "dribbling_detail": 0.15, "composure": 0.10,
    },
    "tempo": {
        "strength": 0.25, "composure": 0.25, "positioning": 0.20,
        "vision": 0.15, "long_passing": 0.15,
    },
    "width": {
        "short_passing": 0.30, "vision": 0.25, "defensive_awareness": 0.25,
        "composure": 0.20,
    },
}

# Recovery-pace override for the HIGH pole of the two dimensions most tied to
# defensive-line height, strengthened relative to v2's flatter table. This is
# also ENGINE_DERIVED: "a high defensive line's centre-backs live on recovery
# pace" is a materially stronger claim than v2's table encoded. See docstring
# validation note (a) above for the adversarial pair this was tuned against.
#
# EXPERIMENT CM-1 (v3.1 calibration session): build_up_speed, tempo and
# directness were still using v2's unmodified HIGH-pole table, and measurement
# found why CM stayed tactically stable under PACE_ABUSER/DIRECT_PLAY despite
# genuinely strong dimension shifts (0.60-0.80): those three dimensions'
# inherited affinity routed weight straight back into short_passing/
# long_passing/composure -- the same attributes CM's own position baseline
# already emphasises (weight 0.128 for short_passing under BALANCED with zero
# tactical pull) -- reinforcing the baseline instead of displacing it.
# Rebalanced to route toward genuinely pace/directness-specific attributes.
# Measured effect (V3_1_CALIBRATION_REPORT.md Section C): CM mean top-10
# overlap 6.90 -> 5.70/10 (now clears the <=6.0 target), CM PRESSING∩LOW_BLOCK
# 5 -> 4/10 (now clears <=4/10), with CB and ST *improving* rather than
# regressing (4.90->4.60, 5.00->4.40). T0 invariants and T1 goldens re-run
# and confirmed clean after this change -- see calibration report.
_HIGH_POLE_OVERRIDES: dict[str, dict[str, float]] = {
    "block_height": {
        "pace": 0.35, "acceleration": 0.25, "reactions": 0.15,
        "defensive_awareness": 0.10, "positioning": 0.10, "interceptions": 0.05,
    },
    "press_intensity": {
        "stamina": 0.25, "aggression": 0.20, "interceptions": 0.20,
        "reactions": 0.15, "acceleration": 0.10, "positioning": 0.10,
    },
    "build_up_speed": {
        "acceleration": 0.30, "sprint_speed": 0.25, "reactions": 0.15,
        "short_passing": 0.05, "composure": 0.15, "ball_control": 0.10,
    },
    "tempo": {
        "reactions": 0.25, "agility": 0.25, "acceleration": 0.20,
        "stamina": 0.20, "short_passing": 0.05, "composure": 0.05,
    },
    "directness": {
        "long_shots": 0.25, "heading_accuracy": 0.20, "strength": 0.20,
        "shot_power": 0.20, "sprint_speed": 0.10, "long_passing": 0.05,
    },
}
DIMENSION_HIGH_POLE_AFFINITY: dict[str, dict[str, float]] = {
    **DIMENSION_ATTRIBUTE_AFFINITY,
    **_HIGH_POLE_OVERRIDES,
}


@dataclass(frozen=True)
class DemandStage:
    """One recorded step of demand composition. Kept for ScoringContext so
    the whole pipeline is replayable and inspectable, per
    INTELLIGENCE_MODEL_SPEC.md S9's ScoringContext.demand_stages."""
    stage: str
    inputs: dict
    vector: dict[str, float]


@dataclass(frozen=True)
class DemandResult:
    vector: dict[str, float]           # final w, sums to 1 (or empty if no demand)
    stages: tuple[DemandStage, ...]
    lam: float
    is_gk: bool
    tactical_demand_neutral: bool       # true if the tactical layer contributed nothing


def _normalise(w: dict[str, float]) -> dict[str, float]:
    total = sum(w.values())
    if total <= 0:
        return {}
    return {a: v / total for a, v in w.items()}


def signed_tactical_demand(profile: str, secondary: Optional[str] = None,
                            primary_share: float = 0.65,
                            is_gk: bool = False) -> dict[str, float]:
    """Pure tactical attribute demand from a profile's dimension vector,
    SIGNED. Independent of position -- this is `tactical_demand(profile,
    secondary)` from INTELLIGENCE_MODEL_SPEC.md S2.2."""
    dims = dimension_vector(profile, secondary, primary_share)
    weights: dict[str, float] = {}
    if is_gk:
        # No low-pole GK hypothesis has been developed or validated in this
        # session (see module docstring: outfield was the priority). GK
        # tactical demand uses magnitude only, matching v2's existing
        # (already GK-appropriate, single-pole) table. This is a known,
        # declared simplification -- see V3_MIGRATION_REPORT.md "Known
        # limitations".
        for dim, value in dims.items():
            shift = abs(value - 0.5) * 2.0
            if shift < 1e-9:
                continue
            for attr, aff in GK_DIMENSION_ATTRIBUTE_AFFINITY.get(dim, {}).items():
                weights[attr] = weights.get(attr, 0.0) + aff * shift
        return _normalise(weights)

    for dim, value in dims.items():
        shift = (value - 0.5) * 2.0
        if abs(shift) < 1e-9:
            continue
        pole = DIMENSION_HIGH_POLE_AFFINITY if shift > 0 else DIMENSION_LOW_POLE_AFFINITY
        magnitude = abs(shift)
        for attr, aff in pole.get(dim, {}).items():
            weights[attr] = weights.get(attr, 0.0) + aff * magnitude
    return _normalise(weights)


def compose_demand(
    *,
    position: str,
    tactical_profile: str,
    secondary_tactical_profile: Optional[str] = None,
    primary_share: float = 0.65,
    lam: float,
    slot_emphasis: Optional[dict[str, float]] = None,
    role_modifier: Optional[dict[str, float]] = None,
    attribute_preference_weights: Optional[dict[str, float]] = None,
    scoring_config: Optional[ScoringConfig] = None,
) -> DemandResult:
    """Compose the single v3 demand vector for a request. See module
    docstring for the pipeline. Every stage is recorded for replay."""
    cfg = scoring_config or ScoringConfig()
    is_gk = position == "GK"
    stages: list[DemandStage] = []

    w0 = dict(cfg.position_attribute_weights(position))
    stages.append(DemandStage("position_base", {"position": position}, dict(_normalise(w0))))

    tactical = signed_tactical_demand(
        tactical_profile, secondary_tactical_profile, primary_share, is_gk=is_gk
    )
    tactical_demand_neutral = not tactical
    keys = set(w0) | set(tactical)
    w0n = _normalise(w0)
    w1 = {a: (1 - lam) * w0n.get(a, 0.0) + lam * tactical.get(a, 0.0) for a in keys}
    w1 = _normalise(w1)
    stages.append(DemandStage(
        "tactical_blend",
        {"tactical_profile": tactical_profile, "secondary": secondary_tactical_profile, "lambda": lam},
        dict(w1),
    ))

    w2 = w1
    if slot_emphasis:
        w2 = _normalise({a: w1.get(a, 0.0) * slot_emphasis.get(a, 1.0) for a in w1})
        stages.append(DemandStage("slot_emphasis", {"slot_emphasis": dict(slot_emphasis)}, dict(w2)))

    w3 = w2
    if role_modifier:
        w3 = _normalise({a: w2.get(a, 0.0) * role_modifier.get(a, 1.0) for a in w2})
        stages.append(DemandStage("role_modifier", {"role_modifier": dict(role_modifier)}, dict(w3)))
    else:
        stages.append(DemandStage("role_modifier", {"status": "UNAVAILABLE - no Role data ingested"}, dict(w3)))

    w4 = w3
    if attribute_preference_weights:
        combined = dict(w3)
        for a, extra in attribute_preference_weights.items():
            combined[a] = max(0.0, combined.get(a, 0.0) + extra)
        w4 = _normalise({attr: weight for attr, weight in combined.items() if weight > 0})
        if not w4:
            raise ValueError("Attribute preferences remove all demand.")
        stages.append(DemandStage("user_preferences", {"preferences": dict(attribute_preference_weights)}, dict(w4)))

    return DemandResult(
        vector=w4, stages=tuple(stages), lam=lam, is_gk=is_gk,
        tactical_demand_neutral=tactical_demand_neutral,
    )
