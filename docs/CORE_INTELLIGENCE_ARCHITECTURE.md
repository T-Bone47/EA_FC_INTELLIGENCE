# CORE INTELLIGENCE ARCHITECTURE — v3

**Status:** architecture decision. No implementation in this pass.
**Supersedes:** recommendation behaviour of engine v2.3.0.
**Preserves:** `benchmarks/engine_baseline_v2_2026-09-14.json` unchanged, as a historical v2 reference artifact.
**Engine version target:** `3.0.0`.

---

## 0. Evidence classification used throughout

Every claim in this document carries one of five tags. Nothing is promoted between tags silently.

| Tag | Meaning |
|---|---|
| `[MEASURED]` | Reproduced in this session against the repository and/or the real FC26 foundation dataset. Command and numbers recorded. |
| `[IMPL]` | Statement about what the code currently does, read from source. |
| `[MATH]` | Mathematically necessary given the stated definitions. Holds independent of data. |
| `[POLICY]` | A product decision. Not derivable from data. Requires a human owner. |
| `[HYPOTHESIS]` | Plausible, untested. Must not be relied on until measured. |
| `[UNKNOWN]` | Not established. Must stay unknown rather than be assumed. |

Separately, per the session mandate, **no FC26 gameplay mechanic is asserted as verified anywhere in this document.** Role behaviour, PlayStyle in-match effects, chemistry rules and market dynamics are all `[UNKNOWN]`. The architecture is designed to work without them and to absorb them when they arrive.

---

## 1. Why v2 is being replaced

The v2 baseline is not being replaced because a more sophisticated design was available. It is being replaced because it was measured to contradict the product thesis. Four independent failures, each reproduced.

### 1.1 Tactical inertness on real data `[MEASURED]`

5,654 real FC26 CM/CDM/CAM candidates, engine v2.3.0, `limit=10`, identical request except `tactical_profile`:

| Profile pair | Top-10 overlap |
|---|---|
| PRESSING vs LOW_BLOCK | **10 / 10** |
| PRESSING vs DIRECT_PLAY | **10 / 10** |
| LOW_BLOCK vs BALANCED | **10 / 10** |
| POSSESSION vs LOW_BLOCK | 9 / 10 |
| PRESSING vs PACE_ABUSER | 8 / 10 |

Gegenpressing and a low block return the same eleven players. Spearman ρ(score, OVR) = +0.683…+0.718 at CM, +0.575…+0.609 at ST, +0.707…+0.754 at CB, and **moves by less than 0.05 when the tactic changes**.

### 1.2 Absolute attribute scoring reproduces OVR `[MEASURED]` `[MATH]`

PCA over the 29 detail attributes for 14,412 outfield players in `data/fc26_real_foundation/players.csv`:

- PC1 explains **40.6%** of standardised attribute variance
- corr(PC1, OVR) = **0.672**
- mean absolute pairwise attribute correlation = **0.388**

`[MATH]` When every attribute is scored on an absolute "higher is better" scale, any weighted mean over a positively correlated attribute set is a linear probe of the dominant common factor. OVR already measures that factor. Re-weighting cannot escape it: the failure is a property of the attribute covariance structure, not of the tactical tables. **This is why adding more tactical profiles or finer weights would not have fixed v2.**

Corollary, and the reason this matters for the fix: the escape is not to remove level from the score. It is to make the *demand vector itself* tactic-specific enough that the weighted mean measures a different direction in attribute space. Section 3 shows this is sufficient.

### 1.3 Missing data is rewarded, not neutralised `[MEASURED]` `[IMPL]`

v2 redistributes the weight of `UNKNOWN`/`INSUFFICIENT_EVIDENCE` components proportionally across `KNOWN` components. Reproduced, POSSESSION CM:

```
1. UndocumentedSameOVR  score=0.8919  coverage=0.30  band=INSUFFICIENT_EVIDENCE
2. WellDocumented84     score=0.8703  coverage=0.75  band=STRONG_FIT
3. UndocumentedLowOVR   score=0.8378  coverage=0.30  band=INSUFFICIENT_EVIDENCE
```

A candidate publishing exactly one attribute — `short_passing=60`, actively bad for possession — ranks first, above a fully documented 84 with excellent possession attributes. Winner confidence 0.397; winner `known_components = ['overall_quality', 'position_fit']`.

`[MATH]` The mechanism is forced. `overall_quality` and `position_fit` are the two components that are essentially always published. When the contextual components drop out, redistribution concentrates the entire weight on exactly those two. Within a single position pool `position_fit` is near-constant, so the score degenerates to a monotone function of OVR. **The policy "missing data is never a penalty" converts, under redistribution, into "missing data is a bonus, and the bonus is paid in OVR."** This is the OVR bias the product was built to avoid, living inside the honesty mechanism.

