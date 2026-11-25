# INTELLIGENCE TEST MATRIX — v3.0.0

The v3 behavioural contract. Every scenario states **why** the expected ordering is correct, not only which card wins.

Governing rule, from the session mandate: **no test is weakened to make the suite green, and no v2 test is carried forward merely for compatibility if it encodes behaviour v3 rejects.**

---

## 1. v2 baseline disposition

### 1.1 Preserved

`benchmarks/engine_baseline_v2_2026-09-14.json` — **read-only historical artifact.** Never edited, never regenerated, never used as a v3 pass criterion. A CI check asserts its content hash is unchanged.

### 1.2 Invalidation register

To be written to `benchmarks/V2_INVALIDATION_REGISTER.md`. Each entry names the defect, the evidence, and the v3 mechanism that replaces it.

| # | Invalidated behaviour | Evidence | v3 replacement |
|---|---|---|---|
| V2-1 | Tactical inertness on real FC26 data | Top-10 overlap 10/10 for PRESSING vs LOW_BLOCK, PRESSING vs DIRECT_PLAY, LOW_BLOCK vs BALANCED on 5,654 real candidates; ρ(score,OVR) moves < 0.05 across tactics | Demand composition, tactical path default, signed dimension affinity |
| V2-2 | Absolute attribute scoring reproduces OVR | PC1 = 40.6% of attribute variance, corr(PC1,OVR) = 0.672, mean pairwise \|r\| = 0.388 over 14,412 players | Tactic-specific demand vector at λ=0.6 |
| V2-3 | Missing-data weight redistribution rewards thin evidence | 1-attribute candidate scored 0.8919 vs fully documented 0.8703 | Evidence interval + `C_lo` ranking + coverage floor |
| V2-4 | OVR dominates under insufficient evidence | Redistribution concentrates all weight on `overall_quality` + `position_fit`; winner had `known_components = ['overall_quality','position_fit']`, confidence 0.397 | Both components deleted from scoring |
| V2-5 | Position incompatibility survives inside the engine | 91 ST ranked for CB, `position_fit=0.05`, `excluded_hard: []` | Gates G3/G4 |
| V2-6 | Broken team-fit league comparison | `fit_components.py:277` — `slot.league == slot.league` | Corrected comparison + regression test |
| V2-7 | Explanations use different weights than scoring | `explanation_service.py:34,37` reads static `COMPONENT_WEIGHTS`; reported 0.15 where scoring used 0.50 | `ScoringContext` + reconstruction test |
| V2-8 | OVR tie-breaking in main sort and Pareto | `recommendation_engine_v2.py:543`, `:658` | Tie-break `(−R, −κ, entity_id)` |
| V2-9 | Alphabetical tie-breaking | `:544` sorts on `name` before `entity_id`; decided the PRESSING/POSSESSION failure at tied 0.8919 | `entity_id` only |
| V2-10 | Failing product-thesis tests | 19 genuine failures incl. `test_pressing_vs_possession_flip`, `test_high_ovr_winger_unsuited_defensive`, `test_90_generic_gk_vs_82_specialist` | Rewritten as §4 golden scenarios |
| V2-11 | Dead `insufficient_evidence` flag | Defined at `:116`, referenced nowhere; docstring contradicts sort comment at `:535` | Replaced by `NOT_EVALUABLE` status |
| V2-12 | Tactical floor as a second exclusion path | Opaque double-penalty alongside tactical demand | `min_fit` threshold in `R` units |

### 1.3 v2 test triage

| Verdict | Applies to | Action |
|---|---|---|
| `CARRIED` | Data-hygiene, UNKNOWN semantics, FC26/FC27 wall, synthetic firewall, determinism, fairness (name/club/nation/price do not affect score) | Unchanged. These are the strongest parts of v2. |
| `REPLACED` | OVR trap, tactical discrimination, position fit, confidence, Pareto | Same intent, expectations recomputed under v3 |
| `INVALIDATED` | Weight-redistribution tests, `overall_quality` weighting tests, tactical-floor exclusion tests, golden bit-identity assertions | Deleted with a register reference |
| `DELETED` | `test_debug_adversarial.py` | Ten `assert False` stubs — debugging scaffolding, not tests |

---

## 2. Test tiers

