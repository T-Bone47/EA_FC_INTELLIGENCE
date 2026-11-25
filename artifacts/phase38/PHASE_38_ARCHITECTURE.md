# PHASE 38: TECHNICAL ARCHITECTURE SPECIFICATION
## Automated Gameplay Vision & Empirical Intelligence Foundation

**Milestone:** Phase 38 — Perception Engine Foundation  
**Version:** 3.8.0  
**Target Environment:** Local Windows x64 (RTX 3050 4GB / Core i5 / Multithreaded CPU Fallback)  
**Budget:** ₹0 (Zero cloud APIs, zero proprietary dependencies)  

---

## 1. High-Level Architectural Flow

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                           RECORDED GAMEPLAY INGESTION                             │
│       User Upload (.mp4 / .webm) ──► Metadata Inspection ──► Job Dispatcher       │
└─────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │
                                          ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                       PHASE 38C: SCENE UNDERSTANDING                              │
│       Frame Differencing & Color Histogram ──► Scene Classification               │
│       [ACTIVE_GAMEPLAY, REPLAY, PAUSE_MENU, CELEBRATION, HALFTIME, LOADING]      │
│       (Camera Cut & Transition Detection ──► Reconcile / Reset Tracker)           │
└─────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │ (Frames classified as ACTIVE_GAMEPLAY)
                                          ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                  PHASE 38D: THREE COOPERATING PERCEPTION CHANNELS                 │
│                                                                                   │
│  ┌─────────────────────────┐  ┌───────────────────────┐  ┌─────────────────────┐  │
│  │  CHANNEL 1: BROADCAST   │  │  CHANNEL 2: MINIMAP   │  │   CHANNEL 3: HUD    │  │
│  │  - Outfield Players     │  │  - Boundary Detection │  │  - Match Clock      │  │
│  │  - Goalkeepers & Ref    │  │  - Icon Segmentation  │  │  - Score & Teams    │  │
│  │  - Ball (ROI Search)    │  │  - Team Color (HSV)   │  │  - Player Name Tag  │  │
│  │  - Selected Marker      │  │  - Coarse Pitch Pos   │  │  - PlayStyle Badge  │  │
│  └────────────┬────────────┘  └───────────┬───────────┘  └──────────┬──────────┘  │
└───────────────┼───────────────────────────┼─────────────────────────┼─────────────┘
                │                           │                         │
                ▼                           ▼                         ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                    PHASE 38E: MULTI-OBJECT TRACKING (BYTETRACK)                   │
│   Two-Stage Kalman Association: High-Conf BBoxes ──► Unmatched Low-Conf Recovery │
│   Camera Motion Compensation (Affine Pan Offset) ──► Persistent Session Tracks    │
└─────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │
                                          ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                  PHASE 38F: PITCH CALIBRATION & HOMOGRAPHY (DLT)                  │
│   Landmark Detection (Penalty Arc, Box Corners, Lines) ──► DLT via SVD + RANSAC   │
│   Metric Transformation: Screen (x, y) ──► Pitch 105m x 68m, 15 Tactical Zones    │
│   Quality Gate: Reprojection Error < 2.0m [GOOD] | 2-4m [COARSE] | >4m [REJECTED]  │
└─────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │
                                          ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                     PHASE 38G: MULTI-SOURCE EVIDENCE FUSION                       │
│   Cross-Channel Alignment: Broadcast Coordinate + Minimap Verification            │
│   Status Tagging: [OBSERVED, INFERRED, INTERPOLATED, UNKNOWN, REJECTED]           │
│   Output: Provenance-Preserved 10 Hz Telemetry Series with SHA-256 Checksum       │
└─────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │
                                          ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                   PHASE 38H: INITIAL GAMEPLAY UNDERSTANDING                       │
│   Possession Ownership ──► Passes (Potential & Completed) ──► Turnovers           │
│   Team Width & Depth ──► Convex Hull Shape ──► Defensive Transitions              │
│   Zone Ball Progression (Defensive Third ──► Middle Third ──► Attacking Third)   │
└─────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │
                                          ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│               PHASE 38I: GAMER-FACING GAMEPLAY STUDIO & COCKPIT                   │
│   Synchronized HTML5 Video Player + Interactive 2D Pitch Radar Canvas             │
│   Timeline Scrubbing ──► Event Markers ──► Bounding Box Overlays                  │
│   Initial Match Summary Metrics ──► Manual Evidence Review Layer (Audited)        │
└───────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Ingestion Subsystem (Phase 38B)

### 2.1 Supported Media Container Formats
- **MP4 (`video/mp4`):** Primary standard for PC and console recorded gameplay (OBS, Xbox Game Bar, PS5 Share).
- **WebM (`video/webm`):** Browser-native capture format.
- **MOV (`video/quicktime`):** Supported via standard H.264/AAC tracks.

### 2.2 Container Inspection & Metadata Validation
The ingestion service executes a multi-stage validation without loading entire videos into RAM:
1. **Magic Header Inspection:** Reads initial 32 bytes to verify standard atom boxes (`ftyp`, `moov`, `mdat`).
2. **Native Atom Parser:** Traverses top-level box offsets to extract:
   - `mvhd` (Movie Header): Timescale, duration in seconds.
   - `tkhd` (Track Header): Display dimensions (width, height in pixels).
   - `mdhd` / `stsd` (Media Header / Sample Description): Codec signature (`avc1` / H.264, `vp09` / VP9).