`[IMPL]` `CandidateEvaluation.insufficient_evidence` (recommendation_engine_v2.py:116) is dead code — defined, never referenced anywhere in the codebase. Its docstring claims thin-evidence candidates are "down-ranked below well-evidenced ones". The sort comment at lines 535–539 states the opposite. Neither is implemented.

### 1.4 Position incompatibility survives inside the engine `[MEASURED]` `[IMPL]`

```
1. RealCB85             score=0.8549  pos_fit=1.00
2. StrikerPlayedAtCB91  score=0.5352  pos_fit=0.05
excluded_hard: []
```

A 91-rated striker is a *ranked candidate* for a CB slot. Only `CandidateRepository` pre-filtering keeps this out of production. Any caller using the engine directly — tests, benchmarks, experiments, future batch tooling — gets no protection.

### 1.5 Supporting defects `[IMPL]`

| Location | Defect |
|---|---|
| `fit_components.py:277` | `slot.league == slot.league` — always true. League link counts in `team_fit` are meaningless. |
| `explanation_service.py:34,37` | Uses static `COMPONENT_WEIGHTS`, not the effective redistributed weights that produced the score. In §1.3's case it reports weight 0.15 where the score used 0.50. Explanations cannot reconstruct the score they explain. |
| `recommendation_engine_v2.py:543` | Main sort tie-breaks on `-overall_rating`. |
| `recommendation_engine_v2.py:658-659` | `pareto.best_overall` tie-breaks on `overall_rating`. |
| `recommendation_engine_v2.py:544` | Tie-break on `candidate.name` introduces alphabetical bias ahead of `entity_id`. |

### 1.6 Test-suite state contradicts the reports `[MEASURED]`

`PHASE_4_INTELLIGENCE_ENGINE_FINAL_REPORT.md:14` claims "208 unit tests pass (all DB-independent)". `ENGINE_INTELLIGENCE_GAP_AUDIT.md:25` marks OVR Trap Protection "✅ GOOD — GK (82 beats 90) and Outfield (81 beats 90) verified."

Actual, full suite: **24 failed, 279 passed, 138 skipped.** Five failures are PostgreSQL unavailability. Nineteen are genuine:

- `test_high_ovr_winger_unsuited_defensive` — Attacker87 beats Worker82 for LOW_BLOCK RM
- `test_pressing_vs_possession_flip` — `Poss` wins under *both* profiles
- `test_90_generic_gk_vs_82_specialist` — Generic90 wins
- `test_shooting_striker_unsuited_possession`, `test_crossing_vs_possession_winger`, `test_buildup_vs_direct_cb`, `test_352_cb_vs_442_cb`, `test_strict_floor_excludes`, `test_tactical_evidence_names_attrs`
- ten cases in `test_debug_adversarial.py` are `assert False` debug scaffolding committed to the repository and permanently red

The suite is also not DB-independent: the autouse `_relax_rate_limits` fixture in `conftest.py:31` imports the FastAPI dependency chain, so pure deterministic math tests cannot be *collected* without `psycopg`, `psycopg_pool`, `bcrypt`, `pyjwt`, `pydantic-settings` and `fastapi` installed. `scoring_config.py:249` asserts "pure-engine unit tests remain DB-independent". That is false.

---

## 2. The v3 thesis, stated as a testable contract

> **Contextual fit modifies card capability. Contextual fit does not replace card capability.**

Formally, the engine must satisfy both directions simultaneously:

- **Direction A (contextual):** there exist request contexts where a lower-OVR card outranks a higher-OVR card, driven by evidence about the demanded attributes.
- **Direction B (guard):** for two cards with the *same* attribute profile shape, the higher-capability card always outranks the lower one; and a card whose profile shape is perfect but whose absolute level is far below the pool cannot outrank a solid, well-matched card.

`[POLICY]` Both directions are product requirements. A system that satisfies only A is as broken as v2, which satisfies only B. Section 7 of the test matrix pins both.

---

## 3. Candidate architectures, stress-tested

The prior session's LEVEL × SHAPE prototype was the starting point. It was tested against a simpler alternative and **rejected**.

Two formulations, both scored over a *composed demand vector* `w` (position base blended with tactical demand at share λ):

- **B — capability only:** `score = Σ w_a · sat(v_a) / Σ w_a`
- **C — capability × shape modifier:** `score = capability · (0.6 + 0.4·σ(1.6·(demand_z − general_z)))`, z-scored within the candidate pool

### 3.1 Results `[MEASURED]`

**Tactical discrimination and OVR correlation**, real CM pool, mean top-10 overlap across five profile pairs:

