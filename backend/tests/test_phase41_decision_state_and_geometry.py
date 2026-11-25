"""Phase 41 Core Invariants: Pre-Action Isolation, Field Adequacy, Passing Geometry & Markov xT."""
from __future__ import annotations

import numpy as np

from backend.domain.phase41_models import (
    DecisionCategory,
    FieldAdequacyStatus,
    PostActionOutcome,
    ValuationStage,
)
from backend.services.counterfactual_football_engine import CounterfactualFootballEngine
from backend.services.decision_state_builder import (
    DecisionOpportunityDetector,
    build_state_from_snapshot,
)
from backend.services.passing_intelligence import PassingIntelligenceEngine
from backend.services.possession_value_engine import CalibratedEPVInterface, ExpectedThreatEngine


def _rich_attacking_snapshot(ts: float = 18.0, cov: float = 90.0, cal: str = "GOOD") -> dict:
    return {
        "timestamp_sec": ts,
        "calibration_state": cal,
        "uncertainty_band": "LOW" if cov >= 70.0 else "MODERATE",
        "observation_coverage_pct": cov,
        "possession_team": "HOME",
        "ball_carrier_track_id": "H-CM",
        "ball_xy": [58.0, 34.0],
        "home_structure": {"rest_defense_count": 3, "def_to_mid_gap_m": 11.0},
        "away_structure": {"rest_defense_count": 4, "def_to_mid_gap_m": 10.5},
        "kinematics": [
            {"track_id": "H-GK", "team": "HOME", "player_slot": "GK", "is_goalkeeper": True, "x_m": 5.0, "y_m": 34.0, "vx_mps": 0.0, "vy_mps": 0.0},
            {"track_id": "H-CM", "team": "HOME", "player_slot": "CM", "x_m": 58.0, "y_m": 34.0, "vx_mps": 1.2, "vy_mps": 0.0},
            {"track_id": "H-ST", "team": "HOME", "player_slot": "ST", "x_m": 78.0, "y_m": 34.5, "vx_mps": 2.5, "vy_mps": 0.0},
            {"track_id": "H-LW", "team": "HOME", "player_slot": "LW", "x_m": 73.0, "y_m": 56.0, "vx_mps": 3.5, "vy_mps": 0.2},
            {"track_id": "H-CDM", "team": "HOME", "player_slot": "CDM", "x_m": 46.0, "y_m": 31.0, "vx_mps": 0.2, "vy_mps": 0.0},
            {"track_id": "A-CDM", "team": "AWAY", "player_slot": "CDM", "x_m": 63.0, "y_m": 34.2, "vx_mps": 1.6, "vy_mps": 0.0},
            {"track_id": "A-CB1", "team": "AWAY", "player_slot": "CB", "x_m": 72.0, "y_m": 34.8, "vx_mps": -1.2, "vy_mps": 0.0},
            {"track_id": "A-RB", "team": "AWAY", "player_slot": "RB", "x_m": 70.0, "y_m": 46.0, "vx_mps": 0.1, "vy_mps": 0.2},
            {"track_id": "A-GK", "team": "AWAY", "player_slot": "GK", "is_goalkeeper": True, "x_m": 99.0, "y_m": 34.0, "vx_mps": 0.0, "vy_mps": 0.0},
        ],
    }


def test_zero_hindsight_leakage_across_contradictory_post_action_outcomes():
    snap = _rich_attacking_snapshot()
    state_turnover = build_state_from_snapshot(
        "M-HINDSIGHT",
        snap,
        observed_action_label="ST blocked pass",
        observed_target_track_id="H-ST",
        post_action_outcome=PostActionOutcome(
            outcome_label="TURNOVER_OBSERVED",
            possession_retained_after_3s=False,
            xt_realized_after_5s=-0.09,
            conceded_transition_within_8s=True,
        ),
    )
    state_miracle_goal = build_state_from_snapshot(
        "M-HINDSIGHT",
        snap,
        observed_action_label="ST blocked pass",
        observed_target_track_id="H-ST",
        post_action_outcome=PostActionOutcome(
            outcome_label="GOAL_SCORED_DEFLECTION",
            possession_retained_after_3s=True,
            xt_realized_after_5s=0.38,
            led_to_shot_within_8s=True,
        ),
    )

    engine = CounterfactualFootballEngine()
    comp_a = engine.evaluate(state_turnover)
    comp_b = engine.evaluate(state_miracle_goal)

    assert comp_a.status == "EVALUATED" and comp_b.status == "EVALUATED"
    assert comp_a.pre_action_only is True
    assert comp_a.best_alternative_id == comp_b.best_alternative_id
    assert comp_a.observed_utility == comp_b.observed_utility
    assert comp_a.regret_estimate == comp_b.regret_estimate
    assert [c.action_id for c in comp_a.candidates] == [c.action_id for c in comp_b.candidates]


