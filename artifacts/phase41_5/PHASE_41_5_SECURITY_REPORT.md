# Phase 41.5 Security, Privacy & OWASP LLM Controls Report

**Primary Modules:** [security.py](../../backend/services/llm/security.py), [free_guard.py](../../backend/services/llm/free_guard.py), [config.py](../../backend/core/config.py), [coach_tools.py](../../backend/services/coach_tools.py), [phase40_coach.py](../../backend/api/routes/phase40_coach.py)

---

## 1. Credential & Environment Hygiene

1. **Zero Secret Leakage (`redact_secrets` & `redact_dict`)**:
   - Strips Google `AIza...`, OpenRouter `sk-or-v1-...`, Bearer tokens, JWTs, `secret`, `password`, and `api_key=` patterns across exception messages, provider notes, conversation logs, and API errors.
   - Public config inspection runs solely through `Settings.safe_ai_public_summary()`, exposing boolean presence flags (`gemini_configured`, `openrouter_configured`) and model IDs only.
2. **Git & Frontend Isolation**:
   - `.gitignore` excludes `.env` and `.env.*` (with `!.env.example`).
   - `.env.example` contains empty secret placeholders only.
   - Playwright browser inspection (`leakedSecret: false`) and backend unit tests (`test_secret_redaction_and_media_policy`, `test_security.py`) verified zero secrets reach API responses or the DOM.

---

## 2. Free-Tier Privacy & Media Transmission Policies

- **External Video Disabled by Default:** Both `AI_COACH_ALLOW_EXTERNAL_VIDEO` and `AI_COACH_VIDEO_UPLOAD_TO_LLM` default to `false` (checked via `Settings.effective_allow_external_video()`). Raw gameplay video remains strictly local in the Phase 38/39 OpenCV/PyAV CV pipeline.
- **External Screenshot Images Gated:** `AI_COACH_ALLOW_EXTERNAL_IMAGES=false` by default; `check_media_transmission_allowed()` blocks image bytes unless both server setting AND per-request `user_consent_media=true` hold, MIME is `image/png`, `image/jpeg`, or `image/webp`, and size `<= 4 MB`.
- **Minimized Prompt Context:** Only compact session metadata (`game_version`, `game_patch`, `active_squad_id`, `active_match_id`), short recent summaries, and sanitized user questions reach external providers—never email addresses, JWT secrets, or raw match files.

---

## 3. OWASP LLM Top-10 Defenses Verified

| Threat / Category | Implemented Safeguard | Verification Coverage |
| :--- | :--- | :--- |
| **LLM01 Prompt Injection** | `detect_prompt_injection()` + `sanitize_untrusted_text()` strip control characters/markup and wrap retrieved docs/history inside explicit untrusted delimiters; injected turns abort before external inference (`SECURITY_BLOCKED`). | `test_prompt_injection_and_cross_user_isolation`, `100.0%` block rate in `FC_COACH_BENCH_V1` & `run_phase40_benchmarks.py`. |
| **LLM02 Insecure Output Handling** | `_AgentStructuredDraft` Pydantic schema repair, `redact_secrets()`, and strict overwrite of grounded entities (`player_cards`, `evidence_references`, `squad_proposal`, `knowledge_sources`) strictly from verified tool outputs (`_merge_and_finalize`). | `test_anti_hallucination_drops_unverified_facts`. |
| **LLM06 Excessive Agency** | 77-handler allowlist (`CoachToolRegistry`); unknown tools rejected (`REJECTED_UNKNOWN_TOOL`); `user_id` injected server-side (`caller_user_id` strips LLM `user_id`); zero arbitrary SQL/shell/file tools; squad edits blocked behind pending proposals (`POST /api/phase40/squad-proposals/{proposal_id}/confirm`) with `/rollback`. | `test_squad_optimization_proposal_confirm_and_rollback`, `test_unknown_tool_rejected`. |
| **LLM08 Cost / Quota Exhaustion** | `FreeUsageGuard` (`PaidModelBlockedError` on paid models or `usage.cost > 0`), `TurnBudgetTracker`, sliding RPM/per-user RPM, daily provider caps, bounded concurrency semaphore, and HTTP 429 cooldowns. | `test_free_guard_blocks_paid_models_and_disallowed_providers`, `100.0%` paid-model block rate in `FC_COACH_BENCH_V1`. |
| **API Auth & Isolation** | All mutating/user-scoped coach endpoints require authenticated JWT (`HTTP 401` verified live on `GET /api/phase40/coach/providers/health`); sessions and squad proposals verify `(user_id, id)` ownership. | `test_security.py`, live HTTP check. |
