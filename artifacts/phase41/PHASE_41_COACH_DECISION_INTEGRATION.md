# PHASE 41O: Personal AI Coach Decision Intelligence Integration

**Modules:** `backend/services/coach_tools.py`, `backend/services/personal_coach_orchestrator.py`

## 1. New Decision Intelligence Tools Registered (Total Tools: 34)
`CoachToolRegistry` retains all 22 Phase 40 tools (`PHASE40_TOOLS`) and registers 12 Phase 41 Decision Intelligence bounded tools (`PHASE41_TOOLS`):
1. `get_decision_opportunities`
2. `get_decision_frame_analysis`
3. `evaluate_candidate_actions`
4. `get_best_alternative_action`
5. `get_decision_regret_summary`
6. `get_football_iq_profile`
7. `get_passing_decision_diagnostics`
8. `get_defensive_decision_diagnostics`
9. `get_shooting_decision_diagnostics`
10. `get_off_ball_run_diagnostics`
11. `generate_decision_training_scenario`
12. `evaluate_player_capability_constraints`

## 2. Guardrails Preserved
- Strict caller `user_id` scoping (`target_user_id` / `user_id` overrides stripped in `execute()`).
- OWASP GenAI prompt-injection detection blocks cross-user / instruction override attempts cleanly before tool execution.
- `needs_personal_footage` abstains cleanly when both `eligible_match_count == 0` AND `eligible_decision_windows == 0`.
