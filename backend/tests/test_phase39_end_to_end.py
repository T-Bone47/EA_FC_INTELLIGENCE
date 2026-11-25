"""Comprehensive End-to-End Test Suite for Phase 39:
Real Video Frame Decoding, Spatial Intelligence, Tactical Coaching,
PlayStyle Signatures & Squad Lab Integration.
"""
from __future__ import annotations

import math
import tempfile
from pathlib import Path
from typing import List
from uuid import uuid4

import av
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.domain.video_ingestion import (
    DataProvenance,
    FusedFrameTelemetry,
    PitchCalibrationState,
    ProcessingProfile,
    SceneClass,
)
from backend.services.playstyle_intelligence import PlayStyleEpistemicState, SUPPORTED_PLAYSTYLES
from backend.services.real_video_decoder import RealVideoDecodeError, probe_video_container
from backend.services.spatial_intelligence import SpatialIntelligenceEngine, SpatialModelMode, UncertaintyBand
from backend.services.squad_coaching_bridge import CausalCategory
from backend.services.tactical_coaching_engine import DiagnosticCode, TacticalCoachingEngine


def _render_synthetic_pitch_clip(path: Path, codec: str = "mpeg4", width: int = 960, height: int = 540, frames: int = 36, fps: int = 12) -> Path:
    """Encodes a real compressed binary MP4/MOV/WebM bitstream via PyAV with scaled pitch markings,
    10 moving players (red HOME vs blue AWAY kits), white ball, HUD banner, and bottom-center minimap.
    Used strictly to validate container decoding & pixel extraction pipelines."""
    ext = path.suffix.lower()
    sx = width / 960.0
    sy = height / 540.0
    with av.open(str(path), mode="w") as container:
        v_codec = "libvpx" if ext == ".webm" else codec
        stream = container.add_stream(v_codec, rate=fps)
        stream.width = width
        stream.height = height
        stream.pix_fmt = "yuv420p"

        for i in range(frames):
            img = np.zeros((height, width, 3), dtype=np.uint8)
            img[:, :] = (46, 144, 62)

            # White touchlines & halfway & 18-yard lines scaled cleanly
            cv2.line(img, (int(80 * sx), int(120 * sy)), (int(880 * sx), int(120 * sy)), (242, 242, 242), 3)
            cv2.line(img, (int(30 * sx), int(470 * sy)), (int(930 * sx), int(470 * sy)), (242, 242, 242), 3)
            cv2.line(img, (int(120 * sx), int(120 * sy)), (int(70 * sx), int(470 * sy)), (242, 242, 242), 3)
            cv2.line(img, (int(480 * sx), int(120 * sy)), (int(480 * sx), int(470 * sy)), (242, 242, 242), 3)
            cv2.line(img, (int(840 * sx), int(120 * sy)), (int(890 * sx), int(470 * sy)), (242, 242, 242), 3)

            # Top-left HUD dark banner + bright digits
            img[int(18 * sy):int(54 * sy), int(24 * sx):int(190 * sx)] = (18, 24, 32)
            img[int(28 * sy):int(44 * sy), int(42 * sx):int(110 * sx)] = (240, 245, 250)

            # Bottom-center minimap dark box + crisp dots inside [0.85H..0.98H, 0.38W..0.62W]
            mx1, my1, mx2, my2 = int(365 * sx), int(456 * sy), int(595 * sx), int(524 * sy)
            img[my1 - 4:my2 + 4, mx1 - 5:mx2 + 5] = (20, 38, 28)
            cv2.rectangle(img, (mx1, my1), (mx2, my2), (200, 220, 200), 1)

            shift = int(math.sin(i * 0.25) * 28 * sx)
            home_positions = [
                (int(240 * sx) + shift, int(240 * sy)), (int(300 * sx) + shift, int(310 * sy)),
                (int(350 * sx) + shift, int(210 * sy)), (int(430 * sx) + shift, int(290 * sy)),
                (int(520 * sx) + shift, int(260 * sy)),
            ]
            away_positions = [
                (int(490 * sx) - shift, int(200 * sy)), (int(540 * sx) - shift, int(330 * sy)),
                (int(610 * sx) - shift, int(230 * sy)), (int(680 * sx) - shift, int(290 * sy)),
                (int(740 * sx) - shift, int(250 * sy)),
            ]

            pw, ph = max(6, int(10 * sx)), max(12, int(24 * sy))
            mw, mh = max(1, mx2 - mx1), max(1, my2 - my1)
            for px, py in home_positions:
                cv2.rectangle(img, (px - pw, py - ph), (px + pw, py + ph), (215, 45, 45), -1)
                cv2.circle(img, (mx1 + int((px / width) * mw), my1 + int((py / height) * mh)), 3, (230, 40, 40), -1)

            for px, py in away_positions:
                cv2.rectangle(img, (px - pw, py - ph), (px + pw, py + ph), (45, 95, 220), -1)
                cv2.circle(img, (mx1 + int((px / width) * mw), my1 + int((py / height) * mh)), 3, (50, 120, 245), -1)

            bx, by = home_positions[-1][0] + pw + 4, home_positions[-1][1] + ph - 4
            cv2.circle(img, (bx, by), max(4, int(5 * sx)), (255, 255, 255), -1)

            frame = av.VideoFrame.from_ndarray(img, format="rgb24")
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return path


