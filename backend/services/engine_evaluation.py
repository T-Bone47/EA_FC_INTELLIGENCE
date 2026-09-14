"""ENGINE EVALUATION SUITE (§49, §50, §51).

Deterministic, DB-independent scenario factories + qualitative expectations.
Used by:
  * backend/tests/test_engine_scenarios.py (regression protection)
  * scripts/run_engine_experiment.py (§48 experiment framework)

Expectations are QUALITATIVE behavioral contracts ("the high-fit low-OVR
candidate must beat the OVR trap", "confidence must differ when evidence
differs") — never "player X must win", unless a scenario's own constructed
data forces it. Real-data golden scenarios live in
benchmarks/engine_baseline_v2_2026-09-14.json instead.

All candidates built here are in-memory test fixtures (data_status CANONICAL
so the synthetic firewall doesn't trip — they never touch the database).
"""
from __future__ import annotations

import uuid
from typing import Callable, Optional

from backend.domain.card_model import (
    Candidate, DataStatus, GameVersionCode, PlayerAttributes,
)
from backend.domain.user_model import (
    AttributeBand, AttributePreference, SquadContext, SquadSlot, UserRequirements,
)


def attrs(**kw) -> PlayerAttributes:
    a = PlayerAttributes()
    for k, v in kw.items():
        a.set(k, v)
    return a


def cand(name: str, position: str, ovr: Optional[int], a: PlayerAttributes,
         playstyles_base: Optional[list[str]] = None,
         playstyles_plus: Optional[list[str]] = None,
         published: bool = True, secondary: Optional[list[str]] = None,
         nation: str = "Testland", club: str = "Test FC", league: str = "Test League",
         price: Optional[int] = None,
         entity_id: Optional[uuid.UUID] = None) -> Candidate:
    return Candidate(
        entity_type="game_player", entity_id=entity_id or uuid.uuid4(),
        game_version=GameVersionCode.FC26, name=name, position_primary=position,
        secondary_positions=secondary or [], overall_rating=ovr, attributes=a,
        playstyles_base=playstyles_base if playstyles_base is not None else [],
        playstyles_plus=playstyles_plus or [], playstyle_data_published=published,
        nation=nation, club=club, league=league, price_coins=price,
        data_status=DataStatus.CANONICAL, is_synthetic=False,
        extra={"identity_status": "RESOLVED"},
    )


# ---------------------------------------------------------------------------
# §50 — the OVR trap: high OVR + poor fit vs low OVR + strong fit.
# ---------------------------------------------------------------------------
def ovr_trap_pool() -> tuple[list[Candidate], UserRequirements]:
    """High-press box-to-box CM request. 'Famous' has OVR 90 but low stamina/
    defensive work; 'Worker' has OVR 81 but elite engine + defense + passing."""
    famous = cand("Famous Star", "CM", 90, attrs(
        short_passing=88, vision=88, long_passing=85, stamina=55,
        ball_control=88, composure=90, defensive_awareness=40,
        interceptions=35, positioning=60, dribbling_detail=88,
        acceleration=70, sprint_speed=68, strength=70, aggression=40,
        long_shots=85, defending=42))
    worker = cand("League Worker", "CM", 81, attrs(
        short_passing=82, vision=76, long_passing=80, stamina=93,
        ball_control=78, composure=78, defensive_awareness=85,
        interceptions=86, positioning=80, dribbling_detail=74,
        acceleration=74, sprint_speed=72, strength=82, aggression=88,
        long_shots=65, defending=83))
    req = UserRequirements(game_version="FC26", position="CM",
                           tactical_profile="PRESSING",
                           attribute_preferences=[
                               AttributePreference("stamina", weight=2.0),
                               AttributePreference("interceptions", weight=1.5)],
                           limit=5)
    return [famous, worker], req


