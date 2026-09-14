"""§56-§58 — ROBUSTNESS, ADVERSARIAL INPUTS, ENGINE SAFETY.

The engine must never crash on malformed / missing / conflicting / empty input,
must be deterministic (no hidden randomness, input order irrelevant), and must
be stable under ±1 rating perturbations.
"""
from __future__ import annotations

import copy
import json
import random
import uuid

import pytest

from backend.domain.card_model import DataStatus
from backend.domain.user_model import AttributeBand, UserRequirements
from backend.services.recommendation_engine_v2 import RecommendationEngineV2

from .helpers import make_attrs, make_candidate, make_req

CM_FULL = dict(short_passing=86, vision=84, long_passing=82, stamina=88,
               ball_control=84, composure=85, defensive_awareness=78,
               interceptions=75, positioning=78, dribbling_detail=80,
               acceleration=74, sprint_speed=72, strength=80, aggression=76,
               reactions=82, long_shots=76, curve=74)


@pytest.fixture()
def engine():
    return RecommendationEngineV2()


class TestDeterminism:
    def test_same_input_same_output(self, engine):
        pool = [make_candidate(name=f"P{i}", ovr=80 + i % 8,
                               attrs=make_attrs(**CM_FULL)) for i in range(12)]
        req = make_req(position="CM", tactical_profile="PRESSING")
        a = engine.recommend(copy.deepcopy(pool), req).to_dict()
        b = engine.recommend(copy.deepcopy(pool), req).to_dict()
        a.pop("request_id"); b.pop("request_id")
        assert json.dumps(a, sort_keys=True, default=str) == \
               json.dumps(b, sort_keys=True, default=str)

    def test_pool_order_irrelevant(self, engine):
        pool = [make_candidate(name=f"P{i}", ovr=80 + i % 8,
                               attrs=make_attrs(**CM_FULL)) for i in range(12)]
        req = make_req(position="CM", tactical_profile="PRESSING")
        forward = engine.recommend(list(pool), req)
        rng = random.Random(42)          # fixed seed: this is an input-shuffle
        shuffled = list(pool)            # test, not engine randomness
        rng.shuffle(shuffled)
        backward = engine.recommend(shuffled, req)
        assert [e.candidate.name for e in forward.ranked] == \
               [e.candidate.name for e in backward.ranked]

    def test_duplicate_entities_do_not_crash(self, engine):
        c = make_candidate(name="Twin", attrs=make_attrs(**CM_FULL))
        res = engine.recommend([c, c], make_req(position="CM"))
        assert len(res.ranked) == 2


class TestPerturbationStability:
    def _pool(self):
        strong = make_candidate(name="Strong Fit", ovr=84, attrs=make_attrs(
            **{**CM_FULL, "stamina": 93, "interceptions": 86,
               "defensive_awareness": 85, "aggression": 88}))
        weak = make_candidate(name="Weak Fit", ovr=88, attrs=make_attrs(
            **{**CM_FULL, "stamina": 60, "interceptions": 52,
               "defensive_awareness": 50, "aggression": 45}))
        return [strong, weak]

    def test_minus_one_ovr_keeps_ranking(self, engine):
        req = make_req(position="CM", tactical_profile="PRESSING")
        pool = self._pool()
        pool[0].overall_rating -= 1
        res = engine.recommend(pool, req)
        assert res.best_evaluation.candidate.name == "Strong Fit"

    def test_plus_one_ovr_keeps_ranking(self, engine):
        req = make_req(position="CM", tactical_profile="PRESSING")
        pool = self._pool()
        pool[1].overall_rating += 1
        res = engine.recommend(pool, req)
        assert res.best_evaluation.candidate.name == "Strong Fit"

    def test_plus_minus_one_attribute_keeps_ranking(self, engine):
        req = make_req(position="CM", tactical_profile="PRESSING")
        for delta in (-1, +1):
            pool = self._pool()
            pool[0].attributes.set("stamina", 93 + delta)
            res = engine.recommend(pool, req)
            assert res.best_evaluation.candidate.name == "Strong Fit", delta


class TestMalformedInput:
    def test_empty_strings_and_whitespace(self, engine):
        c = make_candidate(name="  ", position="CM", attrs=make_attrs(**CM_FULL))
        res = engine.recommend([c], make_req(position="CM"))
        assert res.ranked                      # scored, not crashed

    def test_none_ovr_is_survivable(self, engine):
        c = make_candidate(name="No OVR", ovr=None, attrs=make_attrs(**CM_FULL))
        res = engine.recommend([c], make_req(position="CM"))
        assert res.best_evaluation is not None
        oq = res.best_evaluation.components["overall_quality"]
        assert oq.status.value in ("UNKNOWN", "INSUFFICIENT_EVIDENCE")

    def test_garbage_requirements_rejected_before_scoring(self):
        r = UserRequirements(game_version="FC26", position="CM",
                             archetype="NOT_REAL", slot="ZZZ",
                             secondary_tactical_profile="BLITZ",
                             attribute_bands=[AttributeBand("stamina", "godlike")],
                             overall_quality_bias="extreme")
        problems = r.validate()
        assert len(problems) >= 4              # every bad field is caught

    def test_unknown_position_no_crash(self, engine):
        c = make_candidate(name="Odd", position="CM", attrs=make_attrs(**CM_FULL))
        res = engine.recommend([c], make_req(position="XYZ"))
        # position_fit is UNKNOWN/honest, engine still answers
        assert res.ranked or res.best is None  # either way: no exception

    def test_version_mismatch_guard(self, engine):
        c = make_candidate(name="FC25 ghost", version="FC26",
                           attrs=make_attrs(**CM_FULL))
        with pytest.raises(Exception):
            engine.evaluate(c, make_req(game_version="FC27", position="CM"))

    def test_synthetic_firewall(self, engine):
        c = make_candidate(name="Synthetic", attrs=make_attrs(**CM_FULL),
                           synthetic=True)
        with pytest.raises(ValueError) as exc:
            engine.evaluate(c, make_req(position="CM"))
        assert "SYNTHETIC" in str(exc.value)

    def test_data_status_firewall(self, engine):
        c = make_candidate(name="Tagged", attrs=make_attrs(**CM_FULL))
        c.data_status = DataStatus.SYNTHETIC_TEST
        with pytest.raises(ValueError):
            engine.evaluate(c, make_req(position="CM"))


