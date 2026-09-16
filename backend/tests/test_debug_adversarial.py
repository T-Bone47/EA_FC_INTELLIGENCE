"""Debug test to inspect component values for failing tests."""
from __future__ import annotations

import pytest

from backend.services.recommendation_engine_v2 import RecommendationEngineV2
from backend.domain.user_model import UserRequirements
from backend.services.engine_evaluation import attrs, cand


@pytest.fixture()
def engine():
    return RecommendationEngineV2()


def test_debug_gk_low_block(engine):
    """Debug GK LOW_BLOCK test."""
    gen = cand('Generic90', 'GK', 90, attrs(
        gk_diving=80, gk_handling=80, gk_kicking=80, gk_positioning=80, gk_reflexes=80))
    spec = cand('Specialist82', 'GK', 82, attrs(
        gk_diving=92, gk_handling=90, gk_kicking=70, gk_positioning=90, gk_reflexes=92))
    req = UserRequirements(game_version='FC26', position='GK',
                           tactical_profile='LOW_BLOCK', limit=5)
    res = engine.recommend([gen, spec], req)
    best = res.best_evaluation
    components = {k: (v.status.value, v.value) for k, v in best.components.items()}
    print(f"Winner: {best.candidate.name}")
    print(f"Components: {components}")
    print(f"Score: {best.weighted_score}")
    for e in res.ranked:
        print(f"  {e.candidate.name}: score={e.weighted_score:.4f}, OVR={e.candidate.overall_rating}")
    assert False, f"Debug: winner={best.candidate.name}, components={components}"


def test_debug_st_possession(engine):
    """Debug ST POSSESSION test."""
    shooter = cand('Shooter89', 'ST', 89, attrs(
        finishing=93, shot_power=92, positioning=80, short_passing=62,
        vision=60, ball_control=70, composure=75, dribbling_detail=68))
    linker = cand('Linker83', 'ST', 83, attrs(
        finishing=80, shot_power=78, positioning=82, short_passing=84,
        vision=84, ball_control=86, composure=84, dribbling_detail=84))
    req = UserRequirements(game_version='FC26', position='ST', tactical_profile='POSSESSION', limit=5)
    res = engine.recommend([shooter, linker], req)
    best = res.best_evaluation
    components = {k: (v.status.value, v.value) for k, v in best.components.items()}
    print(f"Winner: {best.candidate.name}")
    print(f"Components: {components}")
    print(f"Score: {best.weighted_score}")
    for e in res.ranked:
        print(f"  {e.candidate.name}: score={e.weighted_score:.4f}, OVR={e.candidate.overall_rating}")
    assert False, f"Debug: winner={best.candidate.name}, components={components}"


def test_debug_winger_low_block(engine):
    """Debug RW LOW_BLOCK test."""
    attacker = cand('Attacker87', 'RW', 87, attrs(
        pace=90, dribbling_detail=90, finishing=85, crossing=84,
        defending=40, interceptions=38, standing_tackle=35, stamina=70))
    worker = cand('Worker82', 'RW', 82, attrs(
        pace=78, dribbling_detail=75, finishing=70, crossing=76,
        defending=75, interceptions=74, standing_tackle=72, stamina=88))
    req = UserRequirements(game_version='FC26', position='RW', tactical_profile='LOW_BLOCK', limit=5)
    res = engine.recommend([attacker, worker], req)
    best = res.best_evaluation
    components = {k: (v.status.value, v.value) for k, v in best.components.items()}
    print(f"Winner: {best.candidate.name}")
    print(f"Components: {components}")
    print(f"Score: {best.weighted_score}")
    for e in res.ranked:
        print(f"  {e.candidate.name}: score={e.weighted_score:.4f}, OVR={e.candidate.overall_rating}")
    assert False, f"Debug: winner={best.candidate.name}, components={components}"


def test_debug_pressing_vs_possession(engine):
    """Debug PRESSING vs POSSESSION flip."""
    cm_press = cand('Press', 'CM', 84, attrs(
        stamina=92, aggression=86, interceptions=85, defensive_awareness=83,
        short_passing=78, vision=74))
    cm_poss = cand('Poss', 'CM', 84, attrs(
        stamina=72, aggression=60, interceptions=62, defensive_awareness=68,
        short_passing=90, vision=92))
    req1 = UserRequirements(game_version='FC26', position='CM',
                           tactical_profile='PRESSING', limit=5)
    req2 = UserRequirements(game_version='FC26', position='CM',
                           tactical_profile='POSSESSION', limit=5)
    res1 = engine.recommend([cm_press, cm_poss], req1)
    res2 = engine.recommend([cm_press, cm_poss], req2)
    print(f"PRESSING winner: {res1.best_evaluation.candidate.name}")
    print(f"POSSESSION winner: {res2.best_evaluation.candidate.name}")
    for e in res1.ranked:
        print(f"  PRESSING: {e.candidate.name} score={e.weighted_score:.4f}")
    for e in res2.ranked:
        print(f"  POSSESSION: {e.candidate.name} score={e.weighted_score:.4f}")
    assert False, "Debug"


