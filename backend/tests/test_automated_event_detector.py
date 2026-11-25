"""Unit test suite for Automated Tactical Event Recognition Engine (Phase 37)."""
import pytest
from backend.domain.video_gameplay import (
    BallTrack,
    ObservationMethod,
    PlayerTrack,
    ReviewStatus,
)
from backend.services.automated_event_detector import (
    AutomatedEventDetector,
    map_pitch_coordinates_to_zone,
)


def test_map_pitch_coordinates_to_zone():
    # Left Back defending (Zone 3: Left Back)
    assert map_pitch_coordinates_to_zone(5.0, 62.0) == 3
    # Pitch center (Zone 8: Center Mid)
    assert map_pitch_coordinates_to_zone(52.5, 34.0) == 8
    # Attacking box (Zone 7: Center Box)
    assert map_pitch_coordinates_to_zone(95.0, 34.0) == 7
    # Right Back defending (Zone 15: Right Back)
    assert map_pitch_coordinates_to_zone(5.0, 5.0) == 15
    # Clamping bounds
    assert 1 <= map_pitch_coordinates_to_zone(-10.0, -5.0) <= 18
    assert 1 <= map_pitch_coordinates_to_zone(200.0, 100.0) <= 18


def test_detect_pressing_triggers():
    detector = AutomatedEventDetector()
    video_id = "test-vid-001"

    # Ball at (45.0, 30.0) at t=10.0
    ball_tracks = [
        BallTrack(video_id=video_id, frame_index=600, timestamp_sec=10.0, pitch_xy_meters=[45.0, 30.0])
    ]

    # Player sprinting toward ball carrier: dist = 2.0m, speed = 5.2 m/s
    player_tracks = [
        PlayerTrack(
            video_id=video_id,
            frame_index=600,
            timestamp_sec=10.0,
            player_slot="RW",
            team="AWAY",
            pitch_xy_meters=[46.5, 31.0],
            velocity_mps=5.2,
        )
    ]

    events = detector.detect_pressing_triggers(player_tracks, ball_tracks, video_id)
    assert len(events) == 1
    ev = events[0]
    assert ev.event_type == "PRESSING_TRIGGER"
    assert ev.observation_method == ObservationMethod.AUTOMATED_DETECTOR
    assert ev.review_status == ReviewStatus.UNDER_REVIEW
    assert ev.integrity_hash is not None
    assert len(ev.integrity_hash) == 64


def test_detect_defensive_line_shifts():
    detector = AutomatedEventDetector()
    video_id = "test-vid-001"

    # Back 4 at x=25m at t=1.0s, then stepping up to x=32m at t=2.2s (+7m shift)
    player_tracks = [
        PlayerTrack(video_id=video_id, frame_index=60, timestamp_sec=1.0, player_slot="LB", pitch_xy_meters=[25.0, 12.0]),
        PlayerTrack(video_id=video_id, frame_index=60, timestamp_sec=1.0, player_slot="LCB", pitch_xy_meters=[25.0, 26.0]),
        PlayerTrack(video_id=video_id, frame_index=60, timestamp_sec=1.0, player_slot="RCB", pitch_xy_meters=[25.0, 42.0]),
        PlayerTrack(video_id=video_id, frame_index=60, timestamp_sec=1.0, player_slot="RB", pitch_xy_meters=[25.0, 56.0]),
        PlayerTrack(video_id=video_id, frame_index=132, timestamp_sec=2.2, player_slot="LB", pitch_xy_meters=[32.0, 12.0]),
        PlayerTrack(video_id=video_id, frame_index=132, timestamp_sec=2.2, player_slot="LCB", pitch_xy_meters=[32.0, 26.0]),
        PlayerTrack(video_id=video_id, frame_index=132, timestamp_sec=2.2, player_slot="RCB", pitch_xy_meters=[32.0, 42.0]),
        PlayerTrack(video_id=video_id, frame_index=132, timestamp_sec=2.2, player_slot="RB", pitch_xy_meters=[32.0, 56.0]),
    ]

    events = detector.detect_defensive_line_shifts(player_tracks, video_id)
    assert len(events) == 1
    assert events[0].event_type == "DEFENSIVE_LINE_SHIFT"
    assert "PUSH_UP_STEP" in events[0].observed_outcome


def test_detect_transition_breaks():
    detector = AutomatedEventDetector()
    video_id = "test-vid-001"

    # Ball at x=30m at t=5.0s, surging to x=55m at t=8.0s (dx=25m, dt=3s, speed=8.3 m/s)
    ball_tracks = [
        BallTrack(video_id=video_id, frame_index=300, timestamp_sec=5.0, pitch_xy_meters=[30.0, 34.0]),
        BallTrack(video_id=video_id, frame_index=480, timestamp_sec=8.0, pitch_xy_meters=[55.0, 34.0]),
    ]

    events = detector.detect_transition_breaks([], ball_tracks, video_id)
    assert len(events) == 1
    assert events[0].event_type == "TRANSITION_BREAK"
    assert "TRANSITION_PENETRATION" in events[0].observed_outcome


def test_detect_overlapping_runs():
    detector = AutomatedEventDetector()
    video_id = "test-vid-001"

    # LB at x=65m, LW at x=60m along left flank at t=15.0s
    player_tracks = [
        PlayerTrack(video_id=video_id, frame_index=900, timestamp_sec=15.0, player_slot="LB", pitch_xy_meters=[65.0, 60.0]),
        PlayerTrack(video_id=video_id, frame_index=900, timestamp_sec=15.0, player_slot="LW", pitch_xy_meters=[60.0, 58.0]),
    ]

    events = detector.detect_overlapping_runs(player_tracks, video_id)
    assert len(events) == 1
    assert events[0].event_type == "OVERLAPPING_RUN"
    assert "FLANK_OVERLOAD_CREATED" in events[0].observed_outcome


def test_detect_line_break_passes():
    detector = AutomatedEventDetector()
    video_id = "test-vid-001"

    # Ball pass from x=35m to x=55m centrally (dx=20m, dt=1.0s)
    ball_tracks = [
        BallTrack(video_id=video_id, frame_index=600, timestamp_sec=10.0, pitch_xy_meters=[35.0, 34.0]),
        BallTrack(video_id=video_id, frame_index=660, timestamp_sec=11.0, pitch_xy_meters=[55.0, 34.0]),
    ]

    events = detector.detect_line_break_passes(ball_tracks, video_id)
    assert len(events) == 1
    assert events[0].event_type == "CENTRAL_LINE_BREAK_PASS"
    assert events[0].integrity_hash is not None
