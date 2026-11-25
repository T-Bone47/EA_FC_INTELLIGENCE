# PHASE 41: Decision Security & Anti-Hindsight Leakage Audit

## 1. Hindsight Leakage Prevention
- `strip_hindsight(state)` clones every `FootballDecisionState` and enforces `post_action_outcome = None` with explicit assertions inside `CandidateActionGenerator.generate`, `PassingIntelligenceEngine.evaluate_pass`, `DefensiveDecisionEngine.evaluate_option`, `ShootingChanceEngine.evaluate_shot`, `OffBallOpportunityEngine.detect_runs`, `CounterfactualFootballEngine.evaluate`, and `DecisionScenarioService.build_scenario`.
- Automated paired outcome-swap verification across all 220 benchmark scenarios (`verification/run_phase41_benchmarks.py`) confirmed **100.0% zero hindsight leakage**: flipping `PostActionOutcome` between `TURNOVER` and `GOAL` produces identical candidate ranks, utilities, and Decision Regret estimates.

## 2. Authentication & Cross-User Isolation (IDOR Protection)
- All `/api/phase41/*` personal endpoints (except `/api/phase41/health`) enforce `Depends(current_user_required)`.
- Anonymous requests to `/api/phase41/windows` and `/api/phase41/football-iq` return `HTTP 401`.
- Cross-user lookups to `/api/phase41/windows/{window_id}` strictly filter by `user_id = current_user.id` and return `HTTP 404` (`test_complete_phase41_e2e_and_cross_user_isolation`).
- Privacy reset (`DELETE /api/phase40/privacy/reset`) cascades cleanly across `phase41_decision_annotation`, `phase41_training_scenario`, `phase41_football_iq_profile`, and `phase41_decision_opportunity`.

## 3. Epistemic Provenance Firewall
- `SYNTHETIC_FIXTURE` decision windows are counted transparently in `synthetic_excluded_count` and strictly barred from contributing to `FootballIQProfile` scores or Personal AI Coach mistake/decision diagnoses.