# ---------------------------------------------------------------------------
# §51 — unknown data: excellent known evidence vs high-theory missing evidence.
# ---------------------------------------------------------------------------
def unknown_data_pool() -> tuple[list[Candidate], UserRequirements]:
    full = cand("Fully Scouted", "CM", 85, attrs(
        short_passing=86, vision=84, long_passing=82, stamina=88,
        ball_control=84, composure=85, defensive_awareness=78,
        interceptions=75, positioning=78, dribbling_detail=80))
    partial = cand("Thin Evidence", "CM", 85, attrs(
        short_passing=92, vision=90, stamina=93))     # top-weight attrs known
    ghost = cand("Mostly Unknown", "CM", 92, attrs(
        curve=95, long_shots=94))                     # low-weight attrs only
    req = UserRequirements(game_version="FC26", position="CM", limit=5)
    return [full, partial, ghost], req


# ---------------------------------------------------------------------------
# scenario registry: name -> (pool_factory, requirement, expectation)
# expectation(engine_result_dict_or_result, evaluations) -> (ok, detail)
# ---------------------------------------------------------------------------
def _result(engine, pool, req, squad_ctx=None, **kw):
    return engine.recommend(pool, req, squad_ctx=squad_ctx, **kw)


SCENARIOS: dict[str, dict] = {}


def scenario(name: str):
    def deco(fn: Callable[[], dict]):
        SCENARIOS[name] = fn
        return fn
    return deco


@scenario("high_press_st")
def _s1():
    target = cand("Pressing Nine", "ST", 84, attrs(
        finishing=85, positioning=86, aggression=90, stamina=92,
        acceleration=86, sprint_speed=84, reactions=84, composure=80,
        shot_power=82, strength=78))
    lazy = cand("Luxury Forward", "ST", 88, attrs(
        finishing=92, positioning=88, aggression=45, stamina=52,
        acceleration=80, sprint_speed=82, reactions=82, composure=88,
        shot_power=90, strength=75))
    req = UserRequirements(game_version="FC26", position="ST",
                           tactical_profile="HIGH_PRESS", limit=5)
    return {"pool": [target, lazy], "req": req,
            "expect": "winner is the pressing forward despite -4 OVR; "
                      "tactical_fit decides"}


@scenario("possession_cam")
def _s2():
    creator = cand("Creator", "CAM", 85, attrs(
        vision=92, short_passing=91, long_passing=85, composure=89,
        ball_control=89, dribbling_detail=85, finishing=75, positioning=80,
        long_shots=78, curve=84, agility=82, reactions=84))
    runner = cand("Runner", "CAM", 86, attrs(
        vision=65, short_passing=70, long_passing=66, composure=70,
        ball_control=78, dribbling_detail=80, finishing=84, positioning=82,
        long_shots=80, curve=65, agility=88, reactions=85,
        acceleration=90, sprint_speed=88, pace=89))
    req = UserRequirements(game_version="FC26", position="CAM",
                           tactical_profile="POSSESSION", limit=5)
    return {"pool": [creator, runner], "req": req,
            "expect": "creator wins on vision/passing/composure demand"}


@scenario("counter_winger")
def _s3():
    bolt = cand("Bolt", "RW", 83, attrs(
        pace=96, acceleration=97, sprint_speed=95, dribbling_detail=82,
        finishing=76, crossing=78, agility=88, balance=78, ball_control=80,
        composure=72, curve=70, short_passing=68, stamina=80, reactions=80))
    technical = cand("Maestro Winger", "RW", 87, attrs(
        pace=74, acceleration=75, sprint_speed=73, dribbling_detail=91,
        finishing=84, crossing=86, agility=85, balance=88, ball_control=92,
        composure=88, curve=85, short_passing=84, stamina=76, reactions=85))
    req = UserRequirements(game_version="FC26", position="RW",
                           tactical_profile="COUNTER_ATTACK",
                           attribute_preferences=[
                               AttributePreference("pace", min_value=90, weight=2.0)],
                           limit=5)
    return {"pool": [bolt, technical], "req": req,
            "expect": "bolt wins; maestro EXCLUDED by the pace>=90 hard minimum"}


