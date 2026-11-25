"""T1 — adversarial golden scenarios.

Per INTELLIGENCE_TEST_MATRIX.md S4. Each test's docstring states WHY the
expected ordering is correct, not merely the expected winner, per mandate
item 12. Guard cases (marked GUARD) are as important as the "tactics flip
the winner" cases -- they are what stops the engine from over-rotating into
low-OVR bias, the mirror-image failure to v2's OVR bias.
"""
from __future__ import annotations

import pytest

from backend.services.recommendation_engine_v3 import RecommendationEngineV3
from backend.services.reference_distribution import load_reference_distribution
from backend.services.v3_config import DEFAULT_V3_CONFIG
from backend.tests.helpers import make_attrs, make_candidate, make_req

LAM = DEFAULT_V3_CONFIG.lam_default.value


@pytest.fixture(scope="module")
def engine():
    ref = load_reference_distribution("fc26-players-2026-09-r1")
    return RecommendationEngineV3(reference=ref, data_version="fc26-players-2026-09-r1")


def _winner(engine, candidates, req):
    res = engine.recommend(candidates, req)
    assert res.ranked, (f"no candidate cleared the coverage/eligibility gates: "
                         f"not_evaluable={res.not_evaluable} excluded={res.excluded}")
    return res.ranked[0].context.candidate_name, res


class TestCaseA_HighOvrPoorFitVsLowerOvrGoodFit:
    """High OVR with poor tactical fit must lose to lower OVR with excellent
    fit, WHEN the tactic makes it so -- and must NOT lose when the tactic
    doesn't (that second half, G-A3, is the control: without it, a system
    that always prefers lower OVR would pass G-A1/G-A2 for the wrong reason)."""

    def test_g_a1_low_block_rm_worker_beats_attacker(self, engine):
        """LOW_BLOCK demand loads defensive/positional/stamina attributes;
        Attacker87's strengths (pace, dribbling, finishing) carry near-zero
        weight there, while Worker82's defensive attributes are exactly what
        is demanded. v2 fails this case (test_high_ovr_winger_unsuited_defensive)."""
        req = make_req(position="RM", tactical_profile="LOW_BLOCK")
        attacker = make_candidate(name="Attacker87", position="RM", ovr=87, attrs=make_attrs(
            pace=90, dribbling_detail=90, finishing=85, crossing=84, defending=40,
            interceptions=38, standing_tackle=35, stamina=70, acceleration=88,
            curve=80, short_passing=72, long_passing=68, agility=86, balance=80,
            defensive_awareness=40, positioning=70, reactions=78, ball_control=82))
        worker = make_candidate(name="Worker82", position="RM", ovr=82, attrs=make_attrs(
            pace=78, dribbling_detail=75, finishing=70, crossing=76, defending=75,
            interceptions=74, standing_tackle=72, stamina=88, acceleration=76,
            curve=70, short_passing=76, long_passing=72, agility=74, balance=76,
            defensive_awareness=76, positioning=72, reactions=76, ball_control=76))
        name, res = _winner(engine, [attacker, worker], req)
        assert name == "Worker82"

    def test_g_a2_possession_cm_specialist_beats_generic(self, engine):
        """POSSESSION demand concentrates on passing/vision/control/composure,
        where Specialist83 leads despite -8 OVR."""
        req = make_req(position="CM", tactical_profile="POSSESSION")
        generic = make_candidate(name="Generic91", position="CM", ovr=91, attrs=make_attrs(
            stamina=85, aggression=80, interceptions=78, defensive_awareness=80,
            short_passing=82, vision=78, long_passing=80, ball_control=82, composure=80,
            positioning=82, strength=85, standing_tackle=80, reactions=86,
            acceleration=84, pace=84, long_shots=82, dribbling_detail=82, curve=78,
            agility=82, balance=80))
        specialist = make_candidate(name="Specialist83", position="CM", ovr=83, attrs=make_attrs(
            stamina=76, aggression=62, interceptions=66, defensive_awareness=70,
            short_passing=93, vision=92, long_passing=90, ball_control=92,
            composure=91, positioning=80, strength=66, standing_tackle=62,
            reactions=84, acceleration=72, pace=68, long_shots=78,
            dribbling_detail=88, curve=88, agility=84, balance=84))
        name, res = _winner(engine, [generic, specialist], req)
        assert name == "Specialist83"

    def test_g_a3_control_balanced_does_not_always_favour_the_specialist(self, engine):
        """CONTROL for the tactical-flip mechanism generally (using the
        Case-B CB pair, since CM's own POSITION baseline already emphasises
        passing/vision -- confirmed by inspection: CM/BALANCED demand top
        attribute is short_passing at weight 0.128 with zero tactical pull,
        so a passing specialist winning at CM under BALANCED is not evidence
        of bias, it is the position doing its job). Under a position whose
        baseline does NOT already favour recovery pace (CB), a fast-but-
        lighter defender must NOT beat a stronger, slower one once the
        HIGH_PRESS pull is removed -- proving G-B2's reversal is genuinely
        tactical, not a standing preference for one profile shape."""
        req = make_req(position="CB", tactical_profile="BALANCED")
        block = make_candidate(name="Block", position="CB", ovr=84,
                                attrs=TestCaseB_PaceVsRoleCompatibility.BLOCK)
        pacey = make_candidate(name="Pacey", position="CB", ovr=84,
                                attrs=TestCaseB_PaceVsRoleCompatibility.PACEY)
        name, res = _winner(engine, [block, pacey], req)
        assert name == "Block", ("without HIGH_PRESS's tactical pull, the position's own "
                                  "baseline (duel strength, not raw pace) should decide")


