# Phase 41.5 Football Agent Tool Contracts & Engine Reuse

**Implementations:** [coach_tools.py](../../backend/services/coach_tools.py) (`CoachToolRegistry`), [coach_tools_extended.py](../../backend/services/coach_tools_extended.py) (`Phase415ExtendedToolsMixin`)  
**Total Registered Handlers:** **77** (preserving all 22 `PHASE40_TOOLS` + 12 `PHASE41_TOOLS` = 34 legacy contract tools, plus 43 `PHASE41_5_TOOLS` covering player discovery, V3.2.1 recommendations, Squad Lab optimization/previews, Gamer/Decision/Training/RAG tools).

---

## 1. Security & Validation Contracts Applied to Every Tool

1. **Pydantic Argument Validation:** Every tool validates incoming LLM JSON arguments against a typed `BaseModel` (`TOOL_INPUT_MODELS`) using `exclude_unset=True`. Unknown tools raise `ValueError` and log `REJECTED_UNKNOWN_TOOL`.
2. **Caller `user_id` Isolation:** `user_id` and `target_user_id` supplied inside LLM arguments are forcefully stripped; the authenticated backend caller `user.id` is always injected by the server.
3. **Read-Only Default & Confirmation Gate:** No SQL execution, shell access, arbitrary HTTP fetch, or direct `user_squad` mutation exists as an LLM tool. `optimize_squad` and `preview_player_replacement` persist read-only previews (`PENDING_CONFIRMATION`) in `phase41_5_squad_proposal`, mutating a saved squad ONLY after explicit user action via `POST /api/phase40/squad-proposals/{proposal_id}/confirm` (with `/rollback` undo support).
4. **Epistemic Provenance & Freshness:** Outputs declare explicit `provenance`, `confidence`, `market_price_status` (`MARKET_PRICE_UNAVAILABLE`), `frozen_v321_untouched: True`, and never leak synthetic fixtures into user Gamer DNA or Football IQ metrics.

---

## 2. Conceptual Tool Mapping to Verified Engines

| Domain | Tool Names | Backing Service / Engine Reused |
| :--- | :--- | :--- |
| **Player Intelligence** | `recommend_players`, `search_players`, `get_player_card`, `get_player_attributes`, `get_player_playstyles`, `get_player_role_suitability`, `compare_players`, `find_similar_players`, `get_personal_gameplay_fit` | `RecommendationServiceV3` (frozen V3.2.1 weights & gates intact), `PlayerRepository`, `CandidateRepository`, `PersonalGameplayFitService` |
| **Squad Intelligence** | `get_current_squad`, `get_squad_snapshot`, `evaluate_squad`, `evaluate_formation`, `evaluate_player_partnership`, `evaluate_whole_xi_cohesion`, `find_squad_weaknesses`, `recommend_squad_upgrades`, `compare_squad_alternatives`, `preview_player_replacement`, `preview_formation_change`, `optimize_squad` | `SquadRepository`, `PersonalGameplayFitService`, `PartnershipIntelligenceEngine`, `compute_whole_xi_synergy`, `formations.slots_for`, `Phase40Repository.save_squad_proposal` |
| **Gameplay Intelligence** | `get_match_history`, `get_match_analysis`, `get_match_statistics`, `get_tactical_diagnostics`, `find_recurring_mistakes`, `get_gameplay_evidence`, `get_evidence_clip`, `get_pitch_control_analysis`, `get_transition_analysis` | `Phase40Repository` (strictly `exclude_synthetic=True`), `MatchIntelligenceService`, `RecurringMistakeAnalyzer` |
| **Gamer Intelligence** | `get_gamer_dna`, `get_football_iq`, `get_gamer_strengths`, `get_gamer_weaknesses`, `get_performance_trends`, `compare_recent_matches` | `GamerDNAEngine`, `FootballIQEngine`, `PerformanceProgressionService` |
| **Decision Intelligence** | `get_decision_opportunities`, `get_decision_state`, `get_candidate_actions`, `evaluate_passing_options`, `compare_decision_alternatives`, `get_decision_regret`, `get_counterfactual_analysis`, `get_off_ball_run_diagnostics`, `evaluate_player_capability_constraints` | `Phase41Repository`, `CounterfactualFootballEngine`, `OffBallOpportunityEngine`, `DecisionScenarioService` (outcome hidden unless `reveal_outcome=True`) |
| **Training Intelligence** | `generate_training_plan`, `get_training_history`, `recommend_training_exercises`, `create_decision_training_scenario`, `evaluate_training_progress` | `TrainingPlanService`, `bkt_update`, `Phase40Repository` |
| **Knowledge / RAG** | `search_football_knowledge`, `get_official_gameplay_mechanics`, `get_playstyle_explanation`, `get_role_explanation`, `get_patch_information`, `get_formation_information` | `FootballKnowledgeService` (BM25 + hierarchy) |
