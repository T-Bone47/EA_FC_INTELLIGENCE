# Phase 43A Search Co-Pilot, Provider Latency & Consent Separation Report

## 1. Live Free-Tier Gemini & OpenRouter Provider Audit
Direct live endpoint probes conducted during Phase 43A surfaced intermittent free-tier instability and high tail latency when iterating blindly across candidate models:
- **Gemini Free Models Probed:** `gemini-4-hydrogen` (`503 UNAVAILABLE`), `gemini-3.6-flash` (request timed out), `gemini-3.8-flash` (`503 UNAVAILABLE`).
- **OpenRouter Free Route Probed:** `openrouter/free` experienced HTTP `429` rate limiting on one probe, while `openrouter:recursive/flint-v1.0:free` completed in **`3633.4 ms`**.
- **Bounded Failover Result:** By enforcing turn-level deadlines and capping per-turn fallback attempts, worst-case multi-provider failure latency was bounded from `>45s` down to **`~17s`** before clean transition to deterministic football tool synthesis.

## 2. Turn-Level Deadline, Budget Reservation & Timeout Clamping
- **`backend/core/config.py`:** Configured `ai_coach_total_deadline_seconds = 24.0`, `gemini_timeout = 10.0`, and `openrouter_timeout = 12.0`.
- **`backend/services/llm/free_guard.py` (`TurnBudgetTracker`):** Added `deadline_seconds`, `started_mono`, `elapsed_seconds()`, `remaining_seconds()`, and `is_deadline_exceeded()`.
- **`backend/services/llm/router.py` (`FootballModelRouter`):**
  - Caps Gemini candidates to `2` in `AUTO` routing whenever an OpenRouter free-tier API key is configured, preserving remaining budget for cross-provider failover.
  - Clamps outgoing HTTP timeout to remaining turn budget (`TurnBudgetTracker.remaining_seconds()`).
  - Reserves at least `11.0s` before falling over from Gemini to OpenRouter, exiting early into deterministic mode instead of hanging past the HTTP SSE window.
- **`backend/services/personal_coach_orchestrator.py` (`_run_bounded_agentic_loop`):** Checks turn deadlines between agentic iterations for clean bounded termination.

## 3. Strict Separation of Provider Selection vs External LLM Data-Sharing Consent
- **Defect Resolved:** Previously, selecting an external provider preference could implicitly weaken or bypass `consent_external_llm` gating (`or explicit_external`).
- **Fix Enforced:** Removed implicit bypasses across backend (`PersonalCoachOrchestrator.ask`) and frontend (`frontend/src/state/copilot.tsx`, `PersonalCoach.tsx`, `CoachCopilotDrawer.tsx`).
  - `CoachQuestionRequest.consent_external_llm=False` **strictly blocks** outbound calls to Gemini and OpenRouter regardless of `preferred_provider="GEMINI"` or `"OPENROUTER"`, returning `response_mode="DETERMINISTIC_COACH"` with `CONSENT_REQUIRED_FOR_EXTERNAL_LLM` in `security_notices`.
  - Fixed `savePreferences` payload keys in `copilot.tsx` so persisted user preferences remain synchronized with `/api/phase40/coach/preferences`.
  - Verified by unit test `test_phase43a_consent_separation_deadline_failover_and_search_copilot`.

## 4. Search Co-Pilot Hydration & Live Browser Proof
- **`backend/domain/phase40_models.py` (`CoachContextEnvelope`):** Extended with `route_name`, `selected_player_names`, `active_filters`, `active_formation`, `active_tactical_profile`, `tactical_snapshot_id`, `experiment_id`, `visible_timestamp_sec`, and `normalized_route()`.
- **`backend/services/coach_tools.py` (`search_player_cards`):** Enhanced to accept and forward `club`, `nation`, `league`, `playstyle`, `ovr_min`, and `ovr_max`, returning full card attributes.
- **`backend/services/personal_coach_orchestrator.py`:** Fixed `self.tools.players.get_player` attribute bug (resolved to `player_page`), hydrated active filters and visible card names in `_authorize_and_hydrate_context`, and fixed Search intent classification + deterministic Search comparison fallback.
- **`frontend/src/pages/Search.tsx`:** Publishes `selected_player_names`, `nation`, `league`, active filters, and visible card context into `useCopilotRouteContext`.
- **Live Browser Verification (`http://localhost:5173/search?position=CM&ovr_min=85`):**
  - Selected `Jude Bellingham` (CAM, OVR 90) and `Rodri` (CDM, OVR 90) in FC26 and asked `"Which one is better?"`.
  - `POST /api/phase40/coach/ask/stream` returned `HTTP 200` in `270ms` with candidate-specific comparison referencing `Jude Bellingham`, `Rodri`, `Federico Valverde`, and `Florian Wirtz` rather than generic Gamer DNA fallback.
