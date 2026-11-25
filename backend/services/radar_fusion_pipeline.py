"""Multi-Camera Calibration & Radar Minimap Sensor Fusion Engine (Phase 37).

Fuses broadcast camera player tracking (high precision, limited frustum) with
in-game HUD radar minimap telemetry (complete 22-player pitch coverage) to produce
uninterrupted full-pitch tracking states and team tactical shape metrics.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4
from pydantic import BaseModel, Field

from backend.domain.video_gameplay import PlayerTrack, BallTrack


class FusedPlayerState(BaseModel):
    player_slot: str
    team: str  # "HOME" or "AWAY"
    pitch_x: float  # 0 to 105m
    pitch_y: float  # 0 to 68m
    velocity_mps: float = 0.0
    heading_deg: float = 0.0
    is_offscreen: bool = False
    source_confidence: float = 1.0


class TeamShapeMetrics(BaseModel):
    team: str
    centroid_x: float
    centroid_y: float
    defensive_line_depth_m: float
    forward_line_depth_m: float
    team_length_m: float
    team_width_m: float
    convex_hull_area_m2: float
    compactness_ratio: float  # ratio of hull area to pitch area


class FusedFrameTelemetry(BaseModel):
    video_id: str
    frame_index: int
    timestamp_sec: float
    ball_position: Optional[Tuple[float, float]] = None
    ball_in_flight: bool = False
    home_players: List[FusedPlayerState] = Field(default_factory=list)
    away_players: List[FusedPlayerState] = Field(default_factory=list)
    home_shape: Optional[TeamShapeMetrics] = None
    away_shape: Optional[TeamShapeMetrics] = None


def compute_convex_hull_area(points: List[Tuple[float, float]]) -> float:
    """Computes 2D convex hull area using Andrew's monotone chain algorithm."""
    if len(points) < 3:
        return 0.0

    # Sort points lexicographically
    pts = sorted(set(points))
    if len(pts) < 3:
        return 0.0

    # Cross product of OA and OB vectors
    def cross(o: Tuple[float, float], a: Tuple[float, float], b: Tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    # Build lower hull
    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    # Build upper hull
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    hull = lower[:-1] + upper[:-1]

    # Shoelace formula for polygon area
    n = len(hull)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += hull[i][0] * hull[j][1]
        area -= hull[j][0] * hull[i][1]
    return abs(area) / 2.0


class RadarMinimapFusionService:
    """Fuses broadcast player detections with radar minimap extractions."""

    def __init__(
        self,
        pitch_length_m: float = 105.0,
        pitch_width_m: float = 68.0,
        cam_weight: float = 0.85,
        radar_weight: float = 0.15,
        association_gate_m: float = 12.0,
    ):
        self.pitch_length_m = pitch_length_m
        self.pitch_width_m = pitch_width_m
        self.cam_weight = cam_weight
        self.radar_weight = radar_weight
        self.association_gate_m = association_gate_m

    def convert_minimap_norm_to_pitch(
        self,
        u_norm: float,
        v_norm: float,
    ) -> Tuple[float, float]:
        """Converts normalized radar minimap coordinates [0, 1] into pitch metric coordinates."""
        # u is along pitch length (0 to 1 -> 0 to 105m)
        # v is along pitch width (0 is top/left, 1 is bottom/right)
        x = max(0.0, min(self.pitch_length_m, u_norm * self.pitch_length_m))
        y = max(0.0, min(self.pitch_width_m, (1.0 - v_norm) * self.pitch_width_m))
        return round(x, 2), round(y, 2)

    def calculate_team_shape(
        self,
        players: List[FusedPlayerState],
        team_name: str,
    ) -> TeamShapeMetrics:
        """Calculates tactical spatial shape metrics for outfield players of a team."""
        outfield = [p for p in players if p.player_slot != "GK"]
        if not outfield:
            # Fallback for empty
            return TeamShapeMetrics(
                team=team_name,
                centroid_x=52.5,
                centroid_y=34.0,
                defensive_line_depth_m=25.0,
                forward_line_depth_m=75.0,
                team_length_m=50.0,
                team_width_m=40.0,
                convex_hull_area_m2=1200.0,
                compactness_ratio=0.168,
            )

        xs = [p.pitch_x for p in outfield]
        ys = [p.pitch_y for p in outfield]

        centroid_x = sum(xs) / len(xs)
        centroid_y = sum(ys) / len(ys)

        sorted_xs = sorted(xs)
        # Lowest 3 outfield x is defensive line
        def_line = sum(sorted_xs[:3]) / max(1, len(sorted_xs[:3]))
        # Highest 3 outfield x is forward line
        fwd_line = sum(sorted_xs[-3:]) / max(1, len(sorted_xs[-3:]))

        team_length = max(5.0, fwd_line - def_line)
        team_width = max(10.0, max(ys) - min(ys))

        points = [(p.pitch_x, p.pitch_y) for p in outfield]
        hull_area = compute_convex_hull_area(points)
        pitch_area = self.pitch_length_m * self.pitch_width_m
        compactness = hull_area / pitch_area

        return TeamShapeMetrics(
            team=team_name,
            centroid_x=round(centroid_x, 2),
            centroid_y=round(centroid_y, 2),
            defensive_line_depth_m=round(def_line, 2),
            forward_line_depth_m=round(fwd_line, 2),
            team_length_m=round(team_length, 2),
            team_width_m=round(team_width, 2),
            convex_hull_area_m2=round(hull_area, 1),
            compactness_ratio=round(compactness, 4),
        )

    def fuse_frame_telemetry(
        self,
        video_id: str,
        frame_index: int,
        timestamp_sec: float,
        broadcast_tracks: List[PlayerTrack],
        radar_points: List[Dict[str, Any]],  # [{u_norm, v_norm, team, slot_hint}]
        ball_track: Optional[BallTrack] = None,
    ) -> FusedFrameTelemetry:
        """Fuses camera-detected players with radar-extracted 22 player dots."""
        home_fused: List[FusedPlayerState] = []
        away_fused: List[FusedPlayerState] = []

        # Convert all radar points to metric pitch positions
        radar_players = []
        for r in radar_points:
            x, y = self.convert_minimap_norm_to_pitch(r["u_norm"], r["v_norm"])
            radar_players.append({
                "team": r.get("team", "HOME"),
                "slot": r.get("slot_hint", "UNKNOWN"),
                "pitch_x": x,
                "pitch_y": y,
                "velocity_mps": r.get("velocity_mps", 0.0),
            })

        # Match camera detections to radar points using greedy nearest neighbor
        cam_matched = set()
        radar_matched = set()

        for c_idx, cam_p in enumerate(broadcast_tracks):
            if not cam_p.pitch_xy_meters:
                continue
            cx, cy = cam_p.pitch_xy_meters

            best_r_idx = None
            min_dist = float("inf")

            for r_idx, rad_p in enumerate(radar_players):
                if r_idx in radar_matched or rad_p["team"] != cam_p.team:
                    continue
                dist = math.hypot(cx - rad_p["pitch_x"], cy - rad_p["pitch_y"])
                if dist < min_dist and dist <= self.association_gate_m:
                    min_dist = dist
                    best_r_idx = r_idx

            slot_name = cam_p.player_slot or "PLAYER"
            if best_r_idx is not None:
                # Fused position
                rad_p = radar_players[best_r_idx]
                fused_x = (cx * self.cam_weight) + (rad_p["pitch_x"] * self.radar_weight)
                fused_y = (cy * self.cam_weight) + (rad_p["pitch_y"] * self.radar_weight)
                cam_matched.add(c_idx)
                radar_matched.add(best_r_idx)
                state = FusedPlayerState(
                    player_slot=slot_name,
                    team=cam_p.team,
                    pitch_x=round(fused_x, 2),
                    pitch_y=round(fused_y, 2),
                    velocity_mps=cam_p.velocity_mps or rad_p["velocity_mps"],
                    is_offscreen=False,
                    source_confidence=0.95,
                )
            else:
                # Solely from camera
                state = FusedPlayerState(
                    player_slot=slot_name,
                    team=cam_p.team,
                    pitch_x=round(cx, 2),
                    pitch_y=round(cy, 2),
                    velocity_mps=cam_p.velocity_mps or 0.0,
                    is_offscreen=False,
                    source_confidence=0.85,
                )

            if cam_p.team == "HOME":
                home_fused.append(state)
            else:
                away_fused.append(state)

        # Include unmatched radar points as off-screen players
        for r_idx, rad_p in enumerate(radar_players):
            if r_idx not in radar_matched:
                state = FusedPlayerState(
                    player_slot=rad_p["slot"],
                    team=rad_p["team"],
                    pitch_x=round(rad_p["pitch_x"], 2),
                    pitch_y=round(rad_p["pitch_y"], 2),
                    velocity_mps=rad_p["velocity_mps"],
                    is_offscreen=True,  # Discovered via radar!
                    source_confidence=0.75,
                )
                if rad_p["team"] == "HOME":
                    home_fused.append(state)
                else:
                    away_fused.append(state)

        # Compute team shape metrics
        home_shape = self.calculate_team_shape(home_fused, "HOME")
        away_shape = self.calculate_team_shape(away_fused, "AWAY")

        ball_pos = None
        ball_flight = False
        if ball_track and ball_track.pitch_xy_meters:
            ball_pos = (ball_track.pitch_xy_meters[0], ball_track.pitch_xy_meters[1])
            ball_flight = ball_track.in_flight

        return FusedFrameTelemetry(
            video_id=video_id,
            frame_index=frame_index,
            timestamp_sec=timestamp_sec,
            ball_position=ball_pos,
            ball_in_flight=ball_flight,
            home_players=home_fused,
            away_players=away_fused,
            home_shape=home_shape,
            away_shape=away_shape,
        )