@scenario("defensive_cdm")
def _s4():
    anchor = cand("Anchor", "CDM", 84, attrs(
        defending=88, interceptions=90, standing_tackle=87,
        defensive_awareness=89, strength=86, aggression=84, stamina=88,
        short_passing=75, long_passing=72, vision=68, positioning=85,
        reactions=80, ball_control=72, composure=76))
    carrier = cand("Carrier", "CDM", 86, attrs(
        defending=65, interceptions=62, standing_tackle=64,
        defensive_awareness=66, strength=75, aggression=60, stamina=80,
        short_passing=88, long_passing=86, vision=88, positioning=75,
        reactions=82, ball_control=88, composure=86, dribbling_detail=85))
    req = UserRequirements(game_version="FC26", position="CDM",
                           tactical_profile="MID_BLOCK", limit=5)
    return {"pool": [anchor, carrier], "req": req,
            "expect": "anchor wins the defensive CDM job despite -2 OVR"}


@scenario("box_to_box_archetype")
def _s5():
    b2b = cand("Engine CM", "CM", 84, attrs(
        stamina=93, short_passing=83, long_passing=80, vision=78,
        defensive_awareness=83, interceptions=82, standing_tackle=78,
        ball_control=80, composure=80, strength=82, positioning=80,
        aggression=80, long_shots=72, dribbling_detail=76, reactions=80))
    ten = cand("Pure Ten", "CM", 88, secondary=["CAM"], a=attrs(
        stamina=62, short_passing=90, long_passing=84, vision=93,
        defensive_awareness=45, interceptions=40, standing_tackle=42,
        ball_control=92, composure=90, strength=65, positioning=70,
        aggression=45, long_shots=88, dribbling_detail=92, reactions=86))
    req = UserRequirements(game_version="FC26", position="CM",
                           archetype="BOX_TO_BOX", limit=5)
    return {"pool": [b2b, ten], "req": req,
            "expect": "BOX_TO_BOX request: engine CM wins; archetype_fit KNOWN "
                      "and weighted; Pure Ten's OVR edge does not save him"}


@scenario("ball_playing_cb")
def _s6():
    passer = cand("Passing CB", "CB", 84, attrs(
        defending=83, standing_tackle=84, interceptions=83, heading_accuracy=80,
        strength=82, defensive_awareness=84, jumping=78, aggression=75,
        reactions=80, pace=72, short_passing=85, long_passing=84, vision=80,
        composure=84, ball_control=78))
    destroyer = cand("Destroyer CB", "CB", 87, attrs(
        defending=91, standing_tackle=90, interceptions=88, heading_accuracy=86,
        strength=90, defensive_awareness=89, jumping=86, aggression=90,
        reactions=84, pace=70, short_passing=55, long_passing=50, vision=45,
        composure=60, ball_control=52))
    req = UserRequirements(game_version="FC26", position="CB",
                           tactical_profile="SLOW_BUILD_UP",
                           attribute_preferences=[
                               AttributePreference("short_passing", min_value=80),
                               AttributePreference("long_passing", weight=1.5)],
                           limit=5)
    return {"pool": [passer, destroyer], "req": req,
            "expect": "passing CB wins; destroyer EXCLUDED by short_passing>=80"}


@scenario("attacking_rb")
def _s7():
    overlap = cand("Overlapping RB", "RB", 82, attrs(
        defending=74, pace=90, stamina=91, crossing=87, standing_tackle=74,
        interceptions=70, defensive_awareness=72, dribbling_detail=80,
        short_passing=78, strength=70, acceleration=89, sprint_speed=88,
        curve=78, long_passing=74, agility=84, ball_control=79, reactions=76))
    stayback = cand("Stay-back RB", "RB", 85, attrs(
        defending=89, pace=72, stamina=76, crossing=60, standing_tackle=88,
        interceptions=85, defensive_awareness=88, dribbling_detail=62,
        short_passing=70, strength=82, acceleration=70, sprint_speed=71,
        curve=55, long_passing=66, agility=68, ball_control=66, reactions=78))
    req = UserRequirements(game_version="FC26", position="RB", formation="4-3-3",
                           slot="RB", archetype="ATTACKING_FULLBACK",
                           tactical_profile="CROSSING", limit=5)
    return {"pool": [overlap, stayback], "req": req,
            "expect": "overlapping RB wins the attacking slot despite -3 OVR"}