| λ (tactical share) | B overlap | B ρ(OVR) range | C overlap | C ρ(OVR) range |
|---|---|---|---|---|
| 0.0 | 10.0 / 10 | +0.86 | 10.0 / 10 | +0.81 |
| 0.3 | 7.0 / 10 | +0.82 … +0.89 | 5.5 / 10 | +0.73 … +0.85 |
| 0.5 | 5.5 / 10 | +0.77 … +0.90 | 3.9 / 10 | +0.61 … +0.86 |
| 0.7 | 4.7 / 10 | +0.68 … +0.90 | 1.5 / 10 | +0.34 … +0.86 |
| 1.0 | 2.1 / 10 | +0.46 … +0.89 | 0.6 / 10 | +0.07 … +0.82 |

**Order-safety**, same demand vector, real candidates:

| Property | B capability only | C capability × shape |
|---|---|---|
| Pareto dominance violations (17,465 dominating pairs) | **0** | 2 (0.01%) |
| **Monotonicity violations** (3,360 single-attribute +5 improvements) | **0** | **1,321 (39.3%)** |
| Pool dependence — max \|Δscore\| when pool changes | **0.0000** | 0.0154 |
| Pool dependence — rank correlation | **+1.0000** | +0.9986 |
| Pool dependence — top-20 stability | **20 / 20** | 19 / 20 |

### 3.2 Why LEVEL × SHAPE is rejected

**The 39.3% monotonicity failure is disqualifying.** `[MEASURED]` Improving a real attribute by +5 points made the candidate score *worse* in four of every ten cases.

`[MATH]` This is not a tuning bug, it is structural. Specialisation is a contrast: `demand_z − general_z`. Raising any attribute outside the demand set raises `general_z` and leaves capability untouched, so the modifier falls and the score falls. Any level-controlled specialisation term has this property. One cannot simultaneously have (i) strict monotonicity in all attributes, (ii) a level-controlled specialisation signal, and (iii) bounded output — the three are incompatible.

The consequences would be visible product-wide: counterfactuals ("what if this attribute were higher") would return negative deltas for genuine improvements; `replacement_analysis` would call an upgraded card a DOWNGRADE; sensitivity analysis would report inverted drivers. No amount of explanation text rescues "we made your player better and the engine says he got worse".

**Pool dependence is a second disqualifier.** `[MATH]` z-scores are computed against whichever candidates are in the request. The same card scores differently depending on which other cards were loaded, so golden scenarios become pool-dependent and results are not reproducible across position filters or data refreshes. Capability-only has exactly zero pool dependence.

### 3.3 Why capability-only is sufficient

The decisive test: six product-thesis adversarial cases, capability-only scoring, λ swept 0.3 → 1.0. `[MEASURED]`

| Case | Expected | Result | Margin at λ=0.6 |
|---|---|---|---|
| LOW_BLOCK RM: 87 attacker vs 82 worker *(currently fails in v2)* | Worker82 | PASS | 0.0904 |
| PRESSING CM: press vs poss profile, both 84 *(currently fails)* | Press | PASS | 0.0689 |
| POSSESSION CM: press vs poss profile, both 84 | Poss | PASS | 0.0838 |
| POSSESSION CM: 91 generic vs 83 specialist | Specialist83 | PASS | 0.0438 |
| **GUARD** — identical shape, 80 vs 88 quality | Higher88 | PASS | 0.0731 |
| **GUARD** — perfect shape at 62% level vs solid 84 | SolidPoss84 | PASS | 0.3241 |

All six pass at **every** λ from 0.3 to 1.0, including both guard cases. Direction A and Direction B hold together.

**The shape machinery was solving a problem that the demand vector already solves.** v2's tactical blindness came from `attribute_fit` using the *position* profile while `tactical_fit` (the only tactic-aware component) carried ~20% of effective weight. Composing position and tactics into a single demand vector recovers the discrimination without z-scores, without pool dependence, and without breaking monotonicity.

`[POLICY]` **Architectural decision: capability-only scoring over a composed demand vector. The LEVEL × SHAPE prototype is rejected.** This is the simpler system and it measures better on every axis that matters.

### 3.4 Choosing λ

`[MEASURED]` λ=0.3 passes all adversarial cases but with thin margins (smallest 0.0136). λ=1.0 discards position knowledge entirely — a POSSESSION CM demand vector would ignore what the CM slot itself requires. λ ∈ [0.5, 0.7] gives adversarial margins of 0.04–0.18 and real-pool top-10 overlap of 4.7–5.5 / 10.

`[POLICY]` **Proposed default λ = 0.6, per-request overridable.** Real-pool discrimination at 0.6 was not measured directly — the sweep measured 0.5 (5.5/10) and 0.7 (4.7/10); 0.6 is interpolated and must be confirmed before the value is frozen. λ is a versioned configuration constant, not a magic number in scoring code.

