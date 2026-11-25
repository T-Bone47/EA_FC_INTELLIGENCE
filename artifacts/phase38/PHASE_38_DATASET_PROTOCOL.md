# PHASE 38: DATASET CURATION & BENCHMARKING PROTOCOL
**Milestone:** Phase 38 — Perception Engine Foundation  
**Date:** 2026-11-24  
**Project:** EA FC Intelligence — Stadium 3.0  
**Status:** APPROVED FOR REPRODUCIBILITY  

---

## 1. Principles of Empirical Video Ground-Truth

1. **Strict Match-Level Partitioning:** Adjacent frames in continuous football footage share near-identical player positions and background lighting. Splitting train/test by random frame selection causes extreme data leakage and false benchmark inflations. All evaluation datasets are strictly partitioned by entire match recordings or discrete, unlinked gameplay sessions.
2. **Epistemic Honesty:** Synthetic simulator footage (e.g. Google Research Football or synthetic coordinate fixtures) must remain strictly tagged and firewalled from real EA FC gameplay evaluation.
3. **Multi-Domain Stratification:** Evaluation clips must be stratified across:
   - **Game Editions:** EA SPORTS FC 26 vs FC 27.
   - **Game Modes:** Ultimate Team Rivals, Champions, Squad Battles, Kick-off.
   - **Camera Presets:** Tele Broadcast (default), Co-Op, Tactical.
   - **Kit Contrasts:** High-contrast (e.g., White vs Red), Dark-on-Dark, Clash scenarios (Referee wearing similar tone).
   - **Resolutions:** 1080p60, 720p60, 4K30.

---

## 2. Dataset Manifest Schema

Every accepted video research clip is registered in `fc27_video_dataset_manifest.json`:

```json
{
  "dataset_id": "eafc-cv-eval-v1",
  "version": "1.0.0",
  "total_matches": 30,
  "total_annotated_frames": 9000,
  "sources": [
    {
      "clip_id": "clip_fc27_001_counter",
      "game_version": "FC27",
      "game_patch": "PATCH_1.02",
      "match_mode": "COMPETITIVE_RIVALS",
      "camera_preset": "TELE_BROADCAST",
      "resolution": "1920x1080",
      "frame_rate": 60,
      "duration_sec": 30.0,
      "sha256": "4b684...f8",
      "annotated_frames_count": 300,
      "split": "TEST",
      "annotator_id": "lead_analyst_01",
      "annotation_source": "CVAT_1.1_EXPORT"
    }
  ]
}
```

---

## 3. Evaluation Annotation Protocol (CVAT Standard)

Ground-truth labeling conforms to standard CVAT 1.1 video annotations:
1. **Bounding Box Classes:**
   - `outfield_home`: Outfield player belonging to Home team.
   - `outfield_away`: Outfield player belonging to Away team.
   - `goalkeeper_home` / `goalkeeper_away`: Goalkeepers.
   - `referee`: Match official.
   - `ball`: Match ball.
   - `selected_marker`: Inverted triangle indicator.
2. **Pitch Landmark Keypoints (for Homography Ground Truth):**
   - Minimum 4 point correspondences per frame (e.g. Penalty box corners, 6-yard box corners, penalty spot, center-circle intersections).
   - Metric pitch ground truth $(X, Y)$ recorded in canonical $[0, 105]\text{m} \times [0, 68]\text{m}$ coordinate space.
3. **Tracking Continuity:**
   - Consistent track ID assigned across all continuous visible frames.
   - Re-ID verified upon player emergence from physical duels or pile-ups.

---

## 4. Benchmark Metric Formulations

In accordance with Section 17 of the Phase 38 Directive, performance is evaluated across:

### 4.1 Detection & Classification Metrics
* **Precision ($P$), Recall ($R$), F1-Score ($F_1$):**
  $$P = \frac{TP}{TP + FP}, \quad R = \frac{TP}{TP + FN}, \quad F_1 = \frac{2 P R}{P + R}$$
  Evaluated at $IoU \ge 0.50$ across outfield players and ball.
* **Team Classification Accuracy:**
  Fraction of correctly assigned Home/Away labels on ground-truth detected players.

### 4.2 Tracking Metrics (TrackEval Standard)
* **IDF1 (Identification F1):**
  $$IDF1 = \frac{2 IDTP}{2 IDTP + IDFP + IDFN}$$
  Measures tracking identity continuity over the entire duration of play.
* **Identity Switches (IDSW):** Total count of identity switches between tracks.

### 4.3 Spatial Localization Metrics
* **Median Pitch Error ($E_{\text{pitch}}$):**
  Euclidean distance between projected pitch coordinates and ground truth:
  $$\Delta d = \sqrt{(X_{\text{pred}} - X_{\text{gt}})^2 + (Y_{\text{pred}} - Y_{\text{gt}})^2}$$
  Reported in meters; benchmark acceptance requires median error $\le 2.0\text{ m}$.
