"""Phase 41D: Context-Grounded Candidate Action Generator.

Enumerates alternative attacking AND defensive choices directly from pre-action geometry:
- Never leaks post_action_outcome into candidate construction (`strip_hindsight` enforced).
- Never assumes unknown controller mechanics unless manually verified.
- Tags feasibility honestly (`FEASIBLE`, `POSSIBLY_FEASIBLE`, `UNSUPPORTED`, `UNKNOWN`).
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

from backend.domain.phase41_models import (
    CandidateAction,
    CandidateFeasibility,
    ControllerAttribution,
    DecisionCategory,
    EpistemicTag,
    FootballDecisionState,
    PreActionPlayerState,
)
from backend.services.decision_state_builder import strip_hindsight
from backend.services.spatial_intelligence import PITCH_LENGTH_M, PITCH_WIDTH_M


def _point_to_segment_dist(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    dx, dy = bx - ax, by - ay
    seg_len2 = dx * dx + dy * dy
    if seg_len2 <= 1e-6:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_len2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


class CandidateActionGenerator:
    """Generates plausible attacking & defensive alternatives strictly from pre-action state."""

    def generate(self, raw_state: FootballDecisionState) -> List[CandidateAction]:
        state = strip_hindsight(raw_state)
        assert state.post_action_outcome is None  # Anti-hindsight safety invariant

        ball = state.pre_action_ball
        if ball.x_m is None or ball.y_m is None:
            return []

        bx, by = ball.x_m, ball.y_m
        pos_team = ball.possession_team
        if pos_team not in ("HOME", "AWAY"):
            pos_team = "HOME"

        def_mode = state.decision_type == DecisionCategory.DEFENSIVE_ACTION or pos_team == "AWAY"
        candidates: List[CandidateAction] = []

        if def_mode:
            candidates.extend(self._generate_defensive_candidates(state, bx, by))
        else:
            candidates.extend(self._generate_attacking_candidates(state, bx, by, pos_team))

        # Flag observed action safely by matching target_track_id or label token
        obs_label = (state.observed_action_label or "").lower()
        obs_tid = state.observed_target_track_id
        for c in candidates:
            if obs_tid and c.target_track_id == obs_tid:
                c.is_observed_choice = True
            elif obs_label and (
                (c.target_slot and c.target_slot.lower() in obs_label)
                or c.action_family.lower().replace("_", " ") in obs_label.replace("_", " ")
                or (c.action_family == "THROUGH_BALL" and "through" in obs_label)
                or (c.action_family == "SHOOT" and "shot" in obs_label)
                or (c.action_family == "PROGRESSIVE_PASS" and "progressive" in obs_label)
                or (c.action_family in ("SHORT_PASS", "LATERAL_OR_BACKWARD_PASS") and "blocked" in obs_label and c.target_slot and c.target_slot.lower() in obs_label)
            ):
                c.is_observed_choice = True

        return candidates

    def _generate_attacking_candidates(
        self,
        state: FootballDecisionState,
        bx: float,
        by: float,
        pos_team: str,
    ) -> List[CandidateAction]:
        attacking_right = pos_team != "AWAY"
        teammates = [
            p for p in state.pre_action_players
            if p.team == pos_team and not p.is_goalkeeper and p.track_id != state.pre_action_ball.carrier_track_id
        ]
        opponents = [p for p in state.pre_action_players if p.team != pos_team]
        cands: List[CandidateAction] = []

        idx = 1
        for tm in teammates:
            dx = tm.x_m - bx
            dy = tm.y_m - by
            dist = math.hypot(dx, dy)
            if dist < 2.2 or dist > 62.0:
                continue

            forward_m = dx if attacking_right else -dx
            lateral_m = abs(dy)
            if dist >= 26.0 and lateral_m >= 18.0:
                family = "SWITCH_PLAY"
                cat = DecisionCategory.SWITCH_OR_CROSS
                feas = CandidateFeasibility.FEASIBLE if state.adequacy.can_score_long_switch else CandidateFeasibility.POSSIBLY_FEASIBLE
                cap = {"attrs": ["long_passing", "vision"], "playstyles": ["Long Ball Pass"]}
            elif forward_m > 12.0 and dist > 17.5:
                family = "THROUGH_BALL"
                cat = DecisionCategory.THROUGH_BALL
                feas = CandidateFeasibility.FEASIBLE if tm.observation_status == "OBSERVED" else CandidateFeasibility.POSSIBLY_FEASIBLE
                cap = {"attrs": ["vision", "short_passing", "through_ball_timing"], "playstyles": ["Incisive Pass"]}
            elif forward_m >= 6.0:
                family = "PROGRESSIVE_PASS"
                cat = DecisionCategory.ATTACKING_PASS
                feas = CandidateFeasibility.FEASIBLE
                cap = {"attrs": ["short_passing", "vision"], "playstyles": ["Incisive Pass", "Tiki Taka"]}
            elif lateral_m >= 16.0 and ((attacking_right and bx >= 72.0) or (not attacking_right and bx <= 33.0)):
                family = "CROSS_OR_CUTBACK"
                cat = DecisionCategory.SWITCH_OR_CROSS
                feas = CandidateFeasibility.FEASIBLE
                cap = {"attrs": ["crossing", "curve"], "playstyles": ["Whipped Pass"]}
            elif forward_m <= -3.0 or abs(forward_m) < 6.0:
                family = "LATERAL_OR_BACKWARD_PASS"
                cat = DecisionCategory.POSSESSION_RETENTION
                feas = CandidateFeasibility.FEASIBLE if state.adequacy.can_score_short_pass else CandidateFeasibility.UNKNOWN
                cap = {"attrs": ["short_passing", "composure"], "playstyles": ["Press Proven"]}
            else:
                family = "SHORT_PASS"
                cat = DecisionCategory.ATTACKING_PASS
                feas = CandidateFeasibility.FEASIBLE
                cap = {"attrs": ["short_passing"], "playstyles": ["Tiki Taka"]}

            cands.append(
                CandidateAction(
                    action_id=f"CAND-{idx}",
                    action_category=cat,
                    action_family=family,
                    label=f"{family.replace('_', ' ').title()} to {tm.player_slot} ({tm.track_id}, {dist:.0f}m)",
                    target_track_id=tm.track_id,
                    target_slot=tm.player_slot,
                    target_xy_m=(round(tm.x_m, 2), round(tm.y_m, 2)),
                    feasibility=feas,
                    epistemic_tag=EpistemicTag.MODELLED,
                    controller_assumption=ControllerAttribution.UNKNOWN,
                    capability_requirement=cap,
                    telemetry_evidence_refs=[state.window_id, tm.track_id],
                )
            )
            idx += 1

        # Ball Carry into clearest forward pocket (angle +30/-30 deg or lateral half-space)
        carry_step = 7.5 if attacking_right else -7.5
        best_carry_xy = (
            max(2.0, min(PITCH_LENGTH_M - 2.0, bx + carry_step)),
            max(4.0, min(PITCH_WIDTH_M - 4.0, by + (4.5 if by < 34.0 else -4.5))),
        )
        nearest_opp_carry = min(
            (math.hypot(o.x_m - best_carry_xy[0], o.y_m - best_carry_xy[1]) for o in opponents),
            default=12.0,
        )
        cands.append(
            CandidateAction(
                action_id=f"CAND-{idx}",
                action_category=DecisionCategory.CARRY_OR_DRIBBLE,
                action_family="CARRY_INTO_SPACE",
                label=f"Carry into open pocket ({nearest_opp_carry:.1f}m nearest defender)",
                target_slot="CARRY_LANE",
                target_xy_m=(round(best_carry_xy[0], 2), round(best_carry_xy[1], 2)),
                feasibility=CandidateFeasibility.FEASIBLE if nearest_opp_carry >= 3.0 else CandidateFeasibility.POSSIBLY_FEASIBLE,
                epistemic_tag=EpistemicTag.HYPOTHETICAL,
                controller_assumption=ControllerAttribution.UNKNOWN,
                capability_requirement={"attrs": ["agility", "ball_control", "dribbling_detail"], "playstyles": ["Technical", "Rapid"]},
                telemetry_evidence_refs=[state.window_id],
            )
        )
        idx += 1

        # Conservative Retain / Shield option
        cands.append(
            CandidateAction(
                action_id=f"CAND-{idx}",
                action_category=DecisionCategory.POSSESSION_RETENTION,
                action_family="RETAIN_AND_RESET",
                label="Shield & retain possession to reset shape",
                target_slot="HOLD",
                target_xy_m=(round(bx, 2), round(by, 2)),
                feasibility=CandidateFeasibility.FEASIBLE,
                epistemic_tag=EpistemicTag.HYPOTHETICAL,
                controller_assumption=ControllerAttribution.UNKNOWN,
                capability_requirement={"attrs": ["composure", "balance", "strength"], "playstyles": ["Press Proven"]},
                telemetry_evidence_refs=[state.window_id],
            )
        )
        idx += 1

        # Shooting option inside attacking range (<= 29m from target goal)
        goal_x = PITCH_LENGTH_M if attacking_right else 0.0
        goal_dist = math.hypot(goal_x - bx, 34.0 - by)
        if goal_dist <= 29.5:
            cands.append(
                CandidateAction(
                    action_id=f"CAND-{idx}",
                    action_category=DecisionCategory.SHOT,
                    action_family="SHOOT",
                    label=f"Attempt shot ({goal_dist:.1f}m from goal)",
                    target_slot="GOAL",
                    target_xy_m=(goal_x, 34.0),
                    feasibility=CandidateFeasibility.FEASIBLE if state.adequacy.can_score_shot else CandidateFeasibility.POSSIBLY_FEASIBLE,
                    epistemic_tag=EpistemicTag.MODELLED,
                    controller_assumption=ControllerAttribution.UNKNOWN,
                    capability_requirement={"attrs": ["finishing", "shot_power", "composure"], "playstyles": ["Finesse Shot", "Low Driven Shot"]},
                    telemetry_evidence_refs=[state.window_id],
                )
            )

        return cands

    def _generate_defensive_candidates(
        self,
        state: FootballDecisionState,
        bx: float,
        by: float,
    ) -> List[CandidateAction]:
        def_team = "HOME" if state.pre_action_ball.possession_team != "HOME" else "AWAY"
        families: List[Tuple[str, str, Dict[str, List[str]]]] = [
            ("HOLD_LINE", "Hold defensive line & preserve back-four spacing", {"attrs": ["defensive_awareness", "reactions"], "playstyles": ["Anticipate"]}),
            ("RECOVER_WITH_CM_CDM", "Track back with CM/CDM into central screening zone", {"attrs": ["interceptions", "stamina", "acceleration"], "playstyles": ["Intercept", "Relentless"]}),
            ("CONTAIN_BALL_CARRIER", "Jockey/contain ball carrier without diving in", {"attrs": ["defensive_awareness", "agility"], "playstyles": ["Jockey"]}),
            ("CLOSE_PASSING_LANE", "Shadow central passing lane into half-space pocket", {"attrs": ["interceptions", "defensive_awareness"], "playstyles": ["Intercept"]}),
            ("PRESS_BALL_CARRIER", "Step out aggressively to press ball carrier", {"attrs": ["aggression", "sprint_speed", "standing_tackle"], "playstyles": ["Bruiser"]}),
            ("TRACK_RUNNER", "Match depth runner attacking behind line", {"attrs": ["sprint_speed", "acceleration", "defensive_awareness"], "playstyles": ["Quick Step"]}),
            ("PRESERVE_CENTRAL_COVER", "Protect Zone 14 / central channel over touchline press", {"attrs": ["defensive_awareness", "interceptions"], "playstyles": ["Anticipate", "Intercept"]}),
        ]
        feas = CandidateFeasibility.FEASIBLE if state.adequacy.can_score_defensive_shape else CandidateFeasibility.POSSIBLY_FEASIBLE
        cands: List[CandidateAction] = []
        for idx, (fam, label, cap) in enumerate(families):
            cands.append(
                CandidateAction(
                    action_id=f"DEF-{idx + 1}",
                    action_category=DecisionCategory.DEFENSIVE_ACTION,
                    action_family=fam,
                    label=label,
                    target_slot=fam,
                    target_xy_m=(round(bx, 2), round(by, 2)),
                    feasibility=feas,
                    epistemic_tag=EpistemicTag.HYPOTHETICAL,
                    controller_assumption=state.controller_attribution,
                    capability_requirement=cap,
                    telemetry_evidence_refs=[state.window_id, def_team],
                )
            )
        return cands
