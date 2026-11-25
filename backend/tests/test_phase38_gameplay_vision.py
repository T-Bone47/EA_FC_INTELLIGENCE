"""Comprehensive Automated Test Suite for Phase 38 Gameplay Vision & Ingestion Foundation."""
import io
import os
import struct
import tempfile
from pathlib import Path
from typing import Dict, List
from uuid import uuid4
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.domain.video_ingestion import (
    FileMetadata,
    JobStatus,
    ObservationStatus,
    PitchCalibrationState,
    ProcessingProfile,
    ReviewVerdict,
    SceneClass,
)
from backend.services.bytetrack_adapter import ByteTrackAdapter, calculate_iou
from backend.services.gameplay_perception_engine import GameplayPerceptionEngine
from backend.services.homography_dlt import PitchHomographyEstimator
from backend.services.multi_channel_perception import HeuristicPerceptionDetector
from backend.services.multi_source_fusion import MultiSourceFusionService
from backend.services.scene_classifier import SceneClassifier
from backend.services.video_ingestion_service import VideoIngestionError, VideoIngestionService


@pytest.fixture
def test_client():
    app = create_app()
    return TestClient(app)


# -----------------------------------------------------------------------------
# 1. Video Ingestion & Atom Parser Tests (Phase 38B)
# -----------------------------------------------------------------------------
def test_mp4_atom_box_parser():
    """Verifies pure-Python MP4 atom box parsing extracts duration, timescale and resolution."""
    # Build synthetic in-memory MP4 with moov -> mvhd and moov -> trak -> tkhd
    buf = io.BytesIO()

    # 1. ftyp box
    ftyp_data = b"isom\x00\x00\x02\x00isomiso2mp41"
    buf.write(struct.pack(">I4s", len(ftyp_data) + 8, b"ftyp") + ftyp_data)

    # 2. mvhd box (timescale=600, duration=18000 -> 30.0 sec)
    mvhd_payload = b"\x00" * 12 + struct.pack(">II", 600, 18000) + b"\x00" * 80
    mvhd_box = struct.pack(">I4s", len(mvhd_payload) + 8, b"mvhd") + mvhd_payload

    # 3. tkhd box (width=1920, height=1080 in 16.16 fixed point)
    w_fixed = 1920 << 16
    h_fixed = 1080 << 16
    tkhd_payload = b"\x00" * 68 + struct.pack(">II", w_fixed, h_fixed)
    tkhd_box = struct.pack(">I4s", len(tkhd_payload) + 8, b"tkhd") + tkhd_payload

    # trak box containing tkhd
    trak_box = struct.pack(">I4s", len(tkhd_box) + 8, b"trak") + tkhd_box

    # moov box containing mvhd and trak
    moov_payload = mvhd_box + trak_box
    buf.write(struct.pack(">I4s", len(moov_payload) + 8, b"moov") + moov_payload)

    buf.seek(0)
    service = VideoIngestionService()
    meta = service.parse_mp4_atoms(buf)

    assert meta["duration_seconds"] == 30.0
    assert meta["timescale"] == 600
    assert meta["resolution_width"] == 1920
    assert meta["resolution_height"] == 1080


