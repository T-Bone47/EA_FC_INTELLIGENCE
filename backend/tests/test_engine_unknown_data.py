"""MANDATORY §51 — UNKNOWN DATA HONESTY.

Missing data must be:
  * never zero, never "bad" (no hidden penalty),
  * never equally certain (confidence must reflect evidence),
  * never invented (UNKNOWN / INSUFFICIENT_EVIDENCE / CONFLICTED vocabulary),
  * visibly distinguished from score (score vs confidence separation).

Also covers the FC27 zero-data wall: the engine must be safe and honest with
NO data at all (§61).
"""
from __future__ import annotations

import pytest

from backend.domain.user_model import UserRequirements
from backend.services import confidence_v2, engine_evaluation
from backend.services.engine_config import ENGINE_VERSION
from backend.services.fit_value import FitStatus
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


class TestScoreVsConfidence:
    def test_mandatory_unknown_data_scenario(self, engine):
        """§51 mandatory pool: full evidence / thin evidence / mostly unknown."""
        pool, req = engine_evaluation.unknown_data_pool()
        res = engine.recommend(pool, req)
        by_name = {e.candidate.name: e for e in res.ranked}
        full, thin, ghost = (by_name["Fully Scouted"], by_name["Thin Evidence"],
                             by_name["Mostly Unknown"])

        # 1) missing data is never "bad": nobody is excluded or zeroed
        assert res.excluded_hard == []
        for e in (full, thin, ghost):
            assert e.weighted_score is not None and e.weighted_score > 0

        # 2) missing data is never equally certain: confidence strictly orders
        assert full.confidence.score > thin.confidence.score
        assert full.confidence.score > ghost.confidence.score

        # 3) score and confidence are distinguished: the ghosts may out-SCORE
        #    the scouted player, but they never out-CONFIDENCE him, and they
        #    never receive a qualitative fit band (§23 honesty gate)
        assert full.score_band["band"] not in ("INSUFFICIENT_EVIDENCE",)
        assert thin.score_band["band"] == "INSUFFICIENT_EVIDENCE"
        assert ghost.score_band["band"] == "INSUFFICIENT_EVIDENCE"
        assert ghost.score_band["evidence_coverage"] < 0.5

    def test_unknown_components_are_listed_never_silenced(self, engine):
        pool, req = engine_evaluation.unknown_data_pool()
        res = engine.recommend(pool, req)
        full = next(e for e in res.ranked if e.candidate.name == "Fully Scouted")
        unknowns = full.confidence.unknown_components + full.confidence.insufficient_components
        assert "playstyle_fit" in unknowns or "team_fit" in unknowns

    def test_confidence_v2_separates_identical_scores(self):
        """confidence 2.0 (§24): two identical legacy scores, different
        evidence situations -> different confidence_v2."""
        from datetime import datetime, timedelta, timezone
        a = confidence_v2.compute(0.8, last_observed=datetime.now(timezone.utc),
                                  source_tier=1, identity_status="RESOLVED")
        b = confidence_v2.compute(0.8,
                                  last_observed=datetime.now(timezone.utc) - timedelta(days=800),
                                  source_tier=4, identity_status="UNRESOLVED",
                                  unresolved_conflicts=2)
        assert a["score_v2"] > b["score_v2"]
        assert b["level"] in ("LOW", "VERY_LOW")
        assert any("freshness" in r.lower() for r in b["reasons"])

    def test_missing_attribute_is_not_a_constraint_violation(self, engine):
        """§19: UNKNOWN attribute vs a required minimum is reported as unknown,
        never as satisfied and never as failed."""
        from backend.domain.user_model import AttributePreference
        c = make_candidate(attrs=make_attrs(vision=90))    # stamina UNKNOWN
        req = make_req(position="CM",
                       attribute_preferences=[AttributePreference("stamina", min_value=85)])
        ev = engine.evaluate(c, req)
        assert ev.hard_constraint_violation is None
        report = RecommendationEngineV2.constraint_report(ev, req)
        assert any("stamina" in u and "UNKNOWN" in u for u in report["unknown"])
        assert not any("stamina" in f for f in report["failed"])


class TestComponentUnknownVocabulary:
    def test_unpublished_playstyles_insufficient_not_zero(self, engine):
        c = make_candidate(playstyle_published=False, attrs=make_attrs(**CM_FULL))
        req = make_req(position="CM", desired_playstyles=["Tiki Taka"])
        ev = engine.evaluate(c, req)
        pf = ev.components["playstyle_fit"]
        assert pf.status == FitStatus.INSUFFICIENT_EVIDENCE   # never KNOWN(0.0)

    def test_role_without_data_never_zero(self, engine):
        c = make_candidate(attrs=make_attrs(**CM_FULL))
        req = make_req(position="CM", role="Playmaker")
        ev = engine.evaluate(c, req)
        rf = ev.components["role_fit"]
        assert rf.status in (FitStatus.INSUFFICIENT_EVIDENCE, FitStatus.UNKNOWN)
        assert rf.status != FitStatus.KNOWN or rf.value > 0

    def test_budget_unknown_never_assumed(self, engine):
        c = make_candidate(attrs=make_attrs(**CM_FULL))    # price None
        req = make_req(position="CM", budget_coins=1000)
        res = engine.recommend([c], req)
        assert "BUDGET_UNVERIFIED" in res.budget_status
        assert res.best_evaluation is not None             # not excluded
        assert res.best_evaluation.budget_decision is None  # UNKNOWN

    def test_gk_without_gk_attrs_is_insufficient(self, engine):
        gk = make_candidate(position="GK", attrs=make_attrs(short_passing=80))
        ev = engine.evaluate(gk, make_req(position="GK"))
        assert ev.components["attribute_fit"].status == FitStatus.INSUFFICIENT_EVIDENCE


class TestEmptyStateFC27:
    def test_engine_handles_empty_pool(self, engine):
        res = engine.recommend([], make_req(position="CM"))
        assert res.best is None and res.ranked == []
        assert res.engine_version == ENGINE_VERSION

    @requires_db
    def test_fc27_wall_is_honest_not_fabricated(self):
        """§61: FC27 with zero ingested data must refuse, say why, and never
        substitute FC26 data or invent records."""
        from backend.services.recommendation_service import RecommendationService
        svc = RecommendationService()
        with pytest.raises(LookupError) as exc:
            svc.recommend(UserRequirements(game_version="FC27", position="CM"))
        msg = str(exc.value)
        assert "NO ingested production data" in msg or "NO_DATA" in msg
        assert "fabricated" in msg.lower() or "invent" in msg.lower() \
            or "never" in msg.lower()
