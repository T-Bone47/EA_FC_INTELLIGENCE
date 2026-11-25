# Phase 42 Latency & Reliability Optimization Benchmark

## 1. Root Causes Identified
- Rebuilding Okapi BM25 over `FootballKnowledgeService` on every coach/tool initialization.
- Sending oversized generic tool lists instead of intent-scoped schemas (`4–6` tools per intent).
- Retrying already-timed-out/5xx provider requests inside provider HTTP wrappers, nearly doubling wait latency.
- Repeating calls against upstream rate-limited or 503-saturated `(provider, model)` endpoints due to lack of model-level circuit breakers.

## 2. Implemented Engineering Optimizations
1. **Shared Singleton BM25 Cache:** `get_shared_knowledge_service()` in `backend/services/football_knowledge_service.py` constructs and caches the BM25 index once per process (`assert kb1 is kb2` verified in pytest).
2. **Targeted Intent Tool Subsets:** `INTENT_TO_TOOLS` in `backend/services/coach_tools_extended.py` trims tool payloads to `4–6` intent-specific tools (`select_tool_specs_for_intent`).
3. **Fail-Fast Timeouts:** `Settings.effective_provider_timeout()` enforces `14.0s` Gemini / `16.0s` OpenRouter caps (`backend/core/config.py`), with duplicate timeout retries removed in `gemini_provider.py` and `openrouter_provider.py`.
4. **Per-`(provider, model)` Circuit Breaker:** `ProviderHealthMonitor` tracks `CLOSED -> OPEN -> HALF_OPEN` states (`failure_threshold=2`, `open_seconds=120.0`), skipping saturated models before quota consumption.
5. **Streaming TTFT Telemetry:** `LLMResponse.ttft_ms`, `StructuredCoachResponse.ttft_ms`, `tools_sent_count`, and `fallback_used` record time-to-first-token across Gemini and OpenRouter SSE streams.
6. **Optional Redis Multi-Worker Quota (`REDIS_URL`):** `RedisQuotaBackend` uses installed `redis 8.1.0` when `REDIS_URL` is configured, falling back to `in_process` cleanly when absent.

## 3. Before vs After Latency Summary
| Scenario | Observed Before Phase 42 | Observed After Phase 42 (`FC_COACH_BENCH_V2`) |
| :--- | :--- | :--- |
| Live OpenRouter Free (`nvidia/nemotron-3.5-lightning:free`, multi-tool) | Up to ~39s with timeout retries | `11.77s` total (`8.29s` TTFT) to `17.20s` total (`9.36s` TTFT) with 4–11 executed tool calls |
| Degraded Gemini Free after circuit trips | Repeated full-timeout retries per turn | **34.02 ms** total via 0ms circuit-open skip + deterministic fallback |
| Deterministic Offline (`BENCH-DNA-WEAKNESS`, `BENCH-FCIQ-KB`) | Per-turn KB index rebuild overhead | **59.4–60.1 ms** wall time (`34.0–39.4 ms` backend) |
