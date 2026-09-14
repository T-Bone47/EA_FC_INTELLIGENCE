"""MANDATORY §50 — THE OVR TRAP.

The engine must be able to pick a LOWER-OVR player when the fit evidence says
so, and it must NOT have a reverse bias either: with equal fit, higher OVR
still wins (overall_quality is a legitimate 0.15-weight component, never the
decider by itself).

Covers:
  * synthetic trap (deterministic, DB-free)
  * real-data trap against the live FC26 pool (requires DB)
  * fairness: names/clubs/nations/fame never enter the score
"""
from __future__ import annotations

import pytest

from backend.domain.user_model import AttributePreference
from backend.services import engine_evaluation
from backend.services.recommendation_engine_v2 import RecommendationEngineV2

from .conftest import requires_db
from .helpers import make_attrs, make_candidate, make_req

CM_FULL = dict(short_passing=86, vision=84, long_passing=82, stamina=88,
               ball_control=84, composure=85, defensive_awareness=78,
               interceptions=75, positioning=78, dribbling_detail=80,
               acceleration=74, sprint_speed=72, strength=80, aggression=76,
               reactions=82, long_shots=76, curve=74)


@pytest.fixture()
def engine():
    return RecommendationEngineV2()


class TestSyntheticOvrTrap:
    def test_lower_ovr_wins_on_fit(self, engine):
        """§50 mandatory: 81-OVR worker beats 90-OVR star for a pressing CM
        job — decided by SOFT fit (no hard minimums in this request)."""
        pool, req = engine_evaluation.ovr_trap_pool()
        res = engine.recommend(pool, req)
        assert res.best_evaluation is not None
        assert res.best_evaluation.candidate.name == "League Worker"
        assert res.best_evaluation.candidate.overall_rating == 81
        loser = next(e for e in res.ranked if e.candidate.name == "Famous Star")
        assert loser.candidate.overall_rating == 90
        # the trap candidate is never hidden — he is ranked with reasons
        assert loser.weighted_score < res.best_evaluation.weighted_score

    def test_what_decided_the_trap(self, engine):
        """Evidence must show attribute/tactical fit as the differentiator and
        overall_quality as the (outvoted) OVR signal."""
        pool, req = engine_evaluation.ovr_trap_pool()
        res = engine.recommend(pool, req)
        win = res.best_evaluation
        lose = next(e for e in res.ranked if e.candidate.name == "Famous Star")
        # OVR component DOES favor the star...
        assert win.components["overall_quality"].value < \
               lose.components["overall_quality"].value
        # ...but attribute + tactical fit overrule it
        assert win.components["attribute_fit"].value > \
               lose.components["attribute_fit"].value + 0.15
        assert win.components["tactical_fit"].value > \
               lose.components["tactical_fit"].value + 0.15

    def test_no_reverse_bias_higher_ovr_wins_equal_fit(self, engine):
        """Same attributes, same fit: the higher-OVR candidate must win —
        overall_quality is a real (0.15) component, not noise."""
        a = make_candidate(name="Same A", ovr=84, attrs=make_attrs(**CM_FULL))
        b = make_candidate(name="Same B", ovr=87, attrs=make_attrs(**CM_FULL))
        res = engine.recommend([a, b], make_req(position="CM"))
        assert res.best_evaluation.candidate.name == "Same B"

    def test_one_ovr_point_does_not_flip_clear_fit(self, engine):
        """±1 OVR robustness: a clear fit winner stays the winner when the
        trap candidate gains one OVR point."""
        pool, req = engine_evaluation.ovr_trap_pool()
        pool[0].overall_rating = 91          # Famous Star 90 -> 91
        res = engine.recommend(pool, req)
        assert res.best_evaluation.candidate.name == "League Worker"


class TestFairness:
    def test_name_club_nation_do_not_affect_score(self, engine):
        base = make_candidate(name="A", ovr=85, attrs=make_attrs(**CM_FULL),
                              club="C", league="L", nation="N")
        famous = make_candidate(name="Lionel Famous III", ovr=85,
                                attrs=make_attrs(**CM_FULL),
                                club="Real Glamour", league="Star League",
                                nation="Famousland")
        ev_a = engine.evaluate(base, make_req(position="CM"))
        ev_b = engine.evaluate(famous, make_req(position="CM"))
        assert ev_a.weighted_score == pytest.approx(ev_b.weighted_score, abs=1e-12)

    def test_price_does_not_enter_fit_score(self, engine):
        cheap = make_candidate(name="Cheap", ovr=85, attrs=make_attrs(**CM_FULL),
                               price=1_000)
        pricey = make_candidate(name="Pricey", ovr=85, attrs=make_attrs(**CM_FULL),
                                price=9_000_000)
        req = make_req(position="CM")     # NO budget => price irrelevant
        ev_a = engine.evaluate(cheap, req)
        ev_b = engine.evaluate(pricey, req)
        assert ev_a.weighted_score == pytest.approx(ev_b.weighted_score, abs=1e-12)


@requires_db
class TestRealDataOvrTrap:
    def test_engine_inverts_ovr_on_real_pool(self):
        """Real FC26 pool: for a defensive CDM-style CM job, the best fit is
        NOT the highest-OVR candidate available."""
        from backend.data_access.candidate_repository import CandidateRepository
        repo = CandidateRepository()
        pool = repo.load_for_position("FC26", "CM", include_adjacent=True)
        assert pool, "expected the live FC26 canonical pool"
        max_ovr = max(c.overall_rating or 0 for c in pool)
        from backend.domain.user_model import UserRequirements
        r = UserRequirements(
            game_version="FC26", position="CM", tactical_profile="LOW_BLOCK",
            attribute_preferences=[
                AttributePreference("interceptions", min_value=85, weight=3.0),
                AttributePreference("defensive_awareness", weight=2.0),
                AttributePreference("standing_tackle", weight=1.5)],
            limit=10)
        res = RecommendationEngineV2().recommend(pool, r)
        win = res.best_evaluation
        assert win is not None
        # the winner is a better fit, not the OVR king
        assert (win.candidate.overall_rating or 0) < max_ovr
        # and at least one lower-OVR candidate outranks a higher-OVR one
        ovr_seq = [e.candidate.overall_rating or 0 for e in res.ranked]
        assert any(ovr_seq[i] < ovr_seq[j]
                   for i in range(len(ovr_seq)) for j in range(i + 1, len(ovr_seq))), \
            "expected an OVR inversion inside the top-10 (fit beats OVR)"
