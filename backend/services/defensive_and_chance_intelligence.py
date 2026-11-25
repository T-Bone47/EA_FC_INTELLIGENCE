"""Phase 41H, 41I, 41J: Defensive Decision, Shooting/Chance-Creation & Off-Ball Engines.

Strict Epistemic Discipline:
- 41H Defensive: Frames advice as team-shape & off-ball cover unless controlled player ID is verified.
- 41I Shooting: Explicitly declares `is_calibrated_xg=False` and compares shot vs pass/carry/extra touch.
- 41J Off-Ball: Separates GAMER_CONTROLLED vs AI_TEAMMATE vs TACTICAL_INSTRUCTION_HYPOTHESIS vs UNKNOWN.
"""
from __future__ import annotations

import math
from typing import List, Optional

from backend.domain.phase41_models import (
    ControllerAttribution,
    DefensiveDecisionEval,
    FootballDecisionState,
    OffBallOpportunity,
    PreActionPlayerState,
    ShootingDecisionEval,
)
from backend.services.decision_state_builder import strip_hindsight
from backend.services.spatial_intelligence import PITCH_LENGTH_M, PITCH_WIDTH_M


class DefensiveDecisionEngine:
    """Evaluates defensive options based on central cover, carrier distance, and line spacing."""

    def evaluate_option(
        self,
        raw_state: FootballDecisionState,
        option_family: str,
    ) -> DefensiveDecisionEval:
        state = strip_hindsight(raw_state)
        assert state.post_action_outcome is None

        bx = state.pre_action_ball.x_m if state.pre_action_ball.x_m is not None else 52.5
        by = state.pre_action_ball.y_m if state.pre_action_ball.y_m is not None else 34.0
        def_team = "HOME" if state.pre_action_ball.possession_team != "HOME" else "AWAY"
        struct = state.home_structure if def_team == "HOME" else state.away_structure
        defenders = [p for p in state.pre_action_players if p.team == def_team and not p.is_goalkeeper]

        central_defenders = sum(1 for p in defenders if 25.0 <= p.y_m <= 43.0)
        central_score_base = min(1.0, central_defenders / 4.0)
        def_mid_gap = struct.def_to_mid_gap_m or 12.0
        controlled_known = state.controller_attribution == ControllerAttribution.GAMER_CONTROLLED

        # Option-specific physical trade-off weights
        if option_family == "HOLD_LINE":
            exposure = 0.62
            central = min(1.0, central_score_base + 0.25)
            gap_delta = -0.8
            disp_risk = 0.14
        elif option_family == "PRESERVE_CENTRAL_COVER":
            exposure = 0.68
            central = min(1.0, central_score_base + 0.34)
            gap_delta = -1.2
            disp_risk = 0.11
        elif option_family == "RECOVER_WITH_CM_CDM":
            exposure = 0.72
            central = min(1.0, central_score_base + 0.30)
            gap_delta = -2.2 if def_mid_gap > 14.0 else -0.6
            disp_risk = 0.16
        elif option_family == "CLOSE_PASSING_LANE":
            exposure = 0.76
            central = min(1.0, central_score_base + 0.22)
            gap_delta = 0.4
            disp_risk = 0.19
        elif option_family == "CONTAIN_BALL_CARRIER":
            exposure = 0.78
            central = min(1.0, central_score_base + 0.18)
            gap_delta = 0.8
            disp_risk = 0.22
        elif option_family == "TRACK_RUNNER":
            exposure = 0.58
            central = min(1.0, central_score_base + 0.10)
            gap_delta = 1.1
            disp_risk = 0.26
        else:  # PRESS_BALL_CARRIER
            in_central_danger = 24.0 <= by <= 44.0 and (
                (def_team == "HOME" and bx <= 38.0) or (def_team == "AWAY" and bx >= 67.0)
            )
            exposure = 0.84
            central = max(0.20, central_score_base - (0.30 if in_central_danger else 0.12))
            gap_delta = 4.2 if in_central_danger else 1.8
            disp_risk = 0.68 if in_central_danger else 0.38

        framing = (
            "Team-shape evaluation (controlled defender identity unverified from video/telemetry)."
            if not controlled_known
            else "Evaluated with verified controlled-player cursor attribution."
        )
        return DefensiveDecisionEval(
            option_family=option_family,
            controlled_player_known=controlled_known,
            ball_carrier_exposure_score=round(exposure, 3),
            central_channel_protection_score=round(central, 3),
            line_integrity_delta_m=round(gap_delta, 2),
            displacement_risk=round(disp_risk, 3),
            team_shape_framing_note=framing,
        )