---

## 4. The v3 pipeline

The §1 pipeline proposed in the mandate is **mostly wrong**, for three specific reasons. The corrected pipeline follows.

**What was wrong with the proposed pipeline:**

1. It lists *Position / Role Requirements*, *Attribute Requirements* and *PlayStyle Requirements* as sequential scoring stages. Measured evidence says they must be **composed into one demand vector before scoring**, because scoring them as separate additive components is precisely what let OVR and position dominate.
2. It places *Data Quality / Confidence* as a stage between value and filtering. Confidence cannot be a downstream stage: evidence coverage determines **eligibility** and the **ranking quantity itself**, so it must act at the gate and inside the score.
3. It places *Candidate Filtering* after tactical and attribute stages. Hard constraints must run first — scoring an ineligible candidate is wasted work and, as §1.4 shows, a correctness hazard.

**v3 pipeline:**

```
  REQUEST  (user context + tactical context + squad context + budget)
      |
  [1] DEMAND COMPOSITION            position x role x tactics x user preference
      |                             -> one normalised weight vector w over attributes
      |
  [2] ELIGIBILITY GATE (hard)       version | position | explicit minima | required
      |                             PlayStyles | league/club/nation | budget ceiling
      |                             | evidence coverage floor
      |                             -> INELIGIBLE candidates leave the ranking entirely,
      |                                each with a machine-readable reason
      |
  [3] CAPABILITY + EVIDENCE INTERVAL
      |                             score_lo / score_hi over w; coverage recorded
      |
  [4] MODIFIERS (bounded, declared) PlayStyle contextual value | role familiarity
      |                             | squad structural fit    -- each capped, each
      |                             logged with its exact contribution
      |
  [5] RANKING                       on score_lo (pessimistic under uncertainty)
      |
  [6] MULTI-OBJECTIVE VIEW          Pareto frontier over declared objectives
      |
  [7] EXPLANATION                   reconstructed from the identical scoring context
```

Key structural differences from v2: demand is composed once rather than scored as competing components; `overall_quality` and `position_fit` are **no longer scored components**; eligibility is enforced in the engine; ranking uses a lower bound rather than a redistributed mean.

---

## 5. Hard constraints vs soft preferences

`[POLICY]` The dividing rule: **a hard constraint expresses something the user cannot use, not something the user would prefer less.** Anything that merely reduces desirability is soft. Anything unverifiable is neither — it is a coverage fact.

### 5.1 Hard — removes the candidate from ranking

| Constraint | Basis | Behaviour when data is missing |
|---|---|---|
| Game version mismatch | `[IMPL]` existing, correct | N/A — always known |
| GK ↔ outfield boundary | `[POLICY]` absolute | N/A |
| Position incompatibility below eligibility threshold | `[POLICY]` **new in v3** | Unpublished position → INELIGIBLE with reason `POSITION_UNKNOWN` |
| Explicit user attribute minimum | `[IMPL]` existing | Unknown attribute → **not** a violation; counts against coverage |
| Required PlayStyle | `[IMPL]` existing | Unpublished → INELIGIBLE, reason `UNVERIFIABLE`, distinct from `NOT_HELD` |
| Required league / club / nation | `[IMPL]` existing | Unknown → INELIGIBLE with `UNVERIFIABLE` |
| Budget ceiling, when the user set one | `[IMPL]` existing | Unverified price → **not** excluded; flagged `BUDGET_UNVERIFIED` |
| Evidence coverage below floor | **new in v3** | This *is* the missing-data rule |

`[POLICY]` `UNVERIFIABLE` and `FAILED` are different exclusion classes and must be reported separately in the API. A card excluded because we could not check it is not a card that failed the check. This distinction is what allows the UI to say "3 cards could not be verified" rather than silently shrinking the pool.

### 5.2 Soft — changes the score

Pace / dribbling / passing / physical preference; preferred PlayStyles; preferred Roles; tactical tendencies; qualitative bands; price efficiency; marginal improvement; squad complementarity. All enter through §1 demand composition or §4 bounded modifiers, never as exclusions.

### 5.3 Neither — changes confidence and coverage only

`[POLICY]` Source disagreement, stale prices, unresolved identity, unpublished PlayStyles and missing Role data must **not** move the score. They move confidence, coverage, and the width of the evidence interval. This is the rule v2 stated and then violated through redistribution.

---

## 6. Ranking model evaluation

Required comparison across the ten candidate approaches.