| Tier | Purpose | Blocking | Needs DB |
|---|---|---|---|
| **T0 Invariants** | Mathematical properties | Yes | No |
| **T1 Adversarial goldens** | Product thesis | Yes | No |
| **T2 Real-data behaviour** | Population-level properties | Yes | Foundation CSV |
| **T3 Integration** | API contract, provenance | Yes | Yes |
| **T4 Drift monitors** | Release-over-release | Warn | Foundation CSV |

`[POLICY]` **T0–T2 must run with zero database and zero web-framework dependencies.** The current autouse `conftest` fixture imports the FastAPI chain, so even pure math tests cannot be *collected* without `psycopg`, `bcrypt`, `pyjwt`, `pydantic-settings` and `fastapi`. This is a prerequisite for the whole matrix: the deterministic core needs its own test lane, and the fixture must be scoped to API tests.

---

## 3. T0 — Invariants

Property-based, run over ≥ 500 real candidates × ≥ 5 demand vectors. All are build-blocking.

| ID | Invariant | Assertion | Measured baseline |
|---|---|---|---|
| **INV-1** | Monotonicity | `v_a += 5` for `a ∈ D` without an explicit target ⟹ `R` non-decreasing | Capability-only **0 / 3,360**; rejected z-score formulation **1,321 / 3,360 (39.3%)** |
| **INV-2** | Pareto dominance | `A ≥ B` on all `a ∈ D`, `K(A) ⊇ K(B)` ⟹ `R(A) ≥ R(B)` | Capability-only **0 / 17,465**; rejected **2** |
| **INV-3** | Irrelevance | changing `a ∉ D` ⟹ `R` unchanged (exact) | Holds by construction |
| **INV-4** | Pool independence | `R(c)` identical alone vs in any pool | Capability-only max \|Δ\| **0.0000**, rank corr **+1.0000**, top-20 **20/20**; rejected 0.0154 / 0.9986 / 19-20 |
| **INV-5** | Evidence non-reward | removing a published demanded attribute never raises `R` or rank | **The direct fix for V2-3** |
| **INV-6** | Bounds ordering | `C_lo ≤ R/M ≤ C_hi`; equality iff `κ = 1` | — |
| **INV-7** | Modifier bound | `M ∈ [0.85, 1.15]` always, with every raw and capped value logged | — |
| **INV-8** | Score reconstruction | `Σ contributions + Σ modifiers == R` ± 1e-9 from `ScoringContext` alone | **Fixes V2-7** |
| **INV-9** | Determinism | same request + data version + config version ⟹ byte-identical response | Carried from v2 |
| **INV-10** | Demand normalisation | `Σ w = 1 ± 1e-9` after every stage | — |
| **INV-11** | UNKNOWN preservation | no `⊥` becomes 0, mean, or default on any path | Carried from v2 |
| **INV-12** | Version wall | FC26 config never applied to FC27; FC27 has no data | Carried from v2 |
| **INV-13** | Synthetic firewall | `SYNTHETIC_TEST` reaching the engine raises | Carried from v2 |
| **INV-14** | Fairness | name, club, nation, price, rarity, card type do not change `R` | Carried from v2 |
| **INV-15** | No OVR channel | `R` is invariant to `overall_rating` when all attributes are held fixed | **New — closes V2-4** |

INV-15 is the sharpest anti-OVR test available: it asserts OVR has **no** independent path into the score. It fails immediately if anyone reintroduces an OVR component, tie-break or nudge.

---

## 4. T1 — Adversarial golden scenarios

Each scenario is a contract entry in `benchmarks/engine_contract_v3.json`:

```json
{
  "id": "G-A1",
  "intent": "high OVR with poor tactical fit must lose to lower OVR with excellent fit",
  "why": "capability is measured over the demanded attributes; the demanded
          attributes are where the lower-OVR card is stronger",
  "request": { ... },
  "candidates": [ ... ],
  "expect": { "rank_1": "...", "reason_must_cite": ["..."], "margin_min": 0.02 },
  "must_not": ["rank_1 decided by overall_rating", "rank_1 has coverage below kappa_min"],
  "claim_class": "POLICY | MATH | EMPIRICAL"
}
```

`[POLICY]` Three mandatory fields beyond the expected winner: `why` (the football and mathematical reason), `reason_must_cite` (the explanation must name this evidence — preventing a right answer for a wrong reason), and `must_not` (the failure modes this case exists to catch).

### CASE A — High OVR, poor tactical fit vs lower OVR, excellent fit

