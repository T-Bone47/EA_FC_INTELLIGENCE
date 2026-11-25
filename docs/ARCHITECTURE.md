# System Architecture (Through Phase 42)

EA FC Intelligence separates **deterministic quantitative computation**, **curated/computer-vision evidence pipelines**, and **constrained natural-language coaching explanation** so no generative model can fabricate match events, player ratings, or unverified causal claims.

## 1. Layered Backend Architecture

| Layer | Key Modules | Responsibility |
| :--- | :--- | :--- |
| **API & Auth Boundary** | `backend/api/main.py`, `routes/auth.py`, `routes/recommendations.py`, `routes/phase40_coach.py`, `routes/phase41_decisions.py`, `routes/video_research.py` | FastAPI HTTP + SSE routing, JWT + bcrypt auth, request size caps, per-route rate limiting, strict IDOR isolation by `user.id`. |
| **Core Configuration** | `backend/core/config.py`, `backend/core/db.py`, `backend/core/security.py` | Pydantic settings loading `.env` server-side only, `redact_secrets()`, PostgreSQL connection pooling, free-only LLM flags, timeout configs. |
| **Recommendation Engine (Frozen V3.2.1)** | `backend/services/recommendation_engine_v3.py`, `v3_config.py`, `fit_components.py`, `recommendation_service.py` | Deterministic component evaluation (`overall_quality`, `attribute_fit`, `position_fit`, `tactical_fit`, `playstyle_fit`, `team_fit`), missing-data coverage gates, Pareto frontiers. |
| **Squad & Partnership Engines** | `backend/services/partnership_intelligence.py`, `squad_synergy_engine.py`, `squad_optimizer_v3.py`, `fc27_card_research_service.py` | Lineup role compatibility, Whole-XI channel cohesion, tactical friction rules, confirmation-gated upgrade proposals with snapshot rollback. |
| **Gameplay Vision & Spatial Engine** | `backend/services/real_video_decoder.py`, `scene_classifier.py`, `homography_dlt.py`, `bytetrack_adapter.py`, `multi_channel_perception.py`, `multi_source_fusion.py`, `gameplay_perception_engine.py`, `backend/cv_training/*` | PyAV frame sampling, scene gating, LK optical flow + DLT/RANSAC pitch calibration, ByteTrack tracking, HSV filled-contour / ONNX DNN dispatch, 10 Hz `FusedFrameTelemetry`. |
| **Decision & Counterfactual Engine** | `backend/services/decision_state_builder.py`, `counterfactual_football_engine.py`, `expected_threat.py`, `football_iq_engine.py`, `decision_scenario_service.py` | Pre-action state cutoffs (`strip_hindsight`), passing lane clearance & interception margins, Markov xT deltas, Monte Carlo sensitivity, Football IQ profiling. |
| **Gamer DNA & Adaptive Training** | `backend/services/gamer_dna_engine.py`, `recurring_mistake_analyzer.py`, `training_plan_service.py`, `performance_progression_service.py` | Separates Style from Execution Proficiency; maps weaknesses + Phase 41 Decision Windows into 8-category freeze-frame drills; updates bounded `practice_only` BKT state; tracks closed-loop observational trends. |
| **Hybrid AI Coach & Co-Pilot** | `backend/services/personal_coach_orchestrator.py`, `coach_tools.py`, `coach_tools_extended.py`, `football_knowledge_service.py`, `llm/{router,registry,free_guard,gemini_provider,openrouter_provider}.py` | Intent routing, `4–6` targeted tool schemas per intent, 77+ typed tool handlers, singleton Okapi BM25 RAG + 23-source registry, per-model circuit breakers, server-authorized `CoachContextEnvelope`, multimodal consent/redaction gate. |

## 2. Database Topology (PostgreSQL 16, Migrations `002`–`018`)
- **Canonical & Safety Layer (`DATABASE_SCHEMA_V1.sql`, `002`–`014`):** `game_version`, `player`, `ut_card`, `user_profile`, saved squads, FC26 canonical data, quarantined `fc27_staging` / `fc27_*` research firewall tables (`008`, `009`, `012`–`014`).
- **Phase 40 (`015`):** `phase40_match_intelligence`, `phase40_coach_session`, `phase40_coach_message`, `phase40_training_plan`, `phase40_training_attempt`, `phase40_cold_start_preferences`.
- **Phase 41 (`016`):** `phase41_decision_opportunity`, `phase41_football_iq_profile`, `phase41_training_scenario`, `phase41_decision_annotation`.
- **Phase 41.5 (`017`):** Multi-turn session extensions, persistent pending/confirmed/rolled-back `squad_proposal` snapshots, `phase41_5_provider_usage_log`.
- **Phase 42 (`018`):** `source_route` / `context_envelope` / `last_context_freshness_ts` on sessions; `ttft_ms` / `tools_sent_count` / `fallback_used` on provider logs; `phase42_user_coach_preferences`; decision metadata on training attempts; `phase42_cv_checkpoint` table.

## 3. Frontend Architecture (`frontend/src/`)
- **Design System (`DESIGN.md` & `.agents/skills/stadium-design-system/SKILL.md`):** Stadium 3.0 Obsidian/Lime dark palette with WCAG 2.2 AA contrast, tabular numeric typography, crisp SVG tactical pitches, and `prefers-reduced-motion` compliance.
- **Route Code-Splitting:** React `lazy` + `Suspense` route modules across `/search`, `/players/:id`, `/compare`, `/cards/squad-lab`, `/intelligence`, `/research/gameplay-studio`, `/research/decision-lab`, and `/coach`.
- **Universal Co-Pilot Overlay:** `CopilotProvider` (`state/copilot.tsx`) synchronizes live route state to `CoachCopilotDrawer.tsx` (`Ctrl+Shift+C`) and integrates `ScreenshotRedactorModal.tsx` for client-side PII masking before optional vision requests.
