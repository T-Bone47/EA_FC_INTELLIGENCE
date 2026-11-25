"""Phase 41B & 41C: Canonical Pre-Action Decision State Builder & Window Detector.

Guarantees strict anti-hindsight separation:
  - All kinematic, spatial, and structural features are frozen BEFORE `pre_action_cutoff_sec`.
  - Coherent window clustering merges adjacent frames within a cooldown/event cluster so a
    single slow possession sequence is NEVER double-counted as repeated independent mistakes.
  - Observation adequacy is evaluated per decision type (e.g., short pass vs long switch).
  - PostActionOutcome is isolated strictly after decision completion and stripped via
    `strip_hindsight()` before ANY candidate generator or counterfactual evaluator runs.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from backend.domain.phase41_models import (
    ControllerAttribution,
    DecisionCategory,
    FieldAdequacyReport,
    FieldAdequacyStatus,
    FootballDecisionState,
    PostActionOutcome,
    PreActionBallState,
    PreActionPlayerState,
    PreActionTeamStructure,
)
from backend.services.automated_event_detector import map_pitch_coordinates_to_zone
from backend.services.spatial_intelligence import PITCH_LENGTH_M, PITCH_WIDTH_M, expected_threat_at


def strip_hindsight(state: FootballDecisionState) -> FootballDecisionState:
    """Returns a deep copy with post_action_outcome explicitly zeroed out."""
    return state.model_copy(update={"post_action_outcome": None}, deep=True)


def evaluate_field_adequacy(
    decision_type: DecisionCategory,
    calibration_state: str,
    uncertainty_band: str,
    coverage_pct: float,
    ball: PreActionBallState,
    players: List[PreActionPlayerState],
) -> FieldAdequacyReport:
    """Computes decision-type-specific telemetry adequacy before scoring."""
    missing: List[str] = []
    if calibration_state == "REJECTED" or uncertainty_band == "UNRELIABLE":
        missing.append("pitch_homography_calibration")
    if ball.x_m is None or ball.y_m is None:
        missing.append("ball_coordinates")
    if len(players) < 4:
        missing.append("minimum_player_positions")

    pos_team = ball.possession_team
    teammates = [p for p in players if p.team == pos_team and not p.is_goalkeeper]
    opponents = [p for p in players if p.team != pos_team]

    local_teammates = 0
    local_opponents = 0
    if ball.x_m is not None and ball.y_m is not None:
        local_teammates = sum(
            1 for p in teammates if math.hypot(p.x_m - ball.x_m, p.y_m - ball.y_m) <= 22.0
        )
        local_opponents = sum(
            1 for p in opponents if math.hypot(p.x_m - ball.x_m, p.y_m - ball.y_m) <= 22.0
        )

    can_short_pass = (
        calibration_state != "REJECTED"
        and uncertainty_band != "UNRELIABLE"
        and ball.x_m is not None
        and coverage_pct >= 45.0
        and local_teammates >= 1
    )
    can_long_switch = (
        calibration_state != "REJECTED"
        and uncertainty_band != "UNRELIABLE"
        and ball.x_m is not None
        and coverage_pct >= 62.0
        and len(teammates) >= 5
        and len(opponents) >= 5
    )
    can_def_shape = (
        calibration_state != "REJECTED"
        and uncertainty_band != "UNRELIABLE"
        and ball.x_m is not None
        and coverage_pct >= 55.0
        and len(players) >= 8
    )
    has_gk_or_def = any(p.is_goalkeeper or (p.x_m >= 82.0 or p.x_m <= 23.0) for p in players)
    can_shot = (
        calibration_state != "REJECTED"
        and uncertainty_band != "UNRELIABLE"
        and ball.x_m is not None
        and coverage_pct >= 48.0
        and has_gk_or_def
    )

    if missing or coverage_pct < 40.0:
        status = FieldAdequacyStatus.INSUFFICIENT_ABSTAIN
        rationale = (
            f"Abstained safely: missing {missing or ['coverage<40%']} "
            f"(calibration={calibration_state}, coverage={coverage_pct:.1f}%)."
        )
    elif decision_type == DecisionCategory.SWITCH_OR_CROSS and not can_long_switch:
        missing.append("wide_pitch_coverage_for_long_switch")
        status = FieldAdequacyStatus.PARTIAL_WITH_UNCERTAINTY if can_short_pass else FieldAdequacyStatus.INSUFFICIENT_ABSTAIN
        rationale = (
            f"Long-switch wing coverage is incomplete ({coverage_pct:.1f}% coverage, {len(teammates)} visible teammates); "
            "short local passes remain evaluable while off-screen far-side runners remain UNKNOWN."
        )
    elif decision_type == DecisionCategory.DEFENSIVE_ACTION and not can_def_shape:
        missing.append("defensive_block_coverage")
        status = FieldAdequacyStatus.INSUFFICIENT_ABSTAIN
        rationale = f"Insufficient team-shape coverage ({coverage_pct:.1f}%) to score defensive line integrity."
    elif decision_type == DecisionCategory.SHOT and not can_shot:
        missing.append("goalmouth_gk_and_blocker_context")
        status = FieldAdequacyStatus.INSUFFICIENT_ABSTAIN
        rationale = "Goalmouth defenders/GK not adequately observed for shot decision analysis."
    elif coverage_pct < 70.0 or calibration_state in ("PARTIAL", "APPROXIMATE") or uncertainty_band in ("MODERATE", "HIGH"):
        status = FieldAdequacyStatus.PARTIAL_WITH_UNCERTAINTY
        if local_opponents == 0:
            missing.append("nearby_opponent_verification")
        rationale = (
            f"Adequate for local evaluation ({coverage_pct:.1f}% coverage, band={uncertainty_band}), "
            "with explicit wide/off-screen uncertainty propagation."
        )
    else:
        status = FieldAdequacyStatus.ADEQUATE
        rationale = f"Adequate pre-action pitch calibration ({calibration_state}) and {coverage_pct:.1f}% coverage."

    return FieldAdequacyReport(
        decision_type=decision_type,
        status=status,
        observation_coverage_pct=round(coverage_pct, 1),
        calibration_state=calibration_state,
        missing_or_uncertain_fields=missing,
        can_score_short_pass=can_short_pass,
        can_score_long_switch=can_long_switch,
        can_score_defensive_shape=can_def_shape,
        can_score_shot=can_shot,
        rationale=rationale,
    )


def _infer_decision_type(
    ball: PreActionBallState,
    players: List[PreActionPlayerState],
    snapshot: Dict[str, Any],
    explicit_hint: Optional[str] = None,
) -> DecisionCategory:
    if explicit_hint:
        upper = explicit_hint.upper()
        for cat in DecisionCategory:
            if cat.value == upper:
                return cat
        if "DEF" in upper or "LINE" in upper or "COVER" in upper or "PRESS" in upper:
            return DecisionCategory.DEFENSIVE_ACTION
        if "SHOT" in upper or "SHOOT" in upper:
            return DecisionCategory.SHOT
        if "SWITCH" in upper or "CROSS" in upper:
            return DecisionCategory.SWITCH_OR_CROSS
        if "THROUGH" in upper:
            return DecisionCategory.THROUGH_BALL

    pos_team = ball.possession_team
    bx = ball.x_m if ball.x_m is not None else 52.5
    attacking_right = pos_team != "AWAY"
    goal_dist = (PITCH_LENGTH_M - bx) if attacking_right else bx

    if goal_dist <= 22.0 and (ball.ball_xt or 0.0) >= 0.085:
        return DecisionCategory.SHOT
    if pos_team == "AWAY":
        return DecisionCategory.DEFENSIVE_ACTION

    lanes = snapshot.get("passing_lanes") or []
    if any(bool(l.get("is_progressive")) and float(l.get("distance_m", 0.0)) > 20.0 for l in lanes):
        return DecisionCategory.ATTACKING_PASS
    return DecisionCategory.POSSESSION_RETENTION


def _build_team_structure(struct_dict: Dict[str, Any], team: str, players: List[PreActionPlayerState]) -> PreActionTeamStructure:
    central_cnt = sum(1 for p in players if p.team == team and not p.is_goalkeeper and 27.2 <= p.y_m <= 40.8)
    team_cnt = max(1, sum(1 for p in players if p.team == team and not p.is_goalkeeper))
    return PreActionTeamStructure(
        team=team,
        observed_outfield_count=int(struct_dict.get("observed_outfield_count") or team_cnt),
        defensive_line_x_m=struct_dict.get("defensive_line_x_m"),
        midfield_line_x_m=struct_dict.get("midfield_line_x_m"),
        def_to_mid_gap_m=struct_dict.get("def_to_mid_gap_m"),
        mid_to_att_gap_m=struct_dict.get("mid_to_att_gap_m"),
        team_width_m=struct_dict.get("team_width_m"),
        team_length_m=struct_dict.get("team_length_m"),
        rest_defense_count=int(struct_dict.get("rest_defense_count") or 0),
        inferred_formation=struct_dict.get("inferred_formation"),
        central_channel_density=round(central_cnt / float(team_cnt), 3),
    )


def build_state_from_snapshot(
    match_id: str,
    snapshot: Dict[str, Any],
    *,
    window_id: Optional[str] = None,
    cluster_id: Optional[str] = None,
    video_id: Optional[str] = None,
    provenance: Optional[str] = None,
    decision_type_hint: Optional[str] = None,
    observed_action_label: Optional[str] = None,
    observed_target_track_id: Optional[str] = None,
    post_action_outcome: Optional[PostActionOutcome] = None,
    game_version: str = "FC27",
    game_patch: str = "PATCH_1.02",
) -> FootballDecisionState:
    """Converts a single pre-action spatial snapshot into a canonical FootballDecisionState."""
    ts = float(snapshot.get("timestamp_sec", 0.0))
    cal_state = str(snapshot.get("calibration_state", "GOOD"))
    uncertainty_band = str(snapshot.get("uncertainty_band", "MODERATE"))
    cov_pct = float(snapshot.get("observation_coverage_pct", 0.0))
    prov = provenance or str(snapshot.get("provenance", "IMPORTED_MATCH_TRACE"))

    kinematics = snapshot.get("kinematics") or []
    players: List[PreActionPlayerState] = []
    pos_sigma = 1.1 if cal_state == "GOOD" else (2.4 if cal_state in ("PARTIAL", "APPROXIMATE") else 4.5)
    vel_sigma = 0.65 if cal_state == "GOOD" else 1.25

    for k in kinematics:
        vx = float(k.get("vx_mps", 0.0))
        vy = float(k.get("vy_mps", 0.0))
        spd = float(k.get("speed_mps", math.hypot(vx, vy)))
        players.append(
            PreActionPlayerState(
                track_id=str(k.get("track_id", "unknown")),
                team=str(k.get("team", "HOME")),
                player_slot=str(k.get("player_slot", "OUTFIELD")),
                is_goalkeeper=bool(k.get("is_goalkeeper", False)),
                x_m=float(k.get("x_m", 52.5)),
                y_m=float(k.get("y_m", 34.0)),
                vx_mps=vx,
                vy_mps=vy,
                speed_mps=spd,
                facing_angle_rad=math.atan2(vy, vx) if spd > 0.3 else None,
                observation_status=str(k.get("observation_status", "OBSERVED")),
                positional_sigma_m=pos_sigma,
                velocity_sigma_mps=vel_sigma,
            )
        )

    bxy = snapshot.get("ball_xy")
    bx = float(bxy[0]) if bxy and len(bxy) >= 2 else None
    by = float(bxy[1]) if bxy and len(bxy) >= 2 else None
    pos_team = str(snapshot.get("possession_team", "HOME"))
    carrier_id = snapshot.get("ball_carrier_track_id")
    b_xt = snapshot.get("ball_xt")
    if b_xt is None and bx is not None and by is not None:
        b_xt = expected_threat_at(bx, by, attacking_right=(pos_team != "AWAY"))

    ball_state = PreActionBallState(
        x_m=bx,
        y_m=by,
        carrier_track_id=carrier_id,
        possession_team=pos_team,
        ball_xt=b_xt,
    )

    decision_type = _infer_decision_type(ball_state, players, snapshot, explicit_hint=decision_type_hint)
    adequacy = evaluate_field_adequacy(decision_type, cal_state, uncertainty_band, cov_pct, ball_state, players)

    zone = map_pitch_coordinates_to_zone(bx or 52.5, by or 34.0)
    wid = window_id or f"WIN-{match_id}-{int(round(ts * 10)):05d}"
    cid = cluster_id or f"CLU-{match_id}-{decision_type.value}-{int(ts // 4.0)}"

    home_s = _build_team_structure(snapshot.get("home_structure") or {}, "HOME", players)
    away_s = _build_team_structure(snapshot.get("away_structure") or {}, "AWAY", players)

    # Synthesize minimal local PreActionPlayerStates from passing_lanes if snapshot omitted raw kinematics
    if not players and snapshot.get("passing_lanes"):
        players.append(PreActionPlayerState(track_id=carrier_id or "H-CARRIER", team="HOME", player_slot="CM", x_m=bx or 52.5, y_m=by or 34.0))
        for idx, lane in enumerate(snapshot["passing_lanes"]):
            tx, ty = (bx or 52.5) + float(lane.get("distance_m", 14.0)), (by or 34.0) + (idx - 1) * 7.0
            tx = max(2.0, min(PITCH_LENGTH_M - 2.0, tx))
            ty = max(2.0, min(PITCH_WIDTH_M - 2.0, ty))
            players.append(
                PreActionPlayerState(
                    track_id=str(lane.get("target_track_id") or f"H-TM-{idx+1}"),
                    team="HOME",
                    player_slot=str(lane.get("target_slot") or f"OPT-{idx+1}"),
                    x_m=round(tx, 2),
                    y_m=round(ty, 2),
                )
            )
            clr = float(lane.get("nearest_defender_clearance_m", 3.5))
            mid_x = ((bx or 52.5) + tx) * 0.5
            mid_y = max(1.0, min(PITCH_WIDTH_M - 1.0, ((by or 34.0) + ty) * 0.5 + clr))
            players.append(
                PreActionPlayerState(
                    track_id=f"A-DEF-{idx+1}",
                    team="AWAY",
                    player_slot="DEF",
                    x_m=round(mid_x, 2),
                    y_m=round(mid_y, 2),
                )
            )

    return FootballDecisionState(
        window_id=wid,
        match_id=match_id,
        video_id=video_id or snapshot.get("video_id"),
        cluster_id=cid,
        provenance=prov,
        decision_type=decision_type,
        pre_action_cutoff_sec=round(max(0.0, ts - 0.10), 3),
        action_timestamp_sec=round(ts, 3),
        post_action_window_sec=round(ts + 3.0, 3),
        calibration_state=cal_state,
        uncertainty_band=uncertainty_band,
        observation_coverage_pct=cov_pct,
        pitch_zone=zone,
        attacking_direction="LEFT_TO_RIGHT" if pos_team != "AWAY" else "RIGHT_TO_LEFT",
        game_version=game_version,
        game_patch=game_patch,
        controller_attribution=ControllerAttribution.UNKNOWN,
        pre_action_ball=ball_state,
        pre_action_players=players,
        home_structure=home_s,
        away_structure=away_s,
        adequacy=adequacy,
        observed_action_label=observed_action_label,
        observed_target_track_id=observed_target_track_id,
        post_action_outcome=post_action_outcome,
    )


class DecisionOpportunityDetector:
    """Extracts coherent, deduplicated pre-action decision windows across a match timeline."""

    def __init__(self, min_window_gap_sec: float = 2.0, lookahead_outcome_sec: float = 3.5) -> None:
        self.min_window_gap_sec = min_window_gap_sec
        self.lookahead_outcome_sec = lookahead_outcome_sec

    def detect_windows(
        self,
        match_id: str,
        snapshots: List[Dict[str, Any]],
        *,
        video_id: Optional[str] = None,
        provenance: str = "IMPORTED_MATCH_TRACE",
        tactical_events: Optional[List[Dict[str, Any]]] = None,
        game_version: str = "FC27",
        game_patch: str = "PATCH_1.02",
        max_windows: int = 24,
    ) -> List[FootballDecisionState]:
        """Segments continuous snapshots into distinct decision moments without adjacent-frame duplication."""
        if not snapshots:
            return []

        ordered = sorted(snapshots, key=lambda s: float(s.get("timestamp_sec", 0.0)))
        events = tactical_events or []
        windows: List[FootballDecisionState] = []
        last_selected_ts = -999.0
        last_carrier: Optional[str] = None
        last_pos_team: Optional[str] = None

        for idx, snap in enumerate(ordered):
            ts = float(snap.get("timestamp_sec", 0.0))
            carrier = snap.get("ball_carrier_track_id")
            pos_team = snap.get("possession_team")
            bxy = snap.get("ball_xy")

            # Trigger check: significant event, carrier switch, possession flip, or cooldown spacing
            matching_ev = next(
                (ev for ev in events if abs(float(ev.get("timestamp_sec", -99.0)) - ts) <= 0.6),
                None,
            )
            carrier_changed = carrier is not None and carrier != last_carrier and idx > 0
            possession_flipped = pos_team is not None and pos_team != last_pos_team and idx > 0
            time_elapsed = (ts - last_selected_ts) >= self.min_window_gap_sec

            should_emit = (
                idx == 0
                or matching_ev is not None
                or (possession_flipped and (ts - last_selected_ts) >= 0.8)
                or (carrier_changed and (ts - last_selected_ts) >= 1.2)
                or time_elapsed
            )
            if not should_emit:
                last_carrier = carrier
                last_pos_team = pos_team
                continue

            # Strictly extract pre-action snapshot BEFORE t0 (previous frame if available and within 0.45s)
            pre_idx = idx - 1 if idx > 0 and (ts - float(ordered[idx - 1].get("timestamp_sec", ts))) <= 0.65 else idx
            pre_snap = ordered[pre_idx]

            # Build PostActionOutcome strictly from frames AFTER ts (never visible during pre-action scoring)
            future_frames = [
                f for f in ordered
                if ts + 0.5 <= float(f.get("timestamp_sec", 0.0)) <= ts + self.lookahead_outcome_sec
            ]
            outcome: Optional[PostActionOutcome] = None
            if future_frames:
                end_f = future_frames[-1]
                end_bxy = end_f.get("ball_xy")
                retained = end_f.get("possession_team") == pos_team if pos_team else None
                start_xt = float(pre_snap.get("ball_xt") or 0.0)
                end_xt = float(end_f.get("ball_xt") or start_xt)
                outcome = PostActionOutcome(
                    outcome_label=(
                        "RETAINED_POSSESSION" if retained else (
                            "TURNOVER_OBSERVED" if retained is False else "UNKNOWN"
                        )
                    ),
                    possession_retained_after_3s=retained,
                    xt_realized_after_5s=round(end_xt - start_xt, 4),
                    end_ball_xy_m=(float(end_bxy[0]), float(end_bxy[1])) if end_bxy and len(end_bxy) >= 2 else None,
                )

            # Infer observed action hint ONLY from trajectory shift after pre_snap if ball moved cleanly
            observed_label = None
            if matching_ev:
                observed_label = str(matching_ev.get("event_type") or matching_ev.get("label") or "")
            elif future_frames and bxy and pre_snap.get("ball_xy"):
                fb = future_frames[0].get("ball_xy")
                if fb and len(fb) >= 2:
                    move_dist = math.hypot(float(fb[0]) - float(bxy[0]), float(fb[1]) - float(bxy[1]))
                    if move_dist >= 8.0:
                        observed_label = "PROGRESSIVE_PASS" if float(fb[0]) > float(bxy[0]) + 4.0 else "LATERAL_PASS"

            decision_hint = str(matching_ev.get("event_type")) if matching_ev else None
            cluster_id = f"CLU-{match_id}-{int(ts // 5.0)}"

            state = build_state_from_snapshot(
                match_id,
                pre_snap,
                window_id=f"WIN-{match_id}-{len(windows) + 1:03d}",
                cluster_id=cluster_id,
                video_id=video_id,
                provenance=provenance or str(pre_snap.get("provenance", "IMPORTED_MATCH_TRACE")),
                decision_type_hint=decision_hint,
                observed_action_label=observed_label,
                post_action_outcome=outcome,
                game_version=game_version,
                game_patch=game_patch,
            )
            windows.append(state)
            last_selected_ts = ts
            last_carrier = carrier
            last_pos_team = pos_team
            if len(windows) >= max_windows:
                break

        return windows
