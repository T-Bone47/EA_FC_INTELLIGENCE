"""Phase 39 Stage 3: Advanced Spatial Intelligence & Uncertainty-Aware Pitch Control Engine.

Operates strictly over structured `FusedFrameTelemetry` streams (decoded video frames,
imported real match traces, or explicitly tagged fixture data).

Methodological foundations & adaptations for EA SPORTS FC:
- Friends of Tracking / William Spearman physics-inspired influence fields (MIT/academic).
- Karun Singh Expected Threat (xT) 12x8 spatial progression value surface adapted for
  EA FC 105m x 68m normalized pitch coordinates.
- Uncertainty-aware gating: distinguishes HEURISTIC_GAUSSIAN_INFLUENCE from
  EMPIRICALLY_CALIBRATED_PITCH_CONTROL and degrades gracefully when pitch calibration
  is COARSE/REJECTED or observation coverage is partial.
"""
from __future__ import annotations

import math
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from pydantic import BaseModel, Field

from backend.domain.video_ingestion import (
    DataProvenance,
    FusedFrameTelemetry,
    ObservationStatus,
    PitchCalibrationState,
    SceneClass,
)
from backend.services.automated_event_detector import map_pitch_coordinates_to_zone


PITCH_LENGTH_M = 105.0
PITCH_WIDTH_M = 68.0
GRID_COLS = 21  # 5.0m resolution along length
GRID_ROWS = 14  # ~4.86m resolution along width

# Karun Singh-inspired 12x8 Expected Threat (xT) surface attacking left->right (0->105m)
_XT_MATRIX_12X8 = np.array([
    [0.006, 0.008, 0.010, 0.013, 0.016, 0.021, 0.026, 0.033, 0.043, 0.056, 0.072, 0.068],
    [0.007, 0.009, 0.012, 0.015, 0.019, 0.025, 0.032, 0.041, 0.054, 0.074, 0.105, 0.118],
    [0.008, 0.011, 0.014, 0.017, 0.022, 0.029, 0.037, 0.049, 0.068, 0.098, 0.148, 0.215],
    [0.009, 0.012, 0.015, 0.019, 0.024, 0.031, 0.041, 0.056, 0.080, 0.120, 0.195, 0.340],
    [0.009, 0.012, 0.015, 0.019, 0.024, 0.031, 0.041, 0.056, 0.080, 0.120, 0.195, 0.340],
    [0.008, 0.011, 0.014, 0.017, 0.022, 0.029, 0.037, 0.049, 0.068, 0.098, 0.148, 0.215],
    [0.007, 0.009, 0.012, 0.015, 0.019, 0.025, 0.032, 0.041, 0.054, 0.074, 0.105, 0.118],
    [0.006, 0.008, 0.010, 0.013, 0.016, 0.021, 0.026, 0.033, 0.043, 0.056, 0.072, 0.068],
], dtype=np.float64)


class SpatialModelMode(str, Enum):
    HEURISTIC_GAUSSIAN_INFLUENCE = "HEURISTIC_GAUSSIAN_INFLUENCE"
    EMPIRICALLY_CALIBRATED_PITCH_CONTROL = "EMPIRICALLY_CALIBRATED_PITCH_CONTROL"
    INSUFFICIENT_OBSERVATION = "INSUFFICIENT_OBSERVATION"


