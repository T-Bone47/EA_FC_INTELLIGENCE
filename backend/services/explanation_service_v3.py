"""V3 explanation service.

Reads ONLY the ScoringContext that produced the score -- never a separate
weight table. This is the direct fix for the measured V2-7 defect: v2's
explanation_service read static COMPONENT_WEIGHTS, which diverged from the
redistributed weights that actually scored a candidate (reported 0.15 where
scoring had used 0.50 under thin evidence). Here there is nothing else to
read: `reconstruct_score(context)` (scoring_context.py) proves the same
numbers the explanation quotes are the numbers that ranked the candidate.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.services.scoring_context import ScoringContext, reconstruct_score


@dataclass(frozen=True)
class Explanation:
    reasons: tuple[str, ...]
    trade_offs: tuple[str, ...]
    unknowns: tuple[str, ...]
    reconstructed_score: float
    matches_ranking_score: bool


def explain(context: ScoringContext, top_n: int = 4) -> Explanation:
    covered = [a for a in context.per_attribute if a.covered]
    covered_sorted = sorted(covered, key=lambda a: -a.contribution_lo)

    reasons: list[str] = []
    for a in covered_sorted[:top_n]:
        reasons.append(
            f"{_label(a.attribute)} ({a.value:g}) contributes {a.contribution_lo:.3f} "
            f"of the {context.tactical_profile} demand at {context.position}"
        )
    for m in context.modifiers:
        if m.capped > 1e-9:
            reasons.append(f"{m.name} modifier: +{m.capped:.3f} ({m.reason})")
    if not reasons:
        reasons.append("no covered demanded attributes scored above the reporting threshold")

    trade_offs: list[str] = []
    weakest = sorted(covered, key=lambda a: a.contribution_lo)[:top_n]
    for a in weakest:
        if a.s_eff is not None and a.s_eff < 0.75:
            trade_offs.append(
                f"{_label(a.attribute)} ({a.value:g}) is the weakest covered attribute "
                f"against this demand (weight {a.weight:.3f})"
            )
    for m in context.modifiers:
        if m.capped <= 1e-9 and m.cap > 0:
            trade_offs.append(f"{m.name} modifier did not apply: {m.reason}")

    unknowns: list[str] = []
    if context.missing_attributes:
        spread = context.c_hi - context.c_lo
        unknowns.append(
            f"{len(context.missing_attributes)} demanded attribute(s) not published "
            f"({', '.join(_label(a) for a in context.missing_attributes[:6])}"
            f"{'...' if len(context.missing_attributes) > 6 else ''}); "
            f"score could range up to {context.c_hi:.3f} (currently ranked on the "
            f"lower bound {context.c_lo:.3f}, a spread of {spread:.3f})"
        )

    recon = reconstruct_score(context)
    return Explanation(
        reasons=tuple(reasons), trade_offs=tuple(trade_offs), unknowns=tuple(unknowns),
        reconstructed_score=recon, matches_ranking_score=abs(recon - context.r) < 1e-9,
    )


def why_not(winner: ScoringContext, other: ScoringContext, top_n: int = 3) -> tuple[str, ...]:
    """Component-level differential between two candidates scored against
    the SAME demand vector, in the same units the ranking used."""
    if winner.demand_vector != other.demand_vector:
        return ("cannot compare -- candidates were scored against different demand vectors",)
    w_by_attr = {a.attribute: a for a in winner.per_attribute}
    o_by_attr = {a.attribute: a for a in other.per_attribute}
    deltas = []
    for attr in winner.demand_vector:
        wa, oa = w_by_attr.get(attr), o_by_attr.get(attr)
        if wa is None or oa is None:
            continue
        deltas.append((attr, wa.contribution_lo - oa.contribution_lo))
    deltas.sort(key=lambda t: -abs(t[1]))
    out = []
    for attr, d in deltas[:top_n]:
        direction = "ahead on" if d > 0 else "behind on"
        out.append(f"{winner.candidate_name} is {direction} {_label(attr)} by {abs(d):.3f} of R")
    return tuple(out)


def _label(attribute: str) -> str:
    return attribute.replace("_", " ")