3. **External Probe Fallback:** If `ffprobe` or `ffmpeg` is available in system PATH, extracts presentation timestamps and keyframe intervals.
4. **Content Checksum:** Computes streaming SHA-256 checksum over the file for deduplication and tamper-evidence.

### 2.3 Job Processing Lifecycle
```
UPLOADED ──► VALIDATED ──► PROCESSING (0-100%) ──► COMPLETED
    │            │              │
    └──► REJECTED └──► CANCELLED └──► FAILED (with error diagnostics)
```
- **Job States:** `QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED`, `CANCELLED`.
- **Cancellation & Cleanup:** Active jobs can be aborted by the user; temporary chunk files and decoding buffers are immediately unlinked.

---

## 3. Scene Understanding Module (Phase 38C)

To prevent replay footage, goal celebrations, or tactical menus from polluting match statistics, every sampled frame is classified into 12 mutually exclusive scene categories:

| Scene Class | Visual Signature & Detection Method | Action on Tracking State |
|---|---|---|
| `ACTIVE_GAMEPLAY` | Green pitch dominates 40–80% of frame; HUD elements (score/clock/minimap) visible; players dispersed. | **Active Tracking** |
| `KICKOFF` | Players clustered in regulation kickoff positions around center circle. | Reset tracking; tag half kickoff |
| `GOAL_REPLAY` | Broadcast wipe transition; tight player zoom without HUD score/clock; alternate camera angle. | **Abstain** (Freeze tracking) |
| `CINEMATIC_REPLAY`| Dynamic close-up, slow motion, broadcast lower-third graphics active. | **Abstain** |
| `SET_PIECE` | Static dead-ball formation (corner, free-kick, penalty box cluster). | Mark set-piece state |
| `PAUSE_MENU` | Darkened gameplay background with central translucent modal cards. | **Abstain** |
| `TACTICAL_MENU` | Full-screen squad management screen (formation layout, card benches). | **Abstain**; extract team sheet if visible |
| `CELEBRATION` | Camera zooms on goalscorer; pitch coverage drops below 30%; crowd or corner flag visible. | **Abstain** |
| `HALFTIME` | Transition sequence, halftime match statistics overlay, players walking off. | Tag half boundary |
| `FULLTIME` | Full-time match summary overlay, final whistle sequence. | Terminate match session |
| `LOADING_SCREEN`| Uniform background with EA FC game mode logos. | **Abstain** |
| `UNKNOWN` | Frame does not meet confidence threshold for any category. | **Abstain with Explicit Flag** |

### 3.1 Transition & Camera Cut Detection
- Computes normalized color histogram Bhattacharyya distance between consecutive sampled frames.
- A distance $>0.65$ indicates a hard cut:
  - If entering non-gameplay scene $\to$ pause perception.
  - If re-entering `ACTIVE_GAMEPLAY` $\to$ re-initialize ByteTrack track IDs to prevent false identity linking across cuts.

---

## 4. Multi-Channel Perception Engine (Phase 38D)

### Channel 1: Broadcast Perception
- **Outfield Players & GKs:** Bounding box $[x, y, w, h]$ normalized to $[0, 1]$.
- **Jersey Color Classification:** Evaluates upper 40% of player bounding box in HSV space. Computes histogram dominant hue and saturation to assign player to `HOME` (Team 1) or `AWAY` (Team 2).
- **Goalkeeper Separation:** Classified based on distinct kit hue differing from both outfield teams and proximity to penalty boxes.
- **Dedicated Ball Detection:**
  - Fast ROI search around current ball-carrier track.
  - White/high-contrast spherical contour filter with aspect ratio $w/h \in [0.8, 1.2]$.
  - Physical velocity gate: trajectories exceeding $45\text{ m/s}$ (162 km/h) are rejected as false visual artifacts.
- **Selected Player Indicator:** Detects inverted triangle marker over player head (cyan/red/green indicator hue).

### Channel 2: Minimap Intelligence
- **Bounding & Segmentation:** Evaluates lower-center viewport $[x \in [0.4, 0.6], y \in [0.85, 0.98]]$.
- **Circle & Icon Extraction:** Detects circular pitch outline and isolates high-contrast team dots ($4\text{ px}$ to $8\text{ px}$).
- **Coarse Pitch Mapping:** Maps minimap 2D position directly into canonical $105\text{m} \times 68\text{m}$ pitch coordinates.
- **Off-Screen Recovery:** Provides approximate spatial locations for defending fullbacks or wingers not currently framed by the broadcast camera.

### Channel 3: HUD Contextual Intelligence
- **Match Clock:** OCR/template matching on top-left scorebox. Distinguishes video runtime (e.g., `04:12`) from in-game accelerated clock (e.g., `32:15`).
- **Scoreline:** Monitors integer transitions in score elements (rejects non-monotonic or jittery fluctuations).
- **Player Name Tag:** Reads lower-screen player identification banner during possession.