def test_video_ingestion_file_validation():
    """Tests file inspection, size validation, SHA-256 calculation, and duplicate handling."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = Path(tmpdir) / "uploads"
        jobs = Path(tmpdir) / "jobs"
        service = VideoIngestionService(storage_dir=storage, jobs_dir=jobs)

        # Create dummy mp4 file
        dummy_file = Path(tmpdir) / "test_match.mp4"
        dummy_file.write_bytes(b"\x00" * 2048)  # 2 KB

        job = service.create_ingestion_job(dummy_file, "test_match.mp4")
        assert job.status == JobStatus.QUEUED
        assert job.file_metadata.format == "mp4"
        assert len(job.file_metadata.sha256) == 64

        # Duplicate submission with same file returns existing job
        job2 = service.create_ingestion_job(dummy_file, "test_match.mp4")
        assert job2.job_id == job.job_id

        # Cancel job
        assert service.cancel_job(job.job_id) is True
        assert service.get_job(job.job_id).status == JobStatus.CANCELLED


# -----------------------------------------------------------------------------
# 2. Scene Classification Tests (Phase 38C)
# -----------------------------------------------------------------------------
def test_scene_classifier_active_gameplay_vs_replay():
    """Tests scene classification differentiates active gameplay (pitch + HUD) from replays."""
    classifier = SceneClassifier()

    # Active gameplay frame: predominantly green pitch with HUD scoreboard and minimap
    gameplay_rgb = np.zeros((1080, 1920, 3), dtype=np.uint8)
    gameplay_rgb[:, :] = [45, 140, 55]  # Green pitch
    gameplay_rgb[20:80, 40:300] = [20, 20, 20]  # Scoreboard dark banner
    gameplay_rgb[30:50, 60:120] = [240, 240, 240]  # Scoreboard white text
    gameplay_rgb[920:1040, 780:1140] = [30, 80, 40]  # Minimap
    gameplay_rgb[950:970, 850:900] = [255, 255, 255]  # Minimap dots

    res = classifier.classify_frame(gameplay_rgb, frame_index=0, timestamp_sec=0.0)
    assert res.scene_class == SceneClass.ACTIVE_GAMEPLAY
    assert res.confidence >= 0.90
    assert res.hud_visible is True
    assert res.minimap_visible is True

    # Goal replay frame: green pitch, but NO HUD scoreboard or minimap
    replay_rgb = np.zeros((1080, 1920, 3), dtype=np.uint8)
    replay_rgb[:, :] = [45, 140, 55]  # Green pitch only

    res_replay = classifier.classify_frame(replay_rgb, frame_index=60, timestamp_sec=1.0)
    assert res_replay.scene_class == SceneClass.GOAL_REPLAY
    assert res_replay.hud_visible is False


def test_scene_classifier_camera_cut_detection():
    """Verifies Bhattacharyya histogram distance detects camera cuts."""
    classifier = SceneClassifier(cut_distance_threshold=0.50)

    # Frame 1: Bright green
    f1 = np.full((100, 100, 3), [40, 150, 50], dtype=np.uint8)
    res1 = classifier.classify_frame(f1, frame_index=0)
    assert res1.is_camera_cut is False

    # Frame 2: Radical cut to dark stadium tunnel (black/grey)
    f2 = np.full((100, 100, 3), [15, 15, 20], dtype=np.uint8)
    res2 = classifier.classify_frame(f2, frame_index=30)
    assert res2.is_camera_cut is True


# -----------------------------------------------------------------------------
# 3. Direct Linear Transformation & Homography Tests (Phase 38F)
# -----------------------------------------------------------------------------
def test_homography_dlt_svd_projection():
    """Verifies DLT with SVD maps screen pixels to canonical pitch coordinates."""
    estimator = PitchHomographyEstimator()

    # Exact synthetic quadrilateral mapping
    src = np.array([
        [0.0, 0.0],
        [100.0, 0.0],
        [100.0, 100.0],
        [0.0, 100.0],
    ], dtype=np.float64)

    dst = np.array([
        [0.0, 0.0],
        [50.0, 0.0],
        [50.0, 30.0],
        [0.0, 30.0],
    ], dtype=np.float64)

    h = estimator.compute_dlt_homography(src, dst)
    assert h is not None

    # Project source points
    projected = estimator.project_points(h, src)
    assert projected is not None
    assert np.allclose(projected, dst, atol=1e-3)


def test_homography_ransac_and_quality_gates():
    """Tests RANSAC inlier filtering and reprojection quality states."""
    estimator = PitchHomographyEstimator(inlier_threshold_m=2.0)

    src = np.array([
        [100.0, 100.0], [500.0, 100.0], [500.0, 500.0], [100.0, 500.0],
        [300.0, 100.0], [300.0, 500.0],
    ], dtype=np.float64)

    dst = np.array([
        [10.0, 10.0], [60.0, 10.0], [60.0, 40.0], [10.0, 40.0],
        [35.0, 10.0], [35.0, 40.0],
    ], dtype=np.float64)

    res = estimator.estimate_homography_ransac(src, dst)
    assert res.state == PitchCalibrationState.GOOD
    assert res.reprojection_error_m < 2.0
    assert res.inliers_count == 6


# -----------------------------------------------------------------------------
# 4. ByteTrack Multi-Object Tracking Tests (Phase 38E)
# -----------------------------------------------------------------------------
def test_bytetrack_association_and_persistence():
    """Verifies two-stage ByteTrack maintains persistent track IDs across frames."""
    tracker = ByteTrackAdapter(high_conf_thresh=0.5, low_conf_thresh=0.2)

    # Frame 1: Detection at (0.2, 0.3)
    f1_dets = [
        {"bbox_xywh": [0.20, 0.30, 0.04, 0.08], "confidence": 0.90, "team": "HOME", "entity_class": "outfield_player"}
    ]
    t1 = tracker.update(f1_dets)
    assert len(t1) == 1
    tid = t1[0]["track_id"]
    assert "home" in tid

    # Frame 2: Minor translation (0.21, 0.30) - track should persist with identical ID
    f2_dets = [
        {"bbox_xywh": [0.21, 0.30, 0.04, 0.08], "confidence": 0.85, "team": "HOME", "entity_class": "outfield_player"}
    ]
    t2 = tracker.update(f2_dets)
    assert len(t2) == 1
    assert t2[0]["track_id"] == tid

    # Frame 3: Low-confidence detection (0.22, 0.30, conf=0.35) - recovered in second stage!
    f3_dets = [
        {"bbox_xywh": [0.22, 0.30, 0.04, 0.08], "confidence": 0.35, "team": "HOME", "entity_class": "outfield_player"}
    ]
    t3 = tracker.update(f3_dets)
    assert len(t3) == 1
    assert t3[0]["track_id"] == tid


# -----------------------------------------------------------------------------
# 5. Multi-Source Fusion & Gameplay Engine Tests (Phase 38G/H)
# -----------------------------------------------------------------------------
def test_multi_source_fusion_and_possession():
    """Verifies fusion assigns status OBSERVED, calculates hull area, and tracks possession."""
    fusion = MultiSourceFusionService()

    tracks = [
        {
            "track_id": "trk_home_01",
            "team": "HOME",
            "entity_class": "outfield_player",
            "bbox_xywh": [0.45, 0.50, 0.04, 0.08],
            "confidence": 0.95,
        },
        {
            "track_id": "trk_home_02",
            "team": "HOME",
            "entity_class": "outfield_player",
            "bbox_xywh": [0.40, 0.40, 0.04, 0.08],
            "confidence": 0.92,
        },
        {
            "track_id": "trk_home_03",
            "team": "HOME",
            "entity_class": "outfield_player",
            "bbox_xywh": [0.50, 0.60, 0.04, 0.08],
            "confidence": 0.91,
        },
    ]

    engine = GameplayPerceptionEngine()
    h_matrix = engine.generate_canonical_homography()

    from backend.domain.video_ingestion import DetectedEntity, HUDContext
    ball = DetectedEntity(
        entity_class="ball",
        team="BALL",
        bbox_xywh=[0.465, 0.57, 0.01, 0.01],
        confidence=0.90,
    )
    hud = HUDContext(match_clock="12:30")

    telemetry = fusion.fuse_frame(
        video_id="vid_test",
        frame_index=10,
        timestamp_sec=1.0,
        tracks=tracks,
        ball_entity=ball,
        minimap_obs=[],
        hud_ctx=hud,
        homography_matrix=h_matrix,
        calibration_state=PitchCalibrationState.GOOD,
        reprojection_error_m=0.85,
    )

    assert telemetry.calibration_state == PitchCalibrationState.GOOD
    assert telemetry.possession_team == "HOME"
    assert telemetry.ball_carrier_track_id == "trk_home_01"
    assert telemetry.team_metrics["home_width_m"] > 0.0
    assert len(telemetry.players) == 3
    assert telemetry.players[0]["status"] == ObservationStatus.OBSERVED.value


def test_gameplay_perception_engine_end_to_end():
    """Runs full pipeline over synthetic match recording, verifying events and summary."""
    engine = GameplayPerceptionEngine()
    telemetry, events, summary = engine.process_match_recording(
        video_id="vid_eval_test",
        duration_seconds=5.0,
        profile=ProcessingProfile.FAST,
    )

    assert len(telemetry) == 10  # 5 sec at 2 Hz
    assert summary["video_id"] == "vid_eval_test"
    assert summary["tracking_coverage_pct"] > 90.0
    assert "passes_completed" in summary
    assert "turnovers_detected" in summary


# -----------------------------------------------------------------------------
# 6. REST API Endpoints & Evidence Review Tests (Phase 38B/I)
# -----------------------------------------------------------------------------
def test_api_video_ingestion_lifecycle(test_client):
    """Tests video upload, job listing, and fixture vs real failure boundaries through REST API."""
    # 1. Upload un-decodable dummy payload: must FAIL real decode (422), succeeding ONLY with explicit allow_synthetic_fixture=true
    file_content = b"\x00" * 4096 + str(uuid4()).encode()
    response = test_client.post(
        "/api/research/ingest/upload",
        files={"file": ("match_clip.mp4", file_content, "video/mp4")},
        data={"game_version": "FC27", "match_mode": "COMPETITIVE_RIVALS", "profile": "FAST"},
    )
    assert response.status_code == 200
    job = response.json()
    job_id = job["job_id"]
    assert job["status"] == "QUEUED"

    # 2. List jobs
    list_res = test_client.get("/api/research/ingest/jobs")
    assert list_res.status_code == 200
    assert any(j["job_id"] == job_id for j in list_res.json())

    # 3a. Real decoding on empty garbage bytes must fail honestly (422)
    fail_res = test_client.post(f"/api/research/ingest/jobs/{job_id}/start")
    assert fail_res.status_code == 422

    # 3b. Explicit synthetic fixture opt-in must stamp SYNTHETIC_FIXTURE provenance
    start_res = test_client.post(f"/api/research/ingest/jobs/{job_id}/start?allow_synthetic_fixture=true")
    assert start_res.status_code == 200
    start_data = start_res.json()
    assert start_data["status"] == "COMPLETED"
    assert start_data["provenance"] == "SYNTHETIC_FIXTURE"
    assert start_data["frames_analyzed"] > 0

    # 4. Retrieve match perception summary
    vid = job["video_id"]
    summary_res = test_client.get(f"/api/research/match-summary/{vid}")
    assert summary_res.status_code == 200
    assert summary_res.json()["tracking_coverage_pct"] >= 90.0


def test_api_manual_evidence_review(test_client):
    """Verifies manual evidence review submissions create audited records with SHA-256 seal."""
    review_payload = {
        "video_id": "vid_review_01",
        "target_id": "trk_home_05",
        "reviewer_id": "chief_tactical_analyst",
        "change_type": "TEAM_CORRECTION",
        "original_value": {"team": "AWAY"},
        "corrected_value": {"team": "HOME"},
        "review_verdict": "ACCEPTED",
        "reason": "Away wore red shorts; corrected to Home based on jersey crest.",
    }

    sub_res = test_client.post("/api/research/review", json=review_payload)
    assert sub_res.status_code == 200
    rec = sub_res.json()
    assert rec["review_verdict"] == "ACCEPTED"
    assert len(rec["audit_hash"]) == 64

    # List reviews for video
    list_res = test_client.get("/api/research/review/vid_review_01")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1
    assert list_res.json()[0]["audit_hash"] == rec["audit_hash"]
