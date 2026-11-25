# Phase 38: Limitations and Next Steps Report

## 1. Known Architectural & Perception Limitations

While Phase 38 establishes a robust, zero-cost, fully certified perception pipeline, the following domain-specific challenges have been identified and documented:

### 1.1 Dynamic Broadcast Camera Zooms & Close-Ups
- **Description:** During rapid transitions, extreme close-up zoom cuts, or goalkeeper goal-kicks, pitch line intersections may drop below the required 4 non-collinear keypoint correspondences.
- **Current Handling:** The DLT homography service detects the deficiency, marks `pitch_calibration_state` as `REJECTED`, flags coordinates as `UNKNOWN`, and disables spatial distance metrics until calibration is re-established.
- **Future Improvement:** Employ temporal homography propagation using optical flow / Lucas-Kanade feature tracking to bridge uncalibrated gaps (< 1.0 s).

### 1.2 Severe Dense Cluster Occlusion (Corner Kicks & Goalmouth Scrambles)
- **Description:** When 8–12 players converge in the 6-yard box during corner kicks, 2D bounding boxes overlap heavily, causing temporary identity switches in standard ByteTrack.
- **Current Handling:** Tracks with ambiguous Kalman covariance are decoupled; possession is classified as `CONTESTED` rather than falsely attributing control.
- **Future Improvement:** Incorporate jersey number OCR and multi-camera / minimap cross-validation to maintain continuous track identity through scrums.

### 1.3 Off-Screen Outfield Players
- **Description:** In standard broadcast camera views (Tele Broadcast / Co-op), opposing wingers or deep sweepers often remain off-screen.
- **Current Handling:** Channel 2 minimap radar extraction detects off-screen blips and infers coarse coordinates, marking their status as `INFERRED` rather than `OBSERVED`.
- **Future Improvement:** Super-resolve the minimap bounding area using bilinear interpolation and adaptive color thresholding to increase coordinate resolution.

---

## 2. Immediate Next Steps for Phase 39

1. **Phase 39 Real-World Gameplay Ingestion:** Run real match recordings through the ingestion pipeline (`ivshwl8WrJA` PSG vs Real Madrid) and generate accepted empirical evidence records.
2. **Advanced Spatial Heatmaps & Pitch Control:** Implement Voronoi / Gaussian Pitch Control Field models based on the 10 Hz fused telemetry streams.
3. **Automated Tactical Error Diagnostics:** Identify tactical mistakes (e.g. out-of-position fullbacks, failed offside traps, excessive gap between midfield and defense) directly from empirical tracking data.
4. **Player Suitability Cross-Validation:** Correlate empirical player sprint bursts and recovery runs with Ultimate Team card ratings and PlayStyles.
