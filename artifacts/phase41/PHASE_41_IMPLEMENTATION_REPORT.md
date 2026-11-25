# PHASE 41: Implementation Report

**Date:** 2026-11-25  
**Target Preservation Baseline:** Frozen V3.2.1 Recommendation Engine + Phase 38/39/40 Stack

## Delivered Artifacts & Modules

| Layer | File / Module | Purpose |
| :--- | :--- | :--- |
| **PostgreSQL Schema** | `db/migrations/016_phase41_decision_intelligence.sql`, `rollback/016_phase41_decision_intelligence_down.sql` | Adds `phase41_decision_opportunity`, `phase41_football_iq_profile`, `phase41_training_scenario`, `phase41_decision_annotation` scoped by `public.user_profile(id)` |
| **Domain Contracts** | `backend/domain/phase41_models.py` | Strictly split pre-action state (`FootballDecisionState`), `PostActionOutcome`, per-decision `FieldAdequacyReport`, `CandidateAction`, `PassingCorridorEval`, `DefensiveDecisionEval`, `ShootingDecisionEval`, `OffBallOpportunity`, `CounterfactualComparison`, `UncertaintyRange`, `FootballIQProfile`, `DecisionTrainingScenario` |
| **Pre-Action Windows** | `backend/services/decision_state_builder.py` | Clusters high-frequency frames without adjacent duplication, enforces `strip_hindsight()`, computes decision-specific adequacy |
| **Candidate Generator** | `backend/services/candidate_action_generator.py` | Generates attacking/defensive candidates (`FEASIBLE`, `POSSIBLY_FEASIBLE`, `UNSUPPORTED`, `UNKNOWN`) without controller hallucination |
| **Passing & Value** | `backend/services/passing_intelligence.py`, `backend/services/possession_value_engine.py` | Point-to-segment clearance, arrival margin `M`, 4 pass-speed sensitivity profiles, Stage 1 Heuristic, Stage 2 iterative Markov `ExpectedThreatEngine`, gated Stage 3 `CalibratedEPVInterface` |
| **Defense, Shot, Off-Ball** | `backend/services/defensive_and_chance_intelligence.py` | Team-shape defensive eval, heuristic shot vs pass/carry (`is_calibrated_xg=False`), cautious `UNKNOWN` off-ball run attribution |
| **Counterfactual & IQ** | `backend/services/counterfactual_football_engine.py`, `backend/services/football_iq_engine.py`, `backend/services/decision_scenario_service.py` | Monte Carlo localization/coverage uncertainty, non-negative regret, 10-dimension synthetic-isolated Football IQ, multi-answer scenario converter |
| **Persistence & Routes** | `backend/repositories/phase41_repository.py`, `backend/api/routes/phase41_decisions.py`, `backend/api/main.py` | User-scoped CRUD/IDOR guards, `/api/phase41/*` REST API + privacy reset hook |
| **Coach & Squad Fit** | `backend/services/coach_tools.py`, `backend/services/personal_coach_orchestrator.py`, `backend/services/personal_gameplay_fit.py`, `backend/services/decision_review_service.py` | Registers 12 new Decision Intelligence tools (34 total), capability vs choice bottleneck isolation, Squad Lab passing-outlet / press-resistance / transition simulation |
| **Frontend UI** | `frontend/src/pages/DecisionReplayLab.{tsx,css}`, `App.tsx`, `Nav.tsx`, `PersonalCoach.tsx`, `CardSquadLab.tsx` | Synchronized `/research/decision-lab` with Blind Review toggle, 2D SVG pitch, candidate reward/risk table, uncertainty bounds, math disclosure, 10-dim Football IQ panel, Squad Decision Support panel |
| **Tests & Benchmark** | `backend/tests/test_phase41_*.py`, `frontend/src/pages/DecisionReplayLab.test.tsx`, `verification/run_phase41_benchmarks.py` | `105 passed, 3 skipped` backend suite, `109 passed | 3 skipped` Vitest suite, `220`-scenario benchmark (`100.0%` gates) |
