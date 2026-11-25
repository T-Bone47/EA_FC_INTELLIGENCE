"""Unit test suite for Radar Minimap Sensor Fusion Pipeline (Phase 37)."""
import math
import pytest
from backend.domain.video_gameplay import BallTrack, PlayerTrack
from backend.services.radar_fusion_pipeline import (
    RadarMinimapFusionService,
    compute_convex_hull_area,
)


def test_convert_minimap_norm_to_pitch():
    service = RadarMinimapFusionService()
    # Minimap (0.0, 0.0) -> x=0 (home goal), y=68 (left touchline)
    x, y = service.convert_minimap_norm_to_pitch(0.0, 0.0)
    assert x == 0.0
    assert y == 68.0

    # Minimap (0.5, 0.5) -> pitch center (52.5, 34.0)
    x, y = service.convert_minimap_norm_to_pitch(0.5, 0.5)
    assert x == 52.5
    assert y == 34.0

    # Minimap (1.0, 1.0) -> x=105, y=0 (right touchline)
    x, y = service.convert_minimap_norm_to_pitch(1.0, 1.0)
    assert x == 105.0
    assert y == 0.0


def test_compute_convex_hull_area():
    # 10m x 20m rectangle -> Area should be 200.0 m2
    rect = [(10.0, 10.0), (30.0, 10.0), (30.0, 20.0), (10.0, 20.0)]
    area = compute_convex_hull_area(rect)
    assert math.isclose(area, 200.0, abs_tol=1e-3)

    # Empty or < 3 points -> 0.0
    assert compute_convex_hull_area([(0.0, 0.0), (1.0, 1.0)]) == 0.0


def test_calculate_team_shape():
    service = RadarMinimapFusionService()
    players = [
        # Back line
        type("P", (), {"player_slot": "LB", "pitch_x": 20.0, "pitch_y": 60.0})(),
        type("P", (), {"player_slot": "LCB", "pitch_x": 18.0, "pitch_y": 45.0})(),
        type("P", (), {"player_slot": "RCB", "pitch_x": 18.0, "pitch_y": 25.0})(),
        type("P", (), {"player_slot": "RB", "pitch_x": 20.0, "pitch_y": 10.0})(),
        # Midfield
        type("P", (), {"player_slot": "CM", "pitch_x": 40.0, "pitch_y": 35.0})(),
        # Attack
        type("P", (), {"player_slot": "LW", "pitch_x": 65.0, "pitch_y": 58.0})(),
        type("P", (), {"player_slot": "ST", "pitch_x": 70.0, "pitch_y": 34.0})(),
        type("P", (), {"player_slot": "RW", "pitch_x": 65.0, "pitch_y": 12.0})(),
        # GK (should be excluded from outfield hull)
        type("P", (), {"player_slot": "GK", "pitch_x": 5.0, "pitch_y": 34.0})(),
    ]

    shape = service.calculate_team_shape(players, "HOME")
    assert shape.team == "HOME"
    assert shape.defensive_line_depth_m < shape.forward_line_depth_m
    assert shape.team_length_m > 30.0
    assert shape.team_width_m > 40.0
    assert shape.convex_hull_area_m2 > 500.0


def test_fuse_frame_telemetry():
    service = RadarMinimapFusionService()
    video_id = "test-vid-002"

    # Camera sees 1 player at (50.0, 30.0)
    cam_tracks = [
        PlayerTrack(
            video_id=video_id,
            frame_index=100,
            timestamp_sec=1.66,
            player_slot="CM",
            team="HOME",
            pitch_xy_meters=[50.0, 30.0],
            velocity_mps=3.2,
        )
    ]

    # Radar sees 2 players:
    # 1. Close to CM: u_norm=0.48 (x=50.4), v_norm=0.55 (y=30.6) -> matched!
    # 2. Far striker off-screen: u_norm=0.80 (x=84.0), v_norm=0.50 (y=34.0) -> off-screen!
    radar_points = [
        {"u_norm": 0.48, "v_norm": 0.55, "team": "HOME", "slot_hint": "CM", "velocity_mps": 3.1},
        {"u_norm": 0.80, "v_norm": 0.50, "team": "HOME", "slot_hint": "ST", "velocity_mps": 5.5},
    ]

    ball_track = BallTrack(
        video_id=video_id,
        frame_index=100,
        timestamp_sec=1.66,
        pitch_xy_meters=[49.0, 29.5],
        in_flight=False,
    )

    fused = service.fuse_frame_telemetry(
        video_id=video_id,
        frame_index=100,
        timestamp_sec=1.66,
        broadcast_tracks=cam_tracks,
        radar_points=radar_points,
        ball_track=ball_track,
    )

    assert fused.video_id == video_id
    assert len(fused.home_players) == 2
    # First player was fused
    p1 = next(p for p in fused.home_players if p.player_slot == "CM")
    assert not p1.is_offscreen
    assert p1.source_confidence == 0.95

    # Second player discovered from radar
    p2 = next(p for p in fused.home_players if p.player_slot == "ST")
    assert p2.is_offscreen
    assert p2.pitch_x == 84.0
    assert p2.source_confidence == 0.75

    # Team shape metrics computed
    assert fused.home_shape is not None
    assert fused.ball_position == (49.0, 29.5)