| ID | Setup | Expect | Why | Condition | Measured |
|---|---|---|---|---|---|
| **G-A1** | LOW_BLOCK RM: Attacker87 (pace 90, defending 40, stamina 70) vs Worker82 (defending 75, stamina 88) | Worker82 | LOW_BLOCK demand loads defensive and stamina attributes; Attacker87's strengths carry near-zero demand weight | `R(Worker82) > R(Attacker87)` by ≥ 0.02 | **PASS, margin 0.0904 at λ=0.6** *(v2: FAILS — Attacker87 wins)* |
| **G-A2** | POSSESSION CM: Generic91 (all ~80-86) vs Specialist83 (passing/vision/control 90-93) | Specialist83 | Possession demand concentrates on passing, vision, ball control, composure — where Specialist83 leads despite −8 OVR | `R(Spec) > R(Gen)` by ≥ 0.02 | **PASS, margin 0.0438** |
| **G-A3** | Same pair, BALANCED profile | Generic91 | With neutral tactical demand, demand is position-generic and the broader card is genuinely better | Ordering **reverses** vs G-A2 | Must hold — proves context drives the flip |

G-A3 is essential. G-A2 alone could be passed by a system biased toward low OVR. The pair together proves the ordering is *contextual*.

### CASE B — Pace vs role compatibility

| ID | Setup | Expect | Why | Condition |
|---|---|---|---|---|
| **G-B1** | LOW_BLOCK CB: Pacey (pace 86, defending 80) vs Block (pace 65, defending 89, tackle 88, strength 88) | Block | Low block reduces `block_height`, which lowers pace demand and raises positional/duel demand | `R(Block) > R(Pacey)` |
| **G-B2** | Same pair, HIGH_PRESS | Pacey | High line raises `block_height`, raising recovery-pace demand | Ordering **reverses** vs G-B1 |
| **G-B3** | PACE_ABUSER: elite pace, poor everything, absolute level far below pool | Not rank 1 | Pace demand is high but not exclusive; a card failing the remaining demand cannot lead | `R` below any balanced candidate of similar level |

G-B2 is the direct test that `block_height` has a **signed** effect. v2's `abs()` treatment gave low block and high press the same attribute pull — a contributing cause of V2-1.

### CASE C — Expensive marginal gain vs cheap strong value

| ID | Setup | Expect | Why | Condition |
|---|---|---|---|---|
| **G-C1** | Two cards, `ΔR = 0.01`, prices 2.0M and 150K, no budget set | Higher `R` ranks 1; cheaper card leads `best_value` | Price is not a ranking input; value is a separate objective | Ranking identical with prices removed |
| **G-C2** | Same pair, `budget_coins = 500K` | Expensive card `FAILED` on budget | Explicit budget is a hard ceiling | Excluded with class `FAILED` |
| **G-C3** | Same pair, prices unverified | Both ranked; `BUDGET_UNVERIFIED`; `best_value` unavailable with reason | Unverified price is not "affordable" and not "expensive" | No fabricated value score |

### CASE D — Duplicating squad strength vs filling a weakness

| ID | Setup | Expect | Why | Condition |
|---|---|---|---|---|
| **G-D1** | Squad already holds two elite `CREATIVE_PLAYMAKER`; candidates are a third playmaker vs a `BALL_WINNER` | Individual ranking **unchanged** by squad context; `squad_structural` favours the ball-winner | Squad fit is advisory and must not silently reorder individual fit | `R` identical with and without squad context while `m_squad` is off |
| **G-D2** | With `m_squad` enabled | Ball-winner may overtake, by at most 0.05 | Bounded modifier, explicitly logged | Rank change traceable to `m_squad` in `ScoringContext` |

G-D1 encodes the `[POLICY]` decision that squad context must be a *visible, bounded* influence, never an invisible reordering.

### CASE E — Excellent but irrelevant PlayStyle vs ordinary but relevant

| ID | Setup | Expect | Why | Condition |
|---|---|---|---|---|
| **G-E1** | POSSESSION CM: card with `Aerial Fortress+`, `Power Shot+` vs card with base `Tiki Taka`, `First Touch` | Tiki Taka card gains more from `m_playstyle` | Context value: profile-valued 1.0 vs neutral 0.35; `+` tier does not rescue irrelevance | `m_playstyle(B) > m_playstyle(A)` despite A holding two `+` |
| **G-E2** | Same cards, DIRECT_PLAY | Reverses | `Aerial Fortress` is profile-valued under DIRECT_PLAY | `m_playstyle(A) > m_playstyle(B)` |
| **G-E3** | Card with 6 PlayStyles, all neutral, vs card with 1 profile-valued | Single relevant PlayStyle contributes more | Guards PlayStyle-count bias | Count alone never wins |