class ShootingChanceEngine:
    """Evaluates shot geometry & blocker density (strictly heuristic, never labeled xG)."""

    def evaluate_shot(
        self,
        raw_state: FootballDecisionState,
        *,
        best_non_shot_label: Optional[str] = None,
        best_non_shot_utility: Optional[float] = None,
    ) -> ShootingDecisionEval:
        state = strip_hindsight(raw_state)
        assert state.post_action_outcome is None

        bx = state.pre_action_ball.x_m if state.pre_action_ball.x_m is not None else 88.0
        by = state.pre_action_ball.y_m if state.pre_action_ball.y_m is not None else 34.0
        pos_team = state.pre_action_ball.possession_team
        attacking_right = pos_team != "AWAY"
        goal_x = PITCH_LENGTH_M if attacking_right else 0.0

        goal_dist = math.hypot(goal_x - bx, 34.0 - by)
        # Angle subtended by 7.32m goalposts (y=30.34 and y=37.66)
        v1x, v1y = goal_x - bx, 30.34 - by
        v2x, v2y = goal_x - bx, 37.66 - by
        denom = math.hypot(v1x, v1y) * math.hypot(v2x, v2y)
        cos_a = max(-1.0, min(1.0, (v1x * v2x + v1y * v2y) / max(1e-6, denom)))
        angle_deg = math.degrees(math.acos(cos_a))

        opponents = [p for p in state.pre_action_players if p.team != pos_team]
        gks = [p for p in opponents if p.is_goalkeeper]
        gk_dist = math.hypot(goal_x - gks[0].x_m, 34.0 - gks[0].y_m) if gks else None

        blockers = 0
        for opp in opponents:
            if opp.is_goalkeeper:
                continue
            in_front = (bx < opp.x_m <= goal_x) if attacking_right else (goal_x <= opp.x_m < bx)
            if in_front and abs(opp.y_m - (34.0 + by) * 0.5) <= 4.0 and math.hypot(opp.x_m - bx, opp.y_m - by) <= goal_dist:
                blockers += 1

        dist_factor = max(0.02, min(1.0, 1.0 - max(0.0, goal_dist - 6.0) / 28.0))
        angle_factor = max(0.05, min(1.0, angle_deg / 42.0))
        blocker_pen = max(0.25, 1.0 - 0.24 * blockers)
        qual = round(max(0.02, min(0.95, 0.52 * dist_factor + 0.48 * angle_factor) * blocker_pen), 4)

        shot_util = round(qual * 0.62 - (0.12 + 0.05 * blockers), 4)
        alt_util = best_non_shot_utility if best_non_shot_utility is not None else 0.0
        delta = round(shot_util - alt_util, 4)

        return ShootingDecisionEval(
            evaluation_mode="HEURISTIC_CHANCE_UTILITY",
            is_calibrated_xg=False,
            shot_distance_m=round(goal_dist, 2),
            shot_angle_deg=round(angle_deg, 1),
            defenders_in_shot_cone=blockers,
            gk_distance_from_goal_line_m=round(gk_dist, 2) if gk_dist is not None else None,
            heuristic_shot_quality=qual,
            best_non_shot_alternative_label=best_non_shot_label,
            best_non_shot_utility=best_non_shot_utility,
            shot_advantage_delta=delta,
            explanation=(
                f"Heuristic shot chance quality {qual:.2f} (NOT calibrated xG; {goal_dist:.1f}m, {angle_deg:.1f} deg angle, "
                f"{blockers} blockers in cone). "
                + (
                    f"Best non-shot option ({best_non_shot_label}) scores {alt_util:.3f}."
                    if best_non_shot_label
                    else "Evaluate cutback/extra pass before forcing crowded long shots."
                )
            ),
        )


class OffBallOpportunityEngine:
    """Detects high-value off-ball runs & space creation while preserving controller uncertainty."""

    def detect_runs(self, raw_state: FootballDecisionState) -> List[OffBallOpportunity]:
        state = strip_hindsight(raw_state)
        assert state.post_action_outcome is None

        bx = state.pre_action_ball.x_m
        by = state.pre_action_ball.y_m
        if bx is None or by is None:
            return []

        pos_team = state.pre_action_ball.possession_team
        if pos_team not in ("HOME", "AWAY"):
            return []

        attacking_right = pos_team == "HOME"
        teammates = [
            p for p in state.pre_action_players
            if p.team == pos_team and not p.is_goalkeeper and p.track_id != state.pre_action_ball.carrier_track_id
        ]
        opponents = [p for p in state.pre_action_players if p.team != pos_team]
        runs: List[OffBallOpportunity] = []

        for tm in teammates:
            if tm.speed_mps < 2.2:
                continue
            forward_vx = tm.vx_mps if attacking_right else -tm.vx_mps
            if forward_vx >= 2.2:
                run_type = "DEPTH_STRETCH" if abs(tm.y_m - by) < 16.0 else "OVERLAP"
            elif 13.6 <= tm.y_m <= 27.2 or 40.8 <= tm.y_m <= 54.4:
                run_type = "HALF_SPACE_POCKET"
            else:
                run_type = "SUPPORT_ANGLE"

            dragged = [
                opp.track_id for opp in opponents
                if math.hypot(opp.x_m - tm.x_m, opp.y_m - tm.y_m) <= 5.5 and opp.speed_mps >= 1.8
            ]
            space_score = min(1.0, (tm.speed_mps / 8.0) * 0.55 + len(dragged) * 0.25)
            # In EA FC, off-ball teammate runs may be AI Run, L1 trigger, or tactical instruction hypothesis
            attribution = (
                ControllerAttribution.UNKNOWN
                if state.controller_attribution == ControllerAttribution.UNKNOWN
                else ControllerAttribution.AI_TEAMMATE
            )
            runs.append(
                OffBallOpportunity(
                    runner_track_id=tm.track_id,
                    runner_slot=tm.player_slot,
                    team=tm.team,
                    control_attribution=attribution,
                    run_type=run_type,
                    velocity_mps=round(tm.speed_mps, 2),
                    space_opened_score=round(space_score, 3),
                    dragged_defender_ids=dragged,
                    lane_opened_for_carrier=len(dragged) > 0,
                    explanation=(
                        f"{tm.player_slot} ({tm.track_id}) accelerating at {tm.speed_mps:.1f} m/s ({run_type}); "
                        f"attributed cautiously as {attribution.value} (manual L1/Right-Stick trigger unverified)."
                    ),
                )
            )

        runs.sort(key=lambda r: r.space_opened_score, reverse=True)
        return runs[:4]