@pytest.fixture
def client():
    return TestClient(create_app())


def test_real_mp4_mov_decode_and_streaming_pipeline(client):
    """Stage 2 & 9: Genuine MP4 upload -> PyAV decode -> Pixel CV -> Track -> Fuse -> Spatial -> Coaching -> Squad Lab."""
    with tempfile.TemporaryDirectory() as tmpdir:
        clip_path = _render_synthetic_pitch_clip(Path(tmpdir) / f"fc27_real_clip_{uuid4().hex[:6]}.mp4")
        meta = probe_video_container(clip_path)
        assert meta["resolution_width"] == 960
        assert meta["resolution_height"] == 540
        assert meta["duration_seconds"] >= 2.5
        assert "PyAV/" in meta["decoder_backend"]

        raw_bytes = clip_path.read_bytes()
        up = client.post(
            "/api/research/ingest/upload",
            files={"file": (clip_path.name, raw_bytes, "video/mp4")},
            data={"game_version": "FC27", "match_mode": "COMPETITIVE_RIVALS", "profile": "HIGH_ACCURACY"},
        )
        assert up.status_code == 200
        job = up.json()
        vid = job["video_id"]
        job_id = job["job_id"]

        # Verify Range-request media endpoint streams bytes cleanly (HTTP 206)
        media_res = client.get(f"/api/research/videos/{vid}/media", headers={"Range": "bytes=0-1023"})
        assert media_res.status_code == 206
        assert len(media_res.content) == 1024

        # Apply optional manual calibration fallback first or let auto line extractor calibrate
        start_res = client.post(f"/api/research/ingest/jobs/{job_id}/start")
        assert start_res.status_code == 200
        payload = start_res.json()
        assert payload["status"] == "COMPLETED"
        assert payload["provenance"] == DataProvenance.REAL_VIDEO_DECODED.value
        assert payload["frames_analyzed"] >= 8
        assert "OpenCV" in payload["summary"]["detector_backend"] or "CV_CLASSICAL" in payload["summary"]["detector_backend"]

        # Fetch genuine fused telemetry without synthetic fallback
        tel_res = client.get(f"/api/research/fused-telemetry/{vid}?allow_synthetic_fixture=false")
        assert tel_res.status_code == 200
        tel_data = tel_res.json()
        assert tel_data["provenance"] == DataProvenance.REAL_VIDEO_DECODED.value
        assert tel_data["evidence_warning"] is None
        assert len(tel_data["frames"]) >= 8

        # Run Stage 3 Spatial Intelligence
        sp_res = client.get(f"/api/research/spatial-intelligence/{vid}?allow_synthetic_fixture=false")
        assert sp_res.status_code == 200
        sp_data = sp_res.json()
        assert sp_data["summary"]["analyzed_frames"] >= 8
        assert sp_data["summary"]["calibrated_empirically"] is False

        # Run Stage 4 Coaching, Stage 5 PlayStyles, and Stage 7 Squad Bridge
        diag_res = client.get(f"/api/research/coaching-diagnostics/{vid}?allow_synthetic_fixture=false")
        assert diag_res.status_code == 200
        ps_res = client.get(f"/api/research/playstyle-signatures/{vid}?allow_synthetic_fixture=false")
        assert ps_res.status_code == 200
        assert len(ps_res.json()["playstyles"]) == 10
        for p in ps_res.json()["playstyles"]:
            assert p["epistemic_state"] in {s.value for s in PlayStyleEpistemicState}
            if p["epistemic_state"] != PlayStyleEpistemicState.EXPLICIT_HUD_OBSERVED.value:
                assert p["activation_claim_permitted"] is False

        sq_res = client.get(f"/api/research/squad-coaching-plan/{vid}?allow_synthetic_fixture=false")
        assert sq_res.status_code == 200
        assert sq_res.json()["frozen_v321_untouched"] is True


