# Phase 42 Security, Privacy & Epistemic Integrity Report

## 1. Zero-Trust Server Authorization of `CoachContextEnvelope`
- Client requests pass `CoachContextEnvelope` (`route_name`, `squad_id`, `match_id`, `video_id`, `decision_id`, `selected_card_ids`, `active_filters`, `visible_timestamp_sec`) to `/api/phase40/coach/ask` and `/ask/stream`.
- `PersonalCoachOrchestrator._authorize_and_hydrate_context()` independently validates `squad_id` (`SquadRepository` / FC27 saved squads), `match_id` (`Phase40Repository.list_matches`), and `decision_id` (`Phase41Repository.get_decision_window`) against the authenticated `user.id`.
- Cross-user ID spoofing is scrubbed before tool invocation and logged in `security_notices` (`UNAUTHORIZED_OR_INVALID_SQUAD_CONTEXT`, `UNAUTHORIZED_OR_MISSING_MATCH_CONTEXT`, verified by `test_phase42_context_envelope_idor_and_multimodal_consent_boundary`).

## 2. Multimodal Screenshot Privacy & Redaction Boundary (`42G`)
- **In-Browser Local Canvas Redaction:** `ScreenshotRedactorModal.tsx` draws black redaction boxes locally (`Mask Top Corners` shortcut + manual rectangular masking) and re-exports pixels through `<canvas>.toDataURL('image/jpeg', 0.86)` to strip camera/file EXIF metadata before upload.
- **Explicit Dual Opt-In Check:** Image upload stays disabled on the client unless BOTH `redactionConfirmed` AND `consentMedia` are checked, kept strictly separate from general text provider consent.
- **Server Hard Gate:** Sending `image_b64` when either `user_consent_media=False` or `redaction_confirmed=False` triggers `IMAGE_TRANSMISSION_BLOCKED_REDACTION_AND_CONSENT_REQUIRED` in `security_notices` (`FC_COACH_BENCH_V2` & pytest verified).
- **Epistemic Segregation:** Permitted screenshots emit `CANDIDATE_MULTIMODAL_OBSERVATION_UNVERIFIED` in `multimodal_candidate_notes` and NEVER alter PostgreSQL Gamer DNA or match telemetry rows.

## 3. Credential, Quota & Prompt Hygiene
- Gemini and OpenRouter keys are loaded strictly server-side from `.env` (`pydantic-settings`), filtered by `redact_secrets()`, and never returned in `/providers/health`, SSE payloads, or `safe_ai_public_summary()`.
- Free-only enforcement (`ai_coach_free_only=True`, `ai_coach_allow_paid_usage=False`), per-user RPM caps, daily provider caps, confirmation-gated Squad Proposals (`Confirm` / `Rollback`), and prompt-injection blocking remain active (`test_security.py` + `test_phase42_copilot_cv_training.py` verified).