### CASE F — Incomplete evidence vs complete lower-rated

| ID | Setup | Expect | Why | Condition | Measured |
|---|---|---|---|---|---|
| **G-F1** | 84 with 1 published attribute vs 84 fully published, POSSESSION CM | Thin card `NOT_EVALUABLE`; documented card rank 1 | κ = 0.16 < 0.60; nothing is known about the thin card, so it is not ranked at all | Thin card absent from `ranked`, present in `not_evaluable` | **PASS** — `C_lo` 0.5257 vs 0.8544 *(v2: thin card ranked #1)* |
| **G-F2** | 84 at κ=0.85 with strong covered values vs 84 at κ=1.00 | Full-coverage card rank 1; partial card rank 2 with `C_hi > C_lo(winner)` | Missing weight charged at P10; upside surfaced honestly, not claimed | `C_hi(partial) = 0.8552 > C_lo(winner) = 0.8544` | **PASS** |
| **G-F3** | Identical candidates, one missing a *weak* demanded attribute | Missing-attribute card ranks **lower** | Missing data must never be an escape from a weakness | INV-5 applied to a golden case |
| **G-F4** | Whole pool below κ_min | Empty ranking + explicit reason; **no** fallback to OVR | Silence is correct when nothing is known | `ranked == []`, reason present |

G-F4 is the scenario v2 handles worst: under redistribution it would confidently return an OVR ordering of cards it knows nothing about.

### CASE G — Conflicting source data

| ID | Setup | Expect | Why | Condition |
|---|---|---|---|---|
| **G-G1** | Two sources disagree on a demanded attribute; resolver picks the higher-authority value | Resolved value scores; **confidence reduced**; `R` unchanged relative to the same card with an undisputed value | Conflict is an evidence-quality fact, not a capability fact | `R` identical; `confidence` strictly lower; conflict named in reasons |
| **G-G2** | Conflict unresolvable (equal authority, equal recency) | Attribute treated as `⊥` — reduces κ, widens the interval | We do not know the value; picking one would be fabrication | κ excludes it; both bounds reflect it |
| **G-G3** | Conflicting *position* | `UNVERIFIABLE`, not `FAILED` | Cannot check ≠ fails check | Exclusion class `UNVERIFIABLE` |

### CASE H — Near-identical scores

| ID | Setup | Expect | Why | Condition |
|---|---|---|---|---|
| **G-H1** | `\|ΔR\| < 0.005`, equal coverage | Reported as a tie; ordering by `entity_id` | Contextually indistinguishable; no informative discriminator remains | Response flags `effectively_equivalent` |
| **G-H2** | `\|ΔR\| < 0.005`, coverage 1.00 vs 0.70 | Better-evidenced card ranks first | Certainty is the only informative discriminator left | Tie-break cites coverage, never OVR |
| **G-H3** | `\|ΔR\| < 0.005`, OVR 91 vs 79 | **OVR must not decide.** Order by coverage then `entity_id` | Capability already contains quality; re-entering OVR double-counts | Flipping only OVR does not change order — **closes V2-8** |
| **G-H4** | `\|ΔR\| < 0.005`, names "Aaron" vs "Zinedine" | Alphabetical order must not decide | — | Renaming does not change order — **closes V2-9** |

### CASE I — Role mismatch *(mandate item 11)*

| ID | Setup | Expect | Why | Condition |
|---|---|---|---|---|
| **G-I1** | Role requested, no Role data ingested | `m_role = 0`; `role_demand: UNAVAILABLE`; candidate **not** excluded | Missing Role ≠ incompatible Role | No candidate excluded on role grounds |
| **G-I2** | Card publishes Roles but not the requested one | Reported as unavailable for that role, not as failing it | Absence of a listing is not a verified incompatibility | Class `UNVERIFIABLE` |
| **G-I3** | Role data present, familiarity known | `m_role` applied, capped at ±0.05, logged | Effect size `[UNKNOWN]` — bound stays tight | Contribution visible in `ScoringContext` |

G-I3 is **inactive until Role data exists** and must be marked `PENDING_DATA`, not silently passing.

### CASE J — Specialist vs generic high OVR *(mandate item 11)*

| ID | Setup | Expect | Why | Condition | Measured |
|---|---|---|---|---|---|
| **G-J1** | POSSESSION CM: Generic91 vs Specialist83 | Specialist83 | Demand concentrates where the specialist leads | ≥ 0.02 margin | **PASS, 0.0438** |
| **G-J2** | **GUARD:** identical profile *shape*, quality 80 vs 88 | Higher88 | Same shape ⟹ fit cannot discriminate; capability must | ≥ 0.02 margin | **PASS, 0.0731** |
| **G-J3** | **GUARD:** perfect shape at 62% of pool level vs solid well-matched 84 | SolidPoss84 | Fit modifies capability; it does not replace it | Large margin expected | **PASS, 0.3241** |
| **G-J4** | 90 GK generic vs 82 GK specialist under a distribution-heavy profile | Specialist82 | GK demand under BUILD_UP loads `gk_kicking`/`gk_positioning` | — | v2 **FAILS** (`test_90_generic_gk_vs_82_specialist`) |

**G-J2 and G-J3 are the most important tests in the matrix.** They are the guard direction of the product thesis. A system that passes G-J1 but fails these has replaced OVR bias with low-OVR bias — the exact over-rotation the mandate warns against, and the failure mode that disqualified the LEVEL × SHAPE prototype's cousin, pure-shape scoring `[MEASURED]`: top-3 under pure shape were 69, 65 and 70-rated unknowns with ρ(OVR) = −0.27.

### CASE K — Squad-context differences *(mandate item 11)*

| ID | Setup | Expect | Why | Condition |
|---|---|---|---|---|
| **G-K1** | Same card, same request, two different squads | Individual `R` **identical**; `squad_structural` differs | Individual fit is a property of card × request, not of squad | `R` equal to 1e-12 |
| **G-K2** | Squad with no verified link facts | `squad_structural` `INSUFFICIENT_EVIDENCE`, not a low score | Unknown structure is not bad structure | Withheld with reason |
| **G-K3** | Chemistry requested, FC26 rules unverified | Chemistry `UNKNOWN`; never a number | `[UNKNOWN]` FC26 mechanic | No chemistry score in any payload |
| **G-K4** | League link counting | Shared-league count correct for a mixed squad | **Closes V2-6** — `slot.league == slot.league` always returned true | Explicit fixture with known link counts |

---

## 5. T2 — Real-data behaviour

Against `data/fc26_real_foundation/players.csv` (16,228 rows). Population-level properties that unit tests cannot express.

| ID | Property | Threshold | v2 measured |
|---|---|---|---|
| **RD-1** | Tactical discrimination: mean top-10 overlap across PRESSING / POSSESSION / LOW_BLOCK / PACE_ABUSER / DIRECT_PLAY | **≤ 6.0 / 10** | **9.6 / 10 — FAIL** |
| **RD-2** | Opposed-tactic separation: PRESSING vs LOW_BLOCK top-10 overlap | **≤ 4 / 10** | **10 / 10 — FAIL** |
| **RD-3** | OVR correlation band: ρ(R, OVR) per profile | **0.35 ≤ ρ ≤ 0.85** | 0.575–0.754, but flat across tactics |
| **RD-4** | Tactical responsiveness: spread of ρ(R,OVR) across profiles | **≥ 0.15** | **< 0.05 — FAIL** |
| **RD-5** | Coverage: share of real candidates reaching `κ ≥ κ_min` | **≥ 0.95** for game_player scope | — |
| **RD-6** | Top-50 quality sanity: median OVR of top 50 within ±6 of pool P95 | guards over-rotation to low OVR | — |
| **RD-7** | Football plausibility panel: top-3 per profile reviewed by a human once per release | qualitative gate | λ=0.6 prototype produced Kanté/Joelinton for PRESSING, Wirtz/Pedri/De Bruyne for POSSESSION, Palhinha/Casemiro/Souček for LOW_BLOCK |

`[POLICY]` **RD-3 is a two-sided band, deliberately.** A floor of 0.35 prevents over-rotation toward obscure specialists; a ceiling of 0.85 prevents the v2 collapse. Both bounds are product decisions and need an owner.

`[POLICY]` RD-4 is the single most diagnostic release metric: it measures whether tactics change *what kind* of player wins, which is the product's entire proposition. v2 would fail it by a factor of three.

---

## 6. T3 — Integration

| ID | Assertion |
|---|---|
| **INT-1** | Every ranked row carries a complete `ScoringContext`; INV-8 reconstruction holds end-to-end through the API |
| **INT-2** | `excluded` is partitioned into `FAILED` / `UNVERIFIABLE` / `NOT_EVALUABLE`, each with a machine-readable reason |
| **INT-3** | Every scored attribute traces to a `source_observation_id` |
| **INT-4** | Response carries `engine_version`, `config_version`, `data_version`, `reference_table_version` |
| **INT-5** | Candidate SQL has no `LIMIT` — the pool is never truncated by an OVR-ordered query |
| **INT-6** | `ingestion/meta_signals` symbols are unreachable from the scoring path (import-graph assertion) |
| **INT-7** | FC27 request returns `NO_DATA`, never FC26 data or config |
| **INT-8** | Engine-derived labels (archetypes, gameplay profile, dimensions, duties) are marked `ENGINE_DERIVED` in every payload |
| **INT-9** | Replaying a stored request at the same versions reproduces the stored response byte-for-byte |

INT-5 and INT-6 are structural anti-bias tests: they make the two most likely future regressions — a truncating query, and meta data leaking into scoring — fail at build time rather than in production.

---

## 7. T4 — Drift monitors

Warn, not block. Recorded per release to `benchmarks/v3_drift/`.

| ID | Monitor | Alert |
|---|---|---|
| **DR-1** | ρ(R, OVR) per position × profile | outside RD-3 band, or moves > 0.10 between releases |
| **DR-2** | Mean top-10 overlap across tactics | rises above 6.0/10 |
| **DR-3** | Share of `NOT_EVALUABLE` candidates | rises > 5 points |
| **DR-4** | Mean `C_hi − C_lo` | widening signals data-quality regression |
| **DR-5** | Modifier saturation rate (`M` hitting a cap) | > 20% suggests bounds are too tight |
| **DR-6** | Rank churn vs previous release on a frozen request set | > 30% top-10 churn requires a changelog entry |

`[POLICY]` DR-6 is the guard against silent behavioural drift. Any config change large enough to churn a third of results must be a declared, versioned decision — not a side effect.

---

## 8. Claim-class register

Per mandate item 13. Each element of the contract is one of four kinds, and the distinction determines who can change it and what evidence is needed.

| Kind | Meaning | Change requires | Examples |
|---|---|---|---|
| **Mathematical correctness** | Provable from definitions; not negotiable | A proof, or a definition change | INV-1…INV-6, INV-8, INV-10, normalisation, bound ordering |
| **Product policy** | A choice with no objectively correct answer | Named owner + changelog | λ, κ_min, θ_pos, M bounds, RD-3 band, ranking on `C_lo`, OVR removed from tie-break, Pareto membership |
| **Empirical hypothesis** | Believed, measured on FC26 data, may not generalise | Re-measurement per version | λ=0.6 discrimination (interpolated, **unmeasured**), P10/P90 quantiles, ρ band feasibility, RD-5 coverage |
| **Verified FC26 mechanic** | Established game behaviour | Source evidence | **Currently empty.** Role behaviour, PlayStyle effect sizes, chemistry rules and market dynamics are all `[UNKNOWN]` and none is asserted anywhere in v3 |

The empty fourth row is deliberate and load-bearing: **v3 asserts no FC26 gameplay mechanic.** Everything tactical is an engine convention, labelled as such in the payload. This is what lets the system survive a gameplay patch without retracting claims it never made.

---

## 9. Definition of done for v3

1. All T0 invariants pass. INV-1, INV-2, INV-4, INV-5, INV-8 and INV-15 are non-negotiable.
2. All T1 goldens pass, **including guards G-A3, G-B2, G-J2, G-J3** — the tests that prevent over-rotation.
3. RD-1 through RD-5 within thresholds; RD-7 panel signed off.
4. All T3 integration assertions pass.
5. v2 baseline file hash unchanged; invalidation register complete with evidence per entry.
6. `test_debug_adversarial.py` deleted.
7. T0–T2 run with no database and no web framework installed.
8. Every `[POLICY]` constant in §14 of the model spec has a named owner and a changelog entry.
9. **λ=0.6 real-pool discrimination measured**, not interpolated, before the constant is frozen.

`[POLICY]` Criterion 2 is the one most likely to be under pressure during implementation, because the guard cases are the ones that make the engine look conservative. They are not optional. An engine that fails them has not fixed v2's bias — it has inverted it.
