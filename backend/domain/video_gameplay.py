"""Domain entities and schemas for Video Gameplay Intelligence (Phase 36)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class VideoPlatform(str, Enum):
    YOUTUBE = "YOUTUBE"
    LOCAL_STORAGE = "LOCAL_STORAGE"
    DIRECT_FEED = "DIRECT_FEED"
    EA_OFFICIAL = "EA_OFFICIAL"


class VideoType(str, Enum):
    FULL_MATCH = "FULL_MATCH"
    EDITED_MATCH = "EDITED_MATCH"
    HIGHLIGHT_COMPILATION = "HIGHLIGHT_COMPILATION"
    CARD_REVIEW = "CARD_REVIEW"
    TACTICAL_TUTORIAL = "TACTICAL_TUTORIAL"
    CONTROLLED_COMPARISON = "CONTROLLED_COMPARISON"
    OFFICIAL_GAMEPLAY_DEMONSTRATION = "OFFICIAL_GAMEPLAY_DEMONSTRATION"
    BETA_GAMEPLAY = "BETA_GAMEPLAY"
    CPU_SIMULATION = "CPU_SIMULATION"
    UNKNOWN = "UNKNOWN"


class RightsStatus(str, Enum):
    PUBLIC_EMBED_ONLY = "PUBLIC_EMBED_ONLY"
    AUTHORIZED_LOCAL_ANALYSIS = "AUTHORIZED_LOCAL_ANALYSIS"
    PROJECT_OWNED = "PROJECT_OWNED"
    DOCUMENTATION_ONLY = "DOCUMENTATION_ONLY"


class EvidenceTier(str, Enum):
    TIER_A = "TIER_A"  # Controlled experiment
    TIER_B = "TIER_B"  # Structured gameplay observation
    TIER_C = "TIER_C"  # Qualitative tactical evidence
    TIER_D = "TIER_D"  # Research discovery only


class ReviewStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class IdentityConfidence(str, Enum):
    HIGH = "HIGH"
    PROVISIONAL = "PROVISIONAL"
    UNRESOLVED = "UNRESOLVED"


class ObservationMethod(str, Enum):
    MANUAL_ANNOTATION = "MANUAL_ANNOTATION"
    CV_ASSISTED = "CV_ASSISTED"
    AUTOMATED_DETECTOR = "AUTOMATED_DETECTOR"


class GameplayVideo(BaseModel):
    video_id: str = Field(default_factory=lambda: str(uuid4()))
    source_url: str
    platform: VideoPlatform = VideoPlatform.YOUTUBE
    title: str
    creator_name: str
    publication_date: str
    game_version: str = "FC27"
    game_patch: Optional[str] = "PATCH_1.01"
    match_mode: str = "COMPETITIVE"
    video_type: VideoType = VideoType.FULL_MATCH
    duration_seconds: float = 0.0
    rights_status: RightsStatus = RightsStatus.PUBLIC_EMBED_ONLY
    permitted_scope: str = "METADATA_AND_MANUAL_ANNOTATION"
    exact_card_status: str = "UNRESOLVED"
    formation_visibility: str = "PARTIAL"
    tactical_visibility: str = "PARTIAL"
    continuity: str = "CONTINUOUS"
    source_quality: str = "HIGH_CLARITY_1080P"
    evidence_tier: EvidenceTier = EvidenceTier.TIER_C
    review_status: ReviewStatus = ReviewStatus.SUBMITTED
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class TacticalEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    video_id: str
    match_id: Optional[str] = None
    timestamp_start: float
    timestamp_end: float
    event_type: str
    team_identity: str = "HOME"
    player_identity: Optional[str] = None
    card_item_id: Optional[str] = None
    formation: Optional[str] = "4-3-3"
    formation_slot: Optional[str] = None
    tactical_context: Optional[str] = "HIGH_PRESS"
    pitch_zone: Optional[int] = 7
    observed_action: str
    observed_outcome: str
    observation_method: ObservationMethod = ObservationMethod.MANUAL_ANNOTATION
    identity_confidence: IdentityConfidence = IdentityConfidence.HIGH
    review_status: ReviewStatus = ReviewStatus.DRAFT
    reviewer_id: Optional[str] = None
    related_hypothesis: Optional[str] = None
    provenance: str = "MANUAL_ANNOTATION"  # REAL_VIDEO_DECODED | IMPORTED_MATCH_TRACE | MANUAL_ANNOTATION | SYNTHETIC_FIXTURE
    integrity_hash: Optional[str] = None
    correction_history: List[Dict[str, Any]] = Field(default_factory=list)

    def compute_integrity_hash(self) -> str:
        payload = {
            "video_id": self.video_id,
            "timestamp_start": round(self.timestamp_start, 3),
            "timestamp_end": round(self.timestamp_end, 3),
            "event_type": self.event_type,
            "player_identity": self.player_identity,
            "card_item_id": self.card_item_id,
            "observed_action": self.observed_action,
            "observed_outcome": self.observed_outcome,
        }
        canonical = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def seal(self) -> TacticalEvent:
        self.integrity_hash = self.compute_integrity_hash()
        return self


class PlayerTrack(BaseModel):
    track_id: str = Field(default_factory=lambda: str(uuid4()))
    video_id: str
    frame_index: int
    timestamp_sec: float
    player_slot: Optional[str] = None
    team: str = "HOME"
    bbox_xywh: List[float] = Field(default_factory=list)  # [x, y, w, h] normalized or pixel
    pitch_xy_meters: Optional[List[float]] = None  # [x, y] in 105x68 meters
    velocity_mps: Optional[float] = None
    confidence: float = 1.0
    is_occluded: bool = False


class BallTrack(BaseModel):
    track_id: str = Field(default_factory=lambda: str(uuid4()))
    video_id: str
    frame_index: int
    timestamp_sec: float
    bbox_xywh: List[float] = Field(default_factory=list)
    pitch_xy_meters: Optional[List[float]] = None
    in_flight: bool = False
    possessing_slot: Optional[str] = None
    confidence: float = 1.0


class PitchMapping(BaseModel):
    mapping_id: str = Field(default_factory=lambda: str(uuid4()))
    video_id: str
    frame_index: int
    homography_matrix: List[List[float]] = Field(default_factory=list)  # 3x3 matrix
    reprojection_error_m: float = 0.0
    visible_landmarks: List[str] = Field(default_factory=list)
    quality_status: str = "CALIBRATED"


class GameplayFeatureVector(BaseModel):
    vector_id: str = Field(default_factory=lambda: str(uuid4()))
    card_item_id: str
    card_name: str
    tactical_context: str
    sample_minutes: float
    events_count: int
    tackles_per_90: float
    interceptions_per_90: float
    turnovers_forced_per_90: float
    progressive_passes_per_90: float
    counterattack_involvements_per_90: float
    avg_press_distance_m: Optional[float] = None
    evidence_tier: EvidenceTier = EvidenceTier.TIER_B
    contributing_event_ids: List[str] = Field(default_factory=list)


class PredictionChallenge(BaseModel):
    challenge_id: str = Field(default_factory=lambda: str(uuid4()))
    hypothesis_code: str  # e.g. "HYP-RULE-HP-FWD-DEF"
    title: str
    description: str
    v321_prediction_summary: str
    expected_direction: str  # e.g. "Dembele Defending 55 yields > 1.5 tackles/90 over Mbappe Defending 29"
    candidate_card_a_id: str
    candidate_card_a_name: str
    candidate_card_b_id: str
    candidate_card_b_name: str
    tactical_profile: str
    evaluation_metric: str
    status: str = "ACTIVE_RESEARCH"  # ACTIVE_RESEARCH, SUPPORTED, CONTRADICTED, INSUFFICIENT_DATA
    observed_delta: Optional[float] = None
    p_value: Optional[float] = None
    conclusion: Optional[str] = None
