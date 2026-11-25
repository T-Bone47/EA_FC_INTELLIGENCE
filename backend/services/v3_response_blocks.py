"""Pure response-block builders for the v3 API (Phase 24 / Plan A).

Every value comes from ScoringContext or the candidate pool; nothing is estimated and no score
is computed here. DB-free so each block is unit-testable.
"""
from __future__ import annotations

from collections.abc import Sequence

from backend.services.explanation_service_v3 import why_not


def division_block(requested: str | None, pool: Sequence, *, applicable: bool = True) -> dict:
    """Make the division scope explicit; the API never silently picks a division.

    applicable=False (game versions that carry no division label, e.g. FC26 whose source only
    has a 'male' gender value) -> scope NOT_APPLICABLE with no counts."""
    if not applicable:
        return {"requested": requested, "scope": "NOT_APPLICABLE", "candidate_counts": {}}
    counts: dict[str, int] = {}
    for c in pool:
        label = c.extra.get("division") or "UNKNOWN"
        counts[label] = counts.get(label, 0) + 1
    return {"requested": requested, "scope": "FILTERED" if requested else "ALL_DIVISIONS",
            "candidate_counts": dict(sorted(counts.items()))}


def confidence_block(ctx) -> dict | None:
    """Engine confidence (reporting-only: it never enters the score)."""
    c = ctx.confidence
    return None if c is None else {"level": c["level"], "score": c["score_v2"], "reasons": list(c["reasons"]),
                                   "composition": c["composition"], "reporting_only": True}


def attribute_row(a) -> dict:
    return {"attribute": a.attribute, "value": a.value, "weight": round(a.weight, 6),
            "contribution": round(a.contribution_lo, 6)}


def tactical_fit_block(ctx, top: int = 5) -> dict:
    """Why this demand vector fits this player: the composition stages + the heaviest demanded attributes."""
    heaviest = sorted(ctx.per_attribute, key=lambda a: -a.weight)[:top]
    return {"position": ctx.position, "tactical_profile": ctx.tactical_profile,
            "secondary_tactical_profile": ctx.secondary_tactical_profile, "lambda": ctx.lam,
            "demand_stages": [{"stage": s.stage, "inputs": s.inputs} for s in ctx.demand_stages],
            "top_demanded": [attribute_row(a) for a in heaviest],
            "capability": {"low": ctx.c_lo, "high": ctx.c_hi}}


def evidence_block(ctx, cand=None) -> dict:
    """How much of the recommendation rests on published data (counts come from the ScoringContext)."""
    ps = next((m for m in ctx.modifiers if m.name == "playstyle"), None)
    return {"coverage": ctx.coverage_kappa, "demanded_attributes": len(ctx.per_attribute),
            "published_attributes": sum(a.covered for a in ctx.per_attribute),
            "missing_attributes": list(ctx.missing_attributes),
            "interval": {"low": ctx.r, "high": ctx.r_hi, "width": ctx.r_hi - ctx.r},
            "playstyle": {"published": getattr(cand, "playstyle_data_published", None),
                          "modifier_applied": ps.capped if ps else None, "reason": ps.reason if ps else None}}


def intervals_overlap(a, b) -> bool:
    """True when the lower-ranked player's optimistic score exceeds the higher-ranked player's ranked score."""
    return b.r_hi > a.r


def evidence_gap(a, b, eps: float) -> dict:
    """Modelled advantage of the higher-ranked option over the alternative."""
    point = a.r - b.r
    lower = a.r - b.r_hi
    upper = a.r_hi - b.r
    status = "NEAR_TIE" if point < eps else "EVIDENCE_SENSITIVE" if lower < eps else "CLEAR_SEPARATION"
    return {"status": status, "margin_low": round(lower, 10), "margin_high": round(upper, 10),
            "noise_threshold": eps}


def leading_pair(ranked, eps: float) -> dict | None:
    if len(ranked) < 2:
        return None
    first, second = ranked[0].context, ranked[1].context
    return {"higher": first.candidate_name, "lower": second.candidate_name, **evidence_gap(first, second, eps)}


def near_tie_block(a, b, eps: float) -> dict | None:
    """Honest closeness between adjacent players (a ahead of b); None when clearly separated."""
    gap = a.r - b.r
    assessment = evidence_gap(a, b, eps)
    if assessment["status"] == "CLEAR_SEPARATION":
        return None
    return {"next_entity_id": str(b.candidate_entity_id), "score_gap": round(gap, 6),
            "within_noise_threshold": gap < eps, "intervals_overlap": intervals_overlap(a, b),
            "why_ahead": list(why_not(a, b, top_n=3)), "decision_evidence": assessment}
