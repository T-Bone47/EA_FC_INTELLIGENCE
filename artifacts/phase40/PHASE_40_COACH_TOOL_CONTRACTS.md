# PHASE 40E: Bounded Personal Coach Tool Contracts

**Implementation:** [coach_tools.py](../../backend/services/coach_tools.py) & [personal_coach_orchestrator.py](../../backend/services/personal_coach_orchestrator.py)

## 1. Complete 22-Tool Registry

Every tool executes inside `CoachToolRegistry.execute(tool_name, user_id, **kwargs)` with strict `user_id` scoping (`target_user_id` / caller overrides stripped), step budget (`MAX_TOOLS_PER_TURN = 6`), per-call latency tracking, and Pydantic output validation:

| # | Tool Name | Purpose | Provenance Tag |
| :--- | :--- | :--- | :--- |
| 1 | `get_gamer_dna` | Retrieve Style vs Proficiency DNA & Mixed Archetype | `REAL_OBSERVED_DNA` / `COLD_START` |
| 2 | `get_gamer_profile_confidence` | Inspect sample sufficiency & excluded synthetics | `REAL_OBSERVED_DNA` / `COLD_START` |
| 3 | `get_match_history` | Query user-owned persisted matches (excluding synthetics) | `USER_SCOPED_REPOSITORY` |
| 4 | `get_match_analysis` | Retrieve full telemetry/findings for specific match | Match provenance |
| 5 | `get_match_squad_snapshot` | Retrieve immutable XI snapshot used in match | Match provenance |
| 6 | `find_recurring_mistakes` | Retrieve opportunity-normalized mistakes & clips | `REAL_OBSERVED_PATTERNS` |
| 7 | `get_tactical_diagnostic` | Inspect specific diagnostic code breakdown | `REAL_OBSERVED_PATTERNS` |
| 8 | `get_evidence_clip` | Fetch timestamped clips with Gameplay Studio deep links | `USER_EVIDENCE_CLIPS` |
| 9 | `compare_match_performance` | Cross-match delta with patch/formation warnings | `USER_MATCH_COMPARISON` |
| 10 | `get_current_squad` | Load user saved squads from PostgreSQL | `USER_SQUAD_DB` |
| 11 | `get_player_card` | Search canonical player cards by name & edition | `CANONICAL_POSTGRES_CATALOGUE` |
| 12 | `search_player_cards` | Filtered position/edition candidate retrieval | `CANONICAL_POSTGRES_CATALOGUE` |
| 13 | `compare_player_cards` | Side-by-side canonical attribute/PlayStyle check | `CANONICAL_POSTGRES_CATALOGUE` |
| 14 | `evaluate_role_suitability` | DNA + FC IQ official role pairing check | `DNA_PLUS_OFFICIAL_KB` |
| 15 | `evaluate_squad_cohesion` | Phase 34B Whole-XI tactical synergy evaluation | `PHASE34B_SYNERGY_ENGINE` |
| 16 | `evaluate_player_partnership` | Phase 35 2-slot harmonic complementarity | `PARTNERSHIP_INTELLIGENCE_V2` |
| 17 | `evaluate_tactical_fit` | Formation & tactical profile suitability summary | `REAL_OBSERVED_DNA` / `COLD_START` |
| 18 | `recommend_player_profiles` | V3.2.1 + PersonalGameplayFit advisory candidates | `PERSONAL_GAMEPLAY_FIT` |
| 19 | `recommend_squad_changes` | Tactical-first intervention & replacement plan | `SQUAD_INTERVENTION_ENGINE` |
| 20 | `get_official_gameplay_knowledge` | Lexical search across versioned EA KB entries | `OFFICIAL_KB` |
| 21 | `generate_training_plan` | Freeze-frame drills & experimental BKT state | `TRAINING_ACADEMY` |
| 22 | `evaluate_improvement` | Longitudinal progression windows & N-of-1 contract | `LONGITUDINAL_PROGRESSION` |

## 2. Provider Architecture & Graceful Degradation
- **Default (`DETERMINISTIC_COACH`):** Zero external API cost; deterministic grounding across retrieved user evidence.
- **Optional External/Local Providers (`OLLAMA_LOCAL`, `OPENAI_COMPATIBLE`):** Gated by explicit `consent_external_llm = True` + configured environment variables (`OLLAMA_HOST`, `OPENAI_API_KEY`). Transmits only anonymized structured findings (never raw video binaries or PII) and degrades automatically back to `DETERMINISTIC_COACH` on network errors, timeouts (`3.5s`/`5.0s`), or malformed responses.
