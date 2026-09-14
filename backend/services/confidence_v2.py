"""CONFIDENCE 2.0 (§24, §26, §27) — ADDITIVE enrichment.

The legacy confidence (component coverage + entity data confidence) stays
untouched for backward compatibility. This module composes an enriched
confidence from four documented inputs:

  legacy_confidence  — what the V2 pipeline already computed
  freshness          — days since the last source observation for the version
  source_authority   — authority tier of the dataset carrying the facts
  identity           — identity-resolution status of the entity

Missing inputs are EXCLUDED and the remaining weights renormalized — an
unknown input never masquerades as a bad one. Output: score_v2, level
(HIGH/MEDIUM/LOW/VERY_LOW), and human-readable reasons. Conflict awareness
(§27): unresolved source conflicts on the entity lower the authority factor
and add an explicit reason.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from backend.services.engine_config import (
    AUTHORITY_TIER_FACTOR, CONFIDENCE_LEVELS, CONFIDENCE_V2_WEIGHTS,
    FRESHNESS_FLOOR_DAYS, FRESHNESS_FLOOR_FACTOR, FRESHNESS_FULL_DAYS,
)


def freshness_factor(last_observed: Optional[datetime]) -> Optional[float]:
    """Linear decay between FULL and FLOOR days; floor 0.4 — stale != false."""
    if last_observed is None:
        return None
    now = datetime.now(timezone.utc)
    if last_observed.tzinfo is None:
        last_observed = last_observed.replace(tzinfo=timezone.utc)
    days = max(0.0, (now - last_observed).total_seconds() / 86400.0)
    if days <= FRESHNESS_FULL_DAYS:
        return 1.0
    if days >= FRESHNESS_FLOOR_DAYS:
        return FRESHNESS_FLOOR_FACTOR
    span = FRESHNESS_FLOOR_DAYS - FRESHNESS_FULL_DAYS
    return 1.0 - (1.0 - FRESHNESS_FLOOR_FACTOR) * (days - FRESHNESS_FULL_DAYS) / span


def authority_factor(tier: Optional[int], unresolved_conflicts: int = 0) -> Optional[float]:
    if tier is None:
        return None
    f = AUTHORITY_TIER_FACTOR.get(tier, 0.5)
    if unresolved_conflicts > 0:
        # §27: conflicts that authority could not settle reduce trust visibly
        f *= max(0.5, 1.0 - 0.15 * unresolved_conflicts)
    return f


def identity_factor(identity_status: Optional[str]) -> Optional[float]:
    if identity_status is None:
        return None
    return {"RESOLVED": 1.0, "REVIEW_REQUIRED": 0.6, "UNRESOLVED": 0.4}.get(
        str(identity_status).upper(), 0.5)


def level_for(score: float) -> str:
    for threshold, level in CONFIDENCE_LEVELS:
        if score >= threshold:
            return level
    return CONFIDENCE_LEVELS[-1][1]


def compute(legacy_score: float,
            last_observed: Optional[datetime] = None,
            source_tier: Optional[int] = None,
            identity_status: Optional[str] = None,
            unresolved_conflicts: int = 0) -> dict:
    """Additive confidence block. Every included dimension is listed in
    `reasons` with its factor — inspectable, never opaque."""
    factors: dict[str, Optional[float]] = {
        "legacy_confidence": max(0.0, min(1.0, legacy_score)),
        "freshness": freshness_factor(last_observed),
        "source_authority": authority_factor(source_tier, unresolved_conflicts),
        "identity": identity_factor(identity_status),
    }
    reasons: list[str] = []
    used_w = 0.0
    acc = 0.0
    for name, f in factors.items():
        w = CONFIDENCE_V2_WEIGHTS[name]
        if f is None:
            reasons.append(f"{name}: UNKNOWN — excluded from composition (not treated as bad)")
            continue
        used_w += w
        acc += w * f
        if name == "freshness":
            days = None
            if last_observed is not None:
                lo = last_observed if last_observed.tzinfo else last_observed.replace(tzinfo=timezone.utc)
                days = (datetime.now(timezone.utc) - lo).days
            reasons.append(f"freshness: factor {f:.2f} (last source observation "
                           f"{days} day(s) ago)")
        elif name == "source_authority":
            extra = (f"; {unresolved_conflicts} unresolved source conflict(s) — "
                     "conflicting evidence reduces confidence (§27)"
                     if unresolved_conflicts else "")
            reasons.append(f"source authority: tier {source_tier} factor {f:.2f}{extra}")
        elif name == "identity":
            reasons.append(f"identity: {identity_status} factor {f:.2f}")
        else:
            reasons.append(f"legacy component/data confidence: {f:.2f}")
    score = acc / used_w if used_w > 0 else 0.0
    return {
        "score_v2": round(score, 3),
        "level": level_for(score),
        "reasons": reasons,
        "composition": {k: (round(v, 3) if v is not None else None)
                        for k, v in factors.items()},
    }
