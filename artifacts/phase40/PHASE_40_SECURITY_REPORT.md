# PHASE 40: Security, Privacy & Agent Boundary Report

Grounded in OWASP GenAI / LLM Top 10 controls verified in `backend/tests/test_phase40_coach_and_knowledge.py` and `backend/tests/test_phase40_match_repo_and_dna.py`.

## 1. Access Control & Cross-User Isolation (IDOR Defense)
- Every `/api/phase40/*` private route requires `CurrentUser = Depends(current_user_required)` (401 on anonymous callers).
- Every repository query filters strictly by `WHERE user_id = %s` (`Phase40Repository`); `CoachToolRegistry.execute` strips any `user_id` or `target_user_id` argument before dispatch so the agent cannot read or mutate another user's records.
- Verified in `test_coach_requires_auth_and_enforces_cross_user_isolation`: User B attempting `GET /matches/{id}`, `DELETE /matches/{id}`, or asking Coach about User A receives `404` / clean abstention with zero cross-user leakage.

## 2. Prompt Injection & Instruction Override Defense (OWASP LLM01 / LLM06)
- `detect_prompt_injection` scans incoming user queries for instruction-override, system-prompt exfiltration, SQL injection fragments, and authorization-bypass phrasing.
- On detection, `PersonalCoachOrchestrator` refuses execution cleanly before downstream generation, records diagnostic `security_notices`, returns `abstained = True`, and executes no sensitive mutations (100% block rate across 10 benchmark injection probes).

## 3. External LLM Consent & Data Minimization (OWASP LLM02)
- Core analytical coaching operates 100% locally (`DETERMINISTIC_COACH`, 0 external calls).
- Optional external/local LLM polishing requires explicit `consent_external_llm = True`, sends ONLY anonymized structured finding JSON (never raw `.mp4`/`.webm` video files or email PII), and falls back safely to deterministic output on timeouts/errors.

## 4. User Privacy Controls & Fair-Play Compliance
- `DELETE /api/phase40/matches/{match_id}` removes individual matches.
- `DELETE /api/phase40/privacy/reset` deletes matches, immutable squad snapshots, Gamer DNA cache, mistake patterns, training plans/attempts, and Coach conversation logs cleanly.
- Zero live match automation, controller macro injection, or process memory reading implemented anywhere in the platform.
