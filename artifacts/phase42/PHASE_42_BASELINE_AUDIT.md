# Phase 42 Baseline Audit

**Date:** 2026-11-25  
**Scope:** End-to-end audit of EA FC Intelligence across backend engine, database schemas, LLM coach orchestration, CV vision pipeline, adaptive training, and Stadium 3.0 frontend prior to Phase 42 delivery.

## 1. Verified Pre-Existing Foundation
- **Frozen V3.2.1 Recommendation Core:** `test_golden_fixtures_v3_2.py`, `test_v3_api_contract.py`, and `test_v3_production_safety.py` remained untouched in math/weights (`recommendation_engine_v3.py`, `v3_config.py`).
- **Database State:** Local embedded PostgreSQL 16 (`127.0.0.1:5432`) held `fc27_staging.source_row` (`9,962` rows from Migration `009`), while `fc27_staging.observation` from `012_fc27_evidence_staging.sql` was absent (`to_regclass` `None`) due to prior `CREATE SCHEMA fc27_staging` conflict.
- **Hybrid Coach & Tools:** `CoachToolRegistry`, Gemini Free + OpenRouter Free adapters, `QuotaManager`, `ModelCapabilityRegistry`, SSE streaming/cancellation, SQL/prompt-injection firewall, and PostgreSQL Migration `017` were operational before Phase 42.

## 2. Baseline Failures Identified (31 Pre-Existing Failures)
| Legacy Test File | Failure Count | Root Cause |
| :--- | :---: | :--- |
| `backend/tests/test_zero_budget_research.py` | 6 | 5 from Starlette `0.37.2` `TestClient` lacking `client=(host, port)` kwarg; 1 from missing `fc27_staging.observation` table returning HTTP `503` instead of `422`. |
| `backend/tests/test_integration_production.py` | 12 | Obsolete V2/early-V3 assertions (removed `explanations` top-level alias, `s.position` renamed to `s.slot`, `price=None` enforcement test expecting non-null budget rejection, missing `strict_rate_limits` fixture). |
| `backend/tests/test_engine_adversarial_phase7.py` | 9 | Tests deliberately targeting deprecated `RecommendationEngineV2` OVR-trap failures explicitly superseded by V3. |
| `backend/tests/test_engine_v3_real_data.py` | 4 | Empirical V3.2 math threshold probes (`rho(R, OVR) in [0.863, 0.911] > 0.85`, CB spread `0.094 < 0.10`). |

## 3. Baseline Hardware, CV & LLM Latency Bottlenecks
- **Compute Hardware:** Windows host with `NVIDIA GeForce RTX 3050 Laptop GPU` (4,096 MiB VRAM) and `OpenCV 5.1.0` (`OpenCL GPU` active), `PyAV 19.0.2`, `SciPy 1.18.1`, `scikit-learn 1.9.1`, `redis 8.1.0`. `torch`, `torchvision`, `onnxruntime`, `ultralytics`, and trained `backend/models/fc_detector.onnx` weights were not installed offline.
- **CV Classical Pitch-Hole Bug:** `PixelPerceptionExtractor` used a `(19, 19)` morphological closing kernel on green turf masks, failing to fill foreground player holes wider than `19px` and causing `0.0%–0.8%` tracking coverage on 960x540 test clips.
- **LLM Latency Bottlenecks:** Retrying timed-out OpenRouter requests doubled timeout windows (~40s worst-case); lack of per-`(provider, model)` circuit breakers caused repeated calls to `503 UNAVAILABLE` Gemini endpoints; per-orchestrator initialization rebuilt the BM25 index repeatedly.
