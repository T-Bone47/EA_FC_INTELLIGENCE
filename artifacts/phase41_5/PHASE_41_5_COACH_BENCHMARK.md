# Phase 41.5 Benchmark Report — `FC_COACH_BENCH_V1` & Regression Benchmarks

**Artifact:** [FC_COACH_BENCH_V1_RESULTS.json](./FC_COACH_BENCH_V1_RESULTS.json)  
**Benchmark Script:** [benchmark_fc_coach_v1.py](../../verification/benchmark_fc_coach_v1.py)

---

## 1. `FC_COACH_BENCH_V1` (120 Scenarios Across 17 Football & Security Families)

Scenario families evaluated: `player_discovery`, `card_comparison`, `formation_suitability`, `squad_optimization`, `player_partnership`, `whole_xi_cohesion`, `gamer_dna`, `gameplay_diagnostics`, `football_iq`, `decision_alternatives`, `tactical_knowledge`, `personalized_training`, `missing_evidence`, `synthetic_isolation`, `prompt_injection`, `unsupported_price`, `invalid_card_id`.

| Metric | Deterministic Baseline (120) | Simulated Hybrid ReAct (120) | Gate Target | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Schema Validity Rate** | `100.0%` (`1.0`) | `100.0%` (`1.0`) | `>= 95%` | **PASS** |
| **Tool Selection Accuracy** | `100.0%` (`1.0`) | `100.0%` (`1.0`) | `>= 90%` | **PASS** |
| **Abstention Compliance** | `100.0%` (`1.0`) | `100.0%` (`1.0`) | `100%` | **PASS** |
| **Synthetic Isolation Rate** | `100.0%` (`1.0`) | `100.0%` (`1.0`) | `100%` | **PASS** |
| **Prompt Injection Block Rate** | `100.0%` (`1.0`) | `100.0%` (`1.0`) | `100%` | **PASS** |
| **Paid Model Block Rate** | `100.0%` (`1.0`) | `100.0%` (`1.0`) | `100%` | **PASS** |
| **Provider Requests Executed** | `0` | `198` | Bounded | **PASS** |
| **Reported External Cost (`USD`)** | `$0.0` | `$0.0` | `$0.0` | **PASS** |
| **Latency `p50` / `p95` (`ms`)** | `436.12` / `907.76` | `695.12` / `1358.2` | — | **Measured** |

---

## 2. Live Free-Tier Smoke Comparison (`--live-sample`)

Executed against configured `.env` Gemini and OpenRouter free accounts with `AI_COACH_FREE_ONLY=true` and `AI_COACH_ALLOW_PAID_USAGE=false`:

| Target Requested | Outcome (`FC_COACH_BENCH_V1_RESULTS.json`) | Mode Reached | Provider Calls | Cost (`USD`) | Latency (`ms`) | Observed Behavior |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| `gemini:gemini-4-hydrogen` | `gemini:gemini-4-hydrogen` | `GEMINI_FREE` | `4` | `$0.0` | `39143.06` | Recovered cleanly after transient `503`/`timeout` retry & structured ReAct tool execution (`5` tool records). |
| `gemini:gemini-3.8-flash` | `gemini:gemini-3.6-flash` | `GEMINI_FREE` | `3` | `$0.0` | `29600.52` | Automatic in-provider free failover when `gemini-3.8-flash` timed out and `gemini-4-hydrogen` returned HTTP `503`. |
| `openrouter:openrouter/free` | `deterministic:deterministic-coach` (prior burst: `nvidia/nemotron-3.5-lightning:free`) | `DETERMINISTIC_COACH` (earlier live run: `OPENROUTER_FREE`) | `0` (`1` earlier) | `$0.0` | `9665.81` (`8439.2` earlier) | Preserved valid `StructuredCoachResponse` fallback when OpenRouter empty/rate-limited; direct `openrouter/free` calls also verified on `nvidia/nemotron-3.5-lightning:free` and `nvidia/nemotron-3-ultra-550b-a55b:free`. |
| `openrouter:nvidia/nemotron-3.5-super-vl:free` | `deterministic:deterministic-coach` | `DETERMINISTIC_COACH` | `0` | `$0.0` | `19671.75` | Fail-closed graceful fallback with valid grounded deterministic coaching. |

---

## 3. Existing Phase 40 & Phase 41 Benchmarks (Post-Phase 41.5 Regressions)

| Suite | Scenarios | Key Verified Gates | Latency (`p50` / `p95`) |
| :--- | :---: | :--- | :--- |
| **`verification/run_phase40_benchmarks.py`** | `110` | `schema_valid`: `100.0%`, `bounded_tool_selection`: `100.0%`, `evidence_ref`: `100.0%`, `unsupported_abstention`: `100.0%`, `prompt_injection_block`: `100.0%` | `6.67ms` / `839.68ms` |
| **`verification/run_phase41_benchmarks.py`** | `220` | `schema_valid`: `100.0%`, `evidence_ref`: `100.0%`, `zero_hindsight_leakage`: `100.0%`, `abstention_compliance`: `100.0%`, `coach_tool_routing`: `100.0%` (`peak_traced_memory_mb: 2.156`) | `10.791ms` / `14.058ms` |
