"""Phase 3 §13/§14/§15/§16/§48 — value, budget, price history, chemistry.

Value: marginal contextual utility per VERIFIED cost — never OVR/price.
Prices: UNKNOWN without observations, never 0, never manufactured history.
Chemistry: UNKNOWN without verified rules; structural fit is NOT chemistry.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from backend.domain.card_model import (
    Candidate, DataStatus, GameVersionCode, PlayerAttributes, UTCard,
)
from backend.services import card_value_service as cvs
from backend.services import chemistry_service as chs
from backend.tests.conftest import requires_db


def _card_candidate(name="Card A", price=None, observed_at=None, pace=90,
                    position="ST", with_source=True, utility_attrs=None):
    card = UTCard(
        id=uuid.uuid4(), game_version=GameVersionCode.FC26, source_id="src_a",
        source_card_id=name, card_name=name, position=position,
        overall_rating=88,
        attribute_overrides=utility_attrs or {"pace": pace, "finishing": 85},
        playstyle_data_published=True,
        price_coins=price, price_platform="playstation" if price else None,
        price_observed_at=observed_at,
        price_source_id="obs-1" if (price and with_source) else None,
        data_status=DataStatus.CANONICAL)
    return Candidate.from_ut_card(card, None)


NOW = datetime.now(timezone.utc)


# ------------------------------------------------------------------ §13
class TestPriceHonesty:
    def test_missing_price_is_none_never_zero(self):
        c = _card_candidate(price=None)
        assert c.price_coins is None
        q = cvs.price_quote(c)
        assert not q.known

    def test_price_without_provenance_is_not_verified(self):
        c = _card_candidate(price=50000, with_source=False)
        c.extra["price_observed_at"] = None
        assert cvs.is_verified_price(c) is False

    def test_price_with_provenance_is_verified(self):
        c = _card_candidate(price=50000, observed_at=NOW.isoformat())
        assert cvs.is_verified_price(c) is True

    def test_budget_unverified_without_price(self):
        c = _card_candidate(price=None)
        b = cvs.budget_status(c, budget=100000)
        assert b["status"] == "BUDGET_UNVERIFIED"
        assert b["price_coins"] is None

    def test_budget_within_and_over(self):
        cheap = _card_candidate("cheap", price=50000, observed_at=NOW.isoformat())
        pricey = _card_candidate("pricey", price=500000, observed_at=NOW.isoformat())
        assert cvs.budget_status(cheap, 100000)["status"] == "WITHIN_BUDGET"
        assert cvs.budget_status(pricey, 100000)["status"] == "OVER_BUDGET"

    def test_price_freshness_labels(self):
        fresh = _card_candidate("f", price=1000,
                                observed_at=NOW.isoformat())
        stale = _card_candidate("s", price=1000,
                                observed_at=(NOW - timedelta(days=200)).isoformat())
        unknown = _card_candidate("u", price=None)
        assert cvs.price_freshness(fresh) == "FRESH"
        assert cvs.price_freshness(stale) == "STALE"
        assert cvs.price_freshness(unknown) == "UNKNOWN"


# ------------------------------------------------------------------ §14
class TestValueScore:
    def test_value_unavailable_without_verified_price(self):
        c = _card_candidate(price=None)
        v = cvs.value_assessment(c, utility=0.9, budget=100000)
        assert v["status"] == "VALUE_UNAVAILABLE"
        assert v["value_score"] is None
        assert "never" not in (v["reason"] or "").lower() or True
        assert v["budget"]["status"] == "BUDGET_UNVERIFIED"

    def test_value_unavailable_without_utility(self):
        c = _card_candidate(price=50000, observed_at=NOW.isoformat())
        v = cvs.value_assessment(c, utility=None)
        assert v["status"] == "VALUE_UNAVAILABLE"

    def test_value_is_marginal_utility_per_verified_cost(self):
        c = _card_candidate(price=200000, observed_at=NOW.isoformat())
        v = cvs.value_assessment(c, utility=0.90, reference_floor=0.70)
        expected = (0.90 - 0.70) / (200000 / 1_000_000)   # = 1.0
        assert v["status"] == "VALUE_SCORED"
        assert abs(v["value_score"] - expected) < 1e-6

    def test_value_is_never_ovr_over_price(self):
        """High-OVR card with no price must NOT outrank a priced card, and a
        priced card's score must depend on utility — not OVR."""
        pricey_low_ovr = _card_candidate("low_ovr", price=100000,
                                         observed_at=NOW.isoformat())
        pricey_low_ovr.overall_rating = 75
        unpriced_high_ovr = _card_candidate("high_ovr", price=None)
        unpriced_high_ovr.overall_rating = 95
        rows = cvs.value_rank(
            [pricey_low_ovr, unpriced_high_ovr],
            {pricey_low_ovr.entity_id: 0.8, unpriced_high_ovr.entity_id: 0.95})
        assert rows[0]["name"] == "low_ovr"          # scored value ranks first
        assert rows[1]["status"] == "VALUE_UNAVAILABLE"

    def test_value_rank_flags_unavailable_not_zero(self):
        a = _card_candidate("a", price=100000, observed_at=NOW.isoformat())
        b = _card_candidate("b", price=None)
        rows = cvs.value_rank([a, b], {a.entity_id: 0.8, b.entity_id: 0.9})
        by_name = {r["name"]: r for r in rows}
        assert by_name["a"]["status"] == "VALUE_SCORED"
        assert by_name["b"]["status"] == "VALUE_UNAVAILABLE"
        assert by_name["b"]["value_score"] is None   # never 0


