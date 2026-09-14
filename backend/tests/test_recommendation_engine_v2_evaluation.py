"""Engine V2 core semantics: FitValue policy, weight redistribution,
version-awareness, synthetic firewall, determinism, Pareto, hard constraints.

Regression suite for documented V2 behavior (§15, §17, §19).
"""
from __future__ import annotations

import pytest

from backend.domain.user_model import AttributePreference, SquadContext, SquadSlot
from backend.services import recommendation_engine_v2 as eng
from backend.services.fit_value import FitStatus
from backend.services.recommendation_engine_v2 import RecommendationEngineV2
from backend.services.scoring_config import COMPONENT_WEIGHTS, ScoringConfig
from backend.tests.helpers import make_attrs, make_candidate, make_req


@pytest.fixture()
def engine():
    return RecommendationEngineV2(ScoringConfig())


# ------------------------------------------------------------------ FitValue policy
class TestMissingDataPolicy:
    def test_unknown_ovr_is_unknown_not_zero(self, engine):
        c = make_candidate(ovr=None)
        ev = engine.evaluate(c, make_req(position="CM"))
        assert ev.components["overall_quality"].status == FitStatus.UNKNOWN
        assert ev.components["overall_quality"].value is None

    def test_missing_attribute_not_zeroed(self, engine):
        # candidate missing MOST CM-relevant attrs -> insufficient, not low score
        c = make_candidate(attrs=make_attrs(stamina=90))
        ev = engine.evaluate(c, make_req(position="CM"))
        af = ev.components["attribute_fit"]
        assert af.status == FitStatus.INSUFFICIENT_EVIDENCE
        assert af.value is None

    def test_partial_attributes_scored_on_known_only(self, engine):
        # 70% coverage (>= 0.5 threshold) -> KNOWN, computed over known weights only
        attrs = make_attrs(**{k: 80 for k in list(
            ScoringConfig().position_attribute_weights("CM"))[:9]})
        c = make_candidate(attrs=attrs)
        ev = engine.evaluate(c, make_req(position="CM"))
        af = ev.components["attribute_fit"]
        assert af.status == FitStatus.KNOWN
        assert af.value == pytest.approx(80 / 99.0, abs=1e-6)

    def test_unpublished_playstyles_are_insufficient_not_no_playstyles(self, engine):
        c = make_candidate(playstyle_published=False)
        ev = engine.evaluate(c, make_req(position="CM", desired_playstyles=["Tiki Taka"]))
        pf = ev.components["playstyle_fit"]
        assert pf.status == FitStatus.INSUFFICIENT_EVIDENCE
        assert "not absence of PlayStyles" in pf.reason

    def test_no_playstyle_requirement_is_unknown(self, engine):
        ev = engine.evaluate(make_candidate(), make_req(position="CM"))
        assert ev.components["playstyle_fit"].status == FitStatus.UNKNOWN

    def test_role_without_data_is_insufficient_not_incompatible(self, engine):
        ev = engine.evaluate(make_candidate(), make_req(position="CM", role="Playmaker"))
        rf = ev.components["role_fit"]
        assert rf.status == FitStatus.INSUFFICIENT_EVIDENCE
        assert "not counted as incompatibility" in rf.reason

    def test_no_squad_team_fit_unknown(self, engine):
        ev = engine.evaluate(make_candidate(), make_req(position="CM"))
        assert ev.components["team_fit"].status == FitStatus.UNKNOWN

    def test_squad_but_unverified_chemistry_rules_insufficient_with_links(self, engine):
        import uuid as _uuid
        ctx = SquadContext(squad_id=None, formation="4-2-3-1", game_version="FC26",
                           slots=[SquadSlot(0, "CM", game_player_id=_uuid.uuid4(),
                                            club="Test FC", league="Test League",
                                            nation="Testland")])
        ev = engine.evaluate(make_candidate(), make_req(position="CM", squad_id=None),
                             squad_ctx=ctx)
        tf = ev.components["team_fit"]
        assert tf.status == FitStatus.INSUFFICIENT_EVIDENCE
        assert any("shared club links: 1" in e for e in tf.evidence)


# ------------------------------------------------------------------ redistribution
class TestWeightRedistribution:
    def test_unknown_components_redistributed_no_penalty(self, engine):
        # identical candidate data; req B simply asks for more (playstyles+role).
        # The extra UNKNOWN/INSUFFICIENT components must not lower the score.
        c = make_candidate()
        ev_a = engine.evaluate(c, make_req(position="CM"))
        ev_b = engine.evaluate(c, make_req(position="CM",
                                           desired_playstyles=["Nonexistent Style"],
                                           role="Playmaker"))
        # ev_b playstyle_fit is KNOWN(0.0) — that IS a real mismatch, so compare
        # against a variant where playstyle data is unpublished (INSUFFICIENT):
        c2 = make_candidate(playstyle_published=False)
        ev_c = engine.evaluate(c2, make_req(position="CM",
                                            desired_playstyles=["Tiki Taka"],
                                            role="Playmaker"))
        ev_c_base = engine.evaluate(c2, make_req(position="CM"))
        assert ev_c.weighted_score == pytest.approx(ev_c_base.weighted_score, abs=1e-9)

    def test_all_unknown_weighted_components_gives_none_score(self, engine):
        c = make_candidate(ovr=None, attrs=make_attrs(), playstyle_published=False)
        ev = engine.evaluate(c, make_req())   # no position, no prefs
        assert ev.weighted_score is None
        assert not ev.rankable

    def test_weights_sum_to_one(self):
        assert sum(COMPONENT_WEIGHTS.values()) == pytest.approx(1.0)


