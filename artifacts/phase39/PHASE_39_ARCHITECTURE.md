# Phase 39: System Architecture Report
## Real Video Frame Decoding, Spatial Intelligence & Tactical Coaching Engine

**Milestone:** Phase 39 — Path B (Real Video Frame Decoding + Spatial Intelligence & Coaching)  
**Baseline:** Frozen V3.2.1 Core (100% untouched parity preserved)  
**Runtime Compute Profile:** NVIDIA GeForce RTX 3050 Laptop GPU (4096 MiB OpenCL) + CPU Fallback, Windows 11, Python 3.15.1  

---

## 1. End-to-End Architecture Diagram

```text
User Match Recording (.mp4 / .webm / .mov)
   │  (HTTP Multipart Upload -> VideoIngestionService)
   ▼
[Stage 2: PyAV Stream Decoder (av 19.0.2)]
   │  - Probe container streams & timestamps (PTS * time_base)
   │  - Adaptive sampling (2 Hz FAST / 5-10 Hz BALANCED / 10 Hz HIGH_ACCURACY)
   │  - Bounded frame streaming (zero full-video RAM buffering) + mid-stream cancel
   ▼
[Scene Understanding & Optical Flow (OpenCV 5.1.0 + OpenCL RTX 3050)]
   │  - 12-Class SceneClassifier (pitch coverage + scoreboard/minimap HUD + cuts)
   │  - Exclude menus, celebrations, goal replays; reset tracker on cuts
   │  - Lucas-Kanade Optical Flow camera-pan compensation (dx_norm, dy_norm)
   ▼
[Pitch Registration & Multi-Channel Perception]
   ├── Channel 1: PixelPerceptionExtractor (HSV turf subtraction -> foreground
   │              contours -> KMeans 2-team torso clustering -> small-object ball ROI;
   │              or optional ONNX weights via cv2.dnn when backend/models/fc_detector.onnx exists)
   ├── Channel 2: Minimap HUD connected-components blip extraction -> coarse [0..105]x[0..68]
   ├── Channel 3: Scoreboard contrast banner check (sets unparsed fields to UNKNOWN cleanly)
   └── Calibration: White pitch-line HoughLinesP + DLT SVD RANSAC (GOOD/COARSE/REJECTED)
                    OR Manual 4+ Landmark Correspondence Fallback (/api/research/calibration/{id})
   ▼
[ByteTrack Adapter (SciPy linear_sum_assignment + Kalman Filter)]
   │  - Two-stage high/low IoU+distance matching with LK pan offset
   ▼
[MultiSourceFusionService -> FusedFrameTelemetry (10 Hz)]
   │  - Stamps DataProvenance: REAL_VIDEO_DECODED | IMPORTED_MATCH_TRACE | SYNTHETIC_FIXTURE
   │  - Individual states: OBSERVED | INFERRED | INTERPOLATED | UNKNOWN | REJECTED
   ▼
[Stage 3: SpatialIntelligenceEngine]
   │  - Uncertainty gate (LOW / MODERATE / HIGH / UNRELIABLE)
   │  - Kinematics (vx, vy, speed, ax, ay, accel) + physical speed anomaly guard
   │  - 21x14 Spearman-inspired anisotropic Gaussian Influence grid (HEURISTIC_GAUSSIAN_INFLUENCE)
   │  - Karun Singh 12x8 Expected Threat (xT) & lateral passing corridor openness
   │  - Def/Mid/Att lines, 5 lateral channels, 18-zone numerical overloads, hull trails & heatmaps
   ▼
[Stage 4 & 5: CoachingDiagnostics & PlayStyle Intelligence]
   │  - 12 sustained tactical mistake classes with all 7 required coaching elements
   │  - 10 PlayStyles+ strictly gated across EXPLICIT_HUD_OBSERVED | BEHAVIOUR_CONSISTENT | UNKNOWN_ACTIVATION
   ▼
[Stage 7: SquadCoachingBridge] -> Causal Attribution (Decision/Instructions/Formation BEFORE Upgrades)
   │  - Routes cleanly to /intelligence?position=..., /search?position=..., /cards/squad-lab
   │  - Frozen V3.2.1 weights remain strictly untouched
   ▼
[Stage 6: Gameplay Studio Cockpit (React + HTML5 <video> + 2D Radar SVG)]
   - HTTP 206 byte-range video stream synced lockstep with interactive pitch overlays
```

---

## 2. Provenance & Evidence Isolation Contract

Every ingestion job, frame sample, tactical diagnostic, and Squad Lab recommendation carries explicit provenance separation (`backend/domain/video_ingestion.py`):
- `REAL_VIDEO_DECODED`: Extracted from decoded packets of an authentic `.mp4`, `.webm`, or `.mov` bitstream.
- `IMPORTED_MATCH_TRACE`: Imported from verified external normalized coordinates (`/api/research/traces/import`).
- `MANUAL_ANNOTATION`: Created/verified directly by analyst actions.
- `SYNTHETIC_FIXTURE`: Generated test fixtures (`_build_synthetic_fixture_telemetry` / `SyntheticFixtureDetector`), **never** auto-used when real decoding fails unless `?allow_synthetic_fixture=true` is explicitly opted in, and strictly blocked (`provenance_gated=True`) from issuing card upgrade recommendations in Squad Lab.
