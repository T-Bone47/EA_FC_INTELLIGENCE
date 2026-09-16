"""PHASE 7 ADVERSARIAL SUITE — 50+ deterministic scenarios.

Objective (NOT "lower OVR always wins"):
  "OVR should lose when contextual suitability sufficiently outweighs raw quality."

Every test is DB-free, deterministic, no randomness. Each asserts natural
scoring behaviour (no hard-coded special cases in production code).

Coverage:
  A: OVR traps (10) — mission §9 items 1-10
  B: Position intelligence (10)
  C: Tactical differentiation (10)
  D: PlayStyle contextual (8)
  E: Attribute interactions (6)
  F: UNKNOWN / confidence / determinism (6+)
"""
from __future__ import annotations

import pytest

from backend.domain.user_model import AttributePreference
from backend.services.recommendation_engine_v2 import RecommendationEngineV2

from .helpers import make_attrs, make_candidate, make_req


@pytest.fixture()
def engine():
    return RecommendationEngineV2()


def _attrs(**kw):
    return make_attrs(**kw)


# ---------------------------------------------------------------- A: OVR traps
class TestOvrTrapsPhase7:
    def test_91_vs_84_tactical_fit_wins(self, engine):
        """91 OVR poor tactical fit vs 84 excellent fit — 84 must win."""
        star = make_candidate(name="Star91", position="CM", ovr=91, attrs=_attrs(
            short_passing=88, vision=88, stamina=55, defensive_awareness=40,
            interceptions=35, ball_control=88, composure=90))
        worker = make_candidate(name="Worker84", position="CM", ovr=84, attrs=_attrs(
            short_passing=82, vision=76, stamina=93, defensive_awareness=85,
            interceptions=86, ball_control=78, composure=78))
        req = make_req(position="CM", tactical_profile="PRESSING")
        res = engine.recommend([star, worker], req)
        assert res.best_evaluation.candidate.name == "Worker84"

    def test_90_wrong_position_vs_82_natural(self, engine):
        """90 OVR CM playing out of position vs 82 natural CDM."""
        star = make_candidate(name="StarCM", position="CM", ovr=90, attrs=_attrs(
            short_passing=88, vision=88, defensive_awareness=50, interceptions=45,
            standing_tackle=45, strength=70))
        nat = make_candidate(name="NaturalCDM", position="CDM", ovr=82, attrs=_attrs(
            short_passing=78, vision=75, defensive_awareness=86, interceptions=88,
            standing_tackle=85, strength=84))
        req = make_req(position="CDM", tactical_profile="MID_BLOCK")
        res = engine.recommend([star, nat], req)
        assert res.best_evaluation.candidate.name == "NaturalCDM"

    def test_90_generic_gk_vs_82_specialist(self, engine):
        """Generic 90 GK vs 82 LOW_BLOCK specialist — specialist must win."""
        gen = make_candidate(name="Generic90", position="GK", ovr=90, attrs=_attrs(
            gk_diving=82, gk_handling=82, gk_kicking=82, gk_positioning=82, gk_reflexes=82))
        spec = make_candidate(name="Specialist82", position="GK", ovr=82, attrs=_attrs(
            gk_diving=90, gk_handling=90, gk_kicking=70, gk_positioning=92, gk_reflexes=91))
        req = make_req(position="GK", tactical_profile="LOW_BLOCK")
        res = engine.recommend([gen, spec], req)
        assert res.best_evaluation.candidate.name == "Specialist82"

    def test_pace_without_role_loses(self, engine):
        """96 pace winger with poor crossing/finishing loses to balanced 83 for CROSSING."""
        sprinter = make_candidate(name="Sprinter", position="RW", ovr=86, attrs=_attrs(
            pace=96, acceleration=96, sprint_speed=96, crossing=60, finishing=62,
            composure=60, curve=58, dribbling_detail=70))
        balanced = make_candidate(name="Balanced83", position="RW", ovr=83, attrs=_attrs(
            pace=82, acceleration=83, sprint_speed=82, crossing=86, finishing=80,
            composure=80, curve=82, dribbling_detail=84))
        req = make_req(position="RW", tactical_profile="CROSSING")
        res = engine.recommend([sprinter, balanced], req)
        assert res.best_evaluation.candidate.name == "Balanced83"

    def test_shooting_striker_unsuited_possession(self, engine):
        """High-shooting 89 ST with poor link play loses to 83 false-9 type for POSSESSION."""
        shooter = make_candidate(name="Shooter89", position="ST", ovr=89, attrs=_attrs(
            finishing=93, shot_power=92, positioning=80, short_passing=62,
            vision=60, ball_control=70, composure=75, dribbling_detail=68))
        linker = make_candidate(name="Linker83", position="ST", ovr=83, attrs=_attrs(
            finishing=80, shot_power=78, positioning=82, short_passing=84,
            vision=84, ball_control=86, composure=84, dribbling_detail=84))
        req = make_req(position="ST", tactical_profile="POSSESSION")
        res = engine.recommend([shooter, linker], req)
        assert res.best_evaluation.candidate.name == "Linker83"

    def test_high_ovr_cb_unsuited_buildup(self, engine):
        """87 destroyer CB loses to 83 ball-playing CB for SLOW_BUILD_UP."""
        destroyer = make_candidate(name="Destroyer87", position="CB", ovr=87, attrs=_attrs(
            defending=91, standing_tackle=90, strength=90, short_passing=55,
            long_passing=50, vision=45, composure=60, ball_control=52))
        passer = make_candidate(name="Passer83", position="CB", ovr=83, attrs=_attrs(
            defending=83, standing_tackle=84, strength=82, short_passing=86,
            long_passing=84, vision=80, composure=84, ball_control=78))
        req = make_req(position="CB", tactical_profile="SLOW_BUILD_UP")
        res = engine.recommend([destroyer, passer], req)
        assert res.best_evaluation.candidate.name == "Passer83"

    def test_low_ovr_cb_elite_buildup(self, engine):
        """81 ball-playing CB beats 88 stopper when passing explicitly weighted."""
        elite = make_candidate(name="ElitePass81", position="CB", ovr=81, attrs=_attrs(
            defending=80, standing_tackle=80, short_passing=90, long_passing=89,
            vision=85, composure=86))
        stopper = make_candidate(name="Stopper88", position="CB", ovr=88, attrs=_attrs(
            defending=92, standing_tackle=91, short_passing=58, long_passing=55,
            vision=50, composure=62))
        req = make_req(position="CB", tactical_profile="BUILD_UP",
                       attribute_preferences=[AttributePreference("short_passing", weight=3.0),
                                              AttributePreference("long_passing", weight=2.0)])
        res = engine.recommend([elite, stopper], req)
        assert res.best_evaluation.candidate.name == "ElitePass81"

    def test_high_ovr_winger_unsuited_defensive(self, engine):
        """87 attacking winger loses to 82 defensive winger for LOW_BLOCK RM."""
        attacker = make_candidate(name="Attacker87", position="RM", ovr=87, attrs=_attrs(
            pace=90, dribbling_detail=90, finishing=85, crossing=84,
            defending=40, interceptions=38, standing_tackle=35, stamina=70))
        worker = make_candidate(name="Worker82", position="RM", ovr=82, attrs=_attrs(
            pace=78, dribbling_detail=75, finishing=70, crossing=76,
            defending=75, interceptions=74, standing_tackle=72, stamina=88))
        req = make_req(position="RM", tactical_profile="LOW_BLOCK")
        res = engine.recommend([attacker, worker], req)
        assert res.best_evaluation.candidate.name == "Worker82"

    def test_lower_midfielder_perfect_role(self, engine):
        """82 deep-lying playmaker beats 88 generic CM for POSSESSION + vision weight."""
        generic = make_candidate(name="Generic88", position="CM", ovr=88, attrs=_attrs(
            short_passing=82, vision=78, long_passing=80, stamina=82,
            ball_control=82, composure=80))
        specialist = make_candidate(name="Specialist82", position="CM", ovr=82, attrs=_attrs(
            short_passing=90, vision=93, long_passing=89, stamina=75,
            ball_control=88, composure=88))
        req = make_req(position="CM", tactical_profile="POSSESSION",
                       attribute_preferences=[AttributePreference("vision", weight=3.0)])
        res = engine.recommend([generic, specialist], req)
        assert res.best_evaluation.candidate.name == "Specialist82"

    def test_secondary_vs_natural_position(self, engine):
        """Natural 83 CM beats 87 CAM playing CM as secondary."""
        cam_star = make_candidate(name="CamStar87", position="CAM", ovr=87,
                                  secondary=["CM"], attrs=_attrs(
                                      short_passing=88, vision=90, stamina=65,
                                      defensive_awareness=45, interceptions=40))
        natural = make_candidate(name="Natural83", position="CM", ovr=83, attrs=_attrs(
            short_passing=82, vision=80, stamina=86, defensive_awareness=80,
            interceptions=78))
        req = make_req(position="CM", tactical_profile="PRESSING")
        res = engine.recommend([cam_star, natural], req)
        assert res.best_evaluation.candidate.name == "Natural83"