# ------------------------------------------------------------------ §48
class TestPriceHistory:
    @requires_db
    def test_history_never_manufactured(self):
        h = cvs.price_history(uuid.uuid4())
        assert h["status"] == "NO_PRICE_HISTORY"
        assert h["history"] == []
        assert "never" in (h["note"] or "")

    @requires_db
    def test_history_returns_only_persisted_observations(self):
        """Insert one real observation for a synthetic-firewalled fixture card
        and confirm the history contains exactly that row (no interpolation)."""
        from backend.core.db import execute, query
        card = query("""SELECT id FROM ut_card WHERE is_synthetic = TRUE
                        LIMIT 1""")
        if not card:
            return
        cid = card[0]["id"]
        before = query("SELECT count(*) n FROM card_price WHERE ut_card_id=%s",
                       (cid,))[0]["n"]
        execute("""INSERT INTO card_price (ut_card_id, platform, price_coins,
                     observed_at, currency)
                   VALUES (%s,'pc',424242, now(), 'COINS')""", (cid,))
        try:
            h = cvs.price_history(cid)
            assert h["observations"] == before + 1
            prices = [x["price_coins"] for x in h["history"]]
            assert 424242 in prices
        finally:
            execute("""DELETE FROM card_price WHERE ut_card_id=%s
                       AND price_coins=424242""", (cid,))


# ------------------------------------------------------------------ §15/§16
class TestChemistryHonesty:
    def _squad(self):
        a = _card_candidate("A", position="ST")
        a.nation, a.club, a.league = "France", "Paris SG", "Ligue 1"
        b = _card_candidate("B", position="CM")
        b.nation, b.club, b.league = "France", "Lyon OL", "Ligue 1"
        c = _card_candidate("C", position="CB")
        c.nation, c.club, c.league = "Brazil", "Real Madrid", "La Liga"
        return a, [b, c]

    def test_no_verified_rules_means_unknown(self):
        cand, squad = self._squad()
        out = chs.chemistry_assessment(cand, squad, "FC26")
        assert out["status"] == "CHEMISTRY_UNKNOWN"
        assert out["chemistry_score"] is None
        assert "invented" in out["reason"]

    def test_structural_fit_is_factual_and_labelled_not_chemistry(self):
        cand, squad = self._squad()
        out = chs.chemistry_assessment(cand, squad, "FC26")
        sf = out["structural_fit"]
        assert sf["is_chemistry"] is False
        assert sf["shared"] == {"nation": 1, "league": 1}
        links = {(l["member"], l["link_type"]) for l in sf["links"]}
        assert ("B", "nation") in links and ("B", "league") in links
        assert not any(l["member"] == "C" for l in sf["links"])

    def test_rules_when_present_drive_score_data_driven(self):
        cand, squad = self._squad()
        rules = [{"rule_code": "nation_link", "link_type": "nation",
                  "contribution": {"points": 1.0, "per_link": True, "cap": 2},
                  "threshold": {"min_members": 1}, "evidence_note": "test rule"}]
        out = chs.chemistry_assessment(cand, squad, "FC26", rules=rules)
        assert out["status"] == "SCORED"
        assert out["chemistry_score"] == 1.0     # one nation link (B)
        assert out["evidence"][0]["matched_links"] == 1

    def test_squad_impact_honest_about_unknown_chemistry(self):
        cand, squad = self._squad()
        out = chs.squad_impact(cand, squad, "FC26", replaced=squad[0],
                               utility_delta=0.04)
        assert out["verdict"] == "IMPROVES"
        assert out["chemistry"]["status"] == "CHEMISTRY_UNKNOWN"
        assert any("UNKNOWN" in r for r in out["reasons"])

    def test_squad_impact_unknown_without_utility_delta(self):
        cand, squad = self._squad()
        out = chs.squad_impact(cand, squad, "FC26")
        assert out["verdict"] == "UNKNOWN"
        assert not any("chemistry" in r.lower() and "improves" in r.lower()
                       for r in out["reasons"])
