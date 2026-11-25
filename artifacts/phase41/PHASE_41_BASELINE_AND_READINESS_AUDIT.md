# PHASE 41A: Baseline & Readiness Audit

**Date:** 2026-11-25  
**Workspace:** `PROJECT/EA_FC_INTELLIGENCE-main`  
**Target Preservation Baseline:** Frozen V3.2.1 Recommendation Engine + Phase 38/39/40 Infrastructure

---

## 1. Inspected Repository & Environment Status

| Component / Artifact | Verified Implementation State | Readiness Classification for Phase 41 |
| :--- | :--- | :--- |
| **PostgreSQL 16 + Migrations** | Live on `127.0.0.1:5432/eafc_intelligence`. Migrations `002`–`012` + `015_phase40_coaching_intelligence.sql` verified in `schema_migrations` (`phase40_*` tables present; `4` user profiles). Note `013`/`014` remain unapplied in DB (`fc27_staging.observation` gated), so Phase 41 migration `016` must reference `public.user_profile(id)` cleanly. | **Verified & Running** |
| **Frozen V3.2.1 Engine** | `recommendation_engine_v3.py`, `v3_config.py`, golden fixtures & invariants verified unmodified (`64 passed, 3 skipped, 0 failed` in pre-Phase-41 V3+Phase37-40 baseline run). | **Verified Frozen** |
| **Telemetry & Spatial Engine** | `spatial_intelligence.py` (`GRID_COLS=21`, `GRID_ROWS=14`, anisotropic Gaussian influence + Karun Singh `12x8` xT matrix + point-to-segment `PassingLaneOption` + `TeamTacticalStructure`), `real_video_decoder.py` (`PyAV 19.0.2`), `multi_channel_perception.py`. | **Verified Ready for Decision State Extraction** |
| **YOLO / ONNX Custom Weights** | `backend/models/fc_detector.onnx` absent; perception runs `CV_CLASSICAL_HSV_CONTOUR` fallback. | **Honest Hardware/Model Limitation** |
| **Unedited Owner Console Video** | Zero retail EA FC26/FC27 full match captures on disk; verified clips/traces use PyAV-encoded test videos, `IMPORTED_MATCH_TRACE`, and `SYNTHETIC_FIXTURE`. | **Honest Corpus Limitation — Benchmarks Explicitly Segregated** |
| **Phase 40 Foundation** | `DecisionReviewService` (basic frame-level `Q_heuristic`), `PersonalCoachOrchestrator` (22 bounded tools), `PersonalGameplayFitService`, `TrainingPlanService`, `PerformanceProgressionService`. | **Ready for Phase 41 Expansion** |
| **Backend & Frontend Runtime** | Embedded Postgres (`task-3799`), Vite Dev Server (`task-3402` on `:5173`), FastAPI Uvicorn (`task-5152` on `:8000` — requires restart after adding `/api/phase41/*`). | **Operational** |

---

## 2. Pre-Phase-41 Baseline Verification Run

Executed immediately before Phase 41 edits:
- Command: `pytest test_golden_fixtures_v3_2.py test_engine_v3_invariants.py test_phase3*.py test_phase40*.py -p no:cacheprovider -q`
- Result: **`64 passed, 3 skipped, 0 failed` (`15.32s`)**.
- Historical pre-existing full-suite caveat carried from Phase 40 audit remains unchanged (`test_engine_adversarial_phase7.py` / `test_integration_production.py` legacy V2, `test_engine_v3_real_data.py` historical $\rho \le 0.85$ bound, `test_zero_budget_research.py` env/release check).

---

## 3. Architectural Reuse & Gap Map Entering Phase 41

1. **Pre-Action State Isolation (Gap -> 41B/41C):** Phase 40 `DecisionReviewService.review_frame` inspects single-frame `passing_lanes` without match-wide temporal windowing, post-action outcome stripping, or decision-type-specific field adequacy checks. Phase 41 introduces `FootballDecisionState`, `decision_state_builder.py`, and explicit hindsight-leakage tests.
2. **Candidate Set Breadth (Gap -> 41D/41H–J):** Phase 40 generates passing options only; Phase 41 adds carries/holds/shots/switches and full **defensive decision options** (`HOLD_LINE`, `RECOVER_WITH_CM_CDM`, `CONTAIN_BALL_CARRIER`, `CLOSE_PASSING_LANE`, `PRESS_BALL_CARRIER`, `TRACK_RUNNER`, `PRESERVE_CENTRAL_COVER`) plus **off-ball run** detection with honest controller attribution (`UNKNOWN` when unverified).
3. **Physics & Valuation (Gap -> 41E–G, 41K–L):** Phase 41 upgrades static corridor clearance to velocity-aware time-to-intercept margin $M = t_{\text{opp}} - t_{\text{ball}}$ across pass-speed assumptions, separates `HeuristicPossessionValue` / configurable Markov `ExpectedThreatEngine` / future calibrated `V(s)` interface, and wraps counterfactual comparisons in Monte Carlo localization/velocity/coefficient uncertainty bounds (`CounterfactualFootballEngine`).
4. **Longitudinal Decision IQ & Replay UI (Gap -> 41M–R):** Phase 41 adds 10-dimensional **Football IQ Profile** (strictly excluding `SYNTHETIC_FIXTURE`), `/research/decision-lab` synchronized blind-review Replay Lab, 12 new Decision Intelligence tools in `CoachToolRegistry`, capability isolation in `PersonalGameplayFit`, Squad Lab outlet/press-resistance simulation, and multi-answer `DecisionTrainingScenario` generation.
