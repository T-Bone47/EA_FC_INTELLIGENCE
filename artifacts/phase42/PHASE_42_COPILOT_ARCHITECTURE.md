# Phase 42 Universal Contextual Co-Pilot Architecture

## 1. Grounding & Control Principle
**Our engine calculates. The LLM retrieves, reasons and explains. Validated evidence remains the source of truth.**

## 2. Persistence Schema (`db/migrations/018_phase42_copilot_training_loop.sql`)
Applied cleanly to local PostgreSQL 16 (`MIGRATION_018_APPLIED_OK`), adding:
- `user_coach_preferences`: stores `user_id`, `preferred_provider`, `consent_external_llm`, `privacy_strict`, `favorite_formation`, `playstyle_focus`.
- Conversation extensions: `rolling_summary` and `source_route` on `coach_conversation`.
- Multimodal opt-in audit columns & closed-loop progression helper tables without modifying V3.2.1 read-only catalogue tables.

## 3. Typed `CoachContextEnvelope` & Anti-Spoofing Flow
Defined in `backend/domain/phase40_models.py` and `frontend/src/state/copilot.tsx`:
```
[Route Component] -> useCopilotRouteContext(CoachContextEnvelope)
                          |
                          v
[CoachCopilotDrawer] -> POST /api/phase40/coach/ask/stream
                          |
                          v
[PersonalCoachOrchestrator._authorize_and_hydrate_context(uid, req)]
   |-- Verifies `squad_id` belongs to `uid` (scoping via SquadRepository / FC27 research squad)
   |-- Verifies `match_id` belongs to `uid` (`Phase40Repository.list_matches`)
   |-- Verifies `decision_id` belongs to `uid` (`Phase41Repository.get_decision_window`)
   |-- Drops unauthorized IDs + appends `UNAUTHORIZED_OR_INVALID_*_CONTEXT` to `security_notices`
```

## 4. Universal Multi-Route Co-Pilot Coverage (`42E`)
A single global slide-over drawer (`frontend/src/components/CoachCopilotDrawer.tsx`) + header launcher (`CopilotHeaderTrigger` in `Nav.tsx`, `Ctrl+Shift+C`) + contextual page triggers across:
1. `PLAYER_DISCOVERY` (`frontend/src/pages/Search.tsx`): forwards active search filters (`position`, `ovr_min`, `ovr_max`, `playstyle`, `compareIds`).
2. `PLAYER_DETAIL` (`frontend/src/pages/PlayerPage.tsx`): forwards active `entity_id` & player display name.
3. `PLAYER_COMPARE` (`frontend/src/pages/Compare.tsx`): forwards picked player IDs, names, active formation, and tactical profile.
4. `SQUAD_LAB` (`frontend/src/pages/CardSquadLab.tsx`): forwards saved research squad ID, XI card IDs, formation, and tactical profile; preserves confirmation-gated squad proposals (`Confirm` / `Rollback`).
5. `GAMEPLAY_STUDIO` (`frontend/src/pages/GameplayStudio.tsx`): forwards active `video_id` and visible timeline `currentTimeSec`.
6. `DECISION_LAB` (`frontend/src/pages/DecisionReplayLab.tsx`): forwards active `match_id`, `decision_id` (`window_id`), and `action_timestamp_sec`.
7. `GAMER_DNA` (`frontend/src/pages/PersonalCoach.tsx`): forwards selected `squad_id` & `match_id`.

## 5. Rolling Memory & Live DB Freshness (`42D`)
- Older turns condense into a compact `rolling_summary` marked as unverified conversational memory (`recent_turns` bounded).
- Before responding, `Phase40Repository.get_freshness_markers(uid)` injects `LIVE_DB_VERIFIED (eligible_matches=..., route=...)` so stale chat history cannot override live DB additions or deletions.
- `GET / PUT /api/phase40/coach/preferences` persists provider preferences across reloads.
