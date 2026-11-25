"""Phase 41 Counterfactual Engine, Monte Carlo Uncertainty, Defensive/Shooting/OffBall & Football IQ Tests."""
from __future__ import annotations

from backend.domain.phase41_models import ControllerAttribution, DecisionCategory
from backend.services.counterfactual_football_engine import CounterfactualFootballEngine
from backend.services.decision_scenario_service import DecisionScenarioService
from backend.services.decision_state_builder import build_state_from_snapshot
from backend.services.defensive_and_chance_intelligence import OffBallOpportunityEngine
from backend.services.football_iq_engine import FOOTBALL_IQ_DIMENSIONS, FootballIQEngine


def _attack_snap(cov: float = 92.0, cal: str = "GOOD") -> dict:
    return {
        "timestamp_sec": 34.0,
        "calibration_state": cal,
        "uncertainty_band": "LOW" if cov >= 70.0 else "MODERATE",
        "observation_coverage_pct": cov,
        "possession_team": "HOME",
        "ball_carrier_track_id": "H-CM",
        "ball_xy": [62.0, 34.0],
        "home_structure": {"rest_defense_count": 3, "def_to_mid_gap_m": 11.2},
        "kinematics": [
            {"track_id": "H-CM", "team": "HOME", "player_slot": "CM", "x_m": 62.0, "y_m": 34.0, "vx_mps": 1.0, "vy_mps": 0.0},
            {"track_id": "H-ST", "team": "HOME", "player_slot": "ST", "x_m": 78.0, "y_m": 34.0, "vx_mps": 3.5, "vy_mps": 0.0},
            {"track_id": "H-LW", "team": "HOME", "player_slot": "LW", "x_m": 75.0, "y_m": 55.0, "vx_mps": 4.8, "vy_mps": 0.2},
            {"track_id": "H-CDM", "team": "HOME", "player_slot": "CDM", "x_m": 50.0, "y_m": 33.0, "vx_mps": 0.2, "vy_mps": 0.0},
            {"track_id": "A-CDM", "team": "AWAY", "player_slot": "CDM", "x_m": 66.0, "y_m": 34.2, "vx_mps": 1.4, "vy_mps": 0.0},
            {"track_id": "A-CB1", "team": "AWAY", "player_slot": "CB", "x_m": 74.0, "y_m": 35.0, "vx_mps": -0.5, "vy_mps": 0.0},
            {"track_id": "A-RB", "team": "AWAY", "player_slot": "RB", "x_m": 73.0, "y_m": 53.5, "vx_mps": 2.4, "vy_mps": 0.1},
            {"track_id": "A-GK", "team": "AWAY", "player_slot": "GK", "is_goalkeeper": True, "x_m": 99.0, "y_m": 34.0, "vx_mps": 0.0, "vy_mps": 0.0},
        ],
    }


def _defensive_snap() -> dict:
    return {
        "timestamp_sec": 51.0,
        "calibration_state": "GOOD",
        "uncertainty_band": "LOW",
        "observation_coverage_pct": 88.0,
        "possession_team": "AWAY",
        "ball_carrier_track_id": "A-CAM",
        "ball_xy": [32.0, 34.0],
        "home_structure": {"rest_defense_count": 4, "def_to_mid_gap_m": 16.5},
        "kinematics": [
            {"track_id": "H-GK", "team": "HOME", "player_slot": "GK", "is_goalkeeper": True, "x_m": 5.0, "y_m": 34.0},
            {"track_id": "H-CB1", "team": "HOME", "player_slot": "CB", "x_m": 22.0, "y_m": 31.0},
            {"track_id": "H-CB2", "team": "HOME", "player_slot": "CB", "x_m": 22.0, "y_m": 38.0},
            {"track_id": "H-CDM", "team": "HOME", "player_slot": "CDM", "x_m": 36.0, "y_m": 33.0},
            {"track_id": "H-CM1", "team": "HOME", "player_slot": "CM", "x_m": 40.0, "y_m": 41.0},
            {"track_id": "H-LB", "team": "HOME", "player_slot": "LB", "x_m": 24.0, "y_m": 54.0},
            {"track_id": "H-RB", "team": "HOME", "player_slot": "RB", "x_m": 24.0, "y_m": 14.0},
            {"track_id": "A-CAM", "team": "AWAY", "player_slot": "CAM", "x_m": 32.0, "y_m": 34.0},
            {"track_id": "A-ST", "team": "AWAY", "player_slot": "ST", "x_m": 24.5, "y_m": 33.5},
        ],
    }


def test_monte_carlo_uncertainty_widens_under_partial_coverage_and_non_negative_regret():
    engine = CounterfactualFootballEngine(monte_carlo_samples=24)
    st_high = build_state_from_snapshot("M-MC", _attack_snap(cov=92.0, cal="GOOD"), observed_action_label="ST blocked pass")
    st_low = build_state_from_snapshot("M-MC", _attack_snap(cov=54.0, cal="PARTIAL"), observed_action_label="ST blocked pass")

    comp_hi = engine.evaluate(st_high)
    comp_lo = engine.evaluate(st_low)

    assert comp_hi.regret_estimate is not None and comp_hi.regret_estimate >= 0.0
    assert comp_hi.uncertainty is not None and comp_lo.uncertainty is not None

    spread_hi = comp_hi.uncertainty.q_p90 - comp_hi.uncertainty.q_p10
    spread_lo = comp_lo.uncertainty.q_p90 - comp_lo.uncertainty.q_p10
    assert spread_lo > spread_hi


