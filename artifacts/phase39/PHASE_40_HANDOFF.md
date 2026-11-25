# Phase 40: Handoff Blueprint & Honest Status Audit

## 1. Feature Classification Ledger

### Implemented and Validated Across Real Encoded Media Bitstreams + Unit/E2E Suites
- Genuine backend video probing & frame streaming (`PyAV 19.0.2`: `.mp4`, `.mov`, `.webm`) with timestamp accuracy, adaptive sampling, corrupt-packet skipping, and mid-stream cancellation.
- HTTP 206 Byte-Range streaming endpoint (`GET /api/research/videos/{id}/media`) driving synchronized HTML5 `<video>` playback in Gameplay Studio.
- Real pixel extraction (`PixelPerceptionExtractor`: HSV turf subtraction, morphological silhouettes, KMeans 2-team jersey classification, ball ROI gating, minimap connected components).
- Camera Motion Compensation (Lucas-Kanade sparse optical flow), Hough pitch-line calibration + SVD DLT/RANSAC, and manual 4-point correspondence calibration API + UI.
- Exact bipartite SciPy Hungarian ByteTrack association + Fusion (`REAL_VIDEO_DECODED`, `IMPORTED_MATCH_TRACE`, `SYNTHETIC_FIXTURE` strictly isolated).
- Stage 3 Spatial Intelligence Engine (21×14 Gaussian player influence `HEURISTIC_GAUSSIAN_INFLUENCE`, Karun Singh 12×8 `xT`, kinematics + anomaly guards, 5 channels, 18-zone overloads, passing lanes, uncertainty gates).
- Stage 4 Tactical Coaching Engine (all 12 mistake classes, 7 required fields, no controller assumptions).
- Stage 5 PlayStyle+ Behavioural Signature Matrix (10 PlayStyles+ across `EXPLICIT_HUD_OBSERVED`, `BEHAVIOUR_CONSISTENT`, `UNKNOWN_ACTIVATION`).
- Stage 7 Squad Coaching Bridge (6 causal classes, tactical-first prescriptions, zero edits to frozen V3.2.1 weights).
- Stage 6 Gameplay Studio Dual-Cockpit UI upgrades + live PostgreSQL (`eafc_intelligence`: 16,228 FC26 + 19,789 FC27 players).

### Implemented with Classical CV Fallback (Remaining Blockers for Supervised DL & Raw Console Captures)
1. **Supervised Neural Player/Ball Detector Weights (`backend/models/fc_detector.onnx`):**
   - *Status:* Pipeline adapter (`cv2.dnn.readNetFromONNX`) is implemented and hardware-ready, **but no pre-trained EA FC YOLOX `.onnx` weights file is shipped in this repository** (`onnx_weights_loaded: false`).
   - *Blocker / Next Step for Phase 40:* Train or place an Apache/MIT-licensed anchor-free YOLOX `.onnx` model fine-tuned on user-owned EA FC 26/27 captures at `backend/models/fc_detector.onnx` to handle stadium shadows, banner overlaps, and congested penalty-box scrums accurately.
2. **Real Owner Console/PC EA FC26/FC27 Gameplay Evaluation:**
   - *Status:* End-to-end real decoding was verified on PyAV-encoded compressed MP4/MOV/WebM clips (`_render_synthetic_pitch_clip`) and normalized imported tracking traces (`IMPORTED_MATCH_TRACE`). Zero unedited user-owned console match recordings existed in local workspace storage.
   - *Next Step for Phase 40:* Upload a genuine 30s–3m competitive FC27 Rivals/Champions `.mp4` recording in Gameplay Studio -> validate calibration quality (`Manual 4-Point Calibration` if dynamic camera zooms trigger `REJECTED`) -> accept/reject proposed tactical mistakes in the SHA-256 audit log to accumulate Tier B/A empirical calibration samples.
3. **Empirically Calibrated Pitch Control Weights:**
   - `SpatialModelMode.EMPIRICALLY_CALIBRATED_PITCH_CONTROL` schema path exists, while live calculations remain explicitly stamped `HEURISTIC_GAUSSIAN_INFLUENCE` until owner-annotated match clips populate calibrated likelihood fits via `scikit-learn` reliability curves.
