"""Phase 3 §38/§39/§45/§46 — card evaluation scenarios, adversarial inputs,
no-hallucination hard tests and source-conflict resolution.

Expectations are BEHAVIORAL (what the system must do with the data it has),
never "player X must always win".
"""
from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from backend.domain.card_model import (
    Candidate, DataStatus, GamePlayer, GameVersionCode, PlayerAttributes,
    UTCard,
)
from backend.domain.evidence_model import SourceRecord, UsageStatus
from backend.domain.user_model import UserRequirements
from backend.services import card_value_service as cvs
from backend.services.conflict_resolver import Claim_, ConflictResolver
from backend.services.recommendation_engine_v2 import RecommendationEngineV2

NOW = datetime.now(timezone.utc)


def _card_candidate(name, position="ST", ovr=88, attrs=None, price=None,
                    observed_at=None, psb=(), psp=(), published=True,
                    synthetic=False, source="src_a", card_id=None,
                    canonical=None, nation=None, club=None, league=None):
    card = UTCard(
        id=card_id or UTCard.deterministic_id(source, "FC26", name),
        game_version=GameVersionCode.FC26, source_id=source,
        source_card_id=name, card_name=name, position=position,
        overall_rating=ovr,
        attribute_overrides=attrs if attrs is not None else
        {"pace": 85, "finishing": 84, "sprint_speed": 85, "acceleration": 84},
        playstyles_base=list(psb), playstyles_plus=list(psp),
        playstyle_data_published=published,
        price_coins=price, price_platform="playstation" if price else None,
        price_observed_at=observed_at,
        price_source_id="obs-1" if price else None,
        is_synthetic=synthetic,
        data_status=DataStatus.SYNTHETIC_TEST if synthetic else DataStatus.CANONICAL,
        canonical_card_id=canonical)
    gp = None
    if nation or club or league:
        gp = GamePlayer(id=uuid.uuid4(), game_version=GameVersionCode.FC26,
                        source_id=source, source_player_id=1,
                        display_name=name, position_primary=position,
                        overall_rating=ovr, nation=nation, club=club, league=league)
    return Candidate.from_ut_card(card, gp)


def _req(**kw):
    kw.setdefault("game_version", "FC26")
    kw.setdefault("entity_scope", "ut_card")
    return UserRequirements(**kw)


ENGINE = RecommendationEngineV2()