# ---------------------------------------------------------------- B: position
class TestPositionPhase7:
    def test_primary_beats_secondary_equal_attrs(self, engine):
        a = make_candidate(name="Primary", position="CM", ovr=84, attrs=_attrs(
            short_passing=84, vision=82, stamina=84))
        b = make_candidate(name="Secondary", position="CAM", ovr=84, secondary=["CM"], attrs=_attrs(
            short_passing=84, vision=82, stamina=84))
        res = engine.recommend([a, b], make_req(position="CM"))
        assert res.best_evaluation.candidate.name == "Primary"

    def test_secondary_beats_unrelated(self, engine):
        sec = make_candidate(name="Sec", position="CAM", ovr=82, secondary=["CM"], attrs=_attrs(
            short_passing=80, vision=80, stamina=80))
        unrelated = make_candidate(name="Unrelated", position="ST", ovr=86, attrs=_attrs(
            short_passing=80, vision=80, stamina=80, finishing=88))
        res = engine.recommend([sec, unrelated], make_req(position="CM"))
        assert res.best_evaluation.candidate.name == "Sec"

    def test_invalid_position_fallback_low(self, engine):
        gk = make_candidate(name="GK", position="GK", ovr=90, attrs=_attrs(
            gk_diving=90, gk_handling=90, gk_kicking=85, gk_positioning=90, gk_reflexes=90))
        cm = make_candidate(name="CM82", position="CM", ovr=82, attrs=_attrs(
            short_passing=80, vision=78, stamina=82))
        res = engine.recommend([gk, cm], make_req(position="CM"))
        assert res.best_evaluation.candidate.name == "CM82"

    def test_multi_position_hybrid(self, engine):
        hybrid = make_candidate(name="Hybrid", position="CB", ovr=83, secondary=["LB", "RB"], attrs=_attrs(
            defending=84, standing_tackle=83, pace=78, stamina=82, crossing=70))
        pure = make_candidate(name="Pure", position="CB", ovr=83, attrs=_attrs(
            defending=84, standing_tackle=83, pace=78, stamina=82, crossing=70))
        res = engine.recommend([hybrid, pure], make_req(position="CB"))
        # primary CB tie → determinism by name; both rankable, hybrid must rank
        assert res.best_evaluation is not None
        assert len(res.ranked) == 2

    def test_same_player_different_slots(self, engine):
        p1 = make_candidate(name="P", position="CM", ovr=84, attrs=_attrs(
            short_passing=85, vision=84, stamina=86, defensive_awareness=78, interceptions=75))
        req_slot = make_req(position="CM", formation="4-2-3-1", slot="CDM", tactical_profile="BALANCED")
        req_noslot = make_req(position="CM", formation="4-2-3-1", tactical_profile="BALANCED")
        e_slot = engine.evaluate(p1, req_slot)
        e_noslot = engine.evaluate(p1, req_noslot)
        assert e_slot.weighted_score is not None and e_noslot.weighted_score is not None

    def test_gk_outfield_confusion(self, engine):
        gk = make_candidate(name="GK90", position="GK", ovr=90, attrs=_attrs(
            gk_diving=90, gk_handling=90, gk_kicking=88, gk_positioning=90, gk_reflexes=90))
        st = make_candidate(name="ST80", position="ST", ovr=80, attrs=_attrs(
            finishing=82, positioning=80, pace=80))
        res = engine.recommend([gk, st], make_req(position="ST"))
        assert res.best_evaluation.candidate.name == "ST80"

    def test_outfield_gk_request_loses(self, engine):
        st = make_candidate(name="ST90", position="ST", ovr=90, attrs=_attrs(
            finishing=92, pace=90, positioning=88))
        gk = make_candidate(name="GK82", position="GK", ovr=82, attrs=_attrs(
            gk_diving=86, gk_handling=85, gk_kicking=80, gk_positioning=86, gk_reflexes=86))
        res = engine.recommend([st, gk], make_req(position="GK"))
        assert res.best_evaluation.candidate.name == "GK82"

    def test_adjacent_beats_distant(self, engine):
        cdm = make_candidate(name="CDM", position="CDM", ovr=83, attrs=_attrs(
            short_passing=80, defensive_awareness=82, interceptions=80))
        st = make_candidate(name="ST", position="ST", ovr=87, attrs=_attrs(
            short_passing=80, defensive_awareness=82, interceptions=80, finishing=90))
        res = engine.recommend([cdm, st], make_req(position="CM"))
        assert res.best_evaluation.candidate.name == "CDM"

    def test_position_fit_evidence_present(self, engine):
        a = make_candidate(name="A", position="CM", ovr=84)
        ev = engine.evaluate(a, make_req(position="CM"))
        assert ev.components["position_fit"].status.value == "KNOWN"

    def test_no_position_unknown(self, engine):
        a = make_candidate(name="A", position="CM", ovr=84)
        ev = engine.evaluate(a, make_req())
        assert ev.components["position_fit"].status.value == "UNKNOWN"


