"""V3 eligibility gate.

Implements INTELLIGENCE_MODEL_SPEC.md S5. Runs before scoring; produces
ELIGIBLE or an exclusion with a class and machine-readable reason.

Three exclusion classes, never conflated (FC26_IDENTITY_RESOLUTION_SPEC.md,
FC26_CONFLICT_RESOLUTION_SPEC.md):

    FAILED          verified to violate a stated requirement
    UNVERIFIABLE     requirement could not be checked -- the fact is UNKNOWN
    NOT_EVALUABLE    evidence coverage below kappa_min

"we checked and it fails" and "we could not check" are different statements
and must stay different in the API payload.

This closes the measured V2-5 defect: a 91-rated striker was a *ranked*
candidate for a CB slot (position_fit=0.05, excluded_hard=[]) because
position was only a soft-scored component, and only repository pre-filtering
kept it out of production. Position is a gate here, never a score --
`compatible_positions`/`POSITION_ADJACENCY` (scoring_config.py) is reused
unchanged so the gate and the pre-existing repository pre-filter agree by
construction (same 0.4 adjacency bar).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from backend.services.scoring_config import POSITION_ADJACENCY
from backend.services.v3_config import DEFAULT_V3_CONFIG


class ExclusionClass(str, Enum):
    FAILED = "FAILED"
    UNVERIFIABLE = "UNVERIFIABLE"
    NOT_EVALUABLE = "NOT_EVALUABLE"


@dataclass(frozen=True)
class EligibilityResult:
    eligible: bool
    gate: Optional[str] = None
    exclusion_class: Optional[ExclusionClass] = None
    reason: Optional[str] = None
    position_eligibility: Optional[float] = None


def position_eligibility(primary: Optional[str], target: str,
                          secondary: tuple[str, ...] = (),
                          allow_out_of_position: bool = False) -> Optional[float]:
    """1.0 exact match; 0.85 if target is a published secondary position;
    else the adjacency value from POSITION_ADJACENCY; else 0.0. Returns None
    when primary is UNKNOWN (caller must treat that as UNVERIFIABLE, not a
    score of 0 -- absence of a fact is not proof it fails)."""
    if primary is None:
        return None
    if primary == target:
        return 1.0
    if target in secondary:
        return 0.85
    adj = POSITION_ADJACENCY.get(target, {}).get(primary)
    adj_rev = POSITION_ADJACENCY.get(primary, {}).get(target)
    best = max(v for v in (adj, adj_rev) if v is not None) if (adj or adj_rev) else 0.0
    if allow_out_of_position:
        return max(best, 0.01)  # keep it evaluable, flagged elsewhere
    return best


def check_eligibility(
    *,
    game_version: str,
    request_game_version: str,
    is_gk: bool,
    request_is_gk: bool,
    primary_position: Optional[str],
    secondary_positions: tuple[str, ...],
    target_position: str,
    is_synthetic: bool,
    allow_out_of_position: bool = False,
    theta_pos: Optional[float] = None,
) -> EligibilityResult:
    """G1-G4 (version, synthetic firewall, GK boundary, position). G5-G9
    (attribute minima, PlayStyles, links, budget, coverage) are applied by
    the caller against per-candidate data the gate does not itself hold --
    see recommendation_engine_v3.evaluate() for the full G1-G9 sequence."""
    theta = theta_pos if theta_pos is not None else DEFAULT_V3_CONFIG.theta_pos.value

    # G1 -- version wall. Never silently mixed (FC26 vs FC27 firewall).
    if game_version != request_game_version:
        return EligibilityResult(False, "G1_version", ExclusionClass.FAILED,
                                  f"game_version {game_version} != requested {request_game_version}")

    # G2 -- synthetic firewall. A SYNTHETIC_TEST/is_synthetic row must never
    # reach a real ranking regardless of caller. This is the engine-level
    # backstop for the measured defect where the repository's synthetic
    # filter could be bypassed by a data_status/is_synthetic mismatch.
    if is_synthetic:
        return EligibilityResult(False, "G2_synthetic", ExclusionClass.FAILED,
                                  "candidate is marked is_synthetic=True; synthetic data is never eligible outside test fixtures")

    # G3 -- GK boundary. Absolute; not configurable per request.
    if is_gk != request_is_gk:
        return EligibilityResult(False, "G3_gk_boundary", ExclusionClass.FAILED,
                                  "goalkeeper/outfield boundary mismatch")

    # G4 -- position eligibility.
    elig = position_eligibility(primary_position, target_position, secondary_positions,
                                 allow_out_of_position)
    if elig is None:
        return EligibilityResult(False, "G4_position", ExclusionClass.UNVERIFIABLE,
                                  "primary_position is UNKNOWN for this candidate",
                                  position_eligibility=None)
    if elig < theta and not allow_out_of_position:
        return EligibilityResult(False, "G4_position", ExclusionClass.FAILED,
                                  f"position_eligibility={elig:.2f} < theta_pos={theta:.2f} "
                                  f"(primary={primary_position}, target={target_position})",
                                  position_eligibility=elig)

    return EligibilityResult(True, position_eligibility=elig)


def check_coverage_gate(kappa: float, kappa_min: Optional[float] = None) -> EligibilityResult:
    """G9 -- evidence coverage floor. Below kappa_min the candidate is
    NOT_EVALUABLE: it leaves the ranking entirely (not ranked last -- we do
    not know that it is bad, we simply do not know)."""
    threshold = kappa_min if kappa_min is not None else DEFAULT_V3_CONFIG.kappa_min.value
    if kappa < threshold:
        return EligibilityResult(False, "G9_coverage", ExclusionClass.NOT_EVALUABLE,
                                  f"evidence coverage kappa={kappa:.3f} < kappa_min={threshold:.3f}")
    return EligibilityResult(True)