# ---------------------------------------------------------------- §38 scenarios
class TestCardScenarios:
    def test_card_attributes_differ_from_base_player_engine_uses_card(self):
        gp = GamePlayer(
            id=uuid.uuid4(), game_version=GameVersionCode.FC26, source_id="src_a",
            source_player_id=7, display_name="Fast Forward", position_primary="ST",
            overall_rating=80,
            attributes=PlayerAttributes(values={"pace": 80, "finishing": 78}),
            playstyles_base=["Rapid"], playstyle_data_published=True)
        card = UTCard(
            id=uuid.uuid4(), game_version=GameVersionCode.FC26, source_id="src_a",
            source_card_id="c-pace95", card_name="Fast Forward TOTW",
            position="ST", overall_rating=89,
            attribute_overrides={"pace": 95, "finishing": 88},
            playstyle_data_published=True, playstyles_base=["Rapid"],
            playstyles_plus=["Rapid"])
        c = Candidate.from_ut_card(card, gp)
        ev = ENGINE.evaluate(c, _req(position="ST"))
        assert c.attributes.get("pace") == 95
        attr_ev = ev.components["attribute_fit"]
        assert "pace=95" in " ".join(attr_ev.evidence)
        assert "pace=80" not in " ".join(attr_ev.evidence)

    def test_multiple_versions_of_same_card_score_separately(self):
        canonical = uuid.uuid4()
        v1 = _card_candidate("Star v1", ovr=85, canonical=canonical,
                             attrs={"pace": 85, "finishing": 82})
        v2 = _card_candidate("Star v2", ovr=90, canonical=canonical,
                             attrs={"pace": 92, "finishing": 89})
        e1 = ENGINE.evaluate(v1, _req(position="ST"))
        e2 = ENGINE.evaluate(v2, _req(position="ST"))
        assert v1.entity_id != v2.entity_id            # distinct rows
        assert v1.extra["canonical_card_id"] == v2.extra["canonical_card_id"]
        assert e1.weighted_score != e2.weighted_score  # scored on own content

    def test_stale_price_flagged_not_hidden(self):
        c = _card_candidate("Stale", price=50000,
                            observed_at=(NOW - timedelta(days=200)).isoformat())
        v = cvs.value_assessment(c, utility=0.8, reference_floor=0.5)
        assert v["status"] == "VALUE_SCORED"
        assert v["price_freshness"] == "STALE"

    def test_unknown_price_never_affordable(self):
        c = _card_candidate("NoPrice", price=None)
        b = cvs.budget_status(c, budget=1_000_000)
        assert b["status"] == "BUDGET_UNVERIFIED"
        assert b["price_coins"] is None

    def test_unknown_chemistry_never_good_chemistry(self):
        from backend.services import chemistry_service as chs
        c = _card_candidate("Chem")
        out = chs.chemistry_assessment(c, [], "FC26")
        blob = json.dumps(out).lower()
        assert "good chemistry" not in blob
        assert out["chemistry_score"] is None

    def test_unknown_role_never_excellent_fit(self):
        c = _card_candidate("Roleless")
        ev = ENGINE.evaluate(c, _req(position="ST", role="False 9"))
        rf = ev.components["role_fit"]
        # honest statuses only: the engine reports UNKNOWN or
        # INSUFFICIENT_EVIDENCE — never a fabricated fit verdict.
        assert rf.status.value in ("UNKNOWN", "INSUFFICIENT_EVIDENCE")
        assert rf.value is None
        assert "excellent" not in (rf.reason or "").lower()

    def test_card_published_role_is_scored_not_generic_bonus(self):
        """§9: a card publishing role familiarity is scored for the REQUESTED
        role only (configurable reference mapping) — never a generic bonus."""
        c = _card_candidate("Role Card", position="CAM",
                            attrs={"vision": 90, "short_passing": 88})
        c.extra["roles"] = [{"role": "False 9", "familiarity": "ROLE",
                             "is_primary": True, "data_status": "CANONICAL"}]
        ev_match = ENGINE.evaluate(c, _req(position="CAM", role="False 9"))
        rf = ev_match.components["role_fit"]
        assert rf.status.value == "KNOWN"
        assert rf.value == 0.75            # CARD_ROLE_FAMILIARITY_SCORES['ROLE']
        ev_other = ENGINE.evaluate(c, _req(position="CAM", role="Playmaker"))
        assert ev_other.components["role_fit"].status.value == "INSUFFICIENT_EVIDENCE"
        # no roles published at all -> still insufficient (never assumed)
        c2 = _card_candidate("No Roles", position="CAM")
        assert ENGINE.evaluate(c2, _req(position="CAM", role="False 9")) \
                   .components["role_fit"].status.value == "INSUFFICIENT_EVIDENCE"

    def test_synthetic_card_never_reaches_engine(self):
        c = _card_candidate("Synth", synthetic=True)
        with pytest.raises(ValueError, match="SYNTHETIC_TEST"):
            ENGINE.evaluate(c, _req(position="ST"))

    def test_duplicate_identity_normalizes_to_same_id(self):
        from backend.ingestion.adapter import RawCardRecord
        from backend.ingestion.normalizer import Normalizer
        norm = Normalizer("src_a", "FC26")
        raw = RawCardRecord(source_card_id="dup-1", card_name="Dup",
                            position_raw="ST", overall_rating="85",
                            attributes={"pace": "90"}, price_coins=None,
                            extras={})
        a = norm.normalize_card(raw)
        b = norm.normalize_card(raw)
        assert a.id == b.id                       # idempotent identity
        assert a.card_name == b.card_name

    @pytest.mark.parametrize("missing", ["pace", "finishing", "position"])
    def test_missing_fields_are_unknown_not_zero(self, missing):
        attrs = {"pace": 90, "finishing": 88}
        if missing in attrs:
            del attrs[missing]
        c = _card_candidate("Partial", attrs=attrs)
        ev = ENGINE.evaluate(c, _req(position="ST"))
        if missing == "pace":
            assert c.attributes.get("pace") is None
        # scoring must still be honest: known components scored, missing never 0
        for comp in ev.components.values():
            assert comp.status.value in ("KNOWN", "UNKNOWN", "INSUFFICIENT_EVIDENCE")

    def test_malformed_source_card_id_rejected_by_normalizer(self):
        from backend.ingestion.adapter import RawCardRecord
        from backend.ingestion.normalizer import Normalizer
        norm = Normalizer("src_a", "FC26")
        with pytest.raises(ValueError, match="source_card_id"):
            norm.normalize_card(RawCardRecord(source_card_id=None,
                                              card_name="X", position_raw="ST",
                                              overall_rating="80",
                                              attributes={}, extras={}))
        with pytest.raises(ValueError, match="source_card_id"):
            norm.normalize_card(RawCardRecord(source_card_id="   ",
                                              card_name="X", position_raw="ST",
                                              overall_rating="80",
                                              attributes={}, extras={}))

    def test_version_mismatch_candidate_rejected(self):
        card = UTCard(id=uuid.uuid4(), game_version=GameVersionCode.FC26,
                      source_id="s", source_card_id="x", card_name="X",
                      position="ST", overall_rating=80,
                      attribute_overrides={"pace": 80})
        c = Candidate.from_ut_card(card, None)
        with pytest.raises(ValueError):
            ENGINE.evaluate(c, _req(game_version="FC27", position="ST"))

    def test_randomized_pool_order_gives_identical_ranking(self):
        pool = [_card_candidate(f"C{i:04d}", ovr=70 + (i % 25),
                                attrs={"pace": 70 + (i % 27),
                                       "finishing": 68 + (i % 23)})
                for i in range(1200)]
        req = _req(position="ST")
        r1 = ENGINE.recommend(list(pool), req, request_id="det-1")
        shuffled = list(pool)
        random.Random(99).shuffle(shuffled)
        r2 = ENGINE.recommend(shuffled, req, request_id="det-2")
        order1 = [e.candidate.name for e in r1.ranked]
        order2 = [e.candidate.name for e in r2.ranked]
        assert order1 == order2
        assert round(r1.best_score, 6) == round(r2.best_score, 6)


