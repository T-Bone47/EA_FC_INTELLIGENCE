"""Empirical Gameplay Observation Domain Models and Validation State Machine (Phase 35).

Defines structured schema, review lifecycle states, observer provenance,
and data quality validation rules for live match observations.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class ReviewStatus(str, Enum):
    """Lifecycle states for match observations."""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    SUPERSEDED = "SUPERSEDED"


class CaptureMethod(str, Enum):
    """Method used by observer to record match telemetry."""
    VIDEO_OCR = "VIDEO_OCR"
    API_SPECTATOR = "API_SPECTATOR"
    MANUAL_TALLY = "MANUAL_TALLY"
    EVENT_LOG = "EVENT_LOG"


class GameMode(str, Enum):
    """Game mode in which the observation occurred."""
    SQUAD_BATTLES = "SQUAD_BATTLES"
    RIVALS = "RIVALS"
    CHAMPIONS = "CHAMPIONS"
    FRIENDLIES = "FRIENDLIES"


class ControllerAssist(str, Enum):
    """Controller assist profile for passing and shooting."""
    ASSISTED = "ASSISTED"
    SEMI_ASSISTED = "SEMI_ASSISTED"
    MANUAL = "MANUAL"


@dataclass
class MatchMetadata:
    """Environmental and configuration metadata for a single match observation."""
    match_id: str
    match_timestamp: str
    game_title: str                         # e.g. "FC27", "FC26"
    patch_version: str                      # e.g. "Patch 1.04"
    game_mode: GameMode
    difficulty: str                         # e.g. "Legendary", "Ultimate", "Rivals Div 1"
    half_length_mins: int                   # e.g. 6
    tactical_defending: bool = True
    pass_assist: ControllerAssist = ControllerAssist.ASSISTED
    shot_assist: ControllerAssist = ControllerAssist.ASSISTED
    connection_ping_ms: Optional[float] = None
    input_delay_rating: str = "NORMAL"      # "EXCELLENT", "NORMAL", "POOR", "SEVERE"
    dnf: bool = False                       # Did not finish / early disconnect
    final_minute_reached: int = 90          # Minute reached before match concluded


@dataclass
class ObserverMetadata:
    """Provenance and cryptographic identity of human/automated observer."""
    observer_id: str
    observer_handle: str
    capture_method: CaptureMethod
    video_proof_url: Optional[str] = None
    client_signature: Optional[str] = None


@dataclass
class PerformanceMetrics:
    """Quantitative performance metrics logged for a player card in a match."""
    card_item_id: str
    minutes_played: int
    goals: int = 0
    assists: int = 0
    shots: int = 0
    shots_on_target: int = 0
    xg: float = 0.0
    passes_attempted: int = 0
    passes_completed: int = 0
    tackles_attempted: int = 0
    tackles_won: int = 0
    interceptions: int = 0
    final_third_presses: int = 0
    turnovers_forced_final_third: int = 0
    transition_recoveries: int = 0
    aerial_duels_attempted: int = 0
    aerial_duels_won: int = 0
    possession_lost: int = 0


@dataclass
class EmpiricalObservationRecord:
    """Comprehensive single-match empirical observation record."""
    observation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    experiment_id: str = "EXP-ST-PRESS-001"
    session_id: str = ""
    match_meta: MatchMetadata = field(default_factory=lambda: MatchMetadata(
        match_id="M-001",
        match_timestamp=datetime.now(timezone.utc).isoformat(),
        game_title="FC27",
        patch_version="Patch 1.04",
        game_mode=GameMode.SQUAD_BATTLES,
        difficulty="Legendary",
        half_length_mins=6,
    ))
    observer: ObserverMetadata = field(default_factory=lambda: ObserverMetadata(
        observer_id="OBS-001",
        observer_handle="tactical_analyst_01",
        capture_method=CaptureMethod.VIDEO_OCR,
    ))
    tactical_profile: str = "HIGH_PRESS"
    formation: str = "4-3-3"
    slot_evaluated: str = "ST"
    candidate_arm: str = "A"               # "A" or "B"
    metrics: PerformanceMetrics = field(default_factory=lambda: PerformanceMetrics(
        card_item_id="top100-022",
        minutes_played=90,
    ))
    review_status: ReviewStatus = ReviewStatus.DRAFT
    rejection_reason: Optional[str] = None
    verification_hash: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def compute_hash(self) -> str:
        """Computes deterministic SHA-256 integrity hash."""
        raw = f"{self.observation_id}|{self.experiment_id}|{self.session_id}|{self.metrics.card_item_id}|{self.metrics.minutes_played}|{self.metrics.turnovers_forced_final_third}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def validate_quality(self, expected_patch: str = "Patch 1.04") -> Tuple[bool, List[str]]:
        """Applies rigorous quality validation rules."""
        issues: List[str] = []
        
        # Rule 1: Match completion threshold (>= 75 minutes)
        if self.match_meta.dnf or self.match_meta.final_minute_reached < 75:
            issues.append("MATCH_PREMATURE_TERMINATION: Match ended before minute 75.")
            
        # Rule 2: Minimum minutes played by subject card (>= 60 minutes)
        if self.metrics.minutes_played < 60:
            issues.append(f"INSUFFICIENT_MINUTES_PLAYED: Card played {self.metrics.minutes_played} min (minimum 60 required).")
            
        # Rule 3: Patch compatibility
        if self.match_meta.patch_version != expected_patch:
            issues.append(f"PATCH_VERSION_MISMATCH: Match on {self.match_meta.patch_version}, expected {expected_patch}.")
            
        # Rule 4: Tactical defending requirement
        if not self.match_meta.tactical_defending:
            issues.append("CONTROLLER_ASSIST_VIOLATION: Legacy defending enabled; Tactical Defending required.")
            
        # Rule 5: Severe network latency / lag
        if self.match_meta.connection_ping_ms and self.match_meta.connection_ping_ms > 80.0:
            issues.append(f"LATENCY_LIMIT_EXCEEDED: Ping was {self.match_meta.connection_ping_ms}ms (> 80ms).")
            
        return len(issues) == 0, issues

    def transition_state(self, new_status: ReviewStatus, reason: Optional[str] = None) -> None:
        """State machine transition with validation."""
        valid_transitions = {
            ReviewStatus.DRAFT: [ReviewStatus.SUBMITTED, ReviewStatus.REJECTED],
            ReviewStatus.SUBMITTED: [ReviewStatus.UNDER_REVIEW, ReviewStatus.REJECTED],
            ReviewStatus.UNDER_REVIEW: [ReviewStatus.ACCEPTED, ReviewStatus.REJECTED, ReviewStatus.INSUFFICIENT_EVIDENCE],
            ReviewStatus.ACCEPTED: [ReviewStatus.SUPERSEDED],
            ReviewStatus.REJECTED: [ReviewStatus.DRAFT],
            ReviewStatus.INSUFFICIENT_EVIDENCE: [ReviewStatus.DRAFT, ReviewStatus.REJECTED],
            ReviewStatus.SUPERSEDED: [],
        }
        allowed = valid_transitions.get(self.review_status, [])
        if new_status not in allowed:
            raise ValueError(f"Illegal state transition from {self.review_status.value} to {new_status.value}")
        
        self.review_status = new_status
        if reason:
            self.rejection_reason = reason
        if new_status == ReviewStatus.ACCEPTED:
            self.verification_hash = self.compute_hash()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