@scenario("low_block_gk")
def _s8():
    gk_a = cand("Keeper A", "GK", 87, attrs(
        gk_diving=88, gk_handling=86, gk_kicking=70, gk_positioning=88,
        gk_reflexes=89))
    gk_b = cand("Keeper B", "GK", 85, attrs(
        gk_diving=84, gk_handling=88, gk_kicking=90, gk_positioning=85,
        gk_reflexes=83))
    req = UserRequirements(game_version="FC26", position="GK",
                           tactical_profile="LOW_BLOCK", limit=5)
    return {"pool": [gk_a, gk_b], "req": req,
            "expect": "GK scored on gk_* only; keeper A wins; no outfield "
                      "attribute may appear in GK evidence"}


@scenario("budget_unverified")
def _s9():
    a = cand("Any A", "CM", 84, attrs(
        short_passing=82, vision=80, long_passing=78, stamina=85,
        ball_control=82, composure=80, defensive_awareness=72,
        interceptions=68, positioning=74, dribbling_detail=76))
    req = UserRequirements(game_version="FC26", position="CM",
                           budget_coins=50000, limit=5)
    return {"pool": [a], "req": req,
            "expect": "BUDGET_UNVERIFIED reported; candidate NOT excluded "
                      "(price UNKNOWN never assumed affordable OR unaffordable)"}


@scenario("chemistry_withheld")
def _s10():
    a = cand("Squad Guy", "CM", 84, attrs(
        short_passing=82, vision=80, long_passing=78, stamina=85,
        ball_control=82, composure=80, defensive_awareness=72,
        interceptions=68, positioning=74, dribbling_detail=76),
        club="Same Club", league="Same League", nation="Same Nation")
    mate = cand("Teammate", "ST", 85, attrs(finishing=85), club="Same Club",
                league="Same League", nation="Same Nation")
    ctx = SquadContext(squad_id=uuid.uuid4(), formation="4-3-3", game_version="FC26",
                       slots=[SquadSlot(0, "ST", game_player_id=mate.entity_id,
                                        club="Same Club", league="Same League",
                                        nation="Same Nation")])
    req = UserRequirements(game_version="FC26", position="CM", limit=5)
    return {"pool": [a], "req": req, "squad_ctx": ctx, "squad_members": [mate],
            "expect": "team_fit INSUFFICIENT (chemistry withheld); link facts "
                      "visible in evidence; squad_structural advisory present"}


@scenario("ovr_trap")
def _s11():
    pool, req = ovr_trap_pool()
    return {"pool": pool, "req": req,
            "expect": "MANDATORY §50: League Worker (81) beats Famous Star (90) "
                      "on SOFT fit — Famous Star ranks (never hidden) but loses"}


@scenario("unknown_data_honesty")
def _s12():
    pool, req = unknown_data_pool()
    return {"pool": pool, "req": req,
            "expect": "MANDATORY §51: nobody is excluded or zeroed for missing "
                      "data; Mostly Unknown / Thin Evidence may rank by score "
                      "(legacy contract: UNKNOWN never penalizes) BUT their band "
                      "is INSUFFICIENT_EVIDENCE and their confidence is far "
                      "below Fully Scouted's — score and confidence are "
                      "distinguished; Fully Scouted carries a real fit band"}


def run_all(engine_factory=None) -> dict[str, dict]:
    """Execute every scenario; returns raw results for tests/experiments."""
    from backend.services.recommendation_engine_v2 import RecommendationEngineV2
    out = {}
    for name, fn in SCENARIOS.items():
        spec = fn()
        engine = engine_factory() if engine_factory else RecommendationEngineV2()
        result = engine.recommend(spec["pool"], spec["req"],
                                  squad_ctx=spec.get("squad_ctx"),
                                  squad_members=spec.get("squad_members"))
        out[name] = {"spec": spec, "result": result}
    return out
