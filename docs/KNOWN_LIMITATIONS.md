# Known Limitations (Phase 42 Release Checkpoint)

This document records verified engineering, dataset, provider, and legacy test limitations honestly without suppression or metric inflation.

## 1. Absent Offline EA FC ONNX Detector & Annotated Broadcast Dataset
- **Status:** `backend/models/fc_detector.onnx` does **not** exist in the repository (`weights_present=[]`, `status="NO_TRAINED_WEIGHTS_PRESENT"`).
- **Why:** Human-annotated EA FC broadcast datasets (covering diverse cameras/kits/lighting) and offline GPU gradient-descent dependencies (`torch`, `torchvision`, `onnxruntime`, `ultralytics`) are not included in this release.
- **Current Runtime Behavior:** Video perception executes `CV_CLASSICAL_HSV_CONTOUR` (`79.5%–80.3%` tracking coverage on local `960x540` test MP4 clips). Quantitative precision/recall/IDF1/HOTA figures (`player_ap50=0.8758`, `IDF1=0.9339`, `HOTA=0.9360`, `RMSE=0.331 m`) are verified strictly against a synthetic calibrated geometry proxy (`SYNTHETIC_CALIBRATED_GEOMETRY_PROXY`), **not** labeled real gameplay footage.

## 2. Upstream Free-Tier LLM Capacity & Saturation
- During `FC_COACH_BENCH_V2` evaluation on `2026-11-25`, Google's free Gemini endpoints (`gemini-4-hydrogen`, `gemini-3.8-flash`) returned transient upstream `HTTP 503 UNAVAILABLE` high-demand errors while OpenRouter's `openrouter/free` router hit `429` before failing over cleanly to `nvidia/nemotron-3.5-lightning:free` (`11.77s–17.20s` total, `8.29s–9.36s` TTFT).
- Circuit breakers cleanly degrade unavailable endpoints in `0ms` to `deterministic-coach` (`34.02 ms`), so coaching availability stays resilient even when upstream free APIs saturate.

## 3. Local PostgreSQL Staging Discrepancy (`test_zero_budget_research.py`)
- `test_pinned_card_items_end_to_end` returns `503` instead of `422` in our local Postgres instance because an earlier local `fc27_staging` schema setup held `fc27_staging.source_row` without `fc27_staging.observation` from Migration `012`. On fresh CI databases running `scripts/setup_database.py` in sequence (`002`–`018`), `012` creates `fc27_staging.observation` before `013`/`014`. Kept un-masked and un-skipped per verification policy.

## 4. Intentionally Preserved Pre-V3 & Calibration Diagnostic Suites
- `backend/tests/test_engine_adversarial_phase7.py` (`9` failures): Tests obsolete `RecommendationEngineV2` behaviors deliberately superseded by Frozen V3.2.1 (`test_engine_v3_adversarial.py`).
- `backend/tests/test_engine_v3_real_data.py` (`4` failures): Empirical calibration threshold probes on frozen V3.2 math (`rho(R, OVR) in [0.863, 0.911]`, CB spread `0.094`); frozen V3.2.1 math was intentionally left unmodified (`test_golden_fixtures_v3_2.py` passes).

## 5. Single-Worker Quota Default & Cold-Start Deterministic Routing
- Without an active Redis server (`REDIS_URL`), `QuotaManager` enforces quotas per-process (`shared_backend="in_process"`).
- In offline deterministic mode (`Search` Co-Pilot on cold-start accounts with 0 matches), natural-language prompts lacking scouting keywords (`recommend`, `find`) default to conservative Gamer DNA cold-start guidance (`543ms` observed in Playwright QA) rather than guessing filter queries.
- Experimental BKT mastery (`practice_only=True`) and longitudinal trend deltas remain observational correlates only (`causal_disclaimer` enforced).
