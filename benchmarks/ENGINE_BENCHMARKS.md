# ENGINE BENCHMARKS

Measured on the live sandbox (single node, PostgreSQL local, 16,228 canonical
FC26 game_players). Reproduce with `python3 scripts/benchmark_engine_v21.py`
(writes `benchmarks/engine_v21_perf.json`). Correctness is validated before
every benchmark run (262 backend tests green).

## 1. Before / after the v2.1 upgrade (§57: measure before optimizing)

Baseline recorded pre-upgrade (`docs/ENGINE_BASELINE.md`,
`benchmarks/reaudit_2026-09-14.json`); after = engine 2.1.0, legacy request
shapes (identical scores — golden regression ALL IDENTICAL).

| scenario | evals | baseline cold/warm (ms) | v2.1 cold/warm (ms) |
|---|---|---|---|
| CM / PRESSING (constrained) | 10,275 | 1,256.9 / 494–581 | 640.8 / 666.6–745.0 |
| ST / COUNTER_ATTACK | 5,241 | 375.6 / 264.5 | 338.2 / 302.1–331.8 |
| GK / LOW_BLOCK | 1,816 | 78.8 / 83.0 | 83.8 / 87.0–94.8 |
| full pool (no position) | 16,228 | 766.7 / 748.8 | 844.5–894.5 / 874.0–951.5 |

Notes:
* Sandbox timing variance between runs is ±15–30% under load; the legacy
  paths are in the same regime as the baseline (full pool ~+15% from the
  additive per-evaluation bookkeeping: effective weights, evidence coverage,
  score bands, constraint hooks).
* Peak RSS for a full-pool run: **210 MB** (baseline process peaked 575 MB
  during the full sweep including all position pools + API traffic).
* Per-request hoisting (`effective_weights`/`_context` computed once, not per
  candidate) is in place since 2.1.0.

## 2. Intelligence mode (all v2.1 layers enabled)

Request: CM, 4-2-3-1, HIGH_PRESS+FAST_BUILD_UP combo, BOX_TO_BOX archetype,
required PlayStyle, 2 attribute bands, interactions + saturation + contextual
playstyles on, complement hint, budget.

| scenario | evals | cold (ms) | warm (ms) |
|---|---|---|---|
| CM family pool | 10,275 | 1,308.6 | 1,268.6–1,388.6 |
| full pool (no position filter) | 16,228 | 1,926.2 | 2,030.4 |
| CM family, counterfactuals disabled | 10,275 | 1,339.4 | 1,268.6 |

* Counterfactual families re-score only the top-20 → ~0 measurable overhead.
* Sub-second warm target (§57): met for legacy paths and all pools ≤ ~10K in
  legacy mode; intelligence mode on a 10K pool is ~1.3 s warm — documented as
  a known limitation, correctness prioritized. Position prefiltering (63%
  pool reduction for CM) and `disable_counterfactuals` are the levers;
  precomputed feature caching (§56) is designed, not yet wired.

## 3. Pool scaling (legacy path, PRESSING, no position filter)

| pool | evals | cold (ms) | warm (ms) | per-candidate (warm) |
|---|---|---|---|---|
| 1,000 | 1,000 | 56.1 | 54.0 | ~54 µs |
| 5,000 | 5,000 | 297.6 | 329.7 | ~66 µs |
| 10,000 | 10,000 | 590.8 | 624.6 | ~62 µs |
| 16,228 | 16,228 | 1,005.0 | 1,129.2 | ~69 µs |

Linear in pool size — retrieval optimization (§56) keeps hard filters before
scoring; no superlinear surprises at 16K+.

## 4. Intent parsing

`intent_parser.parse()` on the §74 acceptance sentence: **~32 ms/call**
(100-iteration mean, includes reference-table scans over 36 PlayStyles and
17 archetypes). Runs once per parse-intent request; not in the scoring loop.

## 5. Reduction ratio examples (telemetry, live)

| request | loaded | evaluated | excluded at constraints |
|---|---|---|---|
| CM (position prefilter) | 16,228 | 10,275 | — |
| CM + required PlayStyle "Intercept" | 16,228 | 10,275 | 9,854 hard-excluded with reasons (421 ranked-eligible holders) |

Every exclusion carries a machine-readable reason; nothing is dropped
silently.

## 6. Preserved historical benchmarks

* `benchmarks/engine_baseline_v2_2026-09-14.json` — golden S1–S8 outputs
  (regression contract; unchanged and re-verified under 2.1.0).
* `benchmarks/API_BENCHMARKS.md`, `benchmarks/reaudit_2026-09-14.json` —
  pre-upgrade API/audit measurements, kept as-is.

## 7. Phase 3 (v2.2.0) — precomputed features, before/after (§29/§30)

Machine note: this sandbox shows ±15% run-to-run variance (CPU contention);
`min of 3-4 warm runs` reported. Warm = pool cache hot, feature caches hot.

| workload (16,228 players FC26) | before §29 | after §29 | target |
|---|---|---|---|
| intelligence CM (PRESSING, interactions+saturation+PS-context, 10,275 evaluated) | 854–863 ms | **779–806 ms** | <1000 ms ✓ (preferred <500 not met — documented) |
| full pool legacy (16,228 evaluated) | 787–880 ms | **792–841 ms** | <1000 ms ✓ |
| archetype ST (POACHER, 5,241 evaluated) | n/a | **287–301 ms** | <500 ms ✓ |

What §29 added: per-candidate `feature_cache` (archetype vectors/scores,
dominant archetype, gameplay profile, versatility, interaction features,
entity data confidence) + memoized normalized position/tactical weight tables
in `ScoringConfig`. All are non-user-specific pure computations; correctness
is unaffected — 338 tests + goldens S1–S8 bit-identical after the change.

Card pool scaling (in-memory card candidates, full intelligence layers,
entity_scope=ut_card, PRESSING):

| cards | cold | warm (min/avg of 3) |
|---|---|---|
| 1,000 | 72 ms | 55 / 56 ms |
| 5,000 | 367 ms | 284 / 302 ms |
| 10,000 | 774 ms | **633 / 669 ms** (<1000 ms ✓) |

`CandidateRepository.load_cards` (60 synthetic firewalled rows via SQL with
LATERAL version/price joins + batched playstyle/role lookups): first load
34 ms, cached 1.4 ms — no N+1 (§49/§50). Production card pool is currently
empty (no permitted source) — timings above are the DATA-READY proof.

Raw JSON: `benchmarks/phase3_precompute_after.json`.