| Approach | Problem it solves | Data required | Do we have it | Primary failure mode | Interpretable | Cold start | Cost | Verdict |
|---|---|---|---|---|---|---|---|---|
| **A. Simple weighted scoring** | Baseline aggregation | Attributes | Yes | Tactically inert; collapses to OVR `[MEASURED]` | High | Fine | Trivial | **Rejected — this is v2** |
| **B. Contextual weighted scoring** | Demand varies by context | Attributes + demand tables | Yes | Demand tables are conventions, not verified mechanics | High | Fine | Trivial | **ADOPT — v3 core** |
| **C. Constrained optimisation** | Hard requirements | Constraint spec | Yes | Over-exclusion when data is thin | High | Fine | Low | **ADOPT — eligibility gate** |
| **D. Multi-objective optimisation** | Genuine trade-offs | Multiple objectives | Partially — price is `[UNKNOWN]` | Objectives with no data produce phantom fronts | High | Fine | Low | **ADOPT — presentation layer only** |
| **E. Pareto optimisation** | Show non-dominated options | Same as D | Partially | Confuses "not ranked #1" with "bad" | High | Fine | Low | **ADOPT — restricted, see §11** |
| **F. Pairwise learning-to-rank** | Learn ordering from choices | Labelled preference pairs at scale | **No** | Learns popularity, not fit | Low | Fails | Medium | **Defer — P2** |
| **G. Gradient-boosted ranking** | Non-linear interactions | Large labelled set | **No** | Bakes in current meta; unexplainable | Very low | Fails | Medium | **Reject for now** |
| **H. Embeddings / similarity** | "Players like X" | Attribute matrix only | Yes | PC1 dominance `[MEASURED]` makes similarity ≈ OVR similarity | Low | Fine | Medium | **Reject as ranker; possible P2 discovery feature** |
| **I. Contextual bandits** | Online adaptation | Live traffic + reward signal | **No** | Non-deterministic; unexplainable; untestable | None | Fails | High | **Reject** |
| **J. Hybrid deterministic + ML** | Calibrate demand from behaviour | Feedback with context | **Not yet** | ML drift contaminating deterministic core | Medium | Fine | Medium | **Target end-state, P2** |

**Recommendation:** B + C + D/E. Deterministic contextual scoring under hard constraints, with a multi-objective presentation layer.

`[POLICY]` **No ML in the ranking path now.** Not because ML is wrong, but because the required labels do not exist. The `feedback_event` table records SHOWN/SELECTED events `[IMPL]`, which is the right foundation, but a selection is confounded by display order — the system teaches itself what it already showed. Minimum bar before ML is reconsidered, all four required:

1. ≥ 50,000 recommendation events with full request context persisted
2. ≥ 10,000 events carrying a *counterfactual* signal — the user chose something other than rank 1
3. Position × tactical-profile cells with ≥ 500 events each, so learning is not dominated by the popular cells
4. A held-out adversarial set that ML must pass *and* that ML did not train on

Until all four hold, ML is `[HYPOTHESIS]`. The first legitimate ML application is **calibrating the demand vectors** (learning λ and the per-position attribute weights), not replacing the ranker — it keeps the model interpretable and the failure mode bounded.

---

## 7. OVR: the correct balance

`[POLICY]` **`overall_quality` is deleted as a scored component.**

Rationale, not stylistic: quality is not a separate axis from capability. A player's ability to perform the demanded job *is* the quality that matters, and it is already measured by the demand-weighted capability. Scoring OVR again alongside it double-counts general ability and creates the exact channel that produced §1.1 and §1.3. `[MEASURED]` Capability-only satisfies both guard cases without any OVR term.

This is not "OVR doesn't matter". Capability retains ρ(OVR) of +0.68…+0.90 `[MEASURED]` — good players still rank well, because they are genuinely better at the demanded attributes. What is removed is the *free, context-independent* OVR mass that survived regardless of fit.

**Every remaining OVR entry point, and its disposition:**

| Entry point | v2 `[IMPL]` | v3 disposition |
|---|---|---|
| `overall_quality` component (0.15) | Scored | **Removed** |
| Main sort tie-break `-overall_rating` | Active | **Removed** (§10) |
| `pareto.best_overall` tie-break | Active | **Removed** |
| Candidate SQL `ORDER BY overall_rating DESC` | Active, no LIMIT | Retained — deterministic ordering only, no truncation. Must gain a regression test forbidding a LIMIT. |
| `min_overall` / `max_overall` | Hard constraint | Retained — explicit user intent |
| `overall_quality_bias` low/normal/high | Scales the OVR weight | **Removed with the component.** Replaced by a `specialisation_preference` that shifts λ. |
| Explanation text | Reports OVR contribution | Removed; OVR shown as context, never as a reason |
| `replacement_analysis._ovr_honesty` | Narrative only | Retained — it correctly says OVR did not decide |

---

## 8. Tactical intelligence

`[POLICY]` The decomposition proposed in the mandate is correct in shape and is adopted, with one correction: it must terminate in a **demand vector**, not in a list of requirements.