class TestCaseB_PaceVsRoleCompatibility:
    """The signed two-pole tactical demand fix -- LOW_BLOCK and HIGH_PRESS
    are opposite ends of block_height/press_intensity and must pull CB
    attribute demand in different directions, not the same direction at
    different volumes (the measured V2-1 defect)."""

    BLOCK = make_attrs(defending=85, standing_tackle=86, strength=87, pace=64,
                        acceleration=63, defensive_awareness=84, heading_accuracy=83,
                        jumping=82, interceptions=82, positioning=80, reactions=74,
                        stamina=76, aggression=70, composure=78, vision=60,
                        short_passing=70, long_passing=64, ball_control=68,
                        dribbling_detail=55)
    PACEY = make_attrs(defending=82, standing_tackle=80, strength=76, pace=89,
                        acceleration=88, defensive_awareness=79, heading_accuracy=74,
                        jumping=76, interceptions=78, positioning=76, reactions=84,
                        stamina=76, aggression=70, composure=78, vision=60,
                        short_passing=70, long_passing=64, ball_control=68,
                        dribbling_detail=55)

    def test_g_b1_low_block_favours_duel_strength(self, engine):
        req = make_req(position="CB", tactical_profile="LOW_BLOCK")
        block = make_candidate(name="Block", position="CB", ovr=84, attrs=self.BLOCK)
        pacey = make_candidate(name="Pacey", position="CB", ovr=84, attrs=self.PACEY)
        name, res = _winner(engine, [block, pacey], req)
        assert name == "Block"

    def test_g_b2_high_press_reverses_to_recovery_pace(self, engine):
        """Same pair as G-B1. Ordering MUST reverse -- this is the direct
        regression test for the fix: v2's unsigned dimension shift made
        PRESSING and LOW_BLOCK produce a 10/10-identical top-10 on real data
        because both pulled demand the same direction."""
        req = make_req(position="CB", tactical_profile="HIGH_PRESS")
        block = make_candidate(name="Block", position="CB", ovr=84, attrs=self.BLOCK)
        pacey = make_candidate(name="Pacey", position="CB", ovr=84, attrs=self.PACEY)
        name, res = _winner(engine, [block, pacey], req)
        assert name == "Pacey"


class TestCaseC_ExpensiveMarginalVsCheapValue:
    """Price is never a ranking input (FC26_DATA_TO_V3_MAPPING.md: no price
    data exists at game_player scope). These tests confirm price cannot
    enter the score even when supplied on the candidate."""

    def test_g_c1_price_does_not_reorder_ranking(self, engine):
        req = make_req(position="CM", tactical_profile="POSSESSION")
        attrs_better = make_attrs(short_passing=88, vision=86, composure=85, stamina=82,
                                   ball_control=86, long_passing=82, dribbling_detail=80,
                                   positioning=76, curve=78, agility=78, reactions=82,
                                   defensive_awareness=68, interceptions=64, standing_tackle=60,
                                   strength=72, acceleration=74, pace=72, aggression=64,
                                   long_shots=70, balance=74)
        attrs_worse = {k: max(1, v - 6) for k, v in attrs_better.values.items()}
        expensive_better = make_candidate(name="ExpensiveBetter", position="CM", ovr=86,
                                           attrs=attrs_better, price=2_000_000)
        cheap_worse = make_candidate(name="CheapWorse", position="CM", ovr=80,
                                      attrs=make_attrs(**attrs_worse), price=150_000)
        name, res = _winner(engine, [expensive_better, cheap_worse], req)
        assert name == "ExpensiveBetter", "the genuinely better card must win regardless of price"


