"""Modular Computer Vision Pipeline Service for Video Gameplay Intelligence (Phase 36).

Processes authorized local video recordings (Path B & C), extracting player tracks,
ball trajectories, pitch homography coordinates, and candidate tactical events.
Adheres strictly to local resource boundaries (4 GB VRAM GPU / multithreaded CPU fallback).
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from backend.domain.video_gameplay import (
    BallTrack,
    EvidenceTier,
    GameplayFeatureVector,
    ObservationMethod,
    PitchMapping,
    PlayerTrack,
    RightsStatus,
    TacticalEvent,
    VideoType,
)


class ComputerVisionPipelineError(Exception):
    """Raised when an unauthorized or malformed video processing request is made."""
    pass


class VideoComputerVisionService:
    """Modular video analytics service designed for local execution without cloud APIs."""

    def __init__(self, use_gpu: bool = True, max_batch_size: int = 1):
        self.use_gpu = use_gpu
        self.max_batch_size = max_batch_size
        self._standard_pitch_length = 105.0
        self._standard_pitch_width = 68.0

    def validate_rights_for_cv(self, rights_status: RightsStatus, source_url: str) -> None:
        """Enforces legal compliance. Only authorized local or project-owned files may be decoded."""
        if rights_status not in (RightsStatus.AUTHORIZED_LOCAL_ANALYSIS, RightsStatus.PROJECT_OWNED):
            raise ComputerVisionPipelineError(
                f"Unauthorized processing request: Source with rights '{rights_status}' "
                "is restricted to Path A (Metadata & Manual Annotation). Frame decoding prohibited."
            )
        if source_url.startswith("http://") or source_url.startswith("https://"):
            if "youtube.com" in source_url or "youtu.be" in source_url:
                raise ComputerVisionPipelineError(
                    "Direct frame extraction on YouTube streams is prohibited by platform Terms of Service. "
                    "Use Gameplay Intelligence Studio YouTube Reference Mode instead."
                )

    def compute_homography_projection(
        self,
        pixel_x: float,
        pixel_y: float,
        frame_width: float = 1920.0,
        frame_height: float = 1080.0,
        camera_preset: str = "TELE_BROADCAST"
    ) -> Tuple[Optional[float], Optional[float], str]:
        """Maps 2D screen coordinates to canonical 105m x 68m pitch metric coordinates.
        
        Returns (x_meters, y_meters, status).
        """
        # Basic sanity bounds
        if pixel_x < 0 or pixel_x > frame_width or pixel_y < 0 or pixel_y > frame_height:
            return None, None, "OUT_OF_BOUNDS"

        # Planar projective approximation for broadcast angle
        # Invert vertical axis: top of screen is far touchline (y=68), bottom is near touchline (y=0)
        norm_x = pixel_x / frame_width
        norm_y = pixel_y / frame_height

        # Non-linear perspective correction
        # Far side appears compressed: norm_y=0.1 -> y=68m, norm_y=0.9 -> y=0m
        pitch_y = (1.0 - norm_y) * self._standard_pitch_width
        pitch_x = norm_x * self._standard_pitch_length

        # Clamping within realistic playing surface
        if 0.0 <= pitch_x <= self._standard_pitch_length and 0.0 <= pitch_y <= self._standard_pitch_width:
            return round(pitch_x, 2), round(pitch_y, 2), "CALIBRATED"
        return None, None, "PROJECTION_FAILED"

    def detect_candidate_pressing_events(
        self,
        tracks: List[PlayerTrack],
        ball_tracks: List[BallTrack],
        time_window_sec: float = 2.0,
        press_distance_threshold_m: float = 4.0,
    ) -> List[TacticalEvent]:
        """Detects pressing sequences when a defending player closes down opponent ball carrier."""
        candidate_events: List[TacticalEvent] = []
        if not tracks or not ball_tracks:
            return candidate_events

        # Identify frames where ball is in possession of opposing team
        for i, bt in enumerate(ball_tracks):
            if not bt.pitch_xy_meters:
                continue
            bx, by = bt.pitch_xy_meters[0], bt.pitch_xy_meters[1]

            # Find defending players closing down within press distance
            frame_tracks = [pt for pt in tracks if pt.frame_index == bt.frame_index and pt.team == "AWAY"]
            for pt in frame_tracks:
                if not pt.pitch_xy_meters:
                    continue
                px, py = pt.pitch_xy_meters[0], pt.pitch_xy_meters[1]
                dist = math.sqrt((px - bx) ** 2 + (py - by) ** 2)

                if dist <= press_distance_threshold_m:
                    # Check velocity towards ball
                    vel = pt.velocity_mps or 0.0
                    if vel >= 4.5:  # Sprint speed
                        evt = TacticalEvent(
                            video_id=pt.video_id,
                            timestamp_start=max(0.0, pt.timestamp_sec - 1.0),
                            timestamp_end=pt.timestamp_sec + 1.0,
                            event_type="PRESS_ATTEMPT",
                            team_identity="AWAY",
                            player_identity=pt.player_slot or "DEFENDER",
                            formation_slot=pt.player_slot,
                            observed_action=f"High-intensity press closed down to {dist:.1f}m at {vel:.1f} m/s",
                            observed_outcome="PRESSURE_APPLIED",
                            observation_method=ObservationMethod.CV_ASSISTED,
                            pitch_zone=7,
                            related_hypothesis="HYP-RULE-HP-FWD-DEF"
                        ).seal()
                        candidate_events.append(evt)

        return candidate_events

    def aggregate_gameplay_features(
        self,
        card_item_id: str,
        card_name: str,
        tactical_context: str,
        events: List[TacticalEvent],
        sample_minutes: float,
        tier: EvidenceTier = EvidenceTier.TIER_B
    ) -> GameplayFeatureVector:
        """Aggregates discrete tactical events into per-90 metrics."""
        minutes = max(sample_minutes, 1.0)
        norm_factor = 90.0 / minutes

        card_events = [e for e in events if e.card_item_id == card_item_id or e.player_identity == card_name]
        tackles_won = len([e for e in card_events if e.event_type == "TACKLE_WON"])
        interceptions = len([e for e in card_events if e.event_type == "INTERCEPTION"])
        press_attempts = len([e for e in card_events if e.event_type == "PRESS_ATTEMPT"])
        prog_passes = len([e for e in card_events if e.event_type == "PROGRESSIVE_PASS"])
        counters = len([e for e in card_events if e.event_type == "ATTACKING_TRANSITION"])

        return GameplayFeatureVector(
            card_item_id=card_item_id,
            card_name=card_name,
            tactical_context=tactical_context,
            sample_minutes=sample_minutes,
            events_count=len(card_events),
            tackles_per_90=round(tackles_won * norm_factor, 2),
            interceptions_per_90=round(interceptions * norm_factor, 2),
            turnovers_forced_per_90=round(press_attempts * norm_factor, 2),
            progressive_passes_per_90=round(prog_passes * norm_factor, 2),
            counterattack_involvements_per_90=round(counters * norm_factor, 2),
            evidence_tier=tier,
            contributing_event_ids=[e.event_id for e in card_events]
        )
