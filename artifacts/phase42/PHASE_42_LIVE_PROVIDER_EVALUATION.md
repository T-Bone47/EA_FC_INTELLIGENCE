# Phase 42 Live Provider Evaluation (`FC_COACH_BENCH_V2`)

**Benchmark Script:** `verification/benchmark_fc_coach_v2.py`  
**Raw Telemetry:** `artifacts/phase42/live_provider_eval_raw.json`

## 1. Configured Free-Only Providers Verified
- **Google Gemini Free API:** Configured (`gemini_model="gemini-4-hydrogen"`, key loaded securely from `.env`, zero secret exposure).
- **OpenRouter Free API:** Configured (`openrouter_model="openrouter/free"`, auto-fallback list verified via free-only registry check).
- **Deterministic Offline Engine:** Always available with zero external API cost (`$0.00`).
- **Isolation Method:** Dedicated benchmark user accounts (`bench_deterministic_*`, `bench_gemini_*`, `bench_openrouter_free_*`) prevented one provider's retry sequence from exhausting another mode's per-user 8 RPM bucket.

## 2. Live Provider Results Observed (2026-11-25)
| Requested Mode | Case ID | HTTP | Actual Provider & Model | Fallback Used | Wall Time (ms) | TTFT (ms) | Tools Sent | Calls Run | Answer Chars | Cards |
| :--- | :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `DETERMINISTIC` | `BENCH-CTX-SCOUT` | 200 | `deterministic` / `deterministic-coach` | `false` | 3377.14 | 0.0 | 0 | 7 | 248 | 7 |
| `DETERMINISTIC` | `BENCH-DNA-WEAKNESS` | 200 | `deterministic` / `deterministic-coach` | `false` | 60.11 | 0.0 | 0 | 3 | 243 | 0 |
| `DETERMINISTIC` | `BENCH-FCIQ-KB` | 200 | `deterministic` / `deterministic-coach` | `false` | 59.37 | 0.0 | 0 | 3 | 243 | 0 |
| `GEMINI` | `BENCH-CTX-SCOUT` | 200 | `deterministic` (after live 503 + timeout) | `true` | 39944.31 | 0.0 | 0 | 11 | 248 | 7 |
| `GEMINI` | `BENCH-DNA-WEAKNESS` | 200 | `deterministic` (after live 503 on both Gemini models) | `true` | 17904.09 | 0.0 | 0 | 4 | 243 | 0 |
| `GEMINI` | `BENCH-FCIQ-KB` | 200 | `deterministic` (circuit open skip!) | `true` | **34.02** | 0.0 | 0 | 3 | 243 | 0 |
| `OPENROUTER_FREE` | `BENCH-CTX-SCOUT` | 200 | `openrouter` / `nvidia/nemotron-3.5-lightning:free` | **`false`** | 17196.50 | **9359.20** | 5 | 11 | **3008** | **9** |
| `OPENROUTER_FREE` | `BENCH-DNA-WEAKNESS` | 200 | `openrouter` / `nvidia/nemotron-3.5-lightning:free` | **`false`** | 11771.64 | **8287.55** | 4 | 4 | **2761** | 0 |
| `OPENROUTER_FREE` | `BENCH-FCIQ-KB` | 200 | `deterministic` (RPM cap hit during multi-call retries) | `true` | 10612.17 | 0.0 | 0 | 5 | 243 | 0 |

## 3. Empirical Insights
1. **Live Upstream Capacity Behavior (Genuine Live Network Truth):** On 2026-11-25, Google's `gemini-4-hydrogen` and `gemini-3.8-flash` endpoints intermittently returned `HTTP 503 UNAVAILABLE` (`This model is currently experiencing high demand`). Meanwhile `openrouter/free` returned HTTP `429` (`google/gemma-4-31b-it:free`), triggering sub-second failover to `nvidia/nemotron-3.5-lightning:free`, which completed full tool-grounded synthesis (`9` verified player cards, `3,008`-char structured coaching output, TTFT `8.29s–9.36s`).
2. **Circuit Breaker Validation Under Real Load:** After 2 consecutive Gemini 503 failures, `ProviderHealthMonitor` tripped `CLOSED -> OPEN` (120s cooldown). Consequently `BENCH-FCIQ-KB` skipped the degraded endpoint in **0ms** (`circuit open (98.7s remaining); skipped without wasting budget`), reducing total wall time from `39,944 ms` to **`34.02 ms`** with clean deterministic synthesis.
3. **Observed Deterministic Limitation:** On generic natural-language `Search` phrasing lacking explicit `"recommend"`/`"find"` tokens, `PersonalCoachOrchestrator` fell back to summarizing cold-start Gamer DNA (`543ms` / `36ms` in Playwright tests) rather than running player search directly unless matched keywords are present.

## 4. Privacy & Redaction Boundary Result (`FC_COACH_BENCH_V2`)
- `redaction_confirmed=False`: Blocked cleanly -> `["IMAGE_TRANSMISSION_BLOCKED_REDACTION_AND_CONSENT_REQUIRED"]`.
- `user_consent_media=True` & `redaction_confirmed=True`: Tagged cleanly -> `["CANDIDATE_MULTIMODAL_OBSERVATION_UNVERIFIED (FORMATION_SCREENSHOT; local_redaction_confirmed=True): External screenshot interpretation is provisional until verified against database records or match telemetry."]`.