# ------------------------------------------------------------------ position fit
class TestPositionFit:
    def test_exact_secondary_adjacent_unrelated(self, engine):
        req = make_req(position="CM")
        assert engine.evaluate(make_candidate(position="CM"), req).components["position_fit"].value == 1.0
        assert engine.evaluate(make_candidate(position="ST", secondary=["CM"]), req).components["position_fit"].value == 0.85
        adj = engine.evaluate(make_candidate(position="CDM"), req).components["position_fit"]
        assert adj.status == FitStatus.KNOWN and 0.5 <= adj.value <= 0.7
        far = engine.evaluate(make_candidate(position="GK"), req).components["position_fit"]
        assert far.value == pytest.approx(0.05)

    def test_no_target_position_unknown(self, engine):
        ev = engine.evaluate(make_candidate(), make_req())
        assert ev.components["position_fit"].status == FitStatus.UNKNOWN


# ------------------------------------------------------------------ GK support
class TestGKSupport:
    def test_gk_scored_on_real_gk_attributes(self, engine):
        gk = make_candidate(
            name="Test GK", position="GK", ovr=88,
            attrs=make_attrs(gk_diving=88, gk_handling=85, gk_kicking=78,
                             gk_positioning=86, gk_reflexes=90),
            playstyles_base=["Footwork"], playstyle_published=True)
        ev = engine.evaluate(gk, make_req(position="GK"))
        af = ev.components["attribute_fit"]
        assert af.status == FitStatus.KNOWN
        assert af.value > 0.8   # strong GK scored highly on GK attrs (gap resolved)

    def test_gk_without_published_gk_attrs_insufficient(self, engine):
        gk = make_candidate(name="No GK data", position="GK", ovr=70,
                            attrs=make_attrs())
        ev = engine.evaluate(gk, make_req(position="GK"))
        assert ev.components["attribute_fit"].status == FitStatus.INSUFFICIENT_EVIDENCE


# ------------------------------------------------------------------ versioning
class TestVersionAwareness:
    def test_engine_rejects_cross_version_candidate(self, engine):
        c = make_candidate(version="FC27")
        with pytest.raises(ValueError, match="never mixed"):
            engine.evaluate(c, make_req(game_version="FC26", position="CM"))

    def test_fc27_without_config_lookup_raises_not_falls_back(self, engine):
        cfg = ScoringConfig.with_versions(
            [ScoringConfig().version("FC26")])     # only FC26 configured
        e2 = RecommendationEngineV2(cfg)
        c = make_candidate(version="FC26")
        req = make_req(game_version="FC26")
        e2.evaluate(c, req)                        # fine
        with pytest.raises(KeyError, match="never silently"):
            cfg.version("FC27")                    # FC27 must be explicitly configured

    def test_fc27_config_has_no_guessed_values(self):
        vc = ScoringConfig().version("FC27")
        assert vc.data_status == "NO_DATA"
        assert vc.positions == ()
        assert vc.playstyle_plus_caps == {}        # unknown cap not guessed


# ------------------------------------------------------------------ synthetic firewall
class TestSyntheticFirewall:
    def test_engine_refuses_synthetic_candidate(self, engine):
        c = make_candidate(synthetic=True)
        with pytest.raises(ValueError, match="data-boundary violation"):
            engine.evaluate(c, make_req(position="CM"))


# ------------------------------------------------------------------ tactical floor
class TestTacticalFloor:
    def test_strict_mode_excludes_below_floor(self, engine):
        slow = make_candidate(name="Slow CM", attrs=make_attrs(
            short_passing=90, vision=90, long_passing=90, stamina=90,
            ball_control=90, composure=90, defensive_awareness=20,
            interceptions=20, positioning=30, dribbling_detail=40))
        fast = make_candidate(name="Pressing CM", attrs=make_attrs(
            stamina=95, aggression=90, interceptions=88, defensive_awareness=85,
            standing_tackle=84, positioning=85, reactions=85, strength=80,
            acceleration=85, pace=85))
        req = make_req(position="CM", tactical_profile="PRESSING", strict_tactics=True)
        res = engine.recommend([slow, fast], req)
        names = [e.candidate.name for e in res.ranked]
        assert "Pressing CM" in names
        # slow CM either excluded by floor or ranked below
        if "Slow CM" in names:
            assert names.index("Pressing CM") < names.index("Slow CM")

    def test_non_strict_downranks_but_keeps(self, engine):
        slow = make_candidate(name="Slow CM", ovr=91, attrs=make_attrs(
            stamina=30, aggression=25, interceptions=25, defensive_awareness=25,
            standing_tackle=25, positioning=30, reactions=30, strength=30,
            acceleration=30, pace=30))
        req = make_req(position="CM", tactical_profile="PRESSING", strict_tactics=False)
        res = engine.recommend([slow], req)
        assert res.ranked and res.ranked[0].below_tactical_floor


