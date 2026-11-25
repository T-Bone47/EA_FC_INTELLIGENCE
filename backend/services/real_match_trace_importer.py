"""Phase 39 Stage 8/9: Real Match Tracking Trace Importer.

Parses external JSON or Metrica-Sports-format normalized [0..1] tracking frames into
verified `FusedFrameTelemetry` stamped `DataProvenance.IMPORTED_MATCH_TRACE` so real
match tracking data and real video CV telemetry can be evaluated under separate
epistemic categories.
"""
from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.domain.video_ingestion import (
    DataProvenance,
    FusedFrameTelemetry,
    ObservationStatus,
    PitchCalibrationState,
    SceneClass,
)
from backend.services.automated_event_detector import map_pitch_coordinates_to_zone
from backend.services.radar_fusion_pipeline import compute_convex_hull_area


class TracePlayerInput(BaseModel):
    track_id: str
    team: str  # HOME | AWAY
    x_norm: float = Field(ge=0.0, le=1.0)
    y_norm: float = Field(ge=0.0, le=1.0)
    player_slot: str = "OUTFIELD"
    is_goalkeeper: bool = False


class TraceFrameInput(BaseModel):
    frame_index: int
    timestamp_sec: float
    match_clock: Optional[str] = None
    ball_x_norm: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    ball_y_norm: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    players: List[TracePlayerInput] = Field(default_factory=list)


def import_json_match_trace(
    video_id: str,
    frames: List[TraceFrameInput],
    pitch_length_m: float = 105.0,
    pitch_width_m: float = 68.0,
) -> List[FusedFrameTelemetry]:
    """Converts normalized [0..1] match tracking JSON into calibrated FusedFrameTelemetry."""
    fused_list: List[FusedFrameTelemetry] = []

    for fr in frames:
        fused_players: List[Dict[str, Any]] = []
        home_pts = []
        away_pts = []

        for p in fr.players:
            xm = round(p.x_norm * pitch_length_m, 2)
            ym = round((1.0 - p.y_norm) * pitch_width_m, 2)
            zone = map_pitch_coordinates_to_zone(xm, ym)
            if p.team == "HOME" and not p.is_goalkeeper:
                home_pts.append((xm, ym))
            elif p.team == "AWAY" and not p.is_goalkeeper:
                away_pts.append((xm, ym))

            fused_players.append({
                "track_id": p.track_id,
                "team": p.team,
                "entity_class": "goalkeeper" if p.is_goalkeeper else "outfield_player",
                "is_goalkeeper": p.is_goalkeeper,
                "is_selected": False,
                "player_slot": p.player_slot,
                "pitch_xy_meters": [xm, ym],
                "pitch_zone": zone,
                "velocity_mps": 0.0,
                "status": ObservationStatus.OBSERVED.value,
                "confidence": 1.0,
            })

        ball_dict = None
        possession_team = "UNKNOWN"
        carrier_id = None
        if fr.ball_x_norm is not None and fr.ball_y_norm is not None:
            bx = round(fr.ball_x_norm * pitch_length_m, 2)
            by = round((1.0 - fr.ball_y_norm) * pitch_width_m, 2)
            ball_dict = {
                "pitch_xy_meters": [bx, by],
                "pitch_zone": map_pitch_coordinates_to_zone(bx, by),
                "status": ObservationStatus.OBSERVED.value,
                "confidence": 1.0,
            }
            best_d = 999.0
            for fp in fused_players:
                px, py = fp["pitch_xy_meters"]
                d = ((px - bx) ** 2 + (py - by) ** 2) ** 0.5
                if d < best_d:
                    best_d = d
                    if d <= 2.5:
                        possession_team = fp["team"]
                        carrier_id = fp["track_id"]

        team_metrics = {
            "home_width_m": round(max(y for _, y in home_pts) - min(y for _, y in home_pts), 2) if len(home_pts) >= 2 else 0.0,
            "home_depth_m": round(max(x for x, _ in home_pts) - min(x for x, _ in home_pts), 2) if len(home_pts) >= 2 else 0.0,
            "home_hull_area_m2": round(compute_convex_hull_area(home_pts), 2) if len(home_pts) >= 3 else 0.0,
            "away_width_m": round(max(y for _, y in away_pts) - min(y for _, y in away_pts), 2) if len(away_pts) >= 2 else 0.0,
            "away_depth_m": round(max(x for x, _ in away_pts) - min(x for x, _ in away_pts), 2) if len(away_pts) >= 2 else 0.0,
            "away_hull_area_m2": round(compute_convex_hull_area(away_pts), 2) if len(away_pts) >= 3 else 0.0,
        }

        fused_list.append(FusedFrameTelemetry(
            video_id=video_id,
            frame_index=fr.frame_index,
            timestamp_sec=fr.timestamp_sec,
            match_clock=fr.match_clock,
            calibration_state=PitchCalibrationState.GOOD,
            reprojection_error_m=0.0,
            possession_team=possession_team,
            ball_carrier_track_id=carrier_id,
            ball=ball_dict,
            players=fused_players,
            team_metrics=team_metrics,
            scene_class=SceneClass.ACTIVE_GAMEPLAY,
            provenance=DataProvenance.IMPORTED_MATCH_TRACE,
            observation_coverage_pct=round(min(100.0, (len(fused_players) / 22.0) * 100.0), 1),
            detector_backend="EXTERNAL_TRACKING_IMPORT",
        ))

    return fused_list