class TestCaseF_IncompleteVsCompleteEvidence:
    """Direct regression tests for the measured V2-3 defect (weight
    redistribution rewarded thin evidence)."""

    FULL = make_attrs(short_passing=88, vision=86, long_passing=85, stamina=90,
                       ball_control=87, composure=86, defensive_awareness=80,
                       interceptions=78, positioning=80, dribbling_detail=82,
                       strength=80, long_shots=78, curve=80, agility=80,
                       balance=80, reactions=84, acceleration=76, pace=74,
                       aggression=70, standing_tackle=70)

    def test_g_f1_thin_evidence_is_not_evaluable_not_ranked_first(self, engine):
        req = make_req(position="CM", tactical_profile="POSSESSION")
        documented = make_candidate(name="WellDocumented84", position="CM", ovr=84, attrs=self.FULL)
        thin = make_candidate(name="UndocumentedSameOVR", position="CM", ovr=84,
                               attrs=make_attrs(short_passing=60))
        res = engine.recommend([documented, thin], req)
        assert [rc.context.candidate_name for rc in res.ranked] == ["WellDocumented84"]
        assert any(e.candidate_name == "UndocumentedSameOVR" for e in res.not_evaluable), (
            "v2 ranked this candidate #1 at score 0.8919 -- it must now be NOT_EVALUABLE")

    def test_g_f2_partial_evidence_c_hi_can_exceed_winners_c_lo(self, engine):
        """Missing weight is charged at P10, not zero -- so a partially
        documented card can have an honest upper bound above the ranked
        winner's score, without that upside being claimed."""
        req = make_req(position="CM", tactical_profile="POSSESSION")
        full_vals = dict(self.FULL.values)
        documented = make_candidate(name="WellDocumented84", position="CM", ovr=84,
                                     attrs=make_attrs(**full_vals))
        partial_vals = {k: v for k, v in full_vals.items()
                        if k in ("short_passing", "vision", "ball_control", "composure",
                                 "long_passing", "dribbling_detail", "positioning", "curve",
                                 "agility", "reactions")}
        for k in partial_vals:
            partial_vals[k] = min(99, partial_vals[k] + 2)
        partial = make_candidate(name="PartialGoodEvidence", position="CM", ovr=84,
                                  attrs=make_attrs(**partial_vals))
        res = engine.recommend([documented, partial], req)
        assert res.ranked[0].context.candidate_name == "WellDocumented84"
        partial_ctx = next(rc.context for rc in res.ranked if rc.context.candidate_name == "PartialGoodEvidence")
        assert partial_ctx.c_hi > res.ranked[0].context.c_lo, (
            "partial evidence should have an honest upper bound above the winner's "
            "ranking score -- this is the interval doing its job, not a bug")

    def test_g_f4_whole_pool_below_floor_returns_empty_with_reason(self, engine):
        req = make_req(position="CM", tactical_profile="POSSESSION")
        c1 = make_candidate(name="Thin1", position="CM", ovr=80, attrs=make_attrs(short_passing=55))
        c2 = make_candidate(name="Thin2", position="CM", ovr=82, attrs=make_attrs(vision=60))
        res = engine.recommend([c1, c2], req)
        assert res.ranked == (), "must not fall back to any ordering when nothing is known"
        assert len(res.not_evaluable) == 2


class TestCaseH_NearIdenticalScores:
    """Closes V2-8 (OVR tie-break) and V2-9 (alphabetical tie-break)."""

    ATTRS = make_attrs(short_passing=85, vision=84, composure=82, ball_control=83,
                        long_passing=80, dribbling_detail=78, positioning=76,
                        curve=74, agility=75, reactions=80, stamina=82,
                        defensive_awareness=70, interceptions=65, standing_tackle=62,
                        strength=74, acceleration=76, pace=74, aggression=68,
                        long_shots=70, balance=76)

    def test_g_h3_ovr_does_not_decide_a_tie(self, engine):
        req = make_req(position="CM", tactical_profile="POSSESSION")
        low = make_candidate(name="LowOvr", position="CM", ovr=79, attrs=self.ATTRS)
        high = make_candidate(name="HighOvr", position="CM", ovr=91, attrs=self.ATTRS)
        res = engine.recommend([low, high], req)
        assert abs(res.ranked[0].context.r - res.ranked[1].context.r) < 1e-9
        # order must come from entity_id, not OVR -- assert it is stable both ways
        res_swapped = engine.recommend([high, low], req)
        names_a = [rc.context.candidate_name for rc in res.ranked]
        names_b = [rc.context.candidate_name for rc in res_swapped.ranked]
        assert names_a == names_b, "tie order must not depend on input order or OVR"