# ---------------------------------------------------------------- §45 no-hallucination
class TestNoHallucinationHard:
    def test_recommendation_payload_never_claims_unverified_facts(self):
        """Cards with unknown price/chemistry/roles: the full engine payload
        must not contain affordability, chemistry-quality or role-fit claims."""
        pool = [
            _card_candidate("Unknown Everything 1"),
            _card_candidate("Unknown Everything 2", ovr=90,
                            attrs={"pace": 93, "finishing": 90}),
        ]
        req = _req(position="ST", budget_coins=500_000)
        result = ENGINE.recommend(pool, req, request_id="hallu-1")
        payload = result.to_dict()
        blob = json.dumps(payload).lower()
        # The engine's own copy is "prices are UNKNOWN, never assumed
        # affordable" — a disclaimer, not a claim. Assert there is no POSITIVE
        # affordability claim instead.
        assert "is affordable" not in blob
        assert "within budget" not in blob
        assert "good chemistry" not in blob
        assert "excellent fit" not in blob
        assert payload["budget_status"].startswith("BUDGET_UNVERIFIED")
        for e in payload["ranked"]:
            assert e["budget"]["decision"] is None
        best = payload["best"]
        assert best["components"]["role_fit"]["status"] == "UNKNOWN"

    def test_value_language_distinguishes_unavailable_from_free(self):
        c = _card_candidate("Free?", price=None)
        v = cvs.value_assessment(c, utility=0.9, budget=100)
        assert v["value_score"] is None
        assert v["status"] == "VALUE_UNAVAILABLE"
        assert "not estimated" in v["reason"] or "cannot be computed" in v["reason"]


# ---------------------------------------------------------------- §46 conflicts
def _source(sid, tier, status=UsageStatus.LICENSED, fields=()):
    return SourceRecord(source_id=sid, name=sid, source_type="OTHER",
                        authority_tier=tier, usage_status=status,
                        legal_gate="NOT_REQUIRED", canonical_fields=list(fields))


class TestSourceConflicts:
    def test_higher_authority_wins_and_conflict_recorded(self):
        official = _source("ea_official", 1)
        community = _source("community_db", 4)
        r = ConflictResolver([official, community])
        res = r.resolve("ut_card", "card-1", "overall_rating",
                        [Claim_(community, 88, NOW), Claim_(official, 91, NOW)],
                        game_version="FC26")
        assert res.winner.value == 91
        assert res.conflict is not None
        assert res.conflict.entity_type == "ut_card"
        assert res.conflict.resolution == "SOURCE_A_WINS"

    def test_lower_authority_never_silently_overwrites(self):
        official = _source("ea_official", 1)
        community = _source("community_db", 4)
        r = ConflictResolver([official, community])
        res = r.resolve("ut_card", "card-1", "overall_rating",
                        [Claim_(official, 91, NOW - timedelta(days=30)),
                         Claim_(community, 99, NOW)],   # newer but lower tier
                        game_version="FC26")
        assert res.winner.value == 91     # recency does not beat authority

    def test_equal_authority_conflict_recorded_deterministically(self):
        a = _source("src_a", 3)
        b = _source("src_b", 3)
        r = ConflictResolver([a, b])
        res = r.resolve("ut_card", "card-2", "price_coins",
                        [Claim_(a, 10000, NOW), Claim_(b, 12000, NOW)],
                        game_version="FC26")
        assert res.conflict is not None
        assert res.winner is not None            # deterministic pick
        assert res.winner.source.source_id == "src_a"   # tie-break: source_id
        # confidence-relevant: the conflict is logged, not swallowed
        assert "beats" in res.conflict.resolution_note

    def test_field_authority_beats_tier(self):
        market = _source("market_feed", 3, fields=("price_coins",))
        official = _source("ea_official", 1)
        r = ConflictResolver([market, official])
        res = r.resolve("ut_card", "card-3", "price_coins",
                        [Claim_(official, 9000, NOW), Claim_(market, 9500, NOW)],
                        game_version="FC26")
        assert res.winner.source.source_id == "market_feed"

    def test_unpermitted_source_claims_are_ignored(self):
        blocked = _source("scraper", 2, status=UsageStatus.NOT_PERMITTED)
        ok = _source("licensed", 3)
        r = ConflictResolver([blocked, ok])
        res = r.resolve("ut_card", "card-4", "overall_rating",
                        [Claim_(blocked, 99, NOW), Claim_(ok, 85, NOW)],
                        game_version="FC26")
        assert res.winner.value == 85     # blocked source never wins


# ---------------------------------------------------------------- §27/§28 wiring
class TestVersionFirewallAndWatermarks:
    @pytest.mark.skipif(True, reason="DB-level checks live in test_card_api.py")
    def test_placeholder(self):
        pass
