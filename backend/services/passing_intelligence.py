"""Phase 41E: Passing Decision Intelligence Engine.

Computes passing corridor feasibility with kinematic interception time margins:
- Point-to-segment distance from every opponent onto pass vector A->B
- Dynamic interception reach margin: M = opponent_arrival_time - ball_arrival_time
- Pass-speed sensitivity analysis across GROUND_PASS, DRIVEN_PASS, THROUGH_BALL, LONG_SWITCH
- Receiver local space radius & turnover exposure under rest-defense pressure
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

from backend.domain.phase41_models import (
    FootballDecisionState,
    PassSpeedSensitivity,
    PassingCorridorEval,
    PreActionPlayerState,
)
from backend.services.decision_state_builder import strip_hindsight
from backend.services.spatial_intelligence import expected_threat_at

PASS_STYLE_SPEEDS_MPS: List[Tuple[str, float]] = [
    ("GROUND_PASS", 16.5),
    ("DRIVEN_PASS", 22.5),
    ("THROUGH_BALL", 14.5),
    ("LONG_SWITCH", 21.0),
]


def _closest_point_on_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> Tuple[float, float, float]:
    """Returns (closest_x, closest_y, t_param in [0, 1])."""
    dx, dy = bx - ax, by - ay
    seg_len2 = dx * dx + dy * dy
    if seg_len2 <= 1e-6:
        return ax, ay, 0.0
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_len2))
    return ax + t * dx, ay + t * dy, t


def _opponent_arrival_time_sec(opp: PreActionPlayerState, target_x: float, target_y: float, reaction_delay: float = 0.25, max_sprint: float = 8.4) -> float:
    """Spearman-inspired kinematic arrival time incorporating current velocity projection."""
    dx = target_x - opp.x_m
    dy = target_y - opp.y_m
    dist = math.hypot(dx, dy)
    if dist <= 0.4:
        return 0.0
    ux, uy = dx / dist, dy / dist
    v_towards = opp.vx_mps * ux + opp.vy_mps * uy
    # Closing distance achieved during reaction window + remaining sprint
    effective_dist = max(0.0, dist - max(0.0, v_towards) * reaction_delay)
    effective_speed = max(5.2, min(max_sprint, 6.8 + 0.25 * max(0.0, v_towards)))
    return round(reaction_delay + effective_dist / effective_speed, 3)


class PassingIntelligenceEngine:
    """Evaluates passing corridors using geometry, kinematics, and pass-speed sensitivity."""

    def evaluate_pass(
        self,
        raw_state: FootballDecisionState,
        target_player: PreActionPlayerState,
        *,
        primary_style: str = "GROUND_PASS",
    ) -> PassingCorridorEval:
        state = strip_hindsight(raw_state)
        assert state.post_action_outcome is None

        bx = state.pre_action_ball.x_m if state.pre_action_ball.x_m is not None else 52.5
        by = state.pre_action_ball.y_m if state.pre_action_ball.y_m is not None else 34.0
        pos_team = state.pre_action_ball.possession_team
        attacking_right = pos_team != "AWAY"

        tx, ty = target_player.x_m, target_player.y_m
        if primary_style == "THROUGH_BALL":
            lead = 4.5 if attacking_right else -4.5
            tx = max(1.0, min(104.0, tx + lead))

        pass_dist = math.hypot(tx - bx, ty - by)
        opponents = [p for p in state.pre_action_players if p.team != pos_team]

        min_clr = 30.0
        nearest_opp_id: Optional[str] = None
        for opp in opponents:
            cx, cy, _ = _closest_point_on_segment(opp.x_m, opp.y_m, bx, by, tx, ty)
            clr = math.hypot(opp.x_m - cx, opp.y_m - cy)
            if clr < min_clr:
                min_clr = clr
                nearest_opp_id = opp.track_id

        # Sensitivity across pass speeds: M = opp_arrival_time - ball_arrival_time
        speed_map = dict(PASS_STYLE_SPEEDS_MPS)
        sensitivity_rows: List[PassSpeedSensitivity] = []
        primary_margin = 1.5

        for style, ball_speed in PASS_STYLE_SPEEDS_MPS:
            worst_margin = 5.0
            best_ball_t = pass_dist / max(1.0, ball_speed)
            worst_opp_t = 5.0

            for opp in opponents:
                cx, cy, t_seg = _closest_point_on_segment(opp.x_m, opp.y_m, bx, by, tx, ty)
                # Slightly discount interceptability near passer (<0.12) where lofted switches clear easily
                effective_seg = max(0.08, t_seg)
                ball_arr_t = (pass_dist * effective_seg) / max(1.0, ball_speed)
                opp_arr_t = _opponent_arrival_time_sec(opp, cx, cy)
                if style == "LONG_SWITCH":
                    # Aerial passes only realistically interceptable near launch or landing
                    if 0.22 <= t_seg <= 0.78:
                        opp_arr_t += 1.4
                margin = opp_arr_t - ball_arr_t
                if margin < worst_margin:
                    worst_margin = margin
                    best_ball_t = ball_arr_t
                    worst_opp_t = opp_arr_t

            status = "OPEN" if worst_margin >= 0.35 else ("CONTESTED" if worst_margin >= -0.05 else "BLOCKED")
            sensitivity_rows.append(
                PassSpeedSensitivity(
                    pass_style=style,
                    assumed_ball_speed_mps=ball_speed,
                    ball_arrival_sec=round(best_ball_t, 3),
                    nearest_opp_arrival_sec=round(worst_opp_t, 3),
                    interception_margin_sec=round(worst_margin, 3),
                    status=status,
                )
            )
            if style == primary_style or (primary_style == "PROGRESSIVE_PASS" and style == "GROUND_PASS") or (primary_style == "SWITCH_PLAY" and style == "LONG_SWITCH"):
                primary_margin = worst_margin

        if primary_style not in speed_map and sensitivity_rows:
            # Fallback to ground pass margin for short/lateral passes
            primary_margin = sensitivity_rows[0].interception_margin_sec

        # Receiver local space (minimum distance from receiver to nearest opponent)
        receiver_space = min((math.hypot(o.x_m - tx, o.y_m - ty) for o in opponents), default=12.0)

        origin_xt = expected_threat_at(bx, by, attacking_right=attacking_right)
        target_xt = expected_threat_at(tx, ty, attacking_right=attacking_right)
        xt_delta = round(target_xt - origin_xt, 4)

        dx = tx - bx
        is_prog = (dx >= 6.5) if attacking_right else (dx <= -6.5)
        is_back_or_lat = (dx <= -2.0) if attacking_right else (dx >= 2.0) or abs(dx) < 5.0

        # Turnover risk combines interception margin M, static corridor clearance, receiver space, and rest defense
        rest_def = state.home_structure.rest_defense_count if pos_team == "HOME" else state.away_structure.rest_defense_count
        margin_risk = max(0.03, min(0.95, 0.55 - 0.55 * primary_margin))
        space_risk = max(0.0, min(0.40, (3.8 - min(3.8, receiver_space)) / 9.0))
        clr_risk = max(0.0, min(0.45, (3.2 - min(3.2, min_clr)) / 7.5))
        rest_mult = 1.18 if rest_def < 3 else 0.92
        turnover_exp = max(0.04, min(0.96, (0.55 * margin_risk + 0.25 * clr_risk + 0.20 * space_risk) * rest_mult))

        return PassingCorridorEval(
            target_track_id=target_player.track_id,
            target_slot=target_player.player_slot,
            target_xy_m=(round(tx, 2), round(ty, 2)),
            distance_m=round(pass_dist, 2),
            point_to_segment_clearance_m=round(min_clr, 2),
            intercepting_opponent_id=nearest_opp_id,
            dynamic_interception_margin_sec=round(primary_margin, 3),
            receiver_space_radius_m=round(receiver_space, 2),
            xt_delta=xt_delta,
            is_progressive=is_prog,
            is_backward_or_lateral=is_back_or_lat,
            turnover_exposure=round(turnover_exp, 3),
            pass_speed_sensitivity=sensitivity_rows,
        )