```
Tactical philosophy   (user-facing language: gegenpressing, tiki-taka, low block)
      |
Tactical dimensions   (press_intensity, block_height, build_up_speed,
      |                width, directness, tempo)          -- ENGINE CONVENTION
      |
Attribute demand      (dimension -> attribute affinity, blended with position base)
      |
Demand vector w       (normalised, the single scoring input)
```

`[IMPL]` The dimension layer already exists and is sound — `formations.PROFILE_DIMENSIONS`, `DIMENSION_ATTRIBUTE_AFFINITY`, `dimension_vector()`. **v3 promotes it from an opt-in path to the only path.** v2's fatal choice was gating it behind `_uses_intelligence_attrs(req)`, so default requests never reached it.

Variable disposition:

| Variable | v3 treatment |
|---|---|
| Formation | Explicit input → selects slot set |
| Position | Explicit input → **hard eligibility** + demand base |
| Slot | Explicit input → demand emphasis multiplier |
| Role | Explicit input → demand modifier + eligibility when user demands it. Behaviour `[UNKNOWN]` |
| Build-up style, defensive approach, depth, width, pressing, directness, tempo | Derived → dimension vector → demand |
| Player instructions | `[UNKNOWN]` — not modelled until FC26 mechanics are established |
| Positional freedom | `[UNKNOWN]` — not modelled |
| User tactical priorities | Explicit input → λ and per-attribute preference weights |

`[POLICY]` Every value in `PROFILE_DIMENSIONS` and `DIMENSION_ATTRIBUTE_AFFINITY` is an **engine convention**, not a verified FC26 mechanic. They must be serialised in the API response as `ENGINE_DERIVED` and versioned (§14). No response may imply EA published them.

---

## 9. Archetypes, PlayStyles, attributes, squad, value

### 9.1 Archetypes

`[IMPL]` The existing `archetypes.py` design is sound and is retained: archetypes are **computed** from attributes and PlayStyles, never assigned to named players, with `INSUFFICIENT_EVIDENCE` below 50% coverage. The mandate's requested archetype list maps onto the existing definitions; gaps (Recovery CB, Inverted Fullback, Controller, the three GK archetypes) are additive table entries, not new mechanisms.

`[POLICY]` One change: archetype must **not** be a weighted scoring component (`ARCHETYPE_WEIGHT = 0.10` renormalising the base table `[IMPL]`). An archetype is a *demand template* — requesting `BALL_WINNER` should compose that archetype's attribute weights into `w`, exactly like a tactical profile. This removes a component, keeps the single-demand-vector invariant, and makes archetype requests explainable in the same terms as everything else.

### 9.2 PlayStyles

`[POLICY]` No universal PlayStyle values. `[IMPL]` The existing `playstyle_context.context_value()` tiering (profile-valued 1.0 / position-useful 0.75 / neutral 0.35) is the right *shape*; it is promoted from opt-in to default.

`[POLICY]` PlayStyles enter as a **bounded modifier**, not as demand weight, because a PlayStyle is a discrete capability rather than a graded attribute. Bound: ±10% of capability, hard-capped. Justification for the bound being small: PlayStyle in-match effect sizes are `[UNKNOWN]`, so a large coefficient would be fabricated precision. The bound is a configuration constant, revisable when evidence arrives.

Unpublished PlayStyles → modifier absent, coverage reduced, confidence reduced. Never "has none". `[IMPL]` Existing behaviour, retained.

### 9.3 Attribute importance and interactions

`Attribute × Position × Role × Tactical context × User preference` becomes one composition:

```
w_raw(a) = base_position(a)
           |> blend with tactical demand at share λ
           |> multiply by slot emphasis
           |> multiply by role modifier         (when role data exists; else identity)
           |> override/augment with user preference weights
w(a)     = w_raw(a) / Σ w_raw
```

Every step is a declared, versioned transform that is replayable from the request. `[MATH]` Normalisation at the end guarantees Σw = 1 and keeps scores comparable across contexts.

`[IMPL]` Interaction features (`INTERACTION_FEATURES`, min/geometric-mean over fully-known attribute groups, capped at 30%) are retained essentially unchanged. They are the one place non-additivity is justified — a pressing midfielder is limited by his weakest of stamina/aggression/reading, which a sum cannot express. They must be re-verified for monotonicity under the v3 scorer before release; `min` and geometric mean are both monotone `[MATH]`, so this should pass, but it must be tested rather than assumed.

Saturation `[IMPL]` is retained and becomes default rather than opt-in: it is monotone `[MATH]` and it is the mechanism that stops 99 pace from being worth twice 95 pace.

### 9.4 Squad context