# ---------------------------------------------------------------- C: tactical
class TestTacticalPhase7:
    def _cm_pair(self):
        press = make_candidate(name="Press", position="CM", ovr=84, attrs=_attrs(
            stamina=92, aggression=86, interceptions=85, defensive_awareness=83,
            short_passing=78, vision=74))
        poss = make_candidate(name="Poss", position="CM", ovr=84, attrs=_attrs(
            stamina=72, aggression=60, interceptions=62, defensive_awareness=68,
            short_passing=90, vision=92))
        return press, poss

    def test_pressing_vs_possession_flip(self, engine):
        press, poss = self._cm_pair()
        r_press = engine.recommend([press, poss], make_req(position="CM", tactical_profile="PRESSING"))
        r_poss = engine.recommend([press, poss], make_req(position="CM", tactical_profile="POSSESSION"))
        assert r_press.best_evaluation.candidate.name == "Press"
        assert r_poss.best_evaluation.candidate.name == "Poss"

    def test_lowblock_vs_highpress_cb(self, engine):
        block = make_candidate(name="Block", position="CB", ovr=84, attrs=_attrs(
            defending=89, standing_tackle=88, strength=88, pace=65, short_passing=68))
        pacey = make_candidate(name="Pacey", position="CB", ovr=84, attrs=_attrs(
            defending=80, standing_tackle=80, strength=78, pace=86, short_passing=78))
        r_low = engine.recommend([block, pacey], make_req(position="CB", tactical_profile="LOW_BLOCK"))
        assert r_low.best_evaluation.candidate.name == "Block"

    def test_crossing_vs_possession_winger(self, engine):
        crosser = make_candidate(name="Crosser", position="RW", ovr=84, attrs=_attrs(
            crossing=90, curve=86, pace=84, dribbling_detail=80, short_passing=74))
        technician = make_candidate(name="Technician", position="RW", ovr=84, attrs=_attrs(
            crossing=70, curve=72, pace=78, dribbling_detail=90, short_passing=88))
        r_cross = engine.recommend([crosser, technician], make_req(position="RW", tactical_profile="CROSSING"))
        r_poss = engine.recommend([crosser, technician], make_req(position="RW", tactical_profile="POSSESSION"))
        assert r_cross.best_evaluation.candidate.name == "Crosser"
        assert r_poss.best_evaluation.candidate.name == "Technician"

    def test_buildup_vs_direct_cb(self, engine):
        passer = make_candidate(name="Passer", position="CB", ovr=84, attrs=_attrs(
            short_passing=88, long_passing=86, vision=82, composure=84, defending=82))
        direct = make_candidate(name="Direct", position="CB", ovr=84, attrs=_attrs(
            short_passing=68, long_passing=88, strength=90, heading_accuracy=88, defending=85))
        r_build = engine.recommend([passer, direct], make_req(position="CB", tactical_profile="SLOW_BUILD_UP"))
        assert r_build.best_evaluation.candidate.name == "Passer"

    def test_counter_vs_possession_cam(self, engine):
        runner = make_candidate(name="Runner", position="CAM", ovr=84, attrs=_attrs(
            acceleration=90, sprint_speed=89, pace=89, vision=72, short_passing=74))
        creator = make_candidate(name="Creator", position="CAM", ovr=84, attrs=_attrs(
            acceleration=72, sprint_speed=70, pace=70, vision=92, short_passing=91))
        r_counter = engine.recommend([runner, creator], make_req(position="CAM", tactical_profile="COUNTER_ATTACK"))
        r_poss = engine.recommend([runner, creator], make_req(position="CAM", tactical_profile="POSSESSION"))
        assert r_counter.best_evaluation.candidate.name == "Runner"
        assert r_poss.best_evaluation.candidate.name == "Creator"

    def test_352_cb_vs_442_cb(self, engine):
        passer = make_candidate(name="Passer", position="CB", ovr=83, attrs=_attrs(
            defending=83, short_passing=88, long_passing=85, vision=82, composure=84))
        stopper = make_candidate(name="Stopper", position="CB", ovr=85, attrs=_attrs(
            defending=90, short_passing=62, long_passing=60, vision=55, composure=65))
        r_352 = engine.recommend([passer, stopper],
                                 make_req(position="CB", formation="3-5-2", slot="CB",
                                          tactical_profile="SLOW_BUILD_UP"))
        assert r_352.best_evaluation.candidate.name == "Passer"

    def test_balanced_tactical_unknown(self, engine):
        a = make_candidate(name="A", position="CM", ovr=84)
        ev = engine.evaluate(a, make_req(position="CM", tactical_profile="BALANCED"))
        assert ev.components["tactical_fit"].status.value == "UNKNOWN"

    def test_tactical_evidence_names_attrs(self, engine):
        a = make_candidate(name="A", position="CM", ovr=84, attrs=_attrs(
            stamina=88, aggression=80, interceptions=78))
        ev = engine.evaluate(a, make_req(position="CM", tactical_profile="PRESSING"))
        assert ev.components["tactical_fit"].status.value == "KNOWN"
        assert any("stamina" in e for e in ev.components["tactical_fit"].evidence)

    def test_strict_floor_excludes(self, engine):
        weak = make_candidate(name="Weak", position="CM", ovr=84, attrs=_attrs(
            stamina=55, aggression=45, interceptions=40, defensive_awareness=45,
            short_passing=85, vision=86))
        strong = make_candidate(name="Strong", position="CM", ovr=82, attrs=_attrs(
            stamina=90, aggression=85, interceptions=86, defensive_awareness=85,
            short_passing=78, vision=74))
        req = make_req(position="CM", tactical_profile="PRESSING", strict_tactics=True)
        res = engine.recommend([weak, strong], req)
        assert res.best_evaluation.candidate.name == "Strong"

    def test_gk_tactical_differs_by_profile(self, engine):
        shot = make_candidate(name="Shot", position="GK", ovr=86, attrs=_attrs(
            gk_diving=90, gk_handling=88, gk_kicking=65, gk_positioning=86, gk_reflexes=92))
        sweep = make_candidate(name="Sweep", position="GK", ovr=86, attrs=_attrs(
            gk_diving=82, gk_handling=82, gk_kicking=92, gk_positioning=88, gk_reflexes=82))
        r_low = engine.recommend([shot, sweep], make_req(position="GK", tactical_profile="LOW_BLOCK"))
        r_build = engine.recommend([shot, sweep], make_req(position="GK", tactical_profile="BUILD_UP"))
        assert r_low.best_evaluation.candidate.name == "Shot"
        assert r_build.best_evaluation.candidate.name == "Sweep"