---

## 5. Multi-Object Tracking Engine (Phase 38E)

Adapts **ByteTrack** two-stage data association:
1. **State Representation:** Each track maintains Kalman state $[x, y, a, h, \dot{x}, \dot{y}, \dot{a}, \dot{h}]$ where $(x, y)$ is bbox center, $a$ is aspect ratio, $h$ is height, and derivatives denote velocities.
2. **Stage 1 (High-Confidence):** Matches detections with confidence $\ge 0.5$ to existing tracks using IoU distance with maximum threshold $0.8$.
3. **Stage 2 (Low-Confidence Recovery):** Matches remaining unassociated tracks against low-confidence detections ($0.1 \le \text{conf} < 0.5$) using IoU distance with maximum threshold $0.5$.
4. **Camera Motion Compensation (CMC):** Calculates frame-to-frame background translation offset $(\Delta x, \Delta y)$ to adjust predicted track positions during camera pans.
5. **Track Lifecycle:** Tracks without matching detections for $>30$ frames are marked lost and subsequently terminated.

---

## 6. Spatial Reconstruction & Pitch Calibration (Phase 38F)

### 6.1 Direct Linear Transformation (DLT) & RANSAC Homography
To project image pixel coordinates $(u, v)$ to metric pitch coordinates $(X, Y) \in [0, 105]\text{m} \times [0, 68]\text{m}$:
$$\begin{bmatrix} s X \\ s Y \\ s \end{bmatrix} = \mathbf{H} \begin{bmatrix} u \\ v \\ 1 \end{bmatrix}$$
where $\mathbf{H}$ is a $3 \times 3$ planar homography matrix.
- **Point Extraction:** Direct linear transformation solved via Singular Value Decomposition (SVD) of matrix $\mathbf{A} \mathbf{h} = 0$.
- **RANSAC Inlier Fitting:** Evaluates landmark correspondences (touchlines, 18-yard box corners, penalty arcs, center circle points) across 500 iterations with inlier tolerance $\epsilon = 3.0\text{ px}$.
- **Ground-Contact Projection:** Projects the bottom-center of the player bounding box $(u + w/2, v + h)$ rather than the centroid, eliminating perspective height distortion.

### 6.2 Quality State Categorization
- **`GOOD` (Reprojection Error $< 2.0\text{ m}$):** Fully calibrated; accepted for tactical metric calculations.
- **`COARSE` (Reprojection Error $2.0\text{ m} - 4.0\text{ m}$):** Approximate positioning; tagged as estimated.
- **`REJECTED` (Reprojection Error $> 4.0\text{ m}$ or $< 4$ inliers):** Discard coordinate projection; fallback to image-space tracking or minimap position.

---

## 7. Multi-Source Evidence Fusion & Telemetry (Phase 38G)

The fusion engine reconciles Channel 1 (broadcast), Channel 2 (minimap), Channel 3 (HUD), and temporal tracks into a unified 10 Hz time-series.

### Observation Status Hierarchy
Every player/ball coordinate is explicitly stamped with its provenance:
- **`OBSERVED`:** Directly detected by broadcast camera with `GOOD` pitch calibration.
- **`INFERRED`:** Derived from minimap icon mapping or high-confidence temporal kinematics.
- **`INTERPOLATED`:** Computed via linear spline across brief visual occlusions ($\le 0.5\text{ s}$).
- **`UNKNOWN`:** Entity absent or occluded beyond interpolation threshold.
- **`REJECTED`:** Detections discarded due to calibration failure, impossible velocity, or scene cut.

---

## 8. Tactical Event Perception (Phase 38H)

Integrates with Phase 37 event taxonomy:
1. **Possession State:** Continuous tracking of ball carrier (distance $\le 2.0\text{ m}$, velocity alignment $\ge 0.7$).
2. **Pass Detection:** Ball leaves carrier at velocity $\ge 8\text{ m/s}$, travels across pitch zones, and arrives within $2.5\text{ m}$ of a teammate (`COMPLETED_PASS`) or opponent (`TURNOVER`).
3. **Pressing Triggers:** Defending player accelerates ($\ge 4.5\text{ m/s}$) towards the ball carrier within $4.0\text{ m}$.
4. **Team Shape Metrics:** Computes team width (lateral distance between widest outfielders), team depth (longitudinal distance between highest forward and lowest defender), and effective convex hull area ($m^2$).

---

## 9. Performance & Hardware Profiles (Phase 38 Execution)

| Profile | Frame Sampling | Resolution | Detector Backend | Target Device | Expected Throughput |
|---|---|---|---|---|---|
| **Fast** | 2 Hz (every 5th frame) | 640x360 | Heuristic / Lightweight | CPU (4-8 threads) | 45–60 FPS |
| **Balanced (Default)** | 5 Hz (every 2nd frame) | 960x540 | Anchor-free ONNX / CV | CPU or RTX 3050 | 25–35 FPS |
| **High Accuracy** | 10 Hz (full rate) | 1280x720 | Full-resolution / FP16 | RTX 3050 (4 GB VRAM) | 15–20 FPS |