def test_debug_crossing_vs_possession(engine):
    """Debug CROSSING vs POSSESSION for RW."""
    crosser = cand('Crosser', 'RW', 84, attrs(
        crossing=90, curve=86, pace=84, dribbling_detail=80, short_passing=74))
    technician = cand('Technician', 'RW', 84, attrs(
        crossing=70, curve=72, pace=78, dribbling_detail=90, short_passing=88))
    req_cross = UserRequirements(game_version='FC26', position='RW',
                                 tactical_profile='CROSSING', limit=5)
    req_poss = UserRequirements(game_version='FC26', position='RW',
                                tactical_profile='POSSESSION', limit=5)
    res_cross = engine.recommend([crosser, technician], req_cross)
    res_poss = engine.recommend([crosser, technician], req_poss)
    print(f"CROSSING winner: {res_cross.best_evaluation.candidate.name}")
    print(f"POSSESSION winner: {res_poss.best_evaluation.candidate.name}")
    for e in res_cross.ranked:
        print(f"  CROSSING: {e.candidate.name} score={e.weighted_score:.4f}")
    for e in res_poss.ranked:
        print(f"  POSSESSION: {e.candidate.name} score={e.weighted_score:.4f}")
    assert False, "Debug"


def test_debug_buildup_vs_direct_cb(engine):
    """Debug SLOW_BUILD_UP vs DIRECT_PLAY for CB."""
    passer = cand('Passer', 'CB', 84, attrs(
        defending=83, standing_tackle=84, interceptions=83, heading_accuracy=80,
        strength=82, defensive_awareness=84, jumping=78, aggression=75,
        reactions=80, pace=72, short_passing=85, long_passing=84, vision=80,
        composure=84, ball_control=78))
    direct = cand('Direct', 'CB', 84, attrs(
        defending=91, standing_tackle=90, heading_accuracy=86,
        strength=90, defensive_awareness=89, jumping=86, aggression=90,
        reactions=84, pace=70, short_passing=55, long_passing=50, vision=45,
        composure=60, ball_control=52))
    req = UserRequirements(game_version='FC26', position='CB',
                           tactical_profile='SLOW_BUILD_UP', limit=5)
    res = engine.recommend([passer, direct], req)
    best = res.best_evaluation
    components = {k: (v.status.value, v.value) for k, v in best.components.items()}
    print(f"Winner: {best.candidate.name}")
    print(f"Components: {components}")
    print(f"Score: {best.weighted_score}")
    for e in res.ranked:
        print(f"  {e.candidate.name}: score={e.weighted_score:.4f}")
    assert False, "Debug"


def test_debug_352_cb(engine):
    """Debug 3-5-2 middle CB slot."""
    passer = cand('Ball Playing CB', 'CB', 83, attrs(
        defending=85, standing_tackle=82, interceptions=80, heading_accuracy=80,
        strength=82, defensive_awareness=82, jumping=78, aggression=75,
        reactions=78, pace=60, short_passing=90, long_passing=88, vision=85, composure=85))
    stopper = cand('Traditional CB', 'CB', 85, attrs(
        defending=88, standing_tackle=86, interceptions=84, heading_accuracy=85,
        strength=88, defensive_awareness=86, jumping=82, aggression=82,
        reactions=80, pace=60, short_passing=50, long_passing=45, vision=40, composure=55))
    req = UserRequirements(game_version='FC26', position='CB', formation='3-5-2',
                           slot='CB', tactical_profile='SLOW_BUILD_UP', limit=5)
    res = engine.recommend([passer, stopper], req)
    best = res.best_evaluation
    components = {k: (v.status.value, v.value) for k, v in best.components.items()}
    print(f"Winner: {best.candidate.name}")
    print(f"Components: {components}")
    print(f"Score: {best.weighted_score}")
    for e in res.ranked:
        print(f"  {e.candidate.name}: score={e.weighted_score:.4f}")
    assert False, "Debug"


def test_debug_strict_floor(engine):
    """Debug strict floor test."""
    weak = cand('Weak', 'CM', 84, attrs(
        stamina=55, aggression=45, interceptions=40, defensive_awareness=45,
        short_passing=85, vision=86))
    strong = cand('Strong', 'CM', 82, attrs(
        stamina=90, aggression=85, interceptions=86, defensive_awareness=85,
        short_passing=78, vision=74))
    req = UserRequirements(game_version='FC26', position='CM',
                           tactical_profile='PRESSING', strict_tactics=True, limit=5)
    res = engine.recommend([weak, strong], req)
    print(f"Winner: {res.best_evaluation.candidate.name}")
    print(f"Excluded by floor: {res.excluded_by_floor}")
    for e in res.ranked:
        print(f"  {e.candidate.name}: score={e.weighted_score:.4f}, floor={e.below_tactical_floor}")
    assert False, "Debug"


def test_debug_tactical_evidence(engine):
    """Debug tactical_fit evidence."""
    a = cand('Test', 'CM', 84, attrs(
        stamina=88, aggression=80, interceptions=78, defensive_awareness=83))
    req = UserRequirements(game_version='FC26', position='CM',
                           tactical_profile='PRESSING', limit=5)
    res = engine.recommend([a], req)
    ev = res.best_evaluation
    tf = ev.components['tactical_fit']
    print(f"tactical_fit status: {tf.status.value}")
    print(f"tactical_fit value: {tf.value}")
    print(f"tactical_fit evidence: {list(tf.evidence) if tf.evidence else 'None'}")
    assert False, "Debug"


def test_debug_gk_evidence(engine):
    """Debug GK tactical_fit evidence."""
    gk = cand('Test GK', 'GK', 87, attrs(
        gk_diving=88, gk_handling=86, gk_kicking=70, gk_positioning=88, gk_reflexes=89))
    req = UserRequirements(game_version='FC26', position='GK',
                           tactical_profile='LOW_BLOCK', limit=5)
    res = engine.recommend([gk], req)
    ev = res.best_evaluation
    tf = ev.components['tactical_fit']
    print(f"tactical_fit status: {tf.status.value}")
    print(f"tactical_fit value: {tf.value}")
    print(f"tactical_fit evidence: {list(tf.evidence) if tf.evidence else 'None'}")
    assert False, "Debug"