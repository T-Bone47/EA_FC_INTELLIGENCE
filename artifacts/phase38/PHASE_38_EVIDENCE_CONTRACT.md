# PHASE 38: EVIDENCE & TELEMETRY CONTRACT SPECIFICATION
**Milestone:** Phase 38 — Perception Engine Foundation  
**Date:** 2026-11-24  
**Project:** EA FC Intelligence — Stadium 3.0  
**Status:** FROZEN & RATIFIED  

This document defines the strict data contracts, schemas, and epistemic honesty rules governing gameplay video ingestion, scene classification, object tracking, and spatial telemetry.

---

## 1. Epistemic Observation Status Hierarchy

To maintain scientific integrity and prevent unvalidated inferences from contaminating competitive tactical analysis, every spatial position, track, and event must carry an explicit `ObservationStatus`:

```typescript
export type ObservationStatus = 
  | 'OBSERVED'     // Direct visual detection from broadcast camera with 'GOOD' calibration
  | 'INFERRED'     // Derived from minimap icon mapping, team tactical context, or high-conf motion
  | 'INTERPOLATED' // Computed via temporal spline across brief visual occlusion (<= 0.5s)
  | 'UNKNOWN'      // Entity is obscured, absent, or below minimum confidence threshold
  | 'REJECTED'     // Detection discarded due to geometric violation, impossible speed, or cut
```

### Invariants:
1. **No Synthetic Promotion:** Synthetic test fixtures must never be written with status `OBSERVED`.
2. **Abstention Over Guesswork:** When pitch calibration is `REJECTED`, metric pitch coordinates `pitch_xy_meters` must be `null` and status set to `UNKNOWN` or `REJECTED`.
3. **No Disguised Interpolation:** When positions are filled across occlusions, they must be marked `INTERPOLATED`, never `OBSERVED`.

---

## 2. Ingestion Job & Video Metadata Schema

```json
{
  "job_id": "uuid",
  "video_id": "uuid",
  "status": "QUEUED | PROCESSING | COMPLETED | FAILED | CANCELLED",
  "progress_pct": 0.0,
  "file_metadata": {
    "filename": "match_fc27_rivals_div1.mp4",
    "format": "mp4",
    "file_size_bytes": 142857140,
    "sha256": "64-character-hex-checksum",
    "duration_seconds": 720.5,
    "resolution_width": 1920,
    "resolution_height": 1080,
    "frame_rate": 60.0,
    "codec": "h264",
    "game_version": "FC27 | FC26",
    "game_patch": "PATCH_1.02",
    "match_mode": "COMPETITIVE_RIVALS | CHAMPIONS | SQUAD_BATTLES | FRIENDLY",
    "camera_preset": "TELE_BROADCAST | CO_OP | TACTICAL | DEFAULT"
  },
  "processing_profile": "FAST | BALANCED | HIGH_ACCURACY",
  "error_diagnostic": null,
  "created_at": "ISO-8601 UTC timestamp",
  "updated_at": "ISO-8601 UTC timestamp"
}
```

---

## 3. Scene Classification Contract

Every sampled video timestamp is classified into one of 12 distinct scene categories:

```json
{
  "video_id": "uuid",
  "frame_index": 120,
  "timestamp_sec": 4.0,
  "scene_class": "ACTIVE_GAMEPLAY | KICKOFF | GOAL_REPLAY | CINEMATIC_REPLAY | SET_PIECE | PAUSE_MENU | TACTICAL_MENU | CELEBRATION | HALFTIME | FULLTIME | LOADING_SCREEN | UNKNOWN",
  "confidence": 0.94,
  "is_camera_cut": false,
  "pitch_pixel_coverage": 0.62,
  "hud_visible": true,
  "minimap_visible": true
}
```

---

## 4. Fused 10 Hz Gameplay Telemetry Contract

Every time tick represents a synchronous snapshot across the entire visible pitch:

```json
{
  "video_id": "uuid",
  "frame_index": 300,
  "timestamp_sec": 10.0,
  "match_clock": "14:22",
  "calibration_state": "GOOD | COARSE | REJECTED",
  "reprojection_error_m": 0.85,
  "possession_team": "HOME | AWAY | CONTESTED | UNKNOWN",
  "ball_carrier_track_id": "trk_home_09",
  "ball": {
    "bbox_xywh": [0.452, 0.612, 0.012, 0.018],
    "pitch_xy_meters": [54.2, 38.1],
    "pitch_zone": 8,
    "velocity_mps": 6.8,
    "status": "OBSERVED",
    "confidence": 0.92
  },
  "players": [
    {
      "track_id": "trk_home_09",
      "team": "HOME",
      "is_goalkeeper": false,
      "is_selected": true,
      "player_slot": "ST",
      "verified_player_id": null,
      "card_item_id": null,
      "bbox_xywh": [0.448, 0.580, 0.032, 0.082],
      "pitch_xy_meters": [53.5, 37.8],
      "pitch_zone": 8,
      "velocity_mps": 4.8,
      "acceleration_mps2": 1.2,
      "status": "OBSERVED",
      "confidence": 0.96
    }
  ],
  "team_metrics": {
    "home_width_m": 42.5,
    "home_depth_m": 31.0,
    "home_hull_area_m2": 780.4,
    "away_width_m": 38.2,
    "away_depth_m": 26.5,
    "away_hull_area_m2": 695.1
  }
}
```

---

## 5. Tactical Event Contract

```json
{
  "event_id": "uuid",
  "video_id": "uuid",
  "timestamp_start": 24.5,
  "timestamp_end": 27.0,
  "event_type": "PRESS_ATTEMPT | DEFENSIVE_RECOVERY | TRANSITION_BREAK | OVERLAPPING_RUN | LINE_BREAK_PASS | COMPLETED_PASS | TURNOVER | BOX_ENTRY",
  "team_identity": "HOME | AWAY",
  "participating_track_ids": ["trk_home_07", "trk_away_04"],
  "pitch_zone": 11,
  "pitch_xy_start": [62.0, 22.4],
  "pitch_xy_end": [78.5, 18.2],
  "observed_action": "High-intensity press closed down to 2.8m at 5.2 m/s",
  "observed_outcome": "PRESSURE_APPLIED | TURNOVER_FORCED | BEATEN",
  "observation_method": "CV_ASSISTED",
  "review_status": "UNDER_REVIEW | ACCEPTED | REJECTED | MODIFIED",
  "confidence": 0.88,
  "integrity_hash": "64-character-sha256-seal"
}
```

---

## 6. Manual Evidence Review Contract

When an analyst or user corrects an observation (e.g. updating team assignment or discarding false ball detection), the original perception record is preserved and a non-destructive audit entry is appended:

```json
{
  "review_id": "uuid",
  "event_or_track_id": "uuid",
  "reviewer_id": "user_id_or_anonymous",
  "timestamp": "ISO-8601 UTC timestamp",
  "change_type": "IDENTITY_CORRECTION | TEAM_CORRECTION | BALL_CORRECTION | CALIBRATION_OVERRIDE | EVENT_VERDICT",
  "original_value": { "team": "AWAY" },
  "corrected_value": { "team": "HOME" },
  "review_verdict": "ACCEPTED | REJECTED",
  "reason": "Kit clash resolution: Away wore black, referee wore yellow"
}
```