class TestFeatureFlags:
    def test_counterfactuals_can_be_disabled(self, engine):
        pool = [make_candidate(name=f"P{i}", attrs=make_attrs(**CM_FULL))
                for i in range(3)]
        on = engine.recommend(pool, make_req(position="CM"))
        off = engine.recommend(pool, make_req(position="CM",
                                              disable_counterfactuals=True))
        assert on.counterfactuals is not None
        assert off.counterfactuals is None
        # disabling must not change scores (no hidden coupling)
        assert [round(e.weighted_score, 9) for e in on.ranked] == \
               [round(e.weighted_score, 9) for e in off.ranked]

    def test_intelligence_flags_off_is_legacy(self, engine):
        c = make_candidate(name="Legacy", attrs=make_attrs(**CM_FULL))
        req_plain = make_req(position="CM")
        req_flagged = make_req(position="CM", enable_interactions=False,
                               enable_saturation=False,
                               enable_playstyle_context=False)
        a = engine.evaluate(c, req_plain)
        b = engine.evaluate(c, req_flagged)
        assert a.weighted_score == pytest.approx(b.weighted_score, abs=1e-12)

    def test_limits_respected(self, engine):
        pool = [make_candidate(name=f"P{i}", attrs=make_attrs(**CM_FULL))
                for i in range(30)]
        for limit in (1, 5, 25):
            res = engine.recommend(pool, make_req(position="CM", limit=limit))
            assert len(res.ranked) == limit


class TestAdversarialRequests:
    def test_conflicting_constraints_reported_not_crashed(self, engine):
        """Budget below every price + min OVR above every rating: empty result
        with honest exclusion reasons."""
        pool = [make_candidate(name="Priced", ovr=70, price=900_000,
                               attrs=make_attrs(**CM_FULL))]
        req = make_req(position="CM", budget_coins=1000, min_overall=95)
        res = engine.recommend(pool, req)
        assert res.best is None
        assert res.excluded_hard

    def test_impossible_playstyle_requirement(self, engine):
        c = make_candidate(name="No Styles", attrs=make_attrs(**CM_FULL),
                           playstyles_base=[])
        req = make_req(position="CM", required_playstyles=["Tiki Taka"])
        res = engine.recommend([c], req)
        assert res.best is None
        assert any("Tiki Taka" in x["reason"] for x in res.excluded_hard)

    def test_unknown_required_playstyle_is_never_satisfied(self, engine):
        c = make_candidate(name="Unpublished", playstyle_published=False,
                           attrs=make_attrs(**CM_FULL))
        req = make_req(position="CM", required_playstyles=["Tiki Taka"])
        res = engine.recommend([c], req)
        # playstyle data unpublished -> cannot verify -> excluded from the
        # verified set with an honest 'cannot verify' reason, never included
        assert res.best is None
        reason = res.excluded_hard[0]["reason"].lower()
        assert "cannot verify" in reason or "unpublished" in reason or \
               "unknown" in reason

    def test_every_intelligence_flag_at_once(self, engine):
        """Kitchen-sink request: all v2.1 layers enabled simultaneously must
        produce a complete, consistent answer."""
        pool = [make_candidate(name=f"P{i}", ovr=80 + i,
                               attrs=make_attrs(**CM_FULL),
                               playstyles_base=["Tiki Taka", "Intercept"])
                for i in range(6)]
        req = make_req(
            position="CM", formation="4-2-3-1", slot="CAM",
            tactical_profile="HIGH_PRESS", secondary_tactical_profile="FAST_BUILD_UP",
            archetype="BOX_TO_BOX",
            attribute_bands=[AttributeBand("stamina", "excellent")],
            enable_interactions=True, enable_saturation=True,
            enable_playstyle_context=True,
            overall_quality_bias="low",
            complement_hint={"bias": "ATTACKING"},
            budget_coins=10**9)
        res = engine.recommend(pool, req)
        assert res.best_evaluation is not None
        best = res.best_evaluation
        assert "archetype_fit" in best.components
        assert best.intelligence is not None
        assert best.score_band is not None
        assert res.counterfactuals is not None
        assert res.sensitivity is not None
        assert abs(sum(best.component_weights.values()) - 1.0) < 1e-9