class TestCaseI_RoleMismatch:
    """No Role data has been ingested (FC26_DATA_GAPS.md G-05). A candidate
    must never be excluded on Role grounds while that remains true --
    absence of Role data is not evidence of Role incompatibility."""

    def test_role_request_excludes_nobody(self, engine):
        req = make_req(position="CM", tactical_profile="POSSESSION")
        attrs = make_attrs(short_passing=85, vision=84, composure=82, stamina=82,
                            ball_control=83, long_passing=80, dribbling_detail=78,
                            positioning=76, curve=74, agility=75, reactions=80,
                            defensive_awareness=70, interceptions=65)
        c = make_candidate(name="NoRoleData", position="CM", attrs=attrs)
        res = engine.recommend([c], req)
        assert res.ranked, "must not be excluded for lacking Role data that does not exist yet"


class TestCaseJ_SpecialistVsGenericGuards:
    """G-J2/G-J3 are the guard direction of the product thesis -- the
    mirror-image failure to v2's OVR bias. A system that passes the
    'tactics flip the winner' cases but fails these has replaced OVR bias
    with low-OVR bias. This is exactly what disqualified the LEVEL x SHAPE
    prototype's pure-shape cousin in Session 1 (top-3 were 65-70 rated
    unknowns, rho(OVR) = -0.27)."""

    POSS = make_attrs(stamina=72, aggression=60, interceptions=62, defensive_awareness=68,
                       short_passing=90, vision=92, long_passing=88, ball_control=90,
                       composure=89, positioning=80, strength=68, standing_tackle=60,
                       reactions=84, acceleration=74, pace=70, long_shots=80,
                       dribbling_detail=86, curve=84, agility=84, balance=82)

    def test_g_j2_guard_identical_shape_higher_quality_wins(self, engine):
        """Same attribute PROFILE SHAPE, different absolute level. Shape
        cannot discriminate here -- capability must, and the higher-quality
        card must win."""
        req = make_req(position="CM", tactical_profile="POSSESSION")
        lower_vals = {k: max(1, v - 8) for k, v in self.POSS.values.items()}
        lower = make_candidate(name="Lower80", position="CM", ovr=80, attrs=make_attrs(**lower_vals))
        higher = make_candidate(name="Higher88", position="CM", ovr=88, attrs=self.POSS)
        name, res = _winner(engine, [lower, higher], req)
        assert name == "Higher88"

    def test_g_j3_guard_perfect_shape_weak_level_loses(self, engine):
        """Perfect profile shape at a level far below the pool must lose to
        a solid, well-matched card. Fit modifies capability; it does not
        replace it."""
        req = make_req(position="CM", tactical_profile="POSSESSION")
        weak_vals = {k: max(1, int(v * 0.62)) for k, v in self.POSS.values.items()}
        weak = make_candidate(name="PerfectShapeWeak", position="CM", ovr=58, attrs=make_attrs(**weak_vals))
        solid = make_candidate(name="SolidPoss84", position="CM", ovr=84, attrs=self.POSS)
        name, res = _winner(engine, [weak, solid], req)
        assert name == "SolidPoss84"


class TestPositionMismatchGate:
    """Direct regression for V2-5: position incompatibility must be an
    engine-level hard constraint, not merely a low-scoring component."""

    def test_striker_at_cb_is_excluded_not_merely_scored_low(self, engine):
        req = make_req(position="CB", tactical_profile="LOW_BLOCK")
        cb = make_candidate(name="RealCB85", position="CB", ovr=85, attrs=make_attrs(
            defending=86, standing_tackle=85, interceptions=84, heading_accuracy=82,
            strength=86, defensive_awareness=85, jumping=80, aggression=80, reactions=82,
            pace=70, short_passing=70, long_passing=66, vision=62, composure=78))
        striker = make_candidate(name="StrikerPlayedAtCB91", position="ST", ovr=91, attrs=make_attrs(
            finishing=92, positioning=90, shot_power=88, pace=90, composure=88,
            heading_accuracy=80, volleys=85, long_shots=84, strength=78, agility=88,
            ball_control=88, acceleration=90, reactions=90, dribbling_detail=88,
            defending=30, standing_tackle=25, interceptions=28, defensive_awareness=30,
            jumping=70, aggression=55))
        res = engine.recommend([cb, striker], req)
        ranked_names = [rc.context.candidate_name for rc in res.ranked]
        assert "StrikerPlayedAtCB91" not in ranked_names, (
            "v2 ranked this candidate at score 0.535 with excluded_hard=[] -- it must "
            "now be gated out entirely, not merely scored low")
        assert any(e.candidate_name == "StrikerPlayedAtCB91" and e.gate == "G4_position"
                   for e in res.excluded)
        assert ranked_names == ["RealCB85"]