`[POLICY]` Squad fit stays **advisory and separate** from individual fit. The three quantities are reported separately and never silently summed:

```
capability      — can this card do the job              (ranking quantity)
squad_structural— what changes if it joins THIS squad   (advisory, bounded)
chemistry       — UNKNOWN until FC26 rules are verified
```

`[IMPL]` `squad_intelligence.py` is broadly correct, with the `slot.league == slot.league` bug (§1.5) to fix. `[POLICY]` Duplicate-archetype scaling and complementarity may become a bounded modifier (≤ ±10%) only after the test matrix shows it does not itself become a hidden ranking driver.

### 9.5 Budget and value

`[POLICY]` Price is **not** a ranking input. It is: (a) a hard ceiling when the user sets one; (b) a separate value objective; (c) a Pareto dimension. Never "cheaper is better" and never "expensive is better".

`[IMPL]` `card_value_service.value_assessment()` — marginal contextual utility per verified coin, `VALUE_UNAVAILABLE` without a verified price — is correct and is retained verbatim. It is one of the strongest pieces of the existing codebase.

`[UNKNOWN]` No market price data exists for FC26. Liquidity and price freshness modelling stay out of scope until it does.

---

## 10. Confidence

`[POLICY]` Answering the mandate's central confidence question directly: **uncertain data must reduce confidence AND constrain the score — but it must never be converted into a point-estimate penalty.**

The mechanism (specified in the model spec, §4):

- Missing demand weight is charged at a **pessimistic bound** derived from the frozen reference distribution, producing `score_lo`.
- The optimistic bound `score_hi` is computed too and exposed.
- Ranking uses `score_lo`. `[MATH]` Missing evidence can therefore only lower a candidate's rank, never raise it — satisfying the requirement that insufficient evidence cannot increase effective recommendation.
- Below the coverage floor the candidate becomes `NOT_EVALUABLE` and leaves the ranking with a reason.

Validation `[MEASURED]`, same candidates that broke v2:

| Candidate | OVR | Coverage | `score_lo` | `score_hi` | Status |
|---|---|---|---|---|---|
| WellDocumented84 | 84 | 1.00 | **0.8544** | 0.8544 | RANKED #1 |
| PartialGoodEvidence | 84 | 0.85 | 0.8030 | 0.8552 | RANKED #2 |
| UndocumentedSameOVR | 84 | 0.16 | 0.5257 | 0.7371 | NOT_EVALUABLE |
| UndocumentedLowOVR | 80 | 0.16 | 0.5177 | 0.7292 | NOT_EVALUABLE |

The v2 pathology is inverted. Note `PartialGoodEvidence` has `score_hi` (0.8552) *above* the winner's score — the engine correctly says "this could be better, but it is not proven", which is exactly the honest statement v2 could not make.

`[IMPL]` `confidence_v2` (freshness, source authority, identity, unresolved conflicts, with unknown inputs excluded rather than penalised) is sound and is retained as the *reporting* layer on top of this.

---

## 11. Pareto and trade-offs

`[POLICY]` Objectives admitted to the Pareto frontier, and the reasons:

| Objective | In frontier? | Reason |
|---|---|---|
| Contextual capability | **Yes** | The primary objective |
| Value (utility per verified coin) | **Yes, when price is verified** | Genuinely independent axis |
| Evidence coverage | **Yes** | Users legitimately trade certainty against upside |
| Squad structural fit | **Yes, when squad context exists** | Independent of individual fit |
| Versatility | **Yes** | Independent; already computed `[IMPL]` |
| **OVR** | **No** | Not an objective. It is a correlate of capability; including it reintroduces §1.1 through the back door |
| **Price alone** | **No** | Cheap is not an objective. Value is. |
| **Confidence score** | **No** | Confidence is a property *of* an estimate, not a competing goal. Coverage covers the user-facing need. |

`[POLICY]` The frontier is exposed to users, framed as alternatives rather than rejects. A dimension with no data returns an explicit `unavailable` reason — `[IMPL]` `_unavailable_dims()` already does this correctly and is retained.

---

## 12. Explainability

`[POLICY]` **Contract: the explanation must reconstruct the exact ranking score from the same scoring context, or the build fails.**

This is enforceable, not aspirational. The scorer emits a `ScoringContext` — demand vector, per-attribute contributions, modifiers with their caps, coverage, bounds, config version. The explainer consumes only that object. A test recomputes `Σ contributions + Σ modifiers` and asserts equality with `score_lo` to 1e-9 across the full golden set.

`[IMPL]` This directly fixes §1.5: the explainer currently reads a different weight table from the one that scored, so its numbers are wrong whenever redistribution or bias applied.

Explanation structure, generated from evidence only, never invented:

