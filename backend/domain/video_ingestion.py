"""Domain entities and contracts for Recorded Gameplay Ingestion & Perception (Phase 38).

Establishes strict epistemic status tracking, scene classification categories,
pluggable multi-channel perception models, and manual review audit contracts.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ProcessingProfile(str, Enum):
    FAST = "FAST"
    BALANCED = "BALANCED"
    HIGH_ACCURACY = "HIGH_ACCURACY"


class SceneClass(str, Enum):
    ACTIVE_GAMEPLAY = "ACTIVE_GAMEPLAY"
    KICKOFF = "KICKOFF"
    GOAL_REPLAY = "GOAL_REPLAY"
    CINEMATIC_REPLAY = "CINEMATIC_REPLAY"
    SET_PIECE = "SET_PIECE"
    PAUSE_MENU = "PAUSE_MENU"
    TACTICAL_MENU = "TACTICAL_MENU"
    CELEBRATION = "CELEBRATION"
    HALFTIME = "HALFTIME"
    FULLTIME = "FULLTIME"
    LOADING_SCREEN = "LOADING_SCREEN"
    UNKNOWN = "UNKNOWN"


class ObservationStatus(str, Enum):
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    INTERPOLATED = "INTERPOLATED"
    UNKNOWN = "UNKNOWN"
    REJECTED = "REJECTED"


class DataProvenance(str, Enum):
    """Explicit epistemic provenance distinguishing decoded real media from fixtures."""
    REAL_VIDEO_DECODED = "REAL_VIDEO_DECODED"
    IMPORTED_MATCH_TRACE = "IMPORTED_MATCH_TRACE"
    MANUAL_ANNOTATION = "MANUAL_ANNOTATION"
    SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"


class PitchCalibrationState(str, Enum):
    GOOD = "GOOD"
    COARSE = "COARSE"
    REJECTED = "REJECTED"


class ReviewVerdict(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    MODIFIED = "MODIFIED"


class FileMetadata(BaseModel):
    filename: str
    format: str = "mp4"
    file_size_bytes: int = 0
    sha256: str = ""
    duration_seconds: float = 0.0
    resolution_width: int = 1920
    resolution_height: int = 1080
    frame_rate: float = 60.0
    codec: str = "h264"
    game_version: str = "FC27"
    game_patch: Optional[str] = "PATCH_1.02"
    match_mode: str = "COMPETITIVE_RIVALS"
    camera_preset: str = "TELE_BROADCAST"


class VideoIngestionJob(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid4()))
    video_id: str = Field(default_factory=lambda: str(uuid4()))
    status: JobStatus = JobStatus.QUEUED
    progress_pct: float = 0.0
    file_metadata: FileMetadata
    processing_profile: ProcessingProfile = ProcessingProfile.BALANCED
    analyzed_frames_count: int = 0
    analyzable_gameplay_seconds: float = 0.0
    provenance: DataProvenance = DataProvenance.REAL_VIDEO_DECODED
    decoder_backend: Optional[str] = None
    detector_backend: Optional[str] = None
    compute_device: Optional[str] = None
    media_path: Optional[str] = None
    error_diagnostic: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def update_progress(self, progress: float, status: Optional[JobStatus] = None) -> None:
        self.progress_pct = max(0.0, min(100.0, round(progress, 1)))
        if status:
            self.status = status
        self.updated_at = datetime.now(timezone.utc).isoformat()


class SceneClassificationResult(BaseModel):
    video_id: str
    frame_index: int
    timestamp_sec: float
    scene_class: SceneClass
    confidence: float = 1.0
    is_camera_cut: bool = False
    pitch_pixel_coverage: float = 0.0
    hud_visible: bool = True
    minimap_visible: bool = True


class PitchLandmark(BaseModel):
    name: str
    pixel_xy: Tuple[float, float]
    pitch_xy_meters: Tuple[float, float]
    confidence: float = 1.0


class HomographyResult(BaseModel):
    matrix_3x3: List[List[float]] = Field(default_factory=list)
    inliers_count: int = 0
    reprojection_error_m: float = 0.0
    state: PitchCalibrationState = PitchCalibrationState.GOOD


class DetectedEntity(BaseModel):
    entity_class: str  # outfield_player | goalkeeper | referee | ball | selected_marker
    team: Optional[str] = None  # HOME | AWAY | REFEREE | UNKNOWN
    bbox_xywh: List[float] = Field(default_factory=list)  # [x, y, w, h] normalized [0, 1]
    confidence: float = 1.0
    pitch_xy_meters: Optional[List[float]] = None
    observation_status: ObservationStatus = ObservationStatus.OBSERVED


class MinimapObservation(BaseModel):
    norm_xy: Tuple[float, float]
    pitch_xy_meters: Tuple[float, float]
    team: str  # HOME | AWAY | BALL
    confidence: float = 0.85


class HUDContext(BaseModel):
    match_clock: Optional[str] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    home_team_abbr: Optional[str] = None
    away_team_abbr: Optional[str] = None
    active_player_name: Optional[str] = None
    playstyle_active: Optional[str] = None


class FusedFrameTelemetry(BaseModel):
    video_id: str
    frame_index: int
    timestamp_sec: float
    match_clock: Optional[str] = None
    calibration_state: PitchCalibrationState = PitchCalibrationState.GOOD
    reprojection_error_m: float = 0.0
    possession_team: str = "UNKNOWN"
    ball_carrier_track_id: Optional[str] = None
    ball: Optional[Dict[str, Any]] = None
    players: List[Dict[str, Any]] = Field(default_factory=list)
    team_metrics: Dict[str, float] = Field(default_factory=dict)
    scene_class: SceneClass = SceneClass.ACTIVE_GAMEPLAY
    provenance: DataProvenance = DataProvenance.REAL_VIDEO_DECODED
    observation_coverage_pct: float = 0.0
    detector_backend: Optional[str] = None


class ManualReviewRecord(BaseModel):
    review_id: str = Field(default_factory=lambda: str(uuid4()))
    video_id: str
    target_id: str  # event_id or track_id
    reviewer_id: str = "local_analyst"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    change_type: str  # IDENTITY_CORRECTION | TEAM_CORRECTION | BALL_CORRECTION | CALIBRATION_OVERRIDE | EVENT_VERDICT
    original_value: Dict[str, Any] = Field(default_factory=dict)
    corrected_value: Dict[str, Any] = Field(default_factory=dict)
    review_verdict: ReviewVerdict = ReviewVerdict.ACCEPTED
    reason: str = ""
    audit_hash: Optional[str] = None
    integrity_hash: Optional[str] = None

    def seal(self) -> ManualReviewRecord:
        payload = {
            "review_id": self.review_id,
            "video_id": self.video_id,
            "target_id": self.target_id,
            "change_type": self.change_type,
            "original_value": self.original_value,
            "corrected_value": self.corrected_value,
            "review_verdict": self.review_verdict.value,
            "reason": self.reason,
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        self.audit_hash = digest
        self.integrity_hash = digest
        return self