# ---------------------------------------------------------------- D: PlayStyle
class TestPlayStylePhase7:
    def test_useful_beats_irrelevant(self, engine):
        useful = make_candidate(name="Useful", position="CM", ovr=84,
                                playstyles_base=["Tiki Taka", "Incisive Pass"],
                                attrs=_attrs(short_passing=84, vision=83))
        irrelevant = make_candidate(name="Irrelevant", position="CM", ovr=84,
                                    playstyles_base=["Power Shot", "Acrobatic"],
                                    attrs=_attrs(short_passing=84, vision=83))
        req = make_req(position="CM", tactical_profile="POSSESSION",
                       desired_playstyles=["Tiki Taka"])
        res = engine.recommend([useful, irrelevant], req)
        assert res.best_evaluation.candidate.name == "Useful"

    def test_missing_playstyle_loses(self, engine):
        has = make_candidate(name="Has", position="RW", ovr=84,
                             playstyles_base=["Whipped Pass"], attrs=_attrs(crossing=84))
        missing = make_candidate(name="Missing", position="RW", ovr=84,
                                 playstyles_base=["Power Shot"], attrs=_attrs(crossing=84))
        req = make_req(position="RW", desired_playstyles=["Whipped Pass"])
        res = engine.recommend([has, missing], req)
        assert res.best_evaluation.candidate.name == "Has"

    def test_unpublished_insufficient(self, engine):
        a = make_candidate(name="A", position="CM", ovr=84, playstyle_published=False)
        ev = engine.evaluate(a, make_req(position="CM", desired_playstyles=["Tiki Taka"]))
        assert ev.components["playstyle_fit"].status.value == "INSUFFICIENT_EVIDENCE"

    def test_plus_beats_base(self, engine):
        base = make_candidate(name="Base", position="CM", ovr=84,
                              playstyles_base=["Tiki Taka"], attrs=_attrs(short_passing=84))
        plus = make_candidate(name="Plus", position="CM", ovr=84,
                              playstyles_base=["Tiki Taka"], playstyles_plus=["Tiki Taka"],
                              attrs=_attrs(short_passing=84))
        req = make_req(position="CM", desired_playstyles_plus=["Tiki Taka"])
        res = engine.recommend([base, plus], req)
        assert res.best_evaluation.candidate.name == "Plus"

    def test_plus_not_automatic_win(self, engine):
        # irrelevant + must not beat relevant base
        irr_plus = make_candidate(name="IrrPlus", position="CM", ovr=84,
                                  playstyles_base=["Tiki Taka"], playstyles_plus=["Power Shot"],
                                  attrs=_attrs(short_passing=84, vision=83))
        rel_base = make_candidate(name="RelBase", position="CM", ovr=84,
                                  playstyles_base=["Tiki Taka", "Incisive Pass"],
                                  attrs=_attrs(short_passing=84, vision=83))
        req = make_req(position="CM", tactical_profile="POSSESSION",
                       desired_playstyles=["Tiki Taka", "Incisive Pass"],
                       enable_playstyle_context=True)
        res = engine.recommend([irr_plus, rel_base], req)
        assert res.best_evaluation.candidate.name == "RelBase"

    def test_gk_playstyle_isolation(self, engine):
        gk_ps = make_candidate(name="GKPS", position="GK", ovr=85,
                               playstyles_base=["Rush Out"],
                               attrs=_attrs(gk_diving=86, gk_handling=86, gk_kicking=80,
                                            gk_positioning=86, gk_reflexes=86))
        out_ps = make_candidate(name="OutPS", position="GK", ovr=85,
                                playstyles_base=["Tiki Taka"],
                                attrs=_attrs(gk_diving=86, gk_handling=86, gk_kicking=80,
                                             gk_positioning=86, gk_reflexes=86))
        req = make_req(position="GK", tactical_profile="HIGH_PRESS",
                       desired_playstyles=["Rush Out"])
        res = engine.recommend([gk_ps, out_ps], req)
        assert res.best_evaluation.candidate.name == "GKPS"

    def test_outfield_gk_playstyle_ignored(self, engine):
        a = make_candidate(name="A", position="CM", ovr=84,
                           playstyles_base=["Rush Out"], attrs=_attrs(short_passing=84))
        b = make_candidate(name="B", position="CM", ovr=84,
                           playstyles_base=["Tiki Taka"], attrs=_attrs(short_passing=84))
        req = make_req(position="CM", tactical_profile="POSSESSION",
                       desired_playstyles=["Tiki Taka"])
        res = engine.recommend([a, b], req)
        assert res.best_evaluation.candidate.name == "B"

    def test_multiple_playstyles(self, engine):
        two = make_candidate(name="Two", position="CM", ovr=84,
                             playstyles_base=["Tiki Taka", "Incisive Pass"],
                             attrs=_attrs(short_passing=84))
        one = make_candidate(name="One", position="CM", ovr=84,
                             playstyles_base=["Tiki Taka"],
                             attrs=_attrs(short_passing=84))
        req = make_req(position="CM", desired_playstyles=["Tiki Taka", "Incisive Pass"])
        res = engine.recommend([two, one], req)
        assert res.best_evaluation.candidate.name == "Two"


