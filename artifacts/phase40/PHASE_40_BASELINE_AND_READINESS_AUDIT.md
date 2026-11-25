# PHASE 40A: Baseline & Readiness Audit

**Date:** 2026-11-25  
**Workspace:** EA FC Intelligence — Stadium 3.0  
**Target Baseline:** Frozen V3.2.1 Recommendation Engine

---

## 1. Pre-Phase-40 Implementation Verification

| Subsystem | Inspected Implementation Status | Honest Readiness Classification |
| :--- | :--- | :--- |
| **PostgreSQL 16 + FC26/FC27 Canonical Data** | Live embedded PostgreSQL on `127.0.0.1:5432`, migrations `002`–`012` applied (`game_version`, `user_profile`, `user_squad`, `game_player`, `ut_card`, `fc27_staging`). | **Verified & Running** |
| **Frozen V3.2.1 Recommendation Engine** | `recommendation_engine_v3.py`, `v3_config.py` (`v3.2-2026-09-30-r1`), golden invariants intact. | **Verified Frozen** |
| **Video Decoding (`PyAV 19.0.2`) & HTTP 206** | `real_video_decoder.py` & `GET /api/research/videos/{id}/media` decode compressed `.mp4`/`.mov`/`.webm`. | **Verified on Encoded Clips** |
| **Pixel Vision & Calibration** | `multi_channel_perception.py` (`OPENCL_GPU`/CPU, HSV+KMeans, Lucas-Kanade CMC, Hough+RANSAC, Hungarian ByteTrack). `backend/models/fc_detector.onnx` absent (`onnx_weights_loaded = false`). | **Classical Fallback Active / ONNX Unshipped** |
| **Spatial Intelligence & Coaching** | `spatial_intelligence.py` (`21x14` Gaussian influence + `12x8` Karun Singh xT), `tactical_coaching_engine.py` (12 mistakes), `playstyle_intelligence.py` (10 PlayStyles+), `squad_coaching_bridge.py`. | **Implemented on Traces & Encoded Clips** |
| **Genuine Owner Console/PC Video Samples** | Zero unedited owner EA FC26/FC27 retail console captures on disk prior to Phase 40. | **Blocked Pending User Media** |
| **Multi-Match Longitudinal Persistence** | Phase 36–39 stores (`_VIDEOS_STORE`, `_telemetry_store`, `_INGESTION_JOBS`) resided in process memory/JSON only. | **Upgraded in Phase 40B (Migration 015)** |

---

## 2. Pre-Phase-40 Baseline Suite Audit

1. **Focused V3.2.1 + Security + DB + Phase 30/31/37/38/39 Suite:**
   - Core Engine + Phase 38/39 run: **`97 passed, 3 skipped, 0 failed`** (`17.40s`).
   - V3 Invariants + API Contract + Security + PG DB run: **`63 passed, 2 skipped, 0 failed`** (`21.06s`).
2. **Legacy / Environment-Gated Full `pytest` Audit (`874 passed, 30 failed, 15 skipped`):**
   - `9` failures in `test_engine_adversarial_phase7.py`: Legacy **V2** (`RecommendationEngineV2`) tests superseded by V3.2.1.
   - `11` failures in `test_integration_production.py`: Legacy **V2** `RecommendationService` integration checks.
   - `4` failures in `test_engine_v3_real_data.py`: FC26 canonical distribution Spearman $\rho(R, \text{OVR})$ measured `0.863`–`0.911` vs tight historical `<= 0.85` band in that older test file.
   - `6` failures in `test_zero_budget_research.py`: Expects `ENVIRONMENT=test` / local host guards and owner card binary snapshot `fc27_card_items-local-r1` whereas runtime `.env` runs `ENVIRONMENT=development`.

---

## 3. Epistemic Pipeline Segregation Established for Phase 40

All Phase 40 persistence and Gamer DNA aggregation strictly classifies and isolates:
1. `REAL_VIDEO_DECODED` (Genuine multi-frame video decoded via PyAV + CV + calibration)
2. `IMPORTED_MATCH_TRACE` (Authorized normalized `[0..1]` external JSON/CSV match telemetry)
3. `MANUAL_ANNOTATION` (Cryptographically SHA-256 sealed human video event annotations)
4. `SYNTHETIC_FIXTURE` (**Strictly excluded** from real Gamer DNA, recurring mistake rates, coaching diagnosis, and model learning)
5. `INSUFFICIENT_EVIDENCE / UNKNOWN / REJECTED` (Explicit abstention triggers)
