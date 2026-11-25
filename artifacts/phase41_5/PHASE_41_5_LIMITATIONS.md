# Phase 41.5 Known Limitations, Operational Notes & Risk Mitigations

1. **Free-Tier Upstream Availability & Latency Spikes:**
   - Live smoke probes on `2026-11-25` showed Google Gemini free endpoints experiencing intermittent HTTP `503` high-demand errors (`gemini-4-hydrogen`) and timeouts (`gemini-3.8-flash`), as well as rate-limiting/empty structured responses on OpenRouter `:free` endpoints under rapid bursts.
   - `gemini-2.5-flash` returned HTTP `404` on this account key and is automatically pruned via `registry.mark_unavailable()`.
   - Latency variance spans `<1s` for deterministic engine mode up to `8s–39s` when an external model executes multi-turn ReAct tool calling and recovers from transient 503 retries.
2. **Market Transfer Coin Prices Remain Unverified:**
   - Live FUT transfer-market pricing APIs are outside this zero-cost verified system; `recommend_players`, `search_player_cards`, and `optimize_squad` explicitly mark `market_price_status="MARKET_PRICE_UNAVAILABLE"` rather than fabricating coin costs.
3. **Free-Tier Data Usage Governance:**
   - Google AI Studio free tier and several zero-priced OpenRouter providers may log/review prompts for service improvement. External video uploads (`AI_COACH_VIDEO_UPLOAD_TO_LLM` / `AI_COACH_ALLOW_EXTERNAL_VIDEO`) and external screenshot uploads (`AI_COACH_ALLOW_EXTERNAL_IMAGES`) remain `false` by default, and users must explicitly consent per request (`consent_external_llm`).
4. **In-Memory Quota State Across Multiple Workers:**
   - `QuotaManager` and `ProviderHealthMonitor` track sliding-window RPM/cooldown counters cleanly per FastAPI worker process via `PersonalCoachOrchestrator.shared_components()`; horizontal multi-worker scaling in production would require moving rate counters to Redis while preserving DB ledger logging in `phase41_5_provider_usage_log`.
5. **Pre-Existing Unrelated Test Suites:**
   - Four legacy suites (`test_engine_adversarial_phase7.py`, `test_engine_v3_real_data.py`, `test_integration_production.py`, `test_zero_budget_research.py`) carry 31 pre-existing assertions targeting earlier V1/V2 schemas or older Starlette test signatures and were left untouched outside Phase 41.5 scope.
6. **Clean-State Test vs Live Separation:**
   - Unit and benchmark suites primarily exercise deterministic mocks (`_BenchSimLLM`) and PostgreSQL catalogue reads, complemented by targeted 4-model live free-tier smoke tests (`benchmark_fc_coach_v1.py --live-sample`). Full live user-authenticated interactive UI chat against live Gemini/OpenRouter streams was verified at component/mock level (`PersonalCoach.test.tsx`) and live backend/knowledge/auth API probes rather than driving an authenticated Playwright login flow end-to-end against live external quotas.
