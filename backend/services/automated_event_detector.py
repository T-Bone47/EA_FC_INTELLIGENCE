"""Automated Tactical Event Recognition & Proposal Engine (Phase 37).

Analyzes high-frequency player and ball tracking telemetry to propose candidate
tactical events (pressing triggers, defensive line shifts, transition breaks,
overlapping runs, central line break passes, and combination sequences).
Every proposed event is assigned confidence, pitch zone coordinates, and a SHA-256
tamper-evident seal, marked as UNDER_REVIEW for analyst certification.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from backend.domain.video_gameplay import (
    IdentityConfidence,
    ObservationMethod,
    ReviewStatus,
    TacticalEvent,
    PlayerTrack,
    BallTrack,
)


def map_pitch_coordinates_to_zone(
    x_meters: float,
    y_meters: float,
    pitch_length: float = 105.0,
    pitch_width: float = 68.0,
) -> int:
    """Maps canonical metric coordinates (x: 0-105m, y: 0-68m) into the standard 18-zone tactical pitch grid.
    
    Grid Alignment (aligned with ANNOTATION_PROTOCOL.md):
    - Longitudinal Columns (x-axis):
        Col 0 (Attacking Third x in [70, 105]): Front zone
        Col 1 (Middle Third x in [35, 70)): Midfield zone
        Col 2 (Defensive Third x in [0, 35)): Backline zone
    - Lateral Rows (y-axis from Left touchline y=68 down to Right touchline y=0):
        Row 0: Left Flank (y in [54.4, 68.0]) -> Zones 1, 2, 3
        Row 1: Left Half-Space (y in [40.8, 54.4)) -> Zones 4, 5, 6
        Row 2: Central Spine (y in [27.2, 40.8)) -> Zones 7, 8, 9 (Center Mid = Zone 8)
        Row 3: Right Half-Space (y in [13.6, 27.2)) -> Zones 10, 11, 12
        Row 4: Right Flank (y in [0.0, 13.6)) -> Zones 13, 14, 15
        Row 5: Sub-pitch boundary / goalmouth -> Zones 16, 17, 18
    """
    x = max(0.0, min(pitch_length, x_meters))
    y = max(0.0, min(pitch_width, y_meters))

    # Longitudinal column (0: Attacking, 1: Middle, 2: Defensive)
    if x >= 70.0:
        col = 0
    elif x >= 35.0:
        col = 1
    else:
        col = 2

    # Lateral row (0: Left Flank at top y=68 to 4: Right Flank at bottom y=0)
    norm_y = y / pitch_width  # 0.0 to 1.0
    # Invert so 1.0 (Left Flank) is row 0, 0.0 (Right Flank) is row 4
    inverted_y = max(0.0, min(0.999, 1.0 - norm_y))
    row = min(5, int(inverted_y * 5))  # rows 0 to 4 (or 5 for exact 0)

    zone_id = (row * 3) + col + 1
    return max(1, min(18, zone_id))


class AutomatedEventDetector:
    """Deterministic spatio-temporal tactical event proposal engine for EA FC 27 video telemetry."""

    def __init__(
        self,
        press_distance_threshold_m: float = 3.5,
        press_velocity_threshold_mps: float = 4.2,
        transition_speed_mps: float = 6.0,
        transition_min_distance_m: float = 18.0,
        line_shift_min_delta_m: float = 4.5,
    ):
        self.press_distance_threshold_m = press_distance_threshold_m
        self.press_velocity_threshold_mps = press_velocity_threshold_mps
        self.transition_speed_mps = transition_speed_mps
        self.transition_min_distance_m = transition_min_distance_m
        self.line_shift_min_delta_m = line_shift_min_delta_m

    def detect_all_events(
        self,
        player_tracks: List[PlayerTrack],
        ball_tracks: List[BallTrack],
        video_id: str,
        match_id: Optional[str] = None,
    ) -> List[TacticalEvent]:
        """Runs the complete suite of spatio-temporal event proposal detectors."""
        events: List[TacticalEvent] = []

        # 1. Detect Pressing Triggers
        events.extend(self.detect_pressing_triggers(player_tracks, ball_tracks, video_id, match_id))

        # 2. Detect Defensive Line Shifts
        events.extend(self.detect_defensive_line_shifts(player_tracks, video_id, match_id))

        # 3. Detect Transition Breaks
        events.extend(self.detect_transition_breaks(player_tracks, ball_tracks, video_id, match_id))

        # 4. Detect Overlapping Runs
        events.extend(self.detect_overlapping_runs(player_tracks, video_id, match_id))

        # 5. Detect Central Line Break Passes
        events.extend(self.detect_line_break_passes(ball_tracks, video_id, match_id))

        # Sort all proposed events chronologically
        events.sort(key=lambda e: e.timestamp_start)
        return events

    def detect_pressing_triggers(
        self,
        player_tracks: List[PlayerTrack],
        ball_tracks: List[BallTrack],
        video_id: str,
        match_id: Optional[str] = None,
    ) -> List[TacticalEvent]:
        """Detects pressing trigger events when a defending player closes down opponent ball carrier."""
        detected: List[TacticalEvent] = []
        if not player_tracks or not ball_tracks:
            return detected

        # Group ball tracks by timestamp
        ball_by_time = {round(b.timestamp_sec, 2): b for b in ball_tracks if b.pitch_xy_meters}
        players_by_time: Dict[float, List[PlayerTrack]] = {}
        for p in player_tracks:
            if p.pitch_xy_meters:
                t = round(p.timestamp_sec, 2)
                players_by_time.setdefault(t, []).append(p)

        last_press_time = -10.0
        for t in sorted(players_by_time.keys()):
            if t - last_press_time < 3.0:
                continue

            bt = ball_by_time.get(t)
            if not bt or not bt.pitch_xy_meters:
                continue

            bx, by = bt.pitch_xy_meters
            current_players = players_by_time[t]

            for p in current_players:
                px, py = p.pitch_xy_meters  # type: ignore
                dist = math.hypot(px - bx, py - by)
                speed = p.velocity_mps or 0.0

                if dist <= self.press_distance_threshold_m and speed >= self.press_velocity_threshold_mps:
                    # Found pressing trigger
                    zone = map_pitch_coordinates_to_zone(px, py)
                    event = TacticalEvent(
                        video_id=video_id,
                        match_id=match_id,
                        timestamp_start=max(0.0, t - 0.5),
                        timestamp_end=t + 2.0,
                        event_type="PRESSING_TRIGGER",
                        team_identity=p.team,
                        player_identity=p.player_slot or "DEFENDER_PRESSER",
                        formation_slot=p.player_slot,
                        pitch_zone=zone,
                        observed_action=f"High-intensity close-down ({speed:.1f} m/s) to {dist:.1f}m separation",
                        observed_outcome="TURNOVER_PRESSURE",
                        observation_method=ObservationMethod.AUTOMATED_DETECTOR,
                        identity_confidence=IdentityConfidence.HIGH if p.player_slot else IdentityConfidence.PROVISIONAL,
                        review_status=ReviewStatus.UNDER_REVIEW,
                        related_hypothesis="HYP-RULE-HP-FWD-DEF",
                    ).seal()
                    detected.append(event)
                    last_press_time = t
                    break

        return detected

    def detect_defensive_line_shifts(
        self,
        player_tracks: List[PlayerTrack],
        video_id: str,
        match_id: Optional[str] = None,
    ) -> List[TacticalEvent]:
        """Detects synchronized defensive line pushing up or dropping deep."""
        detected: List[TacticalEvent] = []
        if not player_tracks:
            return detected

        # Sample timestamps at 1.0s intervals
        def_slots = {"CB", "LCB", "RCB", "LB", "RB"}
        def_tracks: Dict[float, List[float]] = {}
        for p in player_tracks:
            if p.pitch_xy_meters and p.player_slot in def_slots:
                t = round(p.timestamp_sec, 1)
                def_tracks.setdefault(t, []).append(p.pitch_xy_meters[0])

        sorted_times = sorted(def_tracks.keys())
        last_shift_time = -10.0

        for i in range(1, len(sorted_times)):
            t_prev = sorted_times[i - 1]
            t_curr = sorted_times[i]
            dt = t_curr - t_prev
            if dt < 0.8 or dt > 2.5 or (t_curr - last_shift_time < 5.0):
                continue

            prev_xs = def_tracks[t_prev]
            curr_xs = def_tracks[t_curr]

            if len(prev_xs) >= 2 and len(curr_xs) >= 2:
                avg_prev = sum(prev_xs) / len(prev_xs)
                avg_curr = sum(curr_xs) / len(curr_xs)
                delta = avg_curr - avg_prev

                if abs(delta) >= self.line_shift_min_delta_m:
                    shift_direction = "PUSH_UP_STEP" if delta > 0 else "DROP_DEEP_RECOVERY"
                    zone = map_pitch_coordinates_to_zone(avg_curr, 34.0)
                    event = TacticalEvent(
                        video_id=video_id,
                        match_id=match_id,
                        timestamp_start=t_prev,
                        timestamp_end=t_curr + 1.0,
                        event_type="DEFENSIVE_LINE_SHIFT",
                        team_identity="HOME",
                        formation_slot="BACK_LINE_UNIT",
                        pitch_zone=zone,
                        observed_action=f"Synchronized back-line shift of {delta:+.1f}m over {dt:.1f}s",
                        observed_outcome=shift_direction,
                        observation_method=ObservationMethod.AUTOMATED_DETECTOR,
                        identity_confidence=IdentityConfidence.HIGH,
                        review_status=ReviewStatus.UNDER_REVIEW,
                        related_hypothesis="HYP-RULE-DEF-LINE-COMPACTNESS",
                    ).seal()
                    detected.append(event)
                    last_shift_time = t_curr

        return detected

    def detect_transition_breaks(
        self,
        player_tracks: List[PlayerTrack],
        ball_tracks: List[BallTrack],
        video_id: str,
        match_id: Optional[str] = None,
    ) -> List[TacticalEvent]:
        """Detects fast counter-attacking vertical transition breaks."""
        detected: List[TacticalEvent] = []
        if not ball_tracks:
            return detected

        # Check forward progression of ball over 4.0 second sliding window
        sorted_balls = [b for b in ball_tracks if b.pitch_xy_meters]
        sorted_balls.sort(key=lambda b: b.timestamp_sec)

        last_break_time = -10.0
        for i in range(len(sorted_balls)):
            b_start = sorted_balls[i]
            t_start = b_start.timestamp_sec
            if t_start - last_break_time < 8.0:
                continue

            # Look ahead up to 4.0s
            for j in range(i + 1, len(sorted_balls)):
                b_end = sorted_balls[j]
                dt = b_end.timestamp_sec - t_start
                if dt > 4.5:
                    break
                if dt >= 1.5:
                    dx = b_end.pitch_xy_meters[0] - b_start.pitch_xy_meters[0]  # type: ignore
                    dy = b_end.pitch_xy_meters[1] - b_start.pitch_xy_meters[1]  # type: ignore
                    dist = math.hypot(dx, dy)
                    speed = dist / dt

                    if dx >= self.transition_min_distance_m and speed >= self.transition_speed_mps:
                        zone = map_pitch_coordinates_to_zone(b_end.pitch_xy_meters[0], b_end.pitch_xy_meters[1])  # type: ignore
                        event = TacticalEvent(
                            video_id=video_id,
                            match_id=match_id,
                            timestamp_start=t_start,
                            timestamp_end=b_end.timestamp_sec + 1.0,
                            event_type="TRANSITION_BREAK",
                            team_identity="ATTACKING",
                            player_identity="TRANSITION_CARRIER",
                            formation_slot="FORWARD_UNIT",
                            pitch_zone=zone,
                            observed_action=f"Rapid vertical attack (+{dx:.1f}m in {dt:.1f}s at {speed:.1f} m/s)",
                            observed_outcome="TRANSITION_PENETRATION",
                            observation_method=ObservationMethod.AUTOMATED_DETECTOR,
                            identity_confidence=IdentityConfidence.HIGH,
                            review_status=ReviewStatus.UNDER_REVIEW,
                            related_hypothesis="HYP-RULE-TRANSITION-SPRINT",
                        ).seal()
                        detected.append(event)
                        last_break_time = b_end.timestamp_sec
                        break

        return detected

    def detect_overlapping_runs(
        self,
        player_tracks: List[PlayerTrack],
        video_id: str,
        match_id: Optional[str] = None,
    ) -> List[TacticalEvent]:
        """Detects fullbacks overlapping their corresponding wingers along the flank."""
        detected: List[TacticalEvent] = []
        if not player_tracks:
            return detected

        # Map pairings: (LB, LW) and (RB, RW)
        pairs = [("LB", "LW", "LEFT_FLANK"), ("RB", "RW", "RIGHT_FLANK")]
        tracks_by_time: Dict[float, Dict[str, Tuple[float, float]]] = {}
        for p in player_tracks:
            if p.pitch_xy_meters and p.player_slot:
                t = round(p.timestamp_sec, 1)
                tracks_by_time.setdefault(t, {})[p.player_slot] = (p.pitch_xy_meters[0], p.pitch_xy_meters[1])

        last_overlap_time = -10.0
        for t in sorted(tracks_by_time.keys()):
            if t - last_overlap_time < 6.0:
                continue

            frame_players = tracks_by_time[t]
            for fb_slot, wing_slot, flank in pairs:
                if fb_slot in frame_players and wing_slot in frame_players:
                    fb_x, fb_y = frame_players[fb_slot]
                    wing_x, wing_y = frame_players[wing_slot]

                    # Fullback coordinate x exceeds winger coordinate x in attacking half
                    if fb_x > wing_x + 2.0 and fb_x >= 55.0:
                        zone = map_pitch_coordinates_to_zone(fb_x, fb_y)
                        event = TacticalEvent(
                            video_id=video_id,
                            match_id=match_id,
                            timestamp_start=max(0.0, t - 1.0),
                            timestamp_end=t + 2.5,
                            event_type="OVERLAPPING_RUN",
                            team_identity="HOME",
                            player_identity=fb_slot,
                            formation_slot=fb_slot,
                            pitch_zone=zone,
                            observed_action=f"{fb_slot} overlapped beyond {wing_slot} (+{(fb_x - wing_x):.1f}m separation)",
                            observed_outcome="FLANK_OVERLOAD_CREATED",
                            observation_method=ObservationMethod.AUTOMATED_DETECTOR,
                            identity_confidence=IdentityConfidence.HIGH,
                            review_status=ReviewStatus.UNDER_REVIEW,
                            related_hypothesis="HYP-RULE-FLANK-SYNERGY",
                        ).seal()
                        detected.append(event)
                        last_overlap_time = t
                        break

        return detected

    def detect_line_break_passes(
        self,
        ball_tracks: List[BallTrack],
        video_id: str,
        match_id: Optional[str] = None,
    ) -> List[TacticalEvent]:
        """Detects progressive forward passes cutting through central pitch zones."""
        detected: List[TacticalEvent] = []
        if not ball_tracks:
            return detected

        sorted_balls = [b for b in ball_tracks if b.pitch_xy_meters]
        sorted_balls.sort(key=lambda b: b.timestamp_sec)

        last_pass_time = -10.0
        for i in range(len(sorted_balls) - 1):
            b_start = sorted_balls[i]
            t_start = b_start.timestamp_sec
            if t_start - last_pass_time < 5.0:
                continue

            for j in range(i + 1, min(i + 8, len(sorted_balls))):
                b_end = sorted_balls[j]
                dt = b_end.timestamp_sec - t_start
                if dt < 0.4 or dt > 2.2:
                    continue

                sx, sy = b_start.pitch_xy_meters  # type: ignore
                ex, ey = b_end.pitch_xy_meters    # type: ignore
                dx = ex - sx
                dist = math.hypot(dx, ey - sy)

                # Forward pass >= 15m penetrating into or through central middle/attacking zones
                if dx >= 14.0 and 20.0 <= sy <= 48.0 and 20.0 <= ey <= 48.0:
                    zone = map_pitch_coordinates_to_zone(ex, ey)
                    event = TacticalEvent(
                        video_id=video_id,
                        match_id=match_id,
                        timestamp_start=t_start,
                        timestamp_end=b_end.timestamp_sec + 0.5,
                        event_type="CENTRAL_LINE_BREAK_PASS",
                        team_identity="ATTACKING",
                        formation_slot="MIDFIELD_PLAYMAKER",
                        pitch_zone=zone,
                        observed_action=f"Central line-break pass covering {dist:.1f}m into Zone {zone}",
                        observed_outcome="DEFENSIVE_LINES_BYPASSED",
                        observation_method=ObservationMethod.AUTOMATED_DETECTOR,
                        identity_confidence=IdentityConfidence.HIGH,
                        review_status=ReviewStatus.UNDER_REVIEW,
                        related_hypothesis="HYP-RULE-MIDFIELD-LINEBREAK",
                    ).seal()
                    detected.append(event)
                    last_pass_time = b_end.timestamp_sec
                    break

        return detected
