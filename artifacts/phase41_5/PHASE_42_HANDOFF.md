# Phase 42 Handoff — Agentic Video/UI Co-Pilot & Continuous Coach Calibration

## Verified Foundation Delivered in Phase 41.5
- Hybrid Agentic AI Coach (`Gemini Free -> OpenRouter Free -> DeterministicCoachFallback`) with strict free-only guardrails (`$0.0` reported external inference cost).
- `77` registered typed backend tools grounded in frozen V3.2.1 `RecommendationServiceV3`, `PlayerRepository`, `SquadRepository`, `PartnershipIntelligenceEngine`, `SpatialIntelligenceEngine`, `CounterfactualFootballEngine`, Gamer DNA, BKT Training, and calibrated Okapi BM25 Football Knowledge Retrieval.
- Persistent PostgreSQL schema (`017_phase41_5_agentic_coach.sql`), confirmation/rollback squad proposals, SSE streaming, cancellation, and upgraded Stadium 3.0 workspace in `PersonalCoach.tsx`.
- All core regression tests (`102 passed`) and benchmarks (`FC_COACH_BENCH_V1` `100%` across 120 scenarios, Phase 40 `110` scenarios `100%`, Phase 41 `220` scenarios `100%`) verified green.

## Recommended Next Objectives for Phase 42
1. **Shared Distributed Quota & Conversation Summarization:** Back `QuotaManager` cooldowns/RPM windows with Redis if scaling beyond 1 Uvicorn worker, and add automatic periodic conversation compaction for >20-turn coaching threads using `conversation_summary` in `phase40_coach_session`.
2. **Authenticated Live Coach SSE UI Smoke Suite:** Extend Playwright verification with a dedicated seeded test user login flow verifying live SSE streaming tokens, clickable verified player card navigation into `/players/:id`, and squad proposal confirmation/rollback against live PostgreSQL.
3. **Gameplay Studio Deep Link Integration:** Wire direct "Ask AI Coach About This Match Window" triggers from Decision Replay Lab (`DecisionReplayLab.tsx`) and Gameplay Studio (`GameplayStudio.tsx`) pre-filling `active_match_id` and decision window context into `/coach`.
4. **Optional Multimodal Screenshot Inspection Opt-In UX:** When the user enables `AI_COACH_ALLOW_EXTERNAL_IMAGES=true` alongside free VLM endpoints (`gemini-4-hydrogen` / `nvidia/nemotron-3.5-super-vl:free`), add explicit redaction preview and one-time confirmation dialog before uploading local tactical board captures.
5. **Legacy Test Hygiene:** Archive or modernize pre-V3 legacy suites (`test_engine_adversarial_phase7.py`, `test_integration_production.py`, `test_zero_budget_research.py`) in a dedicated cleanup PR while keeping frozen V3.2.1 weights and `test_golden_fixtures_v3_2.py` untouched.