class UncertaintyBand(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    UNRELIABLE = "UNRELIABLE"


class PlayerKinematicState(BaseModel):
    track_id: str
    team: str
    player_slot: str = "OUTFIELD"
    is_goalkeeper: bool = False
    x_m: float
    y_m: float
    vx_mps: float = 0.0
    vy_mps: float = 0.0
    speed_mps: float = 0.0
    ax_mps2: float = 0.0
    ay_mps2: float = 0.0
    accel_mps2: float = 0.0
    kinematic_anomaly: bool = False
    observation_status: str = ObservationStatus.OBSERVED.value


class PassingLaneOption(BaseModel):
    target_track_id: str
    target_slot: str
    target_xy: Tuple[float, float]
    distance_m: float
    nearest_defender_clearance_m: float
    openness_score: float  # [0, 1] heuristic corridor openness
    status: str  # OPEN | CONTESTED | BLOCKED
    xt_gain: float
    is_progressive: bool


class TeamTacticalStructure(BaseModel):
    team: str
    observed_outfield_count: int
    defensive_line_x_m: Optional[float] = None
    midfield_line_x_m: Optional[float] = None
    forward_line_x_m: Optional[float] = None
    def_to_mid_gap_m: Optional[float] = None
    mid_to_att_gap_m: Optional[float] = None
    team_length_m: float = 0.0
    team_width_m: float = 0.0
    compactness_area_m2: float = 0.0
    inferred_formation: Optional[str] = None
    lane_counts: Dict[str, int] = Field(default_factory=dict)
    rest_defense_count: int = 0


class SpatialFrameSnapshot(BaseModel):
    video_id: str
    frame_index: int
    timestamp_sec: float
    provenance: str
    model_mode: SpatialModelMode
    uncertainty_band: UncertaintyBand
    calibration_state: str
    observation_coverage_pct: float
    home_pitch_control_pct: Optional[float] = None
    away_pitch_control_pct: Optional[float] = None
    pitch_control_grid: Optional[List[List[float]]] = None  # [GRID_ROWS][GRID_COLS], values in [0, 1] P(HOME control)
    possession_team: str = "UNKNOWN"
    ball_carrier_track_id: Optional[str] = None
    ball_xy: Optional[Tuple[float, float]] = None
    ball_xt: Optional[float] = None
    zone_overloads: Dict[int, Dict[str, int]] = Field(default_factory=dict)
    home_structure: TeamTacticalStructure
    away_structure: TeamTacticalStructure
    passing_lanes: List[PassingLaneOption] = Field(default_factory=list)
    kinematics: List[PlayerKinematicState] = Field(default_factory=list)
    caveats: List[str] = Field(default_factory=list)


def expected_threat_at(x_m: float, y_m: float, attacking_right: bool = True) -> float:
    """Evaluates positional Expected Threat (xT) on a 105m x 68m pitch."""
    x = max(0.0, min(PITCH_LENGTH_M - 1e-4, x_m))
    y = max(0.0, min(PITCH_WIDTH_M - 1e-4, y_m))
    if not attacking_right:
        x = PITCH_LENGTH_M - x
    col = min(11, int((x / PITCH_LENGTH_M) * 12))
    row = min(7, int(((PITCH_WIDTH_M - y) / PITCH_WIDTH_M) * 8))
    return round(float(_XT_MATRIX_12X8[row, col]), 4)


def _assign_lateral_lane(y_m: float) -> str:
    if y_m >= 54.4:
        return "LEFT_FLANK"
    if y_m >= 40.8:
        return "LEFT_HALF_SPACE"
    if y_m >= 27.2:
        return "CENTRAL_SPINE"
    if y_m >= 13.6:
        return "RIGHT_HALF_SPACE"
    return "RIGHT_FLANK"


class SpatialIntelligenceEngine:
    """Computes uncertainty-aware pitch control, kinematics, passing lanes, and shape."""

    def __init__(self, empirically_calibrated: bool = False):
        self.empirically_calibrated = empirically_calibrated
        # Precompute grid center coordinates once
        xs = (np.arange(GRID_COLS) + 0.5) * (PITCH_LENGTH_M / GRID_COLS)
        ys = (GRID_ROWS - 0.5 - np.arange(GRID_ROWS)) * (PITCH_WIDTH_M / GRID_ROWS)
        self._grid_x, self._grid_y = np.meshgrid(xs, ys)  # shape (GRID_ROWS, GRID_COLS)

    def analyze_timeline(
        self,
        telemetry_frames: List[FusedFrameTelemetry],
        include_grid_per_frame: bool = True,
    ) -> Dict[str, Any]:
        """Runs complete Phase 39 spatial analysis across a match telemetry timeline."""
        if not telemetry_frames:
            return {
                "frames": [],
                "heatmaps": {"home": [], "away": []},
                "trails": {},
                "summary": {
                    "analyzed_frames": 0,
                    "reliable_frames": 0,
                    "mean_home_control_pct": None,
                    "mean_away_control_pct": None,
                    "model_mode": SpatialModelMode.INSUFFICIENT_OBSERVATION.value,
                    "caveats": ["No telemetry frames provided."],
                },
            }

        frames_sorted = sorted(telemetry_frames, key=lambda f: f.timestamp_sec)
        prev_pos: Dict[str, Tuple[float, float, float]] = {}
        prev_vel: Dict[str, Tuple[float, float, float]] = {}

        snapshots: List[SpatialFrameSnapshot] = []
        trails: Dict[str, List[Dict[str, float]]] = {}
        home_heat = np.zeros((GRID_ROWS, GRID_COLS), dtype=np.float64)
        away_heat = np.zeros((GRID_ROWS, GRID_COLS), dtype=np.float64)
        reliable_count = 0
        home_ctrl_samples: List[float] = []

        for frame in frames_sorted:
            t = frame.timestamp_sec
            cal_state = frame.calibration_state
            usable_players = [
                p for p in frame.players
                if p.get("pitch_xy_meters") is not None
                and p.get("status") not in (ObservationStatus.REJECTED.value, ObservationStatus.UNKNOWN.value)
            ]
            # Coverage against expected 22 match participants (or observed count baseline)
            cov_pct = frame.observation_coverage_pct or round(min(100.0, (len(usable_players) / 22.0) * 100.0), 1)

            # Determine uncertainty band and model mode
            caveats: List[str] = []
            if cal_state == PitchCalibrationState.REJECTED or frame.scene_class != SceneClass.ACTIVE_GAMEPLAY:
                uncertainty = UncertaintyBand.UNRELIABLE
                model_mode = SpatialModelMode.INSUFFICIENT_OBSERVATION
                caveats.append("Frame excluded from pitch control: calibration rejected or non-active gameplay.")
            elif len(usable_players) < 6:
                uncertainty = UncertaintyBand.HIGH
                model_mode = SpatialModelMode.INSUFFICIENT_OBSERVATION
                caveats.append(f"Only {len(usable_players)} positioned players; pitch control withheld.")
            else:
                if cal_state == PitchCalibrationState.GOOD and cov_pct >= 70.0:
                    uncertainty = UncertaintyBand.LOW
                elif cov_pct >= 45.0:
                    uncertainty = UncertaintyBand.MODERATE
                    caveats.append(f"Partial tracking coverage ({cov_pct:.0f}%); uncaptured off-screen players increase spatial uncertainty.")
                else:
                    uncertainty = UncertaintyBand.HIGH
                    caveats.append(f"Low tracking coverage ({cov_pct:.0f}%); treat influence boundaries cautiously.")

                if frame.provenance == DataProvenance.SYNTHETIC_FIXTURE:
                    caveats.append("SYNTHETIC_FIXTURE provenance: influence grid is illustrative only.")
                    model_mode = SpatialModelMode.HEURISTIC_GAUSSIAN_INFLUENCE
                else:
                    model_mode = (
                        SpatialModelMode.EMPIRICALLY_CALIBRATED_PITCH_CONTROL
                        if self.empirically_calibrated
                        else SpatialModelMode.HEURISTIC_GAUSSIAN_INFLUENCE
                    )

            # 1. Kinematics per player
            kin_list: List[PlayerKinematicState] = []
            for p in usable_players:
                tid = str(p.get("track_id") or p.get("player_slot") or "unknown")
                team = str(p.get("team", "HOME"))
                px, py = float(p["pitch_xy_meters"][0]), float(p["pitch_xy_meters"][1])

                vx, vy, speed = 0.0, 0.0, float(p.get("velocity_mps", 0.0) or 0.0)
                ax, ay, accel = 0.0, 0.0, 0.0
                anomaly = False

                if tid in prev_pos:
                    ox, oy, ot = prev_pos[tid]
                    dt = t - ot
                    if 0.04 <= dt <= 1.2:
                        vx = (px - ox) / dt
                        vy = (py - oy) / dt
                        raw_speed = math.hypot(vx, vy)
                        if raw_speed > 11.8:  # Physically implausible sprint teleport artifact
                            anomaly = True
                            scale = 9.5 / raw_speed
                            vx *= scale
                            vy *= scale
                            speed = 9.5
                        else:
                            speed = raw_speed

                        if tid in prev_vel:
                            ovx, ovy, ovt = prev_vel[tid]
                            dt_a = t - ovt
                            if 0.04 <= dt_a <= 1.2:
                                ax = (vx - ovx) / dt_a
                                ay = (vy - ovy) / dt_a
                                accel = math.hypot(ax, ay)

                prev_pos[tid] = (px, py, t)
                prev_vel[tid] = (vx, vy, t)

                kin = PlayerKinematicState(
                    track_id=tid,
                    team=team,
                    player_slot=str(p.get("player_slot") or "OUTFIELD"),
                    is_goalkeeper=bool(p.get("is_goalkeeper", False)),
                    x_m=round(px, 2),
                    y_m=round(py, 2),
                    vx_mps=round(vx, 2),
                    vy_mps=round(vy, 2),
                    speed_mps=round(speed, 2),
                    ax_mps2=round(ax, 2),
                    ay_mps2=round(ay, 2),
                    accel_mps2=round(accel, 2),
                    kinematic_anomaly=anomaly,
                    observation_status=str(p.get("status", ObservationStatus.OBSERVED.value)),
                )
                kin_list.append(kin)

                # Accumulate movement trails and positional heatmaps on reliable/moderate frames
                if uncertainty != UncertaintyBand.UNRELIABLE:
                    trails.setdefault(tid, []).append({
                        "t": round(t, 2),
                        "x": round(px, 2),
                        "y": round(py, 2),
                        "speed": round(speed, 2),
                        "team": team,
                    })
                    col_idx = min(GRID_COLS - 1, max(0, int((px / PITCH_LENGTH_M) * GRID_COLS)))
                    row_idx = min(GRID_ROWS - 1, max(0, int(((PITCH_WIDTH_M - py) / PITCH_WIDTH_M) * GRID_ROWS)))
                    if team == "HOME":
                        home_heat[row_idx, col_idx] += 1.0
                    elif team == "AWAY":
                        away_heat[row_idx, col_idx] += 1.0

            # 2. Team Structure & Tactical Lanes
            ball_xy = None
            ball_xt = None
            if frame.ball and frame.ball.get("pitch_xy_meters") is not None:
                bx, by = float(frame.ball["pitch_xy_meters"][0]), float(frame.ball["pitch_xy_meters"][1])
                ball_xy = (round(bx, 2), round(by, 2))
                attacking_right = frame.possession_team != "AWAY"
                ball_xt = expected_threat_at(bx, by, attacking_right=attacking_right)

            home_struct = self._analyze_team_structure(kin_list, "HOME", ball_xy, frame.team_metrics)
            away_struct = self._analyze_team_structure(kin_list, "AWAY", ball_xy, frame.team_metrics)

            # 3. Numerical Overloads in 18 tactical zones
            overloads: Dict[int, Dict[str, int]] = {}
            for k in kin_list:
                if k.is_goalkeeper:
                    continue
                z = map_pitch_coordinates_to_zone(k.x_m, k.y_m)
                entry = overloads.setdefault(z, {"home": 0, "away": 0, "delta": 0})
                if k.team == "HOME":
                    entry["home"] += 1
                elif k.team == "AWAY":
                    entry["away"] += 1
                entry["delta"] = entry["home"] - entry["away"]

            # 4. Gaussian Influence / Pitch Control Surface
            home_ctrl_pct = None
            away_ctrl_pct = None
            grid_payload = None
            if model_mode != SpatialModelMode.INSUFFICIENT_OBSERVATION:
                prob_grid = self._compute_gaussian_influence_grid(kin_list, ball_xy)
                home_ctrl_pct = round(float(np.mean(prob_grid) * 100.0), 1)
                away_ctrl_pct = round(100.0 - home_ctrl_pct, 1)
                home_ctrl_samples.append(home_ctrl_pct)
                reliable_count += 1
                if include_grid_per_frame:
                    grid_payload = np.round(prob_grid, 3).tolist()

            # 5. Passing Lanes from Ball Carrier
            passing_lanes: List[PassingLaneOption] = []
            if uncertainty != UncertaintyBand.UNRELIABLE and ball_xy is not None:
                passing_lanes = self._analyze_passing_lanes(
                    kin_list,
                    possession_team=frame.possession_team,
                    carrier_id=frame.ball_carrier_track_id,
                    ball_xy=ball_xy,
                )

            snapshots.append(SpatialFrameSnapshot(
                video_id=frame.video_id,
                frame_index=frame.frame_index,
                timestamp_sec=t,
                provenance=frame.provenance.value,
                model_mode=model_mode,
                uncertainty_band=uncertainty,
                calibration_state=cal_state.value,
                observation_coverage_pct=cov_pct,
                home_pitch_control_pct=home_ctrl_pct,
                away_pitch_control_pct=away_ctrl_pct,
                pitch_control_grid=grid_payload,
                possession_team=frame.possession_team,
                ball_carrier_track_id=frame.ball_carrier_track_id,
                ball_xy=ball_xy,
                ball_xt=ball_xt,
                zone_overloads=overloads,
                home_structure=home_struct,
                away_structure=away_struct,
                passing_lanes=passing_lanes,
                kinematics=kin_list,
                caveats=caveats,
            ))

        # Normalize team positional heatmaps to [0, 1]
        if home_heat.max() > 0:
            home_heat = home_heat / home_heat.max()
        if away_heat.max() > 0:
            away_heat = away_heat / away_heat.max()

        mean_home = round(sum(home_ctrl_samples) / len(home_ctrl_samples), 1) if home_ctrl_samples else None
        return {
            "frames": [s.model_dump() for s in snapshots],
            "heatmaps": {
                "home": np.round(home_heat, 3).tolist(),
                "away": np.round(away_heat, 3).tolist(),
            },
            "trails": {k: v[-40:] for k, v in trails.items()},
            "summary": {
                "analyzed_frames": len(snapshots),
                "reliable_frames": reliable_count,
                "mean_home_control_pct": mean_home,
                "mean_away_control_pct": round(100.0 - mean_home, 1) if mean_home is not None else None,
                "model_mode": (
                    SpatialModelMode.EMPIRICALLY_CALIBRATED_PITCH_CONTROL.value
                    if self.empirically_calibrated
                    else SpatialModelMode.HEURISTIC_GAUSSIAN_INFLUENCE.value
                ),
                "calibrated_empirically": self.empirically_calibrated,
            },
        }

    def _compute_gaussian_influence_grid(
        self,
        kinematics: List[PlayerKinematicState],
        ball_xy: Optional[Tuple[float, float]],
    ) -> np.ndarray:
        """Spearman-inspired anisotropic Gaussian influence surface over 21x14 pitch grid."""
        home_inf = np.full((GRID_ROWS, GRID_COLS), 1e-6, dtype=np.float64)
        away_inf = np.full((GRID_ROWS, GRID_COLS), 1e-6, dtype=np.float64)
        bx, by = ball_xy if ball_xy else (52.5, 34.0)

        for p in kinematics:
            if p.team not in ("HOME", "AWAY"):
                continue
            # Ball distance adjusts influence radius smoothly (4m near ball up to 10m far away)
            dist_to_ball = math.hypot(p.x_m - bx, p.y_m - by)
            base_radius = min(10.5, 4.2 + 0.08 * dist_to_ball)

            # Forward velocity shifts mean control center by reaction horizon (~0.45s)
            mu_x = max(0.0, min(PITCH_LENGTH_M, p.x_m + 0.45 * p.vx_mps))
            mu_y = max(0.0, min(PITCH_WIDTH_M, p.y_m + 0.45 * p.vy_mps))

            # Speed stretches major axis along motion direction
            s_ratio = min(1.0, p.speed_mps / 10.0)
            sigma_par = base_radius * (1.0 + 0.6 * s_ratio)
            sigma_orth = base_radius * (1.0 - 0.25 * s_ratio)

            dx = self._grid_x - mu_x
            dy = self._grid_y - mu_y
            if p.speed_mps > 0.6:
                theta = math.atan2(p.vy_mps, p.vx_mps)
                ct, st = math.cos(theta), math.sin(theta)
                u = dx * ct + dy * st
                v = -dx * st + dy * ct
            else:
                u, v = dx, dy

            exponent = -0.5 * ((u / sigma_par) ** 2 + (v / sigma_orth) ** 2)
            # Attenuate unverified interpolated tracks slightly vs direct observations
            obs_weight = 0.75 if p.observation_status == ObservationStatus.INTERPOLATED.value else 1.0
            field = obs_weight * np.exp(exponent)

            if p.team == "HOME":
                home_inf += field
            else:
                away_inf += field

        prob_home = home_inf / (home_inf + away_inf)
        return np.clip(prob_home, 0.02, 0.98)

    def _analyze_team_structure(
        self,
        kinematics: List[PlayerKinematicState],
        team: str,
        ball_xy: Optional[Tuple[float, float]],
        team_metrics: Dict[str, float],
    ) -> TeamTacticalStructure:
        outfield = [p for p in kinematics if p.team == team and not p.is_goalkeeper]
        lanes = {
            "LEFT_FLANK": 0,
            "LEFT_HALF_SPACE": 0,
            "CENTRAL_SPINE": 0,
            "RIGHT_HALF_SPACE": 0,
            "RIGHT_FLANK": 0,
        }
        for p in outfield:
            lanes[_assign_lateral_lane(p.y_m)] += 1

        if len(outfield) < 3:
            return TeamTacticalStructure(
                team=team,
                observed_outfield_count=len(outfield),
                lane_counts=lanes,
            )

        xs = sorted(p.x_m for p in outfield)
        ys = [p.y_m for p in outfield]
        # Orient goal direction so lowest X is always closest to own goal
        is_away = team == "AWAY"
        ordered = list(reversed(xs)) if is_away else xs

        # Slice outfielders into Defensive / Midfield / Attacking bands by depth
        n = len(ordered)
        def_band = ordered[: max(2, min(4, n // 3 + 1))]
        att_band = ordered[max(len(def_band), n - max(2, min(3, n // 3))):]
        mid_band = ordered[len(def_band) : n - len(att_band)] if n >= 6 else []

        def_x = round(float(np.median(def_band)), 2) if def_band else None
        mid_x = round(float(np.median(mid_band)), 2) if mid_band else None
        att_x = round(float(np.median(att_band)), 2) if att_band else None

        def_mid_gap = round(abs(mid_x - def_x), 2) if (def_x is not None and mid_x is not None) else None
        mid_att_gap = round(abs(att_x - mid_x), 2) if (mid_x is not None and att_x is not None) else None

        rest_defense = 0
        if ball_xy:
            bx = ball_xy[0]
            if not is_away:
                rest_defense = sum(1 for p in outfield if p.x_m <= bx + 1.5)
            else:
                rest_defense = sum(1 for p in outfield if p.x_m >= bx - 1.5)

        prefix = "home" if team == "HOME" else "away"
        width = float(team_metrics.get(f"{prefix}_width_m") or (max(ys) - min(ys)))
        length = float(team_metrics.get(f"{prefix}_depth_m") or (max(xs) - min(xs)))
        hull_area = float(team_metrics.get(f"{prefix}_hull_area_m2") or 0.0)

        inferred_form = None
        if n >= 8:
            # Approximate band counts using spatial k-means gaps
            d_cnt = len(def_band)
            m_cnt = max(1, len(mid_band))
            a_cnt = max(1, len(att_band))
            inferred_form = f"{d_cnt}-{m_cnt}-{a_cnt}"

        return TeamTacticalStructure(
            team=team,
            observed_outfield_count=n,
            defensive_line_x_m=def_x,
            midfield_line_x_m=mid_x,
            forward_line_x_m=att_x,
            def_to_mid_gap_m=def_mid_gap,
            mid_to_att_gap_m=mid_att_gap,
            team_length_m=round(length, 2),
            team_width_m=round(width, 2),
            compactness_area_m2=round(hull_area, 2),
            inferred_formation=inferred_form,
            lane_counts=lanes,
            rest_defense_count=rest_defense,
        )

    def _analyze_passing_lanes(
        self,
        kinematics: List[PlayerKinematicState],
        possession_team: str,
        carrier_id: Optional[str],
        ball_xy: Tuple[float, float],
    ) -> List[PassingLaneOption]:
        if possession_team not in ("HOME", "AWAY"):
            return []

        teammates = [p for p in kinematics if p.team == possession_team and not p.is_goalkeeper and p.track_id != carrier_id]
        opponents = [p for p in kinematics if p.team != possession_team]
        if not teammates:
            return []

        attacking_right = possession_team == "HOME"
        origin_xt = expected_threat_at(ball_xy[0], ball_xy[1], attacking_right=attacking_right)
        bx, by = ball_xy
        options: List[PassingLaneOption] = []

        for tm in teammates:
            dx = tm.x_m - bx
            dy = tm.y_m - by
            dist = math.hypot(dx, dy)
            if dist < 2.5 or dist > 55.0:
                continue

            # Shortest orthogonal distance from every opponent onto passing segment [ball -> target]
            min_clr = 30.0
            for opp in opponents:
                ox, oy = opp.x_m - bx, opp.y_m - by
                proj = max(0.0, min(1.0, (ox * dx + oy * dy) / (dist * dist)))
                closest_x = bx + proj * dx
                closest_y = by + proj * dy
                clr = math.hypot(opp.x_m - closest_x, opp.y_m - closest_y)
                if clr < min_clr:
                    min_clr = clr

            # Openness heuristic combining lateral corridor clearance and pass distance
            openness = max(0.0, min(1.0, (min_clr / 4.5) * (1.0 - max(0.0, dist - 28.0) / 60.0)))
            status = "OPEN" if openness >= 0.62 else ("CONTESTED" if openness >= 0.30 else "BLOCKED")
            target_xt = expected_threat_at(tm.x_m, tm.y_m, attacking_right=attacking_right)
            xt_gain = round(target_xt - origin_xt, 4)
            is_prog = (dx > 8.0) if attacking_right else (dx < -8.0)

            options.append(PassingLaneOption(
                target_track_id=tm.track_id,
                target_slot=tm.player_slot,
                target_xy=(tm.x_m, tm.y_m),
                distance_m=round(dist, 2),
                nearest_defender_clearance_m=round(min_clr, 2),
                openness_score=round(openness, 3),
                status=status,
                xt_gain=xt_gain,
                is_progressive=is_prog,
            ))

        options.sort(key=lambda o: (o.openness_score + max(0.0, o.xt_gain * 2.0)), reverse=True)
        return options[:5]
