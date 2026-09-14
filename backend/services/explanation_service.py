"""Deterministic explanation generation.

Explanations are built from structured evidence only — no LLM in this path.
An LLM may later rephrase these grounded explanations, but must never invent
facts that are not present here (§16).
"""
from __future__ import annotations

from typing import Optional

from backend.domain.card_model import Candidate
from backend.domain.user_model import UserRequirements
from backend.services.fit_value import FitStatus, FitValue
from backend.services.scoring_config import COMPONENT_WEIGHTS

HUMAN = {
    "overall_quality": "Overall quality",
    "attribute_fit": "Attribute fit",
    "position_fit": "Position fit",
    "tactical_fit": "Tactical fit",
    "playstyle_fit": "PlayStyle fit",
    "team_fit": "Team/chemistry fit",
    "role_fit": "Role fit",
}


def why_this_player(candidate: Candidate,
                    components: dict[str, FitValue],
                    req: UserRequirements) -> list[str]:
    lines: list[str] = []
    ranked = sorted(
        ((n, fv) for n, fv in components.items()
         if fv.status == FitStatus.KNOWN and n in COMPONENT_WEIGHTS),
        key=lambda kv: (COMPONENT_WEIGHTS[kv[0]] * kv[1].value), reverse=True)
    for name, fv in ranked[:4]:
        contrib = COMPONENT_WEIGHTS[name] * fv.value
        lines.append(
            f"{HUMAN.get(name, name)} contributes {contrib:.3f} of the weighted "
            f"score ({fv.value:.2f} fit × {COMPONENT_WEIGHTS[name]:.2f} weight)")
        for ev in fv.evidence[:2]:
            lines.append(f"    · {ev}")
    unknown = [HUMAN.get(n, n) for n, fv in components.items()
               if fv.status != FitStatus.KNOWN and n in COMPONENT_WEIGHTS]
    if unknown:
        lines.append("Not scored (weight redistributed, no penalty): "
                     + ", ".join(unknown))
        for n, fv in components.items():
            if fv.status != FitStatus.KNOWN and fv.reason and n in COMPONENT_WEIGHTS:
                lines.append(f"    · {HUMAN.get(n, n)}: {fv.reason}")
    return lines


def why_not_alternative(best: Candidate, best_components: dict[str, FitValue],
                        alt: Candidate, alt_components: dict[str, FitValue]) -> list[str]:
    """Deterministic differential explanation between winner and one alternative."""
    lines: list[str] = []
    deltas = []
    for name in COMPONENT_WEIGHTS:
        b, a = best_components.get(name), alt_components.get(name)
        if b is None or a is None:
            continue
        if b.status == FitStatus.KNOWN and a.status == FitStatus.KNOWN:
            d = (b.value - a.value) * COMPONENT_WEIGHTS[name]
            if abs(d) >= 0.005:
                deltas.append((d, name, b.value, a.value))
    deltas.sort(reverse=True)
    for d, name, bv, av in deltas[:4]:
        comp = HUMAN.get(name, name)
        if d > 0:
            lines.append(
                f"{alt.name} is behind on {comp}: {av:.2f} vs {best.name}'s {bv:.2f} "
                f"(weighted Δ {d:+.3f} in favor of {best.name})")
        else:
            lines.append(
                f"{alt.name} is ahead on {comp}: {av:.2f} vs {best.name}'s {bv:.2f} "
                f"(weighted Δ {d:+.3f}) — {best.name} still wins overall on the "
                "remaining components")
    if not deltas:
        lines.append(f"{alt.name} is statistically tied on all KNOWN components; "
                     "ordering decided by deterministic tiebreakers (OVR, name)")
    return lines


def strengths_weaknesses(candidate: Candidate, req: UserRequirements,
                         config) -> dict[str, list[str]]:
    from backend.services.feature_extraction import strength_weakness_lists
    s, w = strength_weakness_lists(candidate, req, config)
    return {"strengths": s, "weaknesses": w}


def recommendation_summary(result, req: UserRequirements) -> str:
    """One-paragraph deterministic summary of a full recommendation result."""
    if result.best is None:
        return ("No candidate satisfied the hard constraints for this request. "
                "Nothing was fabricated to fill the gap.")
    parts = [f"Best fit for {req.position or 'the requested slot'} "
             f"({req.game_version}, {req.tactical_profile} profile): "
             f"{result.best.name} "
             f"(fit score {result.best_score:.3f}, confidence {result.confidence.score:.2f})."]
    if result.budget_status:
        parts.append(f"Budget: {result.budget_status}.")
    parts.append(f"{len(result.ranked)} candidates evaluated; "
                 f"{len(result.excluded_by_floor)} excluded by the tactical floor"
                 if result.excluded_by_floor else
                 f"{len(result.ranked)} candidates evaluated.")
    return " ".join(parts)