def test_real_mov_and_corrupt_rejection():
    """Tests MOV container probing + corrupt bitstream raises explicit RealVideoDecodeError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mov_path = _render_synthetic_pitch_clip(Path(tmpdir) / "clip.mov", codec="mpeg4", width=640, height=360, frames=12, fps=12)
        meta = probe_video_container(mov_path)
        assert meta["resolution_width"] == 640

        bad_path = Path(tmpdir) / "corrupt.mp4"
        bad_path.write_bytes(b"NOT_A_REAL_VIDEO" * 200)
        with pytest.raises(RealVideoDecodeError):
            probe_video_container(bad_path)


def test_manual_calibration_fallback_and_imported_trace_coaching(client):
    """Tests manual 4-point homography calibration + imported tracking trace -> coaching & Squad Lab."""
    # Manual 4-point calibration endpoint
    cal_res = client.post("/api/research/calibration/TRACE-MANUAL-TEST", json={
        "frame_width": 1920,
        "frame_height": 1080,
        "landmarks": [
            {"name": "TOP_LEFT", "pixel_xy": [240.0, 320.0], "pitch_xy_meters": [0.0, 68.0]},
            {"name": "TOP_RIGHT", "pixel_xy": [1680.0, 320.0], "pitch_xy_meters": [105.0, 68.0]},
            {"name": "BOT_RIGHT", "pixel_xy": [1900.0, 960.0], "pitch_xy_meters": [105.0, 0.0]},
            {"name": "BOT_LEFT", "pixel_xy": [20.0, 960.0], "pitch_xy_meters": [0.0, 0.0]},
        ],
    })
    assert cal_res.status_code == 200
    assert cal_res.json()["calibration"]["reprojection_error_m"] < 1.0

    # Import realistic match trace exhibiting CB displacement, wide block, isolated striker, counter risk
    trace_frames = []
    for i in range(6):
        t = round(i * 0.2, 2)
        # Alternate away possession (defending poorly) vs home isolated build-up
        in_home_poss = i >= 3
        players = [
            {"track_id": "h_gk", "team": "HOME", "x_norm": 0.05, "y_norm": 0.50, "player_slot": "GK", "is_goalkeeper": True},
            # CB #1 dragged way out (+12m gap vs RCB)
            {"track_id": "h_lcb", "team": "HOME", "x_norm": 0.34, "y_norm": 0.86, "player_slot": "LCB"},
            {"track_id": "h_rcb", "team": "HOME", "x_norm": 0.20, "y_norm": 0.14, "player_slot": "RCB"},
            # LB/RB pushed high leaving Central Spine [27.2..40.8] open and <3 rest defense
            {"track_id": "h_lb", "team": "HOME", "x_norm": 0.56, "y_norm": 0.90, "player_slot": "LB"},
            {"track_id": "h_rb", "team": "HOME", "x_norm": 0.58, "y_norm": 0.10, "player_slot": "RB"},
            {"track_id": "h_cm1", "team": "HOME", "x_norm": 0.55, "y_norm": 0.45, "player_slot": "LCM"},
            {"track_id": "h_cm2", "team": "HOME", "x_norm": 0.56, "y_norm": 0.46, "player_slot": "RCM"},
            # Striker isolated > 25m upfield
            {"track_id": "h_st", "team": "HOME", "x_norm": 0.85, "y_norm": 0.50, "player_slot": "ST"},
            # Opponent AWAY attackers
            {"track_id": "a_st", "team": "AWAY", "x_norm": 0.45, "y_norm": 0.50, "player_slot": "ST"},
            {"track_id": "a_lw", "team": "AWAY", "x_norm": 0.50, "y_norm": 0.20, "player_slot": "LW"},
            {"track_id": "a_rw", "team": "AWAY", "x_norm": 0.50, "y_norm": 0.80, "player_slot": "RW"},
            {"track_id": "a_cm", "team": "AWAY", "x_norm": 0.62, "y_norm": 0.50, "player_slot": "CM"},
            {"track_id": "a_cb1", "team": "AWAY", "x_norm": 0.80, "y_norm": 0.60, "player_slot": "CB"},
            {"track_id": "a_cb2", "team": "AWAY", "x_norm": 0.80, "y_norm": 0.40, "player_slot": "CB"},
        ]
        trace_frames.append({
            "frame_index": i * 12,
            "timestamp_sec": t,
            "match_clock": f"00:0{i}",
            "ball_x_norm": 0.55 if in_home_poss else 0.45,
            "ball_y_norm": 0.45 if in_home_poss else 0.50,
            "players": players,
        })

    imp = client.post("/api/research/traces/import", json={"title": "Metrica Diagnostic Trace", "frames": trace_frames})
    assert imp.status_code == 200
    vid = imp.json()["video_id"]
    assert imp.json()["provenance"] == DataProvenance.IMPORTED_MATCH_TRACE.value

    diag = client.get(f"/api/research/coaching-diagnostics/{vid}?allow_synthetic_fixture=false")
    assert diag.status_code == 200
    diags = diag.json()["diagnostics"]
    codes = {d["code"] for d in diags}
    assert DiagnosticCode.POOR_DEFENSIVE_COMPACTNESS.value in codes
    assert DiagnosticCode.EXPOSED_CENTRAL_CHANNEL.value in codes
    assert DiagnosticCode.UNNECESSARY_CB_DISPLACEMENT.value in codes
    assert DiagnosticCode.ISOLATED_STRIKER.value in codes

    # Every diagnostic must include all 7 required pedagogical elements
    for d in diags:
        assert d["what_happened"]
        assert d["why_it_potentially_happened"]
        assert len(d["supporting_timestamps"]) >= 1
        assert isinstance(d["tactical_visualization"], dict)
        assert d["confidence_level"] in ("HIGH", "MODERATE", "LOW")
        assert len(d["alternative_decisions"]) >= 1
        assert d["actionable_advice"]

    # Verify Squad Coaching Integration prioritizes tactical fixes over purchases
    plan_res = client.get(f"/api/research/squad-coaching-plan/{vid}?allow_synthetic_fixture=false")
    assert plan_res.status_code == 200
    plan = plan_res.json()
    assert plan["status"] == "EVIDENCE_GROUNDED_PLAN"
    assert plan["frozen_v321_untouched"] is True
    assert len(plan["capability_profiles"]) >= 1
    assert all(not a["purchase_recommended"] for a in plan["attributions"])


def test_synthetic_fixture_gated_from_squad_purchases(client):
    """Stage 1 & 7 Guard: SYNTHETIC_FIXTURE cannot trigger canonical card upgrade recommendations."""
    res = client.get("/api/research/squad-coaching-plan/VID-012?allow_synthetic_fixture=true")
    assert res.status_code == 200
    data = res.json()
    assert data["frozen_v321_untouched"] is True
    for attr in data.get("attributions", []):
        assert attr["provenance_gated"] is True
        assert attr["capability_profile"] is None


def test_spatial_engine_withholds_control_when_calibration_rejected():
    """Stage 3 Guard: Calibration REJECTED must set UNRELIABLE & INSUFFICIENT_OBSERVATION."""
    frame = FusedFrameTelemetry(
        video_id="vid_bad",
        frame_index=1,
        timestamp_sec=0.1,
        calibration_state=PitchCalibrationState.REJECTED,
        reprojection_error_m=99.0,
        players=[],
        scene_class=SceneClass.ACTIVE_GAMEPLAY,
        provenance=DataProvenance.REAL_VIDEO_DECODED,
    )
    res = SpatialIntelligenceEngine().analyze_timeline([frame])
    assert res["frames"][0]["uncertainty_band"] == UncertaintyBand.UNRELIABLE.value
    assert res["frames"][0]["model_mode"] == SpatialModelMode.INSUFFICIENT_OBSERVATION.value
    assert res["frames"][0]["home_pitch_control_pct"] is None


def test_system_capabilities_endpoint(client):
    """Confirms honest hardware, decoder, and ONNX weight availability reporting."""
    res = client.get("/api/research/system-capabilities")
    assert res.status_code == 200
    data = res.json()
    assert "PyAV" in data["decoder"]
    assert data["frozen_v321_engine_untouched"] is True
    assert "compute_device" in data
