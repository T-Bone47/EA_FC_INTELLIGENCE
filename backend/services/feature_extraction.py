"""Feature extraction: candidate + requirements -> structured feature views.

Pure/deterministic. Used by the engine and by the comparison service. None
values pass through as None (UNKNOWN) — never coerced.
"""
from __future__ import annotations

from typing import Optional

from backend.domain.card_model import Candidate
from backend.domain.user_model import UserRequirements
from backend.services.scoring_config import ScoringConfig


def candidate_attribute_vector(candidate: Candidate, attrs: list[str]) -> dict[str, Optional[int]]:
    return {a: candidate.attributes.get(a) for a in attrs}


def requirement_feature_view(candidate: Candidate, req: UserRequirements,
                             config: ScoringConfig) -> dict:
    """Deterministic snapshot of what will be scored, for explanations/debug."""
    weights, specs = {}, {}
    if req.attribute_preferences:
        for p in req.attribute_preferences:
            weights[p.attribute] = p.weight
            specs[p.attribute] = {"min": p.min_value, "target": p.target_value}
    else:
        pos = (req.position or candidate.position_primary or "").upper()
        weights = config.position_attribute_weights(pos)
    tac = config.tactical_attribute_weights(req.tactical_profile, req.custom_tactics)
    return {
        "attribute_weights": weights,
        "attribute_constraints": specs,
        "tactical_weights": tac,
        "desired_playstyles": list(req.desired_playstyles),
        "desired_playstyles_plus": list(req.desired_playstyles_plus),
        "target_position": req.position,
        "role": req.role,
        "budget_coins": req.budget_coins,
    }


def strength_weakness_lists(candidate: Candidate, req: UserRequirements,
                            config: ScoringConfig,
                            strong_threshold: int = 85,
                            weak_threshold: int = 60) -> tuple[list[str], list[str]]:
    """Deterministic strengths/weaknesses relative to what THIS request cares about."""
    weights, _ = ({}, {})
    if req.attribute_preferences:
        relevant = {p.attribute for p in req.attribute_preferences}
    else:
        pos = (req.position or candidate.position_primary or "").upper()
        relevant = set(config.position_attribute_weights(pos))
    strengths, weaknesses = [], []
    for attr in sorted(relevant):
        v = candidate.attributes.get(attr)
        if v is None:
            continue
        if v >= strong_threshold:
            strengths.append(f"{attr} {v}")
        elif v <= weak_threshold:
            weaknesses.append(f"{attr} {v}")
    return strengths, weaknesses
