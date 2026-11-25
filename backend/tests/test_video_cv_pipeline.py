"""Unit tests for Video Computer Vision Pipeline Service (Phase 36)."""
import pytest
from backend.domain.video_gameplay import (
    BallTrack,
    EvidenceTier,
    PlayerTrack,
    RightsStatus,
    TacticalEvent,
)
from backend.services.video_cv_pipeline import (
    ComputerVisionPipelineError,
    VideoComputerVisionService,
)


def test_cv_pipeline_enforces_youtube_rights_barrier():
    service = VideoComputerVisionService()

    # YouTube URL must raise error
    with pytest.raises(ComputerVisionPipelineError) as exc_info:
        service.validate_rights_for_cv(
            RightsStatus.PUBLIC_EMBED_ONLY,
            "https://www.youtube.com/watch?v=ivshwl8WrJA"
        )
    assert "restricted to Path A" in str(exc_info.value)

    # Even if someone claims PROJECT_OWNED on a YouTube link, downloading is refused
    with pytest.raises(ComputerVisionPipelineError) as exc_info2:
        service.validate_rights_for_cv(
            RightsStatus.PROJECT_OWNED,
            "https://www.youtube.com/watch?v=some_vid"
        )
    assert "Direct frame extraction on YouTube streams is prohibited" in str(exc_info2.value)

    # Local authorized asset passes cleanly
    service.validate_rights_for_cv(
        RightsStatus.PROJECT_OWNED,
        "local://datasets/controlled_experiments/EXP_ST_PRESS_001.mp4"
    )


def test_homography_projection_bounds():
    service = VideoComputerVisionService()

    # Center of screen (960, 540) on 1920x1080 -> approximate center of pitch
    px, py, status = service.compute_homography_projection(960.0, 540.0)
    assert status == "CALIBRATED"
    assert px is not None and py is not None
    assert 50.0 <= px <= 55.0
    assert 32.0 <= py <= 36.0

    # Negative coordinates fail closed
    px_bad, py_bad, status_bad = service.compute_homography_projection(-10.0, 540.0)
    assert status_bad == "OUT_OF_BOUNDS"
    assert px_bad is None


def test_candidate_pressing_detection():
    service = VideoComputerVisionService()

    # Ball at (60m, 34m)
    ball = BallTrack(
        video_id="vid-test",
        frame_index=100,
        timestamp_sec=10.0,
        pitch_xy_meters=[60.0, 34.0],
        possessing_slot="CB"
    )

    # Away player at (62m, 35m) closing at 6.0 m/s (distance approx 2.23m)
    player = PlayerTrack(
        video_id="vid-test",
        frame_index=100,
        timestamp_sec=10.0,
        team="AWAY",
        player_slot="ST",
        pitch_xy_meters=[62.0, 35.0],
        velocity_mps=6.0
    )

    events = service.detect_candidate_pressing_events([player], [ball], press_distance_threshold_m=4.0)
    assert len(events) == 1
    assert events[0].event_type == "PRESS_ATTEMPT"
    assert events[0].formation_slot == "ST"
    assert events[0].integrity_hash is not None


def test_aggregate_gameplay_features():
    service = VideoComputerVisionService()

    events = [
        TacticalEvent(
            video_id="v1",
            timestamp_start=10.0,
            timestamp_end=12.0,
            event_type="TACKLE_WON",
            card_item_id="card-dembele",
            player_identity="Ousmane Dembélé",
            observed_action="Tackle won",
            observed_outcome="CLEAN_RECOVERY"
        ),
        TacticalEvent(
            video_id="v1",
            timestamp_start=25.0,
            timestamp_end=27.0,
            event_type="PRESS_ATTEMPT",
            card_item_id="card-dembele",
            player_identity="Ousmane Dembélé",
            observed_action="High intensity press",
            observed_outcome="TURNOVER_FORCED"
        )
    ]

    # Sample duration 45 minutes -> norm factor is 2.0
    fv = service.aggregate_gameplay_features(
        card_item_id="card-dembele",
        card_name="Ousmane Dembélé",
        tactical_context="HIGH_PRESS",
        events=events,
        sample_minutes=45.0,
        tier=EvidenceTier.TIER_A
    )

    assert fv.card_name == "Ousmane Dembélé"
    assert fv.tackles_per_90 == 2.0  # 1 * 2.0
    assert fv.turnovers_forced_per_90 == 2.0  # 1 * 2.0
    assert fv.evidence_tier == EvidenceTier.TIER_A
