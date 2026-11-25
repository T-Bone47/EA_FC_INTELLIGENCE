# Phase 41.5 Strict Free-Only Usage & Quota Governance Policy

**Enforcement Modules:** [free_guard.py](../../backend/services/llm/free_guard.py) (`FreeUsageGuard`, `QuotaManager`, `TurnBudgetTracker`), [openrouter_provider.py](../../backend/services/llm/openrouter_provider.py), [gemini_provider.py](../../backend/services/llm/gemini_provider.py)

---

## 1. Mandatory Configuration Controls (`.env` / `Settings`)

| Flag | Value | Structural Enforcement |
| :--- | :--- | :--- |
| `AI_COACH_FREE_ONLY` | `true` | Blocks any model lacking free-tier verification BEFORE HTTP call (`PaidModelBlockedError`). |
| `AI_COACH_ALLOW_PAID_USAGE` | `false` | Keeps Ollama, OpenAI, Anthropic, Groq, and paid Gemini/OpenRouter tiers hard-blocked. |
| `AI_COACH_DETERMINISTIC_FALLBACK` | `true` | Ensures core platform (V3.2.1 recommendations, Squad Lab, Gamer DNA, Football IQ, Decision Intelligence) remains 100% functional with both LLMs offline or rate-limited. |
| `AI_COACH_ALLOW_EXTERNAL_VIDEO` / `AI_COACH_VIDEO_UPLOAD_TO_LLM` | `false` | Dual alias flags both honored; raw match video stays local inside Gameplay Studio CV pipeline. |
| `AI_COACH_ALLOW_EXTERNAL_IMAGES` | `false` | Screenshot vision upload disabled by default; requires server flag + explicit per-request `user_consent_media=true` + MIME/4MB limit. |
| `AI_COACH_MAX_TOOL_ROUNDS` | `3` | Hard loop cap preventing unbounded ReAct tool chatter. |
| `AI_COACH_MAX_PROVIDER_REQUESTS_PER_TURN` | `4` | Counts every individual provider HTTP call (initial round, tool-synthesis follow-ups, failover calls) per user question. |

---

## 2. Gemini & OpenRouter Billing Protections

### Google Gemini Free Controls
1. Project billing remains disabled at the Google AI Studio / GCP level; no credit card or paid fallback is used.
2. Application-side allowlist (`GEMINI_FREE_TIER_MODELS`) permits only confirmed free-tier endpoints (`gemini-4-hydrogen`, `gemini-3.8-flash`, `gemini-3.6-flash`, etc.).
3. Heavy reasoning / Pro / TTS / Image / Live models (`gemini-4-argon`, `gemini-4-carbon`, `gemini-2.5-pro`, `gemini-3.1-pro-preview`, `*-tts`, `*-image`) raise `PaidModelBlockedError` pre-flight.
4. No automatic escalation to paid Gemini models is permitted.

### OpenRouter Free Controls
1. Model identifiers MUST equal `openrouter/free` or carry `:free` AND verify zero USD pricing across `prompt`, `completion`, and secondary fee keys in `ModelCapabilityRegistry`.
2. Every chat completion request injects:
   ```json
   "provider": {
     "allow_fallbacks": false,
     "require_parameters": true,
     "max_price": {"prompt": 0, "completion": 0}
   }
   ```
3. Paid plugins (`web`, file-parser PDF engines, etc.) are never added to request payloads.
4. Any nonzero `usage.cost > 0` response immediately raises `PaidModelBlockedError`.

---

## 3. Quota & Rate-Limit Safeguards (`QuotaManager`)
- **Daily Request Budget:** `AI_COACH_DAILY_PROVIDER_BUDGET=200` per provider per UTC day.
- **Global & Per-User RPM:** `AI_COACH_REQUESTS_PER_MINUTE=15` global per provider; `AI_COACH_PER_USER_REQUESTS_PER_MINUTE=8` per user ID.
- **Concurrency Bound:** `BoundedSemaphore(3)` prevents request bursts from exhausting free concurrency limits.
- **HTTP 429 & Cooldowns:** Reads `Retry-After` header (default 60s) and triggers **per-`(provider, model)` cooldown** so alternate free models remain reachable without burning turn budget.
- **Turn Token Budget:** `AI_COACH_TOKEN_BUDGET_PER_TURN=16000`.
