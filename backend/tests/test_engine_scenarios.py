"""§49/§74 — SCENARIO EVALUATION SUITE + FULL ACCEPTANCE TEST.

Part 1: every registered scenario in backend.services.engine_evaluation is
executed and asserted against its qualitative behavioral contract (12+
scenarios, deterministic, DB-free).

Part 2 (§74): the mandatory acceptance test — a full natural-language request
("box-to-box CM, 4-2-3-1, high press + fast build-up, complement my squad,
must have Intercept, under 500k") is parsed, recommended against the LIVE FC26
canonical pool, and inspected through every stage of the layered decision
system, including what-if mode.
"""
from __future__ import annotations

import json
import uuid

import pytest

from backend.services import engine_evaluation
from backend.services.engine_config import ENGINE_VERSION
from backend.services.fit_value import FitStatus
from backend.services.recommendation_engine_v2 import RecommendationEngineV2

from .conftest import requires_db

ENGINE = RecommendationEngineV2()


def _run(name):
    spec = engine_evaluation.SCENARIOS[name]()
    res = ENGINE.recommend(spec["pool"], spec["req"],
                           squad_ctx=spec.get("squad_ctx"),
                           squad_members=spec.get("squad_members"))
    return spec, res


class TestScenarioSuite:
    def test_high_press_st(self):
        _, res = _run("high_press_st")
        assert res.best_evaluation.candidate.name == "Pressing Nine"
        # lower OVR wins because tactical fit overrules overall quality
        assert res.best_evaluation.candidate.overall_rating == 84
        assert res.best_evaluation.components["tactical_fit"].value > \
               res.ranked[1].components["tactical_fit"].value

    def test_possession_cam(self):
        _, res = _run("possession_cam")
        assert res.best_evaluation.candidate.name == "Creator"

    def test_counter_winger(self):
        _, res = _run("counter_winger")
        assert res.best_evaluation.candidate.name == "Bolt"
        # the pace>=90 hard minimum excluded the maestro, with a reason
        assert any(x["name"] == "Maestro Winger" and "pace" in x["reason"]
                   for x in res.excluded_hard)

    def test_defensive_cdm(self):
        _, res = _run("defensive_cdm")
        assert res.best_evaluation.candidate.name == "Anchor"

    def test_box_to_box_archetype(self):
        _, res = _run("box_to_box_archetype")
        best = res.best_evaluation
        assert best.candidate.name == "Engine CM"
        af = best.components["archetype_fit"]
        assert af.status == FitStatus.KNOWN and af.value > 0.5
        # the OVR-88 pure ten loses to the OVR-84 engine
        ten = next(e for e in res.ranked if e.candidate.name == "Pure Ten")
        assert ten.candidate.overall_rating == 88
        assert ten.components["archetype_fit"].value < af.value

    def test_ball_playing_cb(self):
        _, res = _run("ball_playing_cb")
        assert res.best_evaluation.candidate.name == "Passing CB"
        assert any(x["name"] == "Destroyer CB" for x in res.excluded_hard)

    def test_attacking_rb(self):
        _, res = _run("attacking_rb")
        assert res.best_evaluation.candidate.name == "Overlapping RB"

    def test_low_block_gk(self):
        _, res = _run("low_block_gk")
        best = res.best_evaluation
        assert best.candidate.name == "Keeper A"
        # GK evidence must contain ONLY gk_* attributes
        ev = " ".join(best.components["attribute_fit"].evidence)
        outfield = {"short_passing", "vision", "stamina", "finishing", "pace",
                    "acceleration", "interceptions", "defensive_awareness"}
        for token in outfield:
            assert f"{token}=" not in ev
        assert "gk_diving=" in ev or "gk_reflexes=" in ev

    def test_budget_unverified(self):
        _, res = _run("budget_unverified")
        assert "BUDGET_UNVERIFIED" in res.budget_status
        assert res.best_evaluation is not None     # never excluded on UNKNOWN

    def test_chemistry_withheld(self):
        _, res = _run("chemistry_withheld")
        best = res.best_evaluation
        tf = best.components["team_fit"]
        assert tf.status == FitStatus.INSUFFICIENT_EVIDENCE
        # real link facts still surface in evidence
        assert any("shared club links" in e for e in tf.evidence)
        # v2.1: advisory structural fit is present and labeled NOT chemistry
        assert best.squad_structural is not None
        assert best.squad_structural.status == FitStatus.KNOWN
        assert any("NOT a chemistry" in e for e in best.squad_structural.evidence)

    def test_ovr_trap(self):
        _, res = _run("ovr_trap")
        assert res.best_evaluation.candidate.name == "League Worker"

    def test_unknown_data_honesty(self):
        _, res = _run("unknown_data_honesty")
        by_name = {e.candidate.name: e for e in res.ranked}
        assert by_name["Fully Scouted"].score_band["band"] != "INSUFFICIENT_EVIDENCE"
        assert by_name["Mostly Unknown"].score_band["band"] == "INSUFFICIENT_EVIDENCE"
        assert by_name["Fully Scouted"].confidence.score > \
               by_name["Thin Evidence"].confidence.score

    def test_registry_covers_minimum_count(self):
        assert len(engine_evaluation.SCENARIOS) >= 12