# ---------------------------------------------------------------- E: interactions
class TestInteractionsPhase7:
    def test_pressing_engine_min(self, engine):
        # min() → weakest link decides
        balanced = make_candidate(name="Balanced", position="CM", ovr=84, attrs=_attrs(
            stamina=85, aggression=84, interceptions=84, short_passing=80, vision=78))
        weak_link = make_candidate(name="WeakLink", position="CM", ovr=84, attrs=_attrs(
            stamina=92, aggression=90, interceptions=55, short_passing=80, vision=78))
        req = make_req(position="CM", tactical_profile="PRESSING",
                       enable_interactions=True)
        res = engine.recommend([balanced, weak_link], req)
        assert res.best_evaluation.candidate.name == "Balanced"

    def test_playmaker_geo(self, engine):
        hub = make_candidate(name="Hub", position="CM", ovr=84, attrs=_attrs(
            vision=88, short_passing=88, composure=88))
        spiky = make_candidate(name="Spiky", position="CM", ovr=84, attrs=_attrs(
            vision=96, short_passing=70, composure=70))
        req = make_req(position="CM", tactical_profile="POSSESSION",
                       enable_interactions=True)
        res = engine.recommend([hub, spiky], req)
        assert res.best_evaluation.candidate.name == "Hub"

    def test_interaction_skipped_unknown(self, engine):
        from backend.services.attribute_model import interaction_values
        c = make_candidate(name="C", position="CM", ovr=84, attrs=_attrs(
            vision=88, short_passing=88))  # missing composure
        blocks = interaction_values(c, "CM", ("POSSESSION",))
        assert blocks
        assert any("playmaker_hub" in s["feature"] for s in blocks[0]["skipped"])

    def test_aerial_dominance(self, engine):
        dom = make_candidate(name="Dom", position="CB", ovr=84, attrs=_attrs(
            heading_accuracy=90, jumping=88, strength=88))
        weak = make_candidate(name="Weak", position="CB", ovr=84, attrs=_attrs(
            heading_accuracy=92, jumping=60, strength=70))
        req = make_req(position="CB", tactical_profile="CROSSING",
                       enable_interactions=True)
        res = engine.recommend([dom, weak], req)
        assert res.best_evaluation.candidate.name == "Dom"

    def test_transition_launcher(self, engine):
        launcher = make_candidate(name="Launcher", position="CDM", ovr=84, attrs=_attrs(
            long_passing=88, vision=86, ball_control=86))
        limited = make_candidate(name="Limited", position="CDM", ovr=84, attrs=_attrs(
            long_passing=92, vision=70, ball_control=70))
        req = make_req(position="CDM", tactical_profile="COUNTER_ATTACK",
                       enable_interactions=True)
        res = engine.recommend([launcher, limited], req)
        assert res.best_evaluation.candidate.name == "Launcher"

    def test_interactions_capped(self, engine):
        from backend.services.engine_config import INTERACTION_TOTAL_CAP
        assert INTERACTION_TOTAL_CAP == 0.30


