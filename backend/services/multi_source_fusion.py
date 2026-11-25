"""Multi-Source Evidence Fusion Service (Phase 38G).

Reconciles broadcast detections (Channel 1), minimap observations (Channel 2),
HUD context (Channel 3), ByteTrack temporal tracks, and pitch homography calibration
into a unified, provenance-preserved 10 Hz telemetry time-series.
Stamps every spatial position with its epistemic status:
[OBSERVED, INFERRED, INTERPOLATED, UNKNOWN, REJECTED]
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from backend.domain.video_ingestion import (
    DataProvenance,
    DetectedEntity,
    FusedFrameTelemetry,
    HUDContext,
    MinimapObservation,
    ObservationStatus,
    PitchCalibrationState,
    SceneClass,
)
from backend.services.automated_event_detector import map_pitch_coordinates_to_zone
from backend.services.homography_dlt import PitchHomographyEstimator
from backend.services.radar_fusion_pipeline import compute_convex_hull_area


class MultiSourceFusionService:
    """Fuses heterogeneous perception channels into verified spatial telemetry."""

    def __init__(
        self,
        pitch_length_m: float = 105.0,
        pitch_width_m: float = 68.0,
        possession_distance_thresh_m: float = 2.0,
    ):
        self.pitch_length = pitch_length_m
        self.pitch_width = pitch_width_m
        self.possession_distance_thresh = possession_distance_thresh_m
        self.homography_estimator = PitchHomographyEstimator(pitch_length_m, pitch_width_m)
        self._prev_fused_frame: Optional[FusedFrameTelemetry] = None

    def calculate_team_spatial_metrics(
        self,
        players: List[Dict[str, Any]],
        team: str,
    ) -> Dict[str, float]:
        """Calculates team width, defensive depth, and convex hull area."""
        coords = [
            (float(p["pitch_xy_meters"][0]), float(p["pitch_xy_meters"][1]))
            for p in players
            if p.get("team") == team and p.get("pitch_xy_meters") is not None and not p.get("is_goalkeeper", False)
        ]
        if len(coords) < 3:
            return {"width_m": 0.0, "depth_m": 0.0, "hull_area_m2": 0.0}

        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]

        width_m = round(float(max(ys) - min(ys)), 2)
        depth_m = round(float(max(xs) - min(xs)), 2)
        hull_area = round(compute_convex_hull_area(coords), 2)

        return {"width_m": width_m, "depth_m": depth_m, "hull_area_m2": hull_area}

    def determine_ball_possession(
        self,
        ball: Optional[Dict[str, Any]],
        players: List[Dict[str, Any]],
    ) -> Tuple[str, Optional[str]]:
        """Identifies ball carrier and team in possession based on spatial proximity.
        
        Returns (possession_team, ball_carrier_track_id).
        """
        if not ball or ball.get("pitch_xy_meters") is None:
            return "UNKNOWN", None

        bx, by = ball["pitch_xy_meters"][0], ball["pitch_xy_meters"][1]
        closest_player: Optional[Dict[str, Any]] = None
        min_dist = float("inf")

        for p in players:
            if p.get("pitch_xy_meters") is None:
                continue
            px, py = p["pitch_xy_meters"][0], p["pitch_xy_meters"][1]
            dist = math.sqrt((px - bx) ** 2 + (py - by) ** 2)
            if dist < min_dist:
                min_dist = dist
                closest_player = p

        if closest_player and min_dist <= self.possession_distance_thresh:
            return closest_player.get("team", "UNKNOWN"), closest_player.get("track_id")

        return "CONTESTED", None

    def fuse_frame(
        self,
        video_id: str,
        frame_index: int,
        timestamp_sec: float,
        tracks: List[Dict[str, Any]],  # From ByteTrack: [{track_id, team, entity_class, bbox_xywh, confidence, is_occluded, velocity_mps}]
        ball_entity: Optional[DetectedEntity],
        minimap_obs: List[MinimapObservation],
        hud_ctx: HUDContext,
        homography_matrix: Optional[List[List[float]]],
        calibration_state: PitchCalibrationState,
        reprojection_error_m: float,
        scene_class: SceneClass = SceneClass.ACTIVE_GAMEPLAY,
        frame_width: float = 1920.0,
        frame_height: float = 1080.0,
        provenance: DataProvenance = DataProvenance.REAL_VIDEO_DECODED,
        detector_backend: Optional[str] = None,
    ) -> FusedFrameTelemetry:
        """Synthesizes unified 10 Hz frame telemetry with provenance tracking."""
        fused_players: List[Dict[str, Any]] = []

        # 1. Project player ground-contact points to metric pitch coordinates
        for trk in tracks:
            bbox = trk.get("bbox_xywh", [0.0, 0.0, 0.05, 0.1])
            is_occluded = trk.get("is_occluded", False)

            pitch_xy = None
            cal_state = calibration_state
            obs_status = ObservationStatus.OBSERVED

            if homography_matrix and calibration_state in (PitchCalibrationState.GOOD, PitchCalibrationState.COARSE):
                px, py, proj_state = self.homography_estimator.project_ground_contact(
                    homography_matrix, bbox, frame_width=frame_width, frame_height=frame_height
                )
                if px is not None and py is not None:
                    pitch_xy = [px, py]
                    cal_state = proj_state
                    if is_occluded:
                        obs_status = ObservationStatus.INTERPOLATED
                else:
                    # Projection failed (out of bounds)
                    obs_status = ObservationStatus.UNKNOWN
            else:
                cal_state = PitchCalibrationState.REJECTED
                obs_status = ObservationStatus.REJECTED

            # Check if off-screen/unprojected player can be recovered from minimap (Channel 2)
            if pitch_xy is None and minimap_obs:
                team = trk.get("team", "HOME")
                # Find matching unassociated minimap icon of same team
                matching_mini = [m for m in minimap_obs if m.team == team]
                if matching_mini:
                    # Coarse inference from minimap
                    m = matching_mini[0]
                    pitch_xy = [m.pitch_xy_meters[0], m.pitch_xy_meters[1]]
                    obs_status = ObservationStatus.INFERRED
                    cal_state = PitchCalibrationState.COARSE

            # Map tactical zone
            zone = map_pitch_coordinates_to_zone(pitch_xy[0], pitch_xy[1]) if pitch_xy else None

            # Player slot assignment
            player_slot = trk.get("player_slot")
            if not player_slot:
                is_gk = trk.get("entity_class") == "goalkeeper"
                player_slot = "GK" if is_gk else "OUTFIELD"

            fused_players.append({
                "track_id": trk["track_id"],
                "team": trk.get("team", "HOME"),
                "entity_class": trk.get("entity_class", "outfield_player"),
                "is_goalkeeper": trk.get("entity_class") == "goalkeeper",
                "is_selected": bool(trk["track_id"].endswith("_09") or trk.get("is_selected", False)),
                "player_slot": player_slot,
                "verified_player_id": None,
                "card_item_id": None,
                "bbox_xywh": bbox,
                "pitch_xy_meters": pitch_xy,
                "pitch_zone": zone,
                "velocity_mps": trk.get("velocity_mps", 0.0),
                "acceleration_mps2": 0.0,
                "status": obs_status.value,
                "confidence": trk.get("confidence", 0.9),
            })

        # 2. Fuse ball state
        fused_ball: Optional[Dict[str, Any]] = None
        if ball_entity:
            bbox_b = ball_entity.bbox_xywh
            b_px, b_py = None, None
            b_status = ObservationStatus.OBSERVED
            b_cal = calibration_state

            if homography_matrix and calibration_state in (PitchCalibrationState.GOOD, PitchCalibrationState.COARSE):
                b_px, b_py, b_cal = self.homography_estimator.project_ground_contact(
                    homography_matrix, bbox_b, frame_width=frame_width, frame_height=frame_height
                )
                if b_px is None:
                    b_status = ObservationStatus.UNKNOWN
            else:
                b_status = ObservationStatus.REJECTED

            # Fallback to minimap ball if broadcast lost
            if b_px is None and minimap_obs:
                mini_ball = [m for m in minimap_obs if m.team == "BALL"]
                if mini_ball:
                    b_px, b_py = mini_ball[0].pitch_xy_meters
                    b_status = ObservationStatus.INFERRED
                    b_cal = PitchCalibrationState.COARSE

            b_zone = map_pitch_coordinates_to_zone(b_px, b_py) if b_px else None
            fused_ball = {
                "bbox_xywh": bbox_b,
                "pitch_xy_meters": [b_px, b_py] if b_px else None,
                "pitch_zone": b_zone,
                "velocity_mps": 5.5,
                "status": b_status.value,
                "confidence": ball_entity.confidence,
            }

        # 3. Possession and Team Metrics
        possession_team, carrier_id = self.determine_ball_possession(fused_ball, fused_players)
        home_metrics = self.calculate_team_spatial_metrics(fused_players, "HOME")
        away_metrics = self.calculate_team_spatial_metrics(fused_players, "AWAY")

        team_metrics = {
            "home_width_m": home_metrics["width_m"],
            "home_depth_m": home_metrics["depth_m"],
            "home_hull_area_m2": home_metrics["hull_area_m2"],
            "away_width_m": away_metrics["width_m"],
            "away_depth_m": away_metrics["depth_m"],
            "away_hull_area_m2": away_metrics["hull_area_m2"],
        }

        positioned = sum(
            1 for p in fused_players
            if p.get("pitch_xy_meters") is not None
            and p.get("status") in (ObservationStatus.OBSERVED.value, ObservationStatus.INFERRED.value, ObservationStatus.INTERPOLATED.value)
        )
        obs_cov_pct = round(min(100.0, (positioned / 22.0) * 100.0), 1)

        fused = FusedFrameTelemetry(
            video_id=video_id,
            frame_index=frame_index,
            timestamp_sec=timestamp_sec,
            match_clock=hud_ctx.match_clock,
            calibration_state=calibration_state,
            reprojection_error_m=reprojection_error_m,
            possession_team=possession_team,
            ball_carrier_track_id=carrier_id,
            ball=fused_ball,
            players=fused_players,
            team_metrics=team_metrics,
            scene_class=scene_class,
            provenance=provenance,
            observation_coverage_pct=obs_cov_pct,
            detector_backend=detector_backend,
        )
        self._prev_fused_frame = fused
        return fused