def test_defensive_team_shape_framing_and_crowd_shot_heuristic():
    engine = CounterfactualFootballEngine()
    st_def = build_state_from_snapshot("M-DEF", _defensive_snap(), decision_type_hint="DEFENSIVE_ACTION")
    comp_def = engine.evaluate(st_def)
    assert comp_def.status == "EVALUATED"
    # Should never elevate reckless CB/box diving press above central protection / recovery
    assert comp_def.best_alternative_id != "DEF-5"
    assert any(c.defensive_eval and c.defensive_eval.controlled_player_known is False for c in comp_def.candidates)

    # Blocked crowded long shot vs open pass
    shot_snap = {
        "timestamp_sec": 71.2,
        "calibration_state": "GOOD",
        "uncertainty_band": "LOW",
        "observation_coverage_pct": 90.0,
        "possession_team": "HOME",
        "ball_carrier_track_id": "H-CM",
        "ball_xy": [82.0, 22.0],
        "home_structure": {"rest_defense_count": 3},
        "kinematics": [
            {"track_id": "H-CM", "team": "HOME", "player_slot": "CM", "x_m": 82.0, "y_m": 22.0},
            {"track_id": "H-ST", "team": "HOME", "player_slot": "ST", "x_m": 93.0, "y_m": 34.0},
            {"track_id": "A-CB1", "team": "AWAY", "player_slot": "CB", "x_m": 86.0, "y_m": 26.0},
            {"track_id": "A-CB2", "team": "AWAY", "player_slot": "CB", "x_m": 89.0, "y_m": 28.0},
            {"track_id": "A-RB", "team": "AWAY", "player_slot": "RB", "x_m": 85.0, "y_m": 24.0},
            {"track_id": "A-GK", "team": "AWAY", "player_slot": "GK", "is_goalkeeper": True, "x_m": 103.5, "y_m": 33.0},
        ],
    }
    st_shot = build_state_from_snapshot("M-SHOT", shot_snap, decision_type_hint="SHOT", observed_action_label="Attempt shot")
    comp_shot = engine.evaluate(st_shot)
    shot_cand = next(c for c in comp_shot.candidates if c.action_family == "SHOOT")
    assert shot_cand.shooting_eval is not None
    assert shot_cand.shooting_eval.is_calibrated_xg is False


def test_off_ball_honest_attribution_and_football_iq_synthetic_isolation():
    st = build_state_from_snapshot("M-OFFBALL", _attack_snap())
    runs = OffBallOpportunityEngine().detect_runs(st)
    assert len(runs) >= 1
    assert all(r.control_attribution == ControllerAttribution.UNKNOWN for r in runs)

    # Football IQ must exclude SYNTHETIC_FIXTURE strictly
    iq_engine = FootballIQEngine()
    synth_only = [{
        "window_id": "W-SYN",
        "match_id": "M-SYN",
        "cluster_id": "CL-SYN",
        "decision_type": "ATTACKING_PASS",
        "status": "EVALUATED",
        "provenance": "SYNTHETIC_FIXTURE",
        "regret_estimate": 0.25,
        "normalized_regret": 0.50,
    }]
    prof_synth = iq_engine.compute_profile("user-1", synth_only)
    assert prof_synth.eligible_decision_windows == 0
    assert prof_synth.synthetic_excluded_count == 1
    assert prof_synth.overall_football_iq is None
    assert len(prof_synth.dimensions) == len(FOOTBALL_IQ_DIMENSIONS) == 10

    # Real window + synthetic -> only real contributes, synthetic counted as excluded
    mixed = synth_only + [{
        "window_id": "W-REAL-1",
        "match_id": "M-REAL",
        "cluster_id": "CL-REAL-1",
        "decision_type": "ATTACKING_PASS",
        "status": "EVALUATED",
        "provenance": "IMPORTED_MATCH_TRACE",
        "action_timestamp_sec": 24.0,
        "regret_estimate": 0.04,
        "normalized_regret": 0.08,
        "pre_action_state": {"home_structure": {"rest_defense_count": 3}},
        "post_action_outcome": {"possession_retained_after_3s": False},
    }]
    prof_real = iq_engine.compute_profile("user-1", mixed)
    assert prof_real.eligible_decision_windows == 1
    assert prof_real.synthetic_excluded_count == 1
    assert prof_real.overall_football_iq is not None

    # Scenario export preserves hide_outcome_by_default=True & multi-answer options
    comp = CounterfactualFootballEngine().evaluate(st)
    scn = DecisionScenarioService().build_scenario(st, comp)
    assert scn.hide_outcome_by_default is True
    assert len(scn.defensible_option_ids) >= 1
