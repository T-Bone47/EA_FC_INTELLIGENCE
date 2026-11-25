# PHASE 38: BASELINE AUDIT & REPOSITORY VERIFICATION
**Milestone:** Phase 38A — Repository Audit & Baseline  
**Date:** 2026-11-24  
**Project:** EA FC Intelligence — Stadium 3.0  
**Status:** CERTIFIED BASELINE ESTABLISHED  

---

## 1. System Execution Environment
- **Operating System:** Windows 11 x64
- **Runtime Engines:**
  - Python 3.15.1 (FastAPI 0.110.1, Uvicorn 0.25.0, NumPy 2.5.4, Pillow 13.0.0, Pydantic 2.14.1, Psycopg 3.3.9)
  - Node.js v26.12.1 (Vite 5.4.21, React 18.2.0, Vitest 2.1.9, Playwright 1.50)
  - PostgreSQL 16.16 Embedded Cluster (`127.0.0.1:5432`, database: `eafc_intelligence`)
- **Hardware Profile:**
  - Intel Core i5 12th Gen
  - NVIDIA GeForce RTX 3050 (4 GB VRAM)
  - 16 GB DDR4 System RAM

---

## 2. Test Baseline Verification

### 2.1 Backend Certified Regression Suite
- **Command:** `C:\Python315\python.exe -m pytest <15 certified engine modules> -v`
- **Modules Verified:**
  1. `backend/tests/test_squad_synergy.py` (5 passed)
  2. `backend/tests/test_partnership_intelligence.py` (7 passed)
  3. `backend/tests/test_recommendation_stability.py` (2 passed)
  4. `backend/tests/test_empirical_evaluator.py` (3 passed)
  5. `backend/tests/test_video_cv_pipeline.py` (4 passed)
  6. `backend/tests/test_video_research_api.py` (6 passed)
  7. `backend/tests/test_automated_event_detector.py` (6 passed)
  8. `backend/tests/test_radar_fusion_pipeline.py` (4 passed)
  9. `backend/tests/test_bayesian_calibration.py` (4 passed)
  10. `backend/tests/test_phase37_api.py` (4 passed)
  11. `backend/tests/test_phase30_card_lab.py` (4 passed, 2 skipped)
  12. `backend/tests/test_striker_pilot.py` (6 passed)
  13. `backend/tests/test_v3_2_config.py` (11 passed)
  14. `backend/tests/test_golden_fixtures_v3_2.py` (6 passed — 100% bit-exact frozen core)
  15. `backend/tests/test_phase28_formation.py` (14 passed)
- **Result:** **88 passed, 2 skipped, 0 failed** in 16.93s. Zero regressions.

### 2.2 Frontend Vitest Test Suite
- **Command:** `npm test -- --run`
- **Result:** **100 passed, 3 skipped, 0 failed** across 18 test files in 19.25s.
- **Production Build:** `npm run build` succeeds in 1.52s (457 kB JS, 79 kB CSS).

---

## 3. Existing Video & Gameplay Intelligence Architecture
The existing architecture (implemented in Phases 36 and 37) established the research foundations:
1. **Frontend Studio Cockpit:** `GameplayStudio.tsx` (`/research/gameplay-studio`) with tabs:
   - *Video Perception Cockpit:* Displays registered gameplay videos, tactical events, and feature vectors.
   - *Automated Event Recognition:* Proposes pressing triggers, transition breaks, and line-break passes.
   - *2D Tactical Radar Replay:* Renders 22-player positions on pitch canvas from fused telemetry.
   - *Bayesian Diagnostics:* Reliability diagrams, Brier score calibration curves, and parameter simulation.
   - *Prediction Challenges:* Evaluates engine hypotheses against match observations.
2. **Backend API Endpoints (`backend/api/routes/video_research.py`):**
   - `GET /api/research/videos`: Lists registered research gameplay footage.
   - `POST /api/research/videos`: Registers new footage (enforces rights checks).
   - `GET /api/research/videos/{video_id}/events`: Returns certified tactical events.
   - `GET /api/research/fused-telemetry/{video_id}`: Synthesizes 10 Hz 22-player + ball spatial pitch telemetry.
   - `POST /api/research/automated-detection`: Executes event recognition algorithms over telemetry.
   - `GET /api/research/bayesian-calibration`: Produces prior/posterior parameter shrinkage.
   - `POST /api/research/simulate-recommendation`: Simulates V3.3 calibration scores.
3. **Database & Ingestion:**
   - Database `eafc_intelligence` active on `127.0.0.1:5432`.
   - 16,228 canonical FC26 players.
   - 19,789 research FC27 players (`fc27-players-2026-09-r1`).
   - Catalog-serving views and migrations 001–011 intact.

---

## 4. Technical Gaps & Deficiencies for Phase 38

| Area | Current State (Phase 37) | Phase 38 Requirement |
|---|---|---|
| **Video Ingestion** | Metadata registration only (Path A / YouTube URLs). No raw binary file upload or local decoding. | Full multi-format upload subsystem (MP4, WebM, MOV) with content hashing, metadata inspection, progress tracking, and storage quotas. |
| **Scene Understanding** | Implicitly assumes all footage is active gameplay. | Dedicated frame scene classifier (`ACTIVE_GAMEPLAY`, `REPLAY`, `PAUSE_MENU`, `CELEBRATION`, etc.) with transition cut detection and tracking reset. |
| **Perception Channels** | Fused telemetry is generated from parameterized fixtures. | Three real perception channels: Channel 1 Broadcast detection, Channel 2 Minimap extraction, Channel 3 HUD OCR/clock extraction. |
| **Object Tracking** | Coordinate interpolation without association engine. | Multi-object tracking adapter (ByteTrack / Kalman filter two-stage association) with persistent session track IDs and occlusion handling. |
| **Spatial Calibration** | Simplified non-linear perspective formula. | Full Direct Linear Transformation (DLT) with SVD and RANSAC homography estimation, landmark detection, and reprojection error metrics (`GOOD`, `COARSE`, `REJECTED`). |
| **Evidence Fusion** | Fixed weighted blending without status flags. | Multi-source provenance-preserving fusion tracking `OBSERVED`, `INFERRED`, `INTERPOLATED`, `UNKNOWN`, `REJECTED` states at 10 Hz. |
| **Studio UX** | Independent canvas animation; no video file synchronization. | Synchronized dual-cockpit (HTML5 video player scrubbed in lockstep with 2D radar), drag-and-drop uploader, and manual evidence review layer. |

---

## 5. Architectural Commitment
- **Zero Modification of Frozen Core:** `backend/engine/v3_2/` and golden fixtures remain untouched.
- **Local-First & ₹0 Budget:** Self-contained execution on Windows with NumPy, Pillow, and clean modular adapters for ONNX/GPU acceleration.
- **Epistemic Honesty:** All metrics distinguish direct observations from inferences; no synthetic test fixtures are promoted to canonical evidence.