```
Recommended because
  + <attribute contributions, ranked by actual contribution to score_lo>
  + <modifiers that applied, with their capped values>
  + <constraints satisfied>
Trade-offs
  - <attributes where this card is weakest against demand>
  - <modifiers that did not apply, and why>
  - <what is unknown, and how much score range that leaves open>
Why not <alternative>
  <component-level differential, computed in the same units>
```

`[POLICY]` No LLM in the generation path. An LLM may rephrase a grounded explanation; it may never add a fact.

---

## 13. Anti-bias red team

| Bias | v3 defence |
|---|---|
| OVR bias | Component removed; tie-break removed; ρ(OVR) monitored per release |
| PAC bias | Pace enters only through demand; saturation caps it; λ bounded |
| Price bias | Price excluded from ranking entirely |
| Popularity / famous-player bias | No popularity signal exists in the engine. `[MEASURED]` Existing fairness test confirms name/club/nation do not affect score — retained |
| Generic meta bias | No meta signal in ranking. `ingestion/meta_signals.py` must be proven not to reach the scorer — needs an explicit boundary test |
| Source bias | Conflict resolution records rather than overwrites `[IMPL]`; unresolved conflicts lower confidence, not score |
| **Missing-data bias** | **Inverted by evidence gating (§10) — was the worst offender** |
| PlayStyle-count bias | Modifier is contextual and capped; holding many irrelevant PlayStyles gains nothing |
| Card-type bias | Rarity/card type never enter scoring |
| **Alphabetical bias** | **New finding** — `name` currently precedes `entity_id` in the sort. Removed (§10 of the mandate) |

---

## 14. Version and meta drift

`[POLICY]` Versioned artifacts, each with its own identifier and changelog entry:

| Artifact | Why versioned |
|---|---|
| Demand tables (position, tactical, dimension affinity, archetype) | Gameplay patches change what matters |
| λ and all blend constants | Product tuning |
| Saturation knees | Attribute inflation / power creep |
| Coverage floor and pessimistic quantile | Data-availability dependent |
| Reference distributions per position × version | Power creep shifts the pool |
| Eligibility thresholds | Product policy |
| Engine semantics (`ENGINE_VERSION`) | `[IMPL]` exists, retained |

`[POLICY]` Every recommendation response carries the full set of identifiers that produced it. A stored recommendation must be reproducible years later, or it cannot be audited. `[IMPL]` The FC26/FC27 separation wall is exemplary and is retained unchanged.

---

## 15. Implementation priority

**P0 — the intelligence engine is not correct without these**

1. Demand-vector composition replacing separate `attribute_fit` / `tactical_fit` components, tactical path on by default
2. Delete `overall_quality` and `position_fit` as scored components
3. Evidence gating: coverage floor + `score_lo` ranking, replacing weight redistribution
4. Position eligibility as an engine-level hard constraint
5. `ScoringContext` + explanation reconstruction test
6. v3 golden set; v2 baseline preserved read-only; delete `test_debug_adversarial.py`

**P1 — required before the product is trustworthy, not before it is correct**

7. Remove OVR and name from tie-breaking
8. Fix `team_fit` league comparison
9. PlayStyle and archetype as bounded modifiers / demand templates rather than components
10. Frozen reference distributions per position × version
11. DB-free test lane for the deterministic core

**P2 — after P0/P1 are in production**

12. Squad structural fit as a bounded modifier
13. Role demand modifiers, gated on real Role data
14. Value/coverage Pareto exposure in the UI
15. Demand-weight calibration from feedback, once the §6 dataset bar is met

**REJECT**

- LEVEL × SHAPE / z-score scoring — `[MEASURED]` 39.3% monotonicity failure, pool-dependent
- Embedding similarity as a ranker — `[MEASURED]` PC1 dominance makes it an OVR proxy
- Contextual bandits — non-deterministic, unexplainable, no reward signal
- Gradient-boosted ranking — no labels, unexplainable, bakes in current meta
- Tactical sub-profiles (POSSESSION_HOLD vs POSSESSION_PROGRESSIVE) — proposed in the existing gap audit; premature until the base tactical layer demonstrably discriminates
- Formation-specific tactical profiles — same reason
- PlayStyle anti-synergy detection — `[UNKNOWN]` mechanics; would be invented

---

## 16. What this architecture deliberately does not do

- It does not model FC26 match mechanics. It models *demand* and *evidence*.
- It does not learn. Everything is deterministic and replayable.
- It does not claim probability. Scores are suitability under a declared demand vector.
- It does not fill gaps. Missing data stays missing and costs rank rather than being imputed.
- It does not add a component per idea. v2 had seven components and could not tell gegenpressing from a low block. v3 has one scoring quantity, one gate, and a small set of capped modifiers — and passes every adversarial case v2 fails.
