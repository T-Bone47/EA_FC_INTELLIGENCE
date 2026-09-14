"""Budget / market price providers.

No legitimate live market source is available => NullBudgetProvider is the
production default: every price is UNKNOWN. Budget filtering degrades to a
transparent no-op that is reported in the recommendation metadata, so the
product never silently pretends to enforce a budget it cannot verify.

Prices are NEVER fabricated (§21). When a verified market feed exists, a real
provider implements price_for() and budget enforcement activates automatically.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional, Protocol

from backend.domain.card_model import Candidate


@dataclass(frozen=True)
class PriceQuote:
    price_coins: Optional[int]          # None = UNKNOWN
    platform: Optional[str]
    observed_at: Optional[str]
    source_id: Optional[str]
    confidence: Optional[float]

    @property
    def known(self) -> bool:
        return self.price_coins is not None


class BudgetProvider(Protocol):
    name: str

    def price_for(self, candidate: Candidate) -> PriceQuote: ...


class NullBudgetProvider:
    """No market data: every price UNKNOWN. This is the honest default."""
    name = "null"

    def price_for(self, candidate: Candidate) -> PriceQuote:
        if candidate.price_coins is not None:
            # candidate carries a persisted, provenance-backed price observation
            return PriceQuote(
                price_coins=candidate.price_coins,
                platform=candidate.extra.get("price_platform"),
                observed_at=candidate.extra.get("price_observed_at"),
                source_id=candidate.extra.get("price_source_id"),
                confidence=candidate.extra.get("price_confidence"),
            )
        return PriceQuote(None, None, None, None, None)


def within_budget(candidate: Candidate, provider: BudgetProvider,
                  budget: Optional[int]) -> tuple[Optional[bool], PriceQuote]:
    """Returns (decision, quote). decision None = UNKNOWN (cannot verify)."""
    quote = provider.price_for(candidate)
    if budget is None:
        return None, quote
    if not quote.known:
        return None, quote           # UNKNOWN price -> cannot decide, never assume affordable
    return quote.price_coins <= budget, quote
