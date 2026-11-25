"""Integrated Gameplay Vision & Perception Engine (Phase 38 -> Phase 39 Real Decoding).

Orchestrates genuine recorded gameplay analysis:
Real MP4/WebM/MOV Decoding (PyAV) -> Adaptive Sampling -> Scene Understanding ->
Camera Motion Compensation (LK Flow) -> Pitch Homography (Line Extraction / Manual Override) ->
Multi-Channel Pixel Perception -> ByteTrack (SciPy Hungarian) -> Multi-Source Evidence Fusion ->
Tactical Event Detection -> Summary Generation.

Synthetic simulation (`process_match_recording(..., allow_synthetic_fixture=True)`) is strictly
segregated and stamped `DataProvenance.SYNTHETIC_FIXTURE`.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import numpy as np

from backend.domain.video_gameplay import (
    ObservationMethod,
    ReviewStatus,
    TacticalEvent,
)
from backend.domain.video_ingestion import (
    DataProvenance,
    FusedFrameTelemetry,
    HomographyResult,
    JobStatus,
    PitchCalibrationState,
    ProcessingProfile,
    SceneClass,
    VideoIngestionJob,
)
from backend.services.bytetrack_adapter import ByteTrackAdapter
from backend.services.homography_dlt import PitchHomographyEstimator
from backend.services.multi_channel_perception import (
    PixelPerceptionExtractor,
    SyntheticFixtureDetector,
)
from backend.services.multi_source_fusion import MultiSourceFusionService
from backend.services.real_video_decoder import (
    RealVideoDecodeError,
    detect_compute_device,
    iter_adaptive_frames,
    probe_video_container,
)
from backend.services.scene_classifier import SceneClassifier

log = logging.getLogger("eafc.gameplay_perception")


class GameplayPerceptionEngine:
    """End-to-end perception pipeline for recorded match gameplay footage."""

    def __init__(
        self,
        pitch_length_m: float = 105.0,
        pitch_width_m: float = 68.0,
    ):
        self.pitch_length = pitch_length_m
        self.pitch_width = pitch_width_m
        self.scene_classifier = SceneClassifier()
        self.pixel_detector = PixelPerceptionExtractor(pitch_length_m, pitch_width_m)
        self.synthetic_detector = SyntheticFixtureDetector(pitch_length_m, pitch_width_m)
        self.tracker = ByteTrackAdapter()
        self.homography = PitchHomographyEstimator(pitch_length_m, pitch_width_m)
        self.fusion = MultiSourceFusionService(pitch_length_m, pitch_width_m)

    def generate_canonical_homography(self) -> List[List[float]]:
        """Standard Tele Broadcast canonical 1080p homography matrix used for synthetic fixtures."""
        src = np.array([
            [240.0, 320.0],
            [1680.0, 320.0],
            [1900.0, 960.0],
            [20.0, 960.0],
            [960.0, 320.0],
            [960.0, 960.0],
        ], dtype=np.float64)
        dst = np.array([
            [0.0, 68.0],
            [105.0, 68.0],
            [105.0, 0.0],
            [0.0, 0.0],
            [52.5, 68.0],
            [52.5, 0.0],
        ], dtype=np.float64)
        res = self.homography.estimate_homography_ransac(src, dst)
        return res.matrix_3x3

    def process_video_file(
        self,
        video_id: str,
        file_path: Path,
        profile: ProcessingProfile = ProcessingProfile.BALANCED,
        job: Optional[VideoIngestionJob] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
        manual_homography: Optional[HomographyResult] = None,
        max_seconds: float = 120.0,
    ) -> Tuple[List[FusedFrameTelemetry], List[TacticalEvent], Dict[str, Any]]:
        """Executes genuine video frame decoding and multi-channel CV perception."""
        self.scene_classifier.reset()
        self.tracker.reset()

        device_info = detect_compute_device()
        container_meta = probe_video_container(file_path)
        if job:
            job.provenance = DataProvenance.REAL_VIDEO_DECODED
            job.decoder_backend = container_meta.get("decoder_backend")
            job.detector_backend = self.pixel_detector.backend_name
            job.compute_device = f"{device_info['backend']}: {device_info['device_name']}"

        fused_telemetry: List[FusedFrameTelemetry] = []
        events: List[TacticalEvent] = []

        sampled_count = 0
        active_frames = 0
        excluded_scenes = 0
        cal_good = 0
        cal_coarse = 0
        cal_rejected = 0
        corrupt_skipped = 0

        possession_history: List[str] = []
        passes_count = 0
        turnovers_count = 0
        prev_possession = "UNKNOWN"
        prev_carrier_id: Optional[str] = None
        prev_rgb: Optional[np.ndarray] = None
        last_valid_homography: Optional[HomographyResult] = manual_homography
        frames_since_cal = 0

        def _on_progress(pct: float) -> None:
            if job:
                job.update_progress(pct)

        for sample in iter_adaptive_frames(
            file_path=file_path,
            profile=profile,
            max_seconds=max_seconds,
            cancel_check=cancel_check,
            progress_cb=_on_progress,
        ):
            sampled_count += 1
            corrupt_skipped = sample.corrupt_packets_skipped
            rgb = sample.rgb_array
            fh, fw, _ = rgb.shape
            timestamp = sample.timestamp_sec
            frame_idx = sample.frame_index

            # 1. Scene classification & exclusion of menus/replays/celebrations
            scene_res = self.scene_classifier.classify_frame(
                rgb, video_id=video_id, frame_index=frame_idx, timestamp_sec=timestamp
            )
            if scene_res.is_camera_cut:
                self.tracker.reset()
                if not manual_homography:
                    last_valid_homography = None

            is_analyzable_scene = (
                scene_res.scene_class == SceneClass.ACTIVE_GAMEPLAY
                or (
                    scene_res.scene_class == SceneClass.SET_PIECE
                    and scene_res.pitch_pixel_coverage >= 0.42
                    and (scene_res.hud_visible or scene_res.minimap_visible)
                )
            )
            if not is_analyzable_scene:
                excluded_scenes += 1
                prev_rgb = rgb
                continue

            active_frames += 1

            # 2. Optical-flow camera motion compensation
            cam_offset = (0.0, 0.0)
            if prev_rgb is not None and prev_rgb.shape == rgb.shape:
                cam_offset = self.homography.estimate_camera_motion_lk(prev_rgb, rgb)
            prev_rgb = rgb

            # 3. Pitch Calibration (Manual fallback overrides automatic line extractor)
            if manual_homography and manual_homography.matrix_3x3:
                cal_res = manual_homography
            else:
                auto_cal, _ = self.homography.calibrate_from_frame(rgb)
                if auto_cal.state in (PitchCalibrationState.GOOD, PitchCalibrationState.COARSE):
                    cal_res = auto_cal
                    last_valid_homography = auto_cal
                    frames_since_cal = 0
                elif last_valid_homography and frames_since_cal < 5:
                    # Smooth brief carry forward downgraded to COARSE
                    cal_res = HomographyResult(
                        matrix_3x3=last_valid_homography.matrix_3x3,
                        inliers_count=last_valid_homography.inliers_count,
                        reprojection_error_m=min(3.5, last_valid_homography.reprojection_error_m + 0.5),
                        state=PitchCalibrationState.COARSE,
                    )
                    frames_since_cal += 1
                else:
                    cal_res = auto_cal
                    frames_since_cal += 1

            if cal_res.state == PitchCalibrationState.GOOD:
                cal_good += 1
            elif cal_res.state == PitchCalibrationState.COARSE:
                cal_coarse += 1
            else:
                cal_rejected += 1

            # 4. Multi-channel pixel detection & ByteTrack tracking
            players_det, ball_det, minimap_obs, hud_ctx = self.pixel_detector.detect_frame(
                rgb, frame_index=frame_idx, timestamp_sec=timestamp
            )
            det_dicts = [
                {
                    "bbox_xywh": p.bbox_xywh,
                    "confidence": p.confidence,
                    "team": p.team,
                    "entity_class": p.entity_class,
                }
                for p in players_det
            ]
            tracks = self.tracker.update(det_dicts, camera_offset_xy=cam_offset)

            # 5. Evidence fusion tagged strictly with REAL_VIDEO_DECODED
            telemetry = self.fusion.fuse_frame(
                video_id=video_id,
                frame_index=frame_idx,
                timestamp_sec=timestamp,
                tracks=tracks,
                ball_entity=ball_det,
                minimap_obs=minimap_obs,
                hud_ctx=hud_ctx,
                homography_matrix=cal_res.matrix_3x3,
                calibration_state=cal_res.state,
                reprojection_error_m=cal_res.reprojection_error_m,
                scene_class=scene_res.scene_class,
                frame_width=float(fw),
                frame_height=float(fh),
                provenance=DataProvenance.REAL_VIDEO_DECODED,
                detector_backend=self.pixel_detector.backend_name,
            )
            fused_telemetry.append(telemetry)

            # 6. Event extraction strictly gated by non-rejected calibration
            if cal_res.state != PitchCalibrationState.REJECTED:
                cur_poss = telemetry.possession_team
                carrier_id = telemetry.ball_carrier_track_id
                if cur_poss in ("HOME", "AWAY"):
                    possession_history.append(cur_poss)
                    if prev_possession in ("HOME", "AWAY") and cur_poss != prev_possession:
                        turnovers_count += 1
                        events.append(TacticalEvent(
                            video_id=video_id,
                            timestamp_start=max(0.0, timestamp - 1.2),
                            timestamp_end=timestamp,
                            event_type="TURNOVER",
                            team_identity=prev_possession,
                            player_identity=carrier_id or "DEFENSIVE_PRESSURE",
                            observed_action=f"Observed possession shift from {prev_possession} to {cur_poss}",
                            observed_outcome="TURNOVER_OCCURRED",
                            observation_method=ObservationMethod.CV_ASSISTED,
                            pitch_zone=telemetry.ball.get("pitch_zone", 8) if telemetry.ball else 8,
                            review_status=ReviewStatus.UNDER_REVIEW,
                            provenance=DataProvenance.REAL_VIDEO_DECODED.value,
                        ).seal())
                    elif prev_carrier_id and carrier_id and prev_carrier_id != carrier_id:
                        passes_count += 1
                        events.append(TacticalEvent(
                            video_id=video_id,
                            timestamp_start=max(0.0, timestamp - 1.0),
                            timestamp_end=timestamp,
                            event_type="COMPLETED_PASS",
                            team_identity=cur_poss,
                            player_identity=carrier_id,
                            observed_action="Ball carrier hand-off between same-team tracks",
                            observed_outcome="PASS_SUCCESSFUL",
                            observation_method=ObservationMethod.CV_ASSISTED,
                            pitch_zone=telemetry.ball.get("pitch_zone", 8) if telemetry.ball else 8,
                            review_status=ReviewStatus.UNDER_REVIEW,
                            provenance=DataProvenance.REAL_VIDEO_DECODED.value,
                        ).seal())
                    prev_possession = cur_poss
                    prev_carrier_id = carrier_id

        duration_s = float(container_meta.get("duration_seconds") or 0.0)
        if duration_s <= 0.0 and fused_telemetry:
            duration_s = round(fused_telemetry[-1].timestamp_sec, 2)
        analyzable_s = round((active_frames / max(1, sampled_count)) * duration_s, 1) if sampled_count > 0 else 0.0
        cov_pct = round(
            sum(f.observation_coverage_pct for f in fused_telemetry) / max(1, len(fused_telemetry)),
            1,
        ) if fused_telemetry else 0.0
        home_poss_pct = (
            round((possession_history.count("HOME") / len(possession_history)) * 100.0, 1)
            if possession_history else None
        )

        cal_label = (
            f"GOOD ({cal_good}/{active_frames} active frames calibrated)"
            if cal_good >= max(1, active_frames // 2)
            else (
                f"COARSE ({cal_good + cal_coarse}/{active_frames} calibrated; {cal_rejected} rejected)"
                if (cal_good + cal_coarse) > 0
                else f"REJECTED (0/{active_frames} auto-calibrated; manual 4-point override recommended)"
            )
        )

        summary = {
            "video_id": video_id,
            "provenance": DataProvenance.REAL_VIDEO_DECODED.value,
            "decoder_backend": container_meta.get("decoder_backend"),
            "detector_backend": self.pixel_detector.backend_name,
            "compute_device": f"{device_info['backend']}: {device_info['device_name']}",
            "resolution": f"{container_meta.get('resolution_width')}x{container_meta.get('resolution_height')}",
            "codec": container_meta.get("codec"),
            "duration_seconds": duration_s,
            "sampled_frames": sampled_count,
            "active_gameplay_frames": active_frames,
            "excluded_non_gameplay_frames": excluded_scenes,
            "corrupt_packets_skipped": corrupt_skipped,
            "analyzable_gameplay_seconds": analyzable_s,
            "tracking_coverage_pct": cov_pct,
            "total_frames_sampled": len(fused_telemetry),
            "home_possession_pct": home_poss_pct,
            "away_possession_pct": round(100.0 - home_poss_pct, 1) if home_poss_pct is not None else None,
            "passes_completed": passes_count,
            "turnovers_detected": turnovers_count,
            "tactical_events_count": len(events),
            "calibration_breakdown": {"good": cal_good, "coarse": cal_coarse, "rejected": cal_rejected},
            "calibration_quality": cal_label,
        }

        if job:
            job.analyzed_frames_count = len(fused_telemetry)
            job.analyzable_gameplay_seconds = analyzable_s
            job.update_progress(100.0, JobStatus.COMPLETED)

        return fused_telemetry, events, summary

    def process_match_recording(
        self,
        video_id: str,
        duration_seconds: float = 30.0,
        profile: ProcessingProfile = ProcessingProfile.BALANCED,
        job: Optional[VideoIngestionJob] = None,
        allow_synthetic_fixture: bool = True,
    ) -> Tuple[List[FusedFrameTelemetry], List[TacticalEvent], Dict[str, Any]]:
        """Explicitly labeled synthetic fixture generator for offline unit tests ONLY.
        Real video ingestion paths call `process_video_file` instead.
        """
        if not allow_synthetic_fixture:
            raise RealVideoDecodeError("Synthetic fixture execution disabled for real-video validation.")

        self.scene_classifier.reset()
        self.tracker.reset()

        step_sec = 0.5 if profile == ProcessingProfile.FAST else (0.1 if profile == ProcessingProfile.HIGH_ACCURACY else 0.2)
        total_frames = int(duration_seconds / step_sec)
        h_matrix = self.generate_canonical_homography()

        fused_telemetry: List[FusedFrameTelemetry] = []
        events: List[TacticalEvent] = []
        active_gameplay_frames = 0
        possession_history: List[str] = []
        passes_count = 0
        turnovers_count = 0
        prev_possession = "UNKNOWN"
        prev_carrier_id: Optional[str] = None

        for i in range(total_frames):
            timestamp = round(i * step_sec, 2)
            frame_idx = int(timestamp * 60)

            frame_rgb = np.zeros((1080, 1920, 3), dtype=np.uint8)
            frame_rgb[:, :] = [48, 142, 64]
            frame_rgb[30:100, 50:350] = [20, 25, 30]
            frame_rgb[40:60, 70:150] = [245, 245, 245]
            frame_rgb[920:1040, 780:1140] = [30, 45, 35]
            frame_rgb[950:970, 850:900] = [255, 255, 255]

            scene_res = self.scene_classifier.classify_frame(
                frame_rgb, video_id=video_id, frame_index=frame_idx, timestamp_sec=timestamp
            )
            if scene_res.scene_class != SceneClass.ACTIVE_GAMEPLAY:
                continue

            active_gameplay_frames += 1
            players_det, ball_det, minimap_obs, hud_ctx = self.synthetic_detector.detect_frame(
                frame_rgb, frame_index=frame_idx, timestamp_sec=timestamp
            )
            det_dicts = [
                {"bbox_xywh": p.bbox_xywh, "confidence": p.confidence, "team": p.team, "entity_class": p.entity_class}
                for p in players_det
            ]
            tracks = self.tracker.update(det_dicts)

            telemetry = self.fusion.fuse_frame(
                video_id=video_id,
                frame_index=frame_idx,
                timestamp_sec=timestamp,
                tracks=tracks,
                ball_entity=ball_det,
                minimap_obs=minimap_obs,
                hud_ctx=hud_ctx,
                homography_matrix=h_matrix,
                calibration_state=PitchCalibrationState.GOOD,
                reprojection_error_m=0.82,
                scene_class=scene_res.scene_class,
                provenance=DataProvenance.SYNTHETIC_FIXTURE,
                detector_backend=self.synthetic_detector.backend_name,
            )
            fused_telemetry.append(telemetry)

            cur_poss = telemetry.possession_team
            carrier_id = telemetry.ball_carrier_track_id
            if cur_poss in ("HOME", "AWAY"):
                possession_history.append(cur_poss)
                if prev_possession in ("HOME", "AWAY") and cur_poss != prev_possession:
                    turnovers_count += 1
                    events.append(TacticalEvent(
                        video_id=video_id,
                        timestamp_start=max(0.0, timestamp - 1.5),
                        timestamp_end=timestamp + 0.5,
                        event_type="TURNOVER",
                        team_identity=prev_possession,
                        player_identity="DEFENSIVE_PRESSURE",
                        observed_action=f"[SYNTHETIC_FIXTURE] Possession surrendered to {cur_poss}",
                        observed_outcome="TURNOVER_OCCURRED",
                        observation_method=ObservationMethod.CV_ASSISTED,
                        pitch_zone=telemetry.ball.get("pitch_zone", 8) if telemetry.ball else 8,
                        review_status=ReviewStatus.UNDER_REVIEW,
                        provenance=DataProvenance.SYNTHETIC_FIXTURE.value,
                    ).seal())
                elif prev_carrier_id and carrier_id and prev_carrier_id != carrier_id:
                    passes_count += 1
                    events.append(TacticalEvent(
                        video_id=video_id,
                        timestamp_start=max(0.0, timestamp - 1.2),
                        timestamp_end=timestamp,
                        event_type="COMPLETED_PASS",
                        team_identity=cur_poss,
                        player_identity=carrier_id,
                        observed_action="[SYNTHETIC_FIXTURE] Completed ball progression pass",
                        observed_outcome="PASS_SUCCESSFUL",
                        observation_method=ObservationMethod.CV_ASSISTED,
                        pitch_zone=telemetry.ball.get("pitch_zone", 8) if telemetry.ball else 8,
                        review_status=ReviewStatus.UNDER_REVIEW,
                        provenance=DataProvenance.SYNTHETIC_FIXTURE.value,
                    ).seal())
            prev_possession = cur_poss
            prev_carrier_id = carrier_id

            if job and i % 10 == 0:
                job.update_progress(round((i + 1) / max(1, total_frames) * 100.0, 1))

        analyzable_sec = round(active_gameplay_frames * step_sec, 1)
        home_possession_pct = (
            round((possession_history.count("HOME") / len(possession_history)) * 100.0, 1)
            if possession_history else 50.0
        )

        summary = {
            "video_id": video_id,
            "provenance": DataProvenance.SYNTHETIC_FIXTURE.value,
            "decoder_backend": "SYNTHETIC_IN_MEMORY_GENERATOR",
            "detector_backend": self.synthetic_detector.backend_name,
            "duration_seconds": duration_seconds,
            "analyzable_gameplay_seconds": analyzable_sec,
            "tracking_coverage_pct": round((analyzable_sec / max(1.0, duration_seconds)) * 100.0, 1),
            "total_frames_sampled": len(fused_telemetry),
            "home_possession_pct": home_possession_pct,
            "away_possession_pct": round(100.0 - home_possession_pct, 1),
            "passes_completed": passes_count,
            "turnovers_detected": turnovers_count,
            "tactical_events_count": len(events),
            "calibration_quality": "SYNTHETIC_FIXTURE (Canonical 1080p grid)",
        }

        if job:
            job.provenance = DataProvenance.SYNTHETIC_FIXTURE
            job.analyzed_frames_count = len(fused_telemetry)
            job.analyzable_gameplay_seconds = analyzable_sec
            job.update_progress(100.0)

        return fused_telemetry, events, summary
