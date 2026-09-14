# ENGINE EVALUATION (v2.1.0) — 2026-09-14

How the engine is evaluated, what is measured, and the current results.
Three independent layers protect quality:

1. **Golden regression** — exact legacy outputs (bit-identical contract).
2. **Scenario suite** — qualitative behavioral contracts (§49), DB-free.
3. **Quality metrics** — measured properties of real runs (§50), plus the
   experiment framework (§48) and feedback analytics (§33) for the future.

---

## 1. Test inventory (all green, 2026-09-14)

| suite | tests | scope |
|---|---|---|
| baseline backend (14 modules) | 161 | V2 contract, API, auth, security, boundary, e2e |
| `test_engine_intelligence.py` | 50 | unit: formations, intent, archetypes, attribute model, playstyle context, squad intelligence, counterfactuals, confidence v2, bands, weights, validation |
| `test_engine_scenarios.py` | 14 | 12-scenario suite + registry floor + §74 full acceptance (live DB) |
| `test_engine_robustness.py` | 20 | determinism, ±1 perturbation, malformed input, firewalls, flags, adversarial requests |
| `test_engine_ovr_trap.py` | 7 | MANDATORY §50 — synthetic + real-data OVR inversion + fairness |
| `test_engine_unknown_data.py` | 10 | MANDATORY §51 — score/confidence separation, UNKNOWN vocabulary, FC27 empty state |
| frontend (6 files) | 38 | client, UNKNOWN rendering, hooks, session + 5 new v2.1 result-surface tests |
| **total** | **262 backend / 38 frontend** | |

## 2. Golden regression (the frozen contract)

`benchmarks/engine_baseline_v2_2026-09-14.json` — 8 real-data scenarios
(S1 CM/PRESSING constrained … S8 LB balanced) captured pre-upgrade.
After every engine change the winners, exact scores (1e-9), evaluation
counts, confidences, effective weights and full ranked orders are re-checked.
**Current status: ALL IDENTICAL under engine 2.1.0.**

## 3. Scenario suite (§49) — `engine_evaluation.SCENARIOS`

Deterministic fixtures; expectations are behavioral, never "player X must
win" against real data. 12 scenarios:

| # | scenario | contract asserted in tests |
|---|---|---|
| 1 | high_press_st | 84-OVR pressing forward beats 88-OVR luxury forward; tactical_fit decides |
| 2 | possession_cam | creator beats runner under POSSESSION |
| 3 | counter_winger | pace merchant wins; maestro excluded by pace≥90 with reason |
| 4 | defensive_cdm | anchor beats carrier despite −2 OVR |
| 5 | box_to_box_archetype | archetype request: engine CM beats OVR-88 pure ten; archetype_fit KNOWN |
| 6 | ball_playing_cb | passing CB wins; destroyer excluded by short_passing≥80 |
| 7 | attacking_rb | overlapping RB wins the attacking slot despite −3 OVR |
| 8 | low_block_gk | GK scored on gk_* only; no outfield attribute in evidence |
| 9 | budget_unverified | BUDGET_UNVERIFIED reported; candidate kept |
| 10 | chemistry_withheld | team_fit INSUFFICIENT; link facts in evidence; structural fit ADVISORY |
| 11 | **ovr_trap (§50)** | 81-OVR worker beats 90-OVR star on soft fit; star ranked, never hidden |
| 12 | **unknown_data (§51)** | nobody excluded/zeroed; thin evidence → INSUFFICIENT_EVIDENCE band + far lower confidence |

§74 acceptance (live): natural-language "box-to-box CM, 4-2-3-1, high press +
fast build-up, good stamina, must have Intercept, under 500k, complement my
attacking squad" → parse (provenance-checked) → validated requirements →
full layered run → every §54 response field asserted → what-if (swap
secondary profile) must alter the decision surface.

## 4. Quality metrics (§50) — current measurements

| metric | definition | current value |
|---|---|---|
| consistency | same request twice → identical payload | PASS (test_determinism; pool-order shuffle too) |
| constraint accuracy | hard constraints satisfied by every ranked row | PASS — winner verified against pool facts in §74 test (Intercept held; excluded_hard reasons exact) |
| honesty | UNKNOWN never rendered as 0/pass/fail; bands gated | PASS — §51 suite; `INSUFFICIENT_EVIDENCE` band when coverage < 0.5 |
| calibration | score bands validated against real outputs; never probabilities | band text carries "not a probability"; live spot-check: full-intelligence CM winner 0.841 → STRONG_FIT (cov 0.903) |
| latency | warm p50 per pool size | see `benchmarks/ENGINE_BENCHMARKS.md` (54 ms @1K → ~1.0 s @16K legacy; ~1.3 s @10K full-intelligence) |
| reduction ratio | evaluated / loaded after hard filters | position prefilter: CM 10,275/16,228 (63%); Intercept requirement excluded 9,854/10,275 at constraint stage with reasons |
| explanation coverage | ranked rows with evidence + why-not for runners-up | 100% of ranked rows carry component evidence; top-3 always get why_not_alternatives |
| diversity | alternatives across archetypes | pareto `best_alternative_archetype` present whenever ≥2 archetypes exist in range |
| NDCG / MRR | relevance-based ranking metrics | **NOT COMPUTED — requires human labels; deferred until feedback sufficiency (§33). No proxy labels are invented.** |

## 5. Experiment framework (§48)

`scripts/run_engine_experiment.py` + `engine_experiments.run_experiment()`:
baseline vs variant across all 12 scenarios, metrics = winner_change_rate,
mean_abs_score_delta, mean_top3_overlap, constraint_behavior_identical;
persisted to `experiment` / `experiment_result` with config + fingerprint +
engine_version. Production config is never mutated; adopting a variant
requires a code change + full regression + golden validation.

Smoke experiment (persisted, id `82ee6b82…`): attribute_fit 0.30→0.35 at
tactical_fit 0.15→0.10 flipped exactly 1/12 winners (high_press_st) with
identical constraint behavior — evidence that BASELINE V1 weights protect
pressing scenarios; the variant was **not** adopted.

## 6. Feedback analytics (§33)

`GET /api/recommendations/feedback/analytics` — current live state:
68 rows, 21 labeled decisions, context coverage ~60%,
`sufficient_for_ml_experiment: false` (needs ≥500 labels at ≥80% coverage).
Phase remains 1-CAPTURE/2-MEASURE. The deterministic engine is the permanent
fallback; no ML training exists anywhere in the codebase.

## 7. Known limitations (honest list)

* Full-intelligence mode over the unfiltered 10K CM pool runs ~1.3 s warm —
  above the sub-second target; correctness was prioritized (§57). Position
  prefiltering and `disable_counterfactuals` are the available levers;
  caching of precomputed features is designed (§56) but not yet wired.
* Role fit remains INSUFFICIENT/UNKNOWN for FC26 (no verified role data —
  `ENGINE_DATA_REQUIREMENTS.md`).
* Gameplay-profile label thresholds (82) and interaction weights are expert
  priors in `engine_config.py` — to be validated against feedback labels,
  never against cherry-picked examples.
* Versatility uses position-adjacency only (formation-slot awareness wired
  but unexercised without squad-wide slot requests).