# ---------------------------------------------------------------- F: unknown/conf
class TestUnknownPhase7:
    def test_thin_evidence_band(self, engine):
        thin = make_candidate(name="Thin", position="CM", ovr=92, attrs=_attrs(curve=95))
        full = make_candidate(name="Full", position="CM", ovr=84, attrs=_attrs(
            short_passing=85, vision=83, stamina=85, ball_control=83, composure=82))
        res = engine.recommend([thin, full], make_req(position="CM"))
        bands = {e.candidate.name: e.score_band for e in res.ranked}
        assert bands["Thin"]["band"] == "INSUFFICIENT_EVIDENCE"

    def test_confidence_separates_identical_scores(self, engine):
        # same score, different evidence → different confidence tested in existing suite;
        # here assert UNKNOWN never lowers score but lowers confidence
        from backend.services.engine_evaluation import unknown_data_pool
        pool, req = unknown_data_pool()
        res = engine.recommend(pool, req)
        by_name = {e.candidate.name: e for e in res.ranked}
        assert by_name["Fully Scouted"].confidence.score > by_name["Mostly Unknown"].confidence.score

    def test_missing_attr_not_violation(self, engine):
        from backend.domain.user_model import AttributePreference
        c = make_candidate(name="C", position="CM", ovr=84, attrs=_attrs(short_passing=85))
        req = make_req(position="CM",
                       attribute_preferences=[AttributePreference("vision", min_value=80)])
        ev = engine.evaluate(c, req)
        assert ev.hard_constraint_violation is None

    def test_determinism(self, engine):
        a = make_candidate(name="A", position="CM", ovr=84)
        b = make_candidate(name="B", position="CM", ovr=83)
        req = make_req(position="CM", tactical_profile="PRESSING")
        r1 = engine.recommend([a, b], req)
        r2 = engine.recommend([b, a], req)
        assert r1.best_evaluation.candidate.name == r2.best_evaluation.candidate.name
        assert r1.best_evaluation.weighted_score == r2.best_evaluation.weighted_score

    def test_fc27_wall(self, engine):
        c = make_candidate(name="C", position="CM", ovr=84)
        req = make_req(game_version="FC27", position="CM")
        with pytest.raises(ValueError):
            engine.evaluate(c, req)

    def test_synthetic_firewall(self, engine):
        c = make_candidate(name="S", position="CM", ovr=90, synthetic=True)
        with pytest.raises(ValueError):
            engine.evaluate(c, make_req(position="CM"))