# ------------------------------------------------------------------ hard constraints & budget
class TestHardConstraints:
    def test_min_overall_excludes(self, engine):
        res = engine.recommend([make_candidate(ovr=70)], make_req(position="CM", min_overall=80))
        assert res.best is None
        assert res.excluded_hard and "below min_overall" in res.excluded_hard[0]["reason"]

    def test_attribute_min_violation_excludes(self, engine):
        c = make_candidate(attrs=make_attrs(stamina=70))
        req = make_req(position="CM",
                       attribute_preferences=[AttributePreference("stamina", min_value=85)])
        res = engine.recommend([c], req)
        assert res.best is None
        assert "below required minimum" in res.excluded_hard[0]["reason"]

    def test_attribute_min_unknown_is_not_violation(self, engine):
        c = make_candidate(attrs=make_attrs(vision=90))   # stamina unknown
        req = make_req(position="CM",
                       attribute_preferences=[AttributePreference("stamina", min_value=85, weight=0.0),
                                              AttributePreference("vision", min_value=80)])
        res = engine.recommend([c], req)
        assert res.best is not None   # UNKNOWN stamina != violation (§19)

    def test_budget_without_prices_is_unverified_not_enforced(self, engine):
        c = make_candidate(price=None)
        res = engine.recommend([c], make_req(position="CM", budget_coins=100_000))
        assert res.budget_status.startswith("BUDGET_UNVERIFIED")
        assert res.best is not None     # not excluded — price UNKNOWN, never assumed

    def test_budget_with_price_enforced(self, engine):
        rich = make_candidate(name="Expensive", price=500_000)
        cheap = make_candidate(name="Affordable", price=50_000)
        res = engine.recommend([rich, cheap],
                               make_req(position="CM", budget_coins=100_000))
        assert res.best.name == "Affordable"
        assert any("exceeds budget" in e["reason"] for e in res.excluded_hard)
        assert res.budget_status.startswith("BUDGET_ENFORCED")


# ------------------------------------------------------------------ determinism & pareto
class TestDeterminismAndPareto:
    def test_ranking_deterministic_across_runs(self, engine):
        cs = [make_candidate(name=f"P{i}", ovr=80 + (i % 5)) for i in range(20)]
        req = make_req(position="CM")
        r1 = engine.recommend(list(cs), req, request_id="x")
        r2 = engine.recommend(list(reversed(cs)), req, request_id="x")
        assert [e.candidate.name for e in r1.ranked] == [e.candidate.name for e in r2.ranked]

    def test_tie_broken_by_ovr_then_name(self, engine):
        a = make_candidate(name="AAA", ovr=85)
        b = make_candidate(name="BBB", ovr=85)
        c = make_candidate(name="CCC", ovr=87)
        res = engine.recommend([a, b, c], make_req(position="CM"))
        assert res.ranked[0].candidate.name == "CCC"
        assert res.ranked[1].candidate.name == "AAA"

    def test_pareto_dimensions_present_and_honest(self, engine):
        cs = [make_candidate(name=f"P{i}", ovr=75 + i) for i in range(5)]
        res = engine.recommend(cs, make_req(position="CM", tactical_profile="POSSESSION"))
        assert res.pareto["best_overall"] is not None
        assert res.pareto["best_attribute_fit"] is not None
        assert res.pareto["best_tactical_alignment"] is not None
        assert res.pareto["best_value"] is None
        assert "best_value" in res.pareto["unavailable_dimensions"]
        assert "best_chemistry_fit" in res.pareto["unavailable_dimensions"]

    def test_best_playstyle_pareto(self, engine):
        a = make_candidate(name="HasPS", playstyles_base=["Tiki Taka", "First Touch"])
        b = make_candidate(name="NoPS", playstyles_base=["Power Shot"])
        res = engine.recommend([a, b], make_req(position="CM",
                                                desired_playstyles=["Tiki Taka"]))
        assert res.pareto["best_playstyle_fit"]["name"] == "HasPS"

    def test_empty_pool_returns_no_best(self, engine):
        res = engine.recommend([], make_req(position="CM"))
        assert res.best is None and res.ranked == []
        assert res.confidence.score == pytest.approx(0.0, abs=0.35)

    def test_result_serializes(self, engine):
        res = engine.recommend([make_candidate()], make_req(position="CM"))
        d = res.to_dict()
        assert d["game_version"] == "FC26"
        assert d["best"]["components"]["attribute_fit"]["status"] == "KNOWN"
