"""Card VALUE + PRICE services (§13/§14/§48).

Hard rules:
* A price exists only as a persisted observation with provenance. Missing
  price => UNKNOWN — never 0, never estimated, never inferred from OVR.
* VALUE = marginal contextual utility per verified cost. It is NOT OVR/price
  and NOT a generic quality measure: the utility input is the contextual
  engine score for THIS user's requirements, so value is contextual too.
* Without a verified price, value is UNAVAILABLE — reported explicitly.
* Market history is never manufactured: `price_history` returns only rows
  that exist; an empty history is reported as NO_PRICE_HISTORY.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.domain.card_model import Candidate
from backend.services import engine_config as ec
from backend.services.budget_provider import NullBudgetProvider, PriceQuote, within_budget

_provider = NullBudgetProvider()


def price_quote(candidate: Candidate) -> PriceQuote:
    return _provider.price_for(candidate)


def is_verified_price(candidate: Candidate) -> bool:
    """A price is VERIFIED only when it is present AND provenance-backed."""
    q = _provider.price_for(candidate)
    if not q.known:
        return False
    return bool(q.source_id or q.observed_at)


def price_freshness(candidate: Candidate) -> str:
    q = _provider.price_for(candidate)
    if not q.known or not q.observed_at:
        return "UNKNOWN"
    try:
        observed = datetime.fromisoformat(str(q.observed_at).replace("Z", "+00:00"))
    except ValueError:
        return "UNKNOWN"
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - observed
    if age <= timedelta(days=ec.PRICE_FRESH_DAYS):
        return "FRESH"
    if age <= timedelta(days=ec.PRICE_STALE_DAYS):
        return "AGING"
    return "STALE"


def budget_status(candidate: Candidate, budget: Optional[int]) -> dict:
    """§13: BUDGET_UNVERIFIED when we cannot verify the price — never a
    silent 'affordable'."""
    decision, quote = within_budget(candidate, _provider, budget)
    if decision is None:
        status = ("NO_BUDGET_GIVEN" if budget is None else "BUDGET_UNVERIFIED")
    elif decision:
        status = "WITHIN_BUDGET"
    else:
        status = "OVER_BUDGET"
    return {
        "status": status,
        "budget_coins": budget,
        "price_coins": quote.price_coins,
        "price_platform": quote.platform,
        "price_observed_at": quote.observed_at,
        "price_source_id": quote.source_id,
        "price_confidence": quote.confidence,
        "price_freshness": price_freshness(candidate),
    }


def value_assessment(candidate: Candidate, utility: Optional[float],
                     reference_floor: Optional[float] = None,
                     budget: Optional[int] = None) -> dict:
    """§14 value score = marginal contextual utility per verified cost.

    * `utility`          — contextual engine score (0..1) for THIS request.
    * `reference_floor`  — lowest utility among verified-price candidates in
                           the same position pool (the marginal baseline).
                           Falls back to 0.0 (absolute utility per cost).
    Returns a dict with status VALUE_SCORED / VALUE_UNAVAILABLE and the full
    evidence trail. Never OVR/price; OVR is not used anywhere here.
    """
    out: dict = {
        "status": "VALUE_UNAVAILABLE",
        "value_score": None,
        "utility": utility,
        "reference_floor": reference_floor,
        "method": ("marginal contextual utility per "
                   f"{ec.VALUE_PRICE_UNIT:,} verified coins"),
        "reason": None,
        "budget": budget_status(candidate, budget) if budget is not None else None,
    }
    q = _provider.price_for(candidate)
    if not q.known:
        out["reason"] = ("no verified price observation for this card — value "
                         "cannot be computed and is not estimated (§13/§14)")
        return out
    if not (q.source_id or q.observed_at):
        out["reason"] = "price lacks provenance — treated as unverified"
        return out
    if utility is None:
        out["reason"] = "no contextual utility for this request — value is contextual"
        return out
    floor = reference_floor if reference_floor is not None else 0.0
    marginal = max(float(utility) - float(floor), 0.0)
    price = max(int(q.price_coins or 0), ec.VALUE_MIN_PRICE_COINS)
    score = marginal / (price / ec.VALUE_PRICE_UNIT)
    out.update({
        "status": "VALUE_SCORED",
        "value_score": round(score, 6),
        "price_coins": q.price_coins,
        "price_platform": q.platform,
        "price_observed_at": q.observed_at,
        "price_source_id": q.source_id,
        "price_freshness": price_freshness(candidate),
    })
    return out


def value_rank(pool: list[Candidate], utilities: dict[uuid.UUID, float],
               budget: Optional[int] = None) -> list[dict]:
    """Rank verified-price candidates by contextual value (§14/§17).

    Candidates without verified prices are returned with VALUE_UNAVAILABLE
    (never ranked as if free, never ranked as if worthless).
    """
    scored = [(c, utilities.get(c.entity_id)) for c in pool]
    priced_utils = [u for c, u in scored if is_verified_price(c) and u is not None]
    floor = min(priced_utils) if priced_utils else None
    out = []
    for c, u in scored:
        assessment = value_assessment(c, u, reference_floor=floor, budget=budget)
        out.append({
            "entity_id": str(c.entity_id),
            "name": c.name,
            "entity_type": c.entity_type,
            **assessment,
        })
    out.sort(key=lambda r: (r["value_score"] is None,
                            -(r["value_score"] or 0.0), r["name"]))
    return out


# --------------------------------------------------------------------- history
def price_history(ut_card_id: uuid.UUID, limit: int = 100) -> dict:
    """§48: only observations that exist. Never interpolated, never
    back-filled. Empty history is reported honestly."""
    from backend.core.db import query
    rows = query(
        """SELECT cp.price_coins, cp.platform, cp.observed_at, cp.confidence,
                  cp.source_id, cp.currency, so.source_id AS observation_source,
                  so.retrieval_context
           FROM card_price cp
           LEFT JOIN source_observation so ON so.id = cp.source_observation_id
           WHERE cp.ut_card_id = %s
           ORDER BY cp.observed_at DESC
           LIMIT %s""",
        (ut_card_id, int(limit)))
    history = [{
        "price_coins": r["price_coins"],
        "platform": r["platform"],
        "observed_at": r["observed_at"].isoformat() if r["observed_at"] else None,
        "confidence": float(r["confidence"]) if r["confidence"] is not None else None,
        "source_id": r["source_id"] or r["observation_source"],
        "currency": r["currency"],
        "retrieval_context": r["retrieval_context"],
    } for r in rows]
    return {
        "ut_card_id": str(ut_card_id),
        "observations": len(history),
        "status": "HAS_HISTORY" if history else "NO_PRICE_HISTORY",
        "history": history,
        "note": None if history else (
            "no price observations persisted for this card — history is never "
            "manufactured (§48)"),
    }