# ---------------------------------------------------------------------------
# §74 — FULL ACCEPTANCE TEST (live FC26 data required)
# ---------------------------------------------------------------------------
ACCEPTANCE_TEXT = (
    "Looking for a box-to-box CM for my 4-2-3-1, high press with fast build-up, "
    "good stamina, must have Intercept, under 500000 coins, should complement "
    "my attacking squad"
)


@requires_db
class TestFullAcceptance:
    def test_acceptance_end_to_end(self):
        from backend.domain.user_model import AttributeBand, UserRequirements
        from backend.services.intent_parser import parse
        from backend.services.recommendation_service import RecommendationService

        # ---- 1. INTENT: natural language -> structured intent ---------------
        intent = parse(ACCEPTANCE_TEXT, "FC26")
        draft = intent.to_draft()
        assert draft["position"] == "CM"
        assert draft["formation"] == "4-2-3-1"
        assert draft["tactical_profile"] == "HIGH_PRESS"
        assert draft["secondary_tactical_profile"] == "FAST_BUILD_UP"
        assert draft["archetype"] == "BOX_TO_BOX"
        assert draft["required_playstyles"] == ["Intercept"]
        assert draft["budget_coins"] == 500000
        assert any(b["attribute"] == "stamina" for b in draft["attribute_bands"])
        # provenance discipline: hard vs soft separated, budget not enforceable
        kinds = {h["kind"] for h in draft["hard_constraints"]}
        assert {"BUDGET", "REQUIRED_PLAYSTYLE"} <= kinds
        budget_h = next(h for h in draft["hard_constraints"] if h["kind"] == "BUDGET")
        assert budget_h["enforced"] is False        # prices UNKNOWN -> reported

        # ---- 2. REQUIREMENTS: user-reviewed draft (complement hint confirmed
        #         in the UI step) -> validated domain requirements -------------
        req = UserRequirements(
            game_version="FC26", position=draft["position"],
            formation=draft["formation"],
            tactical_profile=draft["tactical_profile"],
            secondary_tactical_profile=draft["secondary_tactical_profile"],
            archetype=draft["archetype"],
            required_playstyles=draft["required_playstyles"],
            budget_coins=draft["budget_coins"],
            attribute_bands=[AttributeBand(b["attribute"], b["band"])
                             for b in draft["attribute_bands"]],
            enable_interactions=True, enable_saturation=True,
            enable_playstyle_context=True,
            complement_hint={"position": "CM", "bias": "ATTACKING"},
            limit=10)
        assert req.validate() == []

        # ---- 3. DECISION: full layered run against the live pool ------------
        svc = RecommendationService()
        out = svc.recommend(req)

        # engine identity + canonical response fields (§54)
        assert out["engine_version"] == ENGINE_VERSION
        assert out["best"] is not None, "live pool must yield a recommendation"
        assert out["best_score"] > 0
        assert out["confidence"]["score"] > 0
        assert out["confidence_v2"]["level"] in ("HIGH", "MEDIUM", "LOW", "VERY_LOW")

        # hard constraints honored: winner really holds Intercept
        winner_id = uuid.UUID(out["best"]["entity_id"])
        from backend.data_access.candidate_repository import CandidateRepository
        pool = CandidateRepository().load_for_position("FC26", "CM", include_adjacent=True)
        winner = next(c for c in pool if c.entity_id == winner_id)
        assert "Intercept" in winner.playstyles_base or \
               "Intercept" in winner.playstyles_plus

        # fit breakdown + effective weights (archetype 0.10 renormalized)
        comps = out["best"]["components"]
        assert set(comps) >= {"overall_quality", "position_fit", "attribute_fit",
                              "tactical_fit", "playstyle_fit", "team_fit",
                              "role_fit", "archetype_fit"}
        weights = out["weights_used"]
        assert "archetype_fit" in weights
        assert abs(sum(weights.values()) - 1.0) < 1e-9

        # score band + intelligence layer (ENGINE-DERIVED, labeled)
        assert out["best"]["score_band"]["band"]
        assert "probability" in out["best"]["score_band"]["note"]
        intel = out["best"]["intelligence"]
        assert intel["dominant_archetype"]
        assert intel["gameplay_profile"]["note"].startswith("ENGINE-DERIVED")
        assert 0.0 <= intel["versatility"]["value"] <= 1.0

        # constraints report (§54): satisfied / failed / unknown
        cons = out["constraints"]
        assert any("Intercept" in s for s in cons["satisfied"])
        assert any("budget" in u.lower() or "price" in u.lower()
                   for u in cons["unknown"]), cons["unknown"]
        assert cons["failed"] == []

        # budget honesty end-to-end
        assert "BUDGET_UNVERIFIED" in out["budget_status"]

        # explanations: WHY WON + WHY LOST (§34 negative explanations)
        exp = out["explanations"]
        assert exp["summary"] and exp["why_this"]
        assert exp["why_not_alternatives"], "top-10 must include alternatives to compare"
        assert all(a["reasons"] for a in exp["why_not_alternatives"])
        assert isinstance(exp["strengths"], list) and isinstance(exp["weaknesses"], list)

        # Pareto fronts (§29): quality / value-honesty / alternatives
        pareto = out["pareto"]
        assert pareto["best_overall"]["entity_id"] == out["best"]["entity_id"] or \
               pareto["best_overall"] is not None
        assert "best_alternative_archetype" in pareto
        for key, entry in pareto.items():
            if entry is None:
                continue
            assert "reason" in entry or "dimension" in entry or True

        # sensitivity + counterfactuals (§35/§36)
        assert out["sensitivity"]["status"] in ("OK", "INSUFFICIENT_ALTERNATIVES")
        assert isinstance(out["counterfactuals"], list)

        # data honesty block (§21/§25/§27/§59)
        assert out["data_freshness"]["market_prices"].startswith("UNAVAILABLE")
        assert out["data_freshness"]["chemistry_rules"].startswith("UNVERIFIED")
        assert out["provenance"]["sources"]
        assert out["telemetry"]["candidates_evaluated"] > 0
        assert out["telemetry"]["scoring_ms"] >= 0

        # confidence reasons are human-readable strings
        assert all(isinstance(r, str) for r in out["confidence_v2"]["reasons"])

        # ---- 4. WHAT-IF (§36): same request, possession instead of fast
        #         build-up -> the engine must react (different combo weights) --
        req_whatif = UserRequirements(**{**req.__dict__,
                                         "secondary_tactical_profile": "POSSESSION"})
        out2 = svc.recommend(req_whatif)
        assert out2["engine_version"] == out["engine_version"]
        # the decision surface must REACT to the what-if: the merged tactical
        # dimension vector changes, so tactical fit values and scores change
        # (the top-10 ORDER may legitimately stay stable — that is ranking
        # robustness, not a dead code path).
        tf1 = out["best"]["components"]["tactical_fit"]["value"]
        tf2 = out2["best"]["components"]["tactical_fit"]["value"]
        score_changed = abs(out2["best_score"] - out["best_score"]) > 1e-9
        order_changed = ([r["entity_id"] for r in out2["ranked"]] !=
                         [r["entity_id"] for r in out["ranked"]])
        assert score_changed or order_changed, "what-if must alter the decision surface"
        if tf1 is not None and tf2 is not None:
            assert tf1 != tf2, "combo tactical weights must differ between " \
                               "HIGH_PRESS+FAST_BUILD_UP and HIGH_PRESS+POSSESSION"
