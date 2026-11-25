# Changelog

All notable project milestones for **EA FC Intelligence** from the initial Phase 7 baseline through the **Phase 42 Release Checkpoint**. Frozen **V3.2.1** player recommendation weights and golden scenarios remain preserved throughout.

## [Phase 42] — 2026-11-25 — Universal Contextual Co-Pilot, Adaptive Training & CV Harness
### Added
- **Universal Context-Aware Co-Pilot (`42E`):** Global slide-over drawer (`CoachCopilotDrawer.tsx`, `Ctrl+Shift+C`), shared context provider (`frontend/src/state/copilot.tsx`), header trigger (`Nav.tsx`), and typed `CoachContextEnvelope` triggers across Player Discovery, Player Detail, Compare, Squad Lab, Gameplay Studio, Decision Replay Lab, and Personal Coach.
- **Server-Side Context Authorization & Privacy Redaction (`42E`, `42G`):** `_authorize_and_hydrate_context()` preventing cross-user context spoofing; local `<canvas>` PII black-box masking + EXIF stripping (`ScreenshotRedactorModal.tsx`); separate media opt-in gate with `CANDIDATE_MULTIMODAL_OBSERVATION_UNVERIFIED` isolation.
- **LLM Reliability, Circuit Breakers & Memory (`42C`, `42D`):** Per-`(provider, model)` `CLOSED -> OPEN -> HALF_OPEN` circuit breakers (`ProviderHealthMonitor`), fail-fast `14s`/`16s` provider timeouts, minimal `4–6` tool subsets (`INTENT_TO_TOOLS`), shared singleton BM25 cache + 23-source `RESEARCH_SOURCE_REGISTRY`, `ttft_ms` telemetry, `GET`/`PUT /api/phase40/coach/preferences`, rolling conversation summary, live DB freshness cross-checks, and optional `RedisQuotaBackend` (`REDIS_URL`).
- **Domain CV Training & Evaluation Harness (`42F`):** Created `backend/cv_training/` (`manifest.py`, `dataset_splitter.py`, `config_generator.py`, `evaluator.py`, `export_onnx.py`, `benchmark_cv.py`) with 5-class EA FC schema, leakage-free match splitting, commercial-safe `YOLOX_APACHE2` vs gated `ULTRALYTICS_AGPL3_OPT_IN`, Hungarian/HOTA/IDF1/AP@50/pitch-RMSE evaluation, and `_detect_with_onnx()` inference dispatch.
- **Adaptive 8-Category Training & Closed-Loop Progression (`42H`, `42I`):** Expanded `TrainingPlanService` across all 8 skill categories, linked non-synthetic Phase 41 Decision Windows directly into blind-review challenges (`hide_outcome_by_default=True`, outcome reveal post-submission), bounded BKT calibration + Brier evaluation, and added `weakness_loop_tracking` + covariate stratification to `PerformanceProgressionService`.
- **Database Migration `018`:** Added `018_phase42_copilot_training_loop.sql` + reversible rollback migration.
- **Verification & Documentation:** Added `test_phase42_copilot_cv_training.py`, `CoachCopilotDrawer.test.tsx`, `verification/benchmark_fc_coach_v2.py`, `scripts/browser_qa/verify_phase42_copilot_live.mjs`, and 12 Phase 42 engineering reports (`artifacts/phase42/`).

### Fixed
- Fixed classical CV pitch turf hole-fill defect in `PixelPerceptionExtractor.detect_broadcast_players_and_ball()` using `cv2.RETR_EXTERNAL` filled contours (`0.0%–0.8%` -> `79.5%–80.3%` coverage on `960x540` test MP4 clips).
- Fixed `EvidenceClipRef` schema construction when linking Decision Windows inside `TrainingPlanService`.
- Fixed dict-vs-attribute diagnostic code extraction inside `PerformanceProgressionService._compute_weakness_loops()`.
- Fixed obsolete test assertions in `test_integration_production.py` (`41/41` passing) and Starlette `TestClient` client injection in `test_zero_budget_research.py`.

---

## [Phase 41.5] — 2026-11-24 — Hybrid Agentic AI Coach (Gemini & OpenRouter Free Tiers)
- Added free-only multi-provider orchestrator (`backend/services/llm/`) integrating Google Gemini Free & OpenRouter Free with strict quota guards, secret redaction, 77+ typed tool handlers, SSE streaming/cancellation, confirmation-gated Squad Proposals with rollback, and Migration `017`.

## [Phase 41] — 2026-11-24 — Advanced Decision Intelligence & Counterfactual Football Engine
- Implemented zero-hindsight pre-action `DecisionStateBuilder`, `CounterfactualFootballEngine`, Markov expected threat (xT), dynamic interception margin modeling, bounded Monte Carlo uncertainty, `FootballIQEngine`, `DecisionReplayLab` UI, and Migration `016`.

## [Phase 40] — 2026-11-24 — Personal AI Football Coach, Gamer DNA & Training Foundation
- Built `GamerDNAEngine`, `RecurringMistakeAnalyzer`, Okapi BM25 football knowledge retrieval, `TrainingPlanService`, `PerformanceProgressionService`, `PersonalCoach` UI, and Migration `015`.

## [Stadium 3.0 & Phases 20–39] — 2026-09 — FC27 Isolation, Squad Lab, Gameplay Vision & UI Transformation
- **Phases 36–39:** Built real `PyAV` video ingestion, scene classification, optical-flow camera compensation, DLT/RANSAC pitch homography, ByteTrack multi-object tracking, minimap fusion, and `GameplayStudio`.
- **Phases 24–35:** Enforced strict FC26/FC27 research firewall (`008`–`014`), interactive 11-player `CardSquadLab` with Partnership Intelligence & Whole-XI Synergy, and Stadium 3.0 Obsidian/Lime accessible design system transformation.
- **Phases 8–23:** Upgraded core scorer to Frozen V3.2.1 (`005`–`007`), golden fixtures, calibration benchmarking, and release membership architecture (`011`).

## [Phase 7 Baseline] — Prior Published GitHub Commit (`e3f2608`)
- Initial `RecommendationEngineV2`, adversarial audit reports, EA FC player schema foundation, and `FC26` canonical ingestion.