def test_decision_type_specific_adequacy_and_calibration_abstention():
    # Switch decision under sparse wide coverage (50% cov, <5 teammates) flags long switch limitation
    partial_snap = _rich_attacking_snapshot(cov=50.0, cal="PARTIAL")
    st_switch = build_state_from_snapshot("M-ADEQ", partial_snap, decision_type_hint="SWITCH_OR_CROSS")
    assert st_switch.adequacy.can_score_long_switch is False
    assert st_switch.adequacy.can_score_short_pass is True
    assert st_switch.adequacy.status == FieldAdequacyStatus.PARTIAL_WITH_UNCERTAINTY

    # REJECTED calibration must strictly abstain in CounterfactualFootballEngine
    bad_snap = _rich_attacking_snapshot(cov=35.0, cal="REJECTED")
    st_bad = build_state_from_snapshot("M-ADEQ", bad_snap)
    assert st_bad.adequacy.status == FieldAdequacyStatus.INSUFFICIENT_ABSTAIN
    comp_bad = CounterfactualFootballEngine().evaluate(st_bad)
    assert comp_bad.status == "ABSTAINED_INSUFFICIENT_CONTEXT"
    assert comp_bad.regret_estimate is None


def test_window_detector_clusters_adjacent_frames_without_duplication():
    detector = DecisionOpportunityDetector(min_window_gap_sec=2.0)
    # 20 frames over 1.9 seconds (10 Hz) -> should collapse to 1 coherent window cleanly
    snaps = [_rich_attacking_snapshot(ts=10.0 + 0.1 * i) for i in range(20)]
    windows = detector.detect_windows("M-CLUSTER", snaps)
    assert len(windows) <= 2


def test_passing_corridor_interception_margin_and_speed_sensitivity():
    snap = _rich_attacking_snapshot()
    state = build_state_from_snapshot("M-PASS", snap)
    p_eng = PassingIntelligenceEngine()

    tm_st = next(p for p in state.pre_action_players if p.track_id == "H-ST")
    tm_lw = next(p for p in state.pre_action_players if p.track_id == "H-LW")

    ev_st = p_eng.evaluate_pass(state, tm_st, primary_style="GROUND_PASS")
    ev_lw = p_eng.evaluate_pass(state, tm_lw, primary_style="LONG_SWITCH")

    # Central corridor through A-CDM + A-CB1 has tighter margin & higher turnover risk than open LW wing switch
    assert ev_st.point_to_segment_clearance_m < ev_lw.point_to_segment_clearance_m
    assert ev_st.turnover_exposure > ev_lw.turnover_exposure

    sens = {s.pass_style: s.interception_margin_sec for s in ev_st.pass_speed_sensitivity}
    assert sens["DRIVEN_PASS"] >= sens["GROUND_PASS"]


def test_markov_xt_solver_converges_and_calibrated_epv_stays_gated():
    xt = ExpectedThreatEngine(cols=12, rows=8)
    n = 96
    moves = np.full((n, n), 0.1, dtype=np.float64)
    shots = np.ones(n, dtype=np.float64)
    goals = np.zeros(n, dtype=np.float64)
    for r in range(8):
        for c in range(12):
            idx = r * 12 + c
            if c < 11:
                moves[idx, r * 12 + (c + 1)] = 18.0
            if c >= 9 and 2 <= r <= 5:
                shots[idx] = 25.0
                goals[idx] = 7.5
            elif c >= 8:
                shots[idx] = 6.0
                goals[idx] = 0.5
    stats = xt.fit_markov_surface(moves, shots, goals, max_iter=35)
    assert stats["final_max_delta"] < 1e-3
    assert xt.value_at(98.0, 34.0, attacking_right=True) > xt.value_at(15.0, 10.0, attacking_right=True)

    gate_cold = CalibratedEPVInterface(sample_matches=4, brier_score=0.22)
    assert gate_cold.is_ready is False
    assert gate_cold.status_report()["stage"] == ValuationStage.STAGE_3_CALIBRATED_EPV_INTERFACE.value

    gate_ready = CalibratedEPVInterface(sample_matches=30, brier_score=0.16)
    assert gate_ready.is_ready is True
