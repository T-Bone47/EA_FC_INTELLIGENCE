# INTELLIGENCE MODEL SPEC — v3.0.0

Normative specification for the v3 recommendation model. Every quantity is defined, bounded, versioned and reconstructable.

Companion documents: `CORE_INTELLIGENCE_ARCHITECTURE.md` (why), `INTELLIGENCE_TEST_MATRIX.md` (proof obligations).

**Claim classes used below:** `[MATH]` provable from the definitions · `[POLICY]` product decision needing a human owner · `[HYPOTHESIS]` plausible, untested · `[MEASURED]` reproduced this session · `[UNKNOWN]` not established, must not be assumed.

---

## 1. Notation

| Symbol | Meaning | Range |
|---|---|---|
| `c` | candidate (game_player or ut_card) | — |
| `A` | attribute universe for the game version | `ALL_ATTRS` |
| `v_a(c)` | published value of attribute `a`, or `⊥` (UNKNOWN) | `1…99` or `⊥` |
| `K(c)` | `{a ∈ A : v_a(c) ≠ ⊥}` — published set | — |
| `w` | demand vector | `Σ w_a = 1`, `w_a ≥ 0` |
| `D` | demand support, `{a : w_a > 0}` | — |
| `κ(c,w)` | evidence coverage `Σ_{a ∈ D ∩ K} w_a` | `[0,1]` |
| `s(v,a)` | saturating normaliser | `[0,1]` |
| `C_lo, C_hi` | capability bounds | `[0,1]` |
| `M` | total bounded modifier | `[M_min, M_max]` |
| `R` | ranking quantity | `[0,1]` |

`⊥` is UNKNOWN. **`⊥` is never coerced to 0, to a mean, or to a default anywhere in this specification.**

---

## 2. Demand composition

The single scoring input. Composed once per request, before any candidate is touched.

### 2.1 Pipeline

```
w⁰ = position_base(position)                                    # normalised
w¹ = (1 − λ)·w⁰ + λ·tactical_demand(profile, secondary)         # normalised
w² = w¹ ⊙ slot_emphasis(formation, slot)                        # elementwise, normalised
w³ = w² ⊙ role_modifier(role)                                   # identity when role data absent
w⁴ = apply_user_preferences(w³, prefs, bands)                    # normalised
w  = w⁴ / Σ w⁴
```

Every stage emits a `DemandStage` record: stage name, inputs, resulting vector, config version. `[MATH]` Composition is deterministic and replayable from the request plus the config version.

### 2.2 Stage definitions

**`position_base`** `[POLICY]` From `POSITION_ATTRIBUTE_WEIGHTS`, normalised. Engine convention. Unknown position → error, never a default profile.

**`tactical_demand`** `[POLICY]` Derived from the dimension vector, not from flat per-profile tables:

```
dims          = dimension_vector(profile, secondary, primary_share)
demand(dim)   = |dims[dim] − 0.5| · 2                # 0 at neutral, 1 at extreme
t_raw(a)      = Σ_dim  affinity[dim][a] · demand(dim) · sign(dims[dim] − 0.5)
tactical(a)   = normalise(max(t_raw(a), 0))
```

`[POLICY]` The `sign` term is new in v3 and matters: a *low* block and a *high* press are opposite ends of `block_height`, and must pull attribute importance in opposite directions. v2's `abs()` treatment `[IMPL]` made them pull in the same direction, which is a contributing cause of the measured PRESSING/LOW_BLOCK top-10 overlap of 10/10.

`[MEASURED]` With `CUSTOM` or fully neutral dimensions, `tactical` is empty and `w = w⁰`; discrimination degenerates to position-only, which is correct and must be reported as `TACTICAL_DEMAND_NEUTRAL`.

**`slot_emphasis`** `[POLICY]` Multiplicative, from `FORMATION_SLOTS`. `[IMPL]` Existing implementation is correct: unknown emphasis keys are ignored, never injected.

**`role_modifier`** `[UNKNOWN]` Role behaviour is not established for FC26. Until Role data is ingested this returns identity and the response carries `role_demand: UNAVAILABLE`. It must never fabricate a modifier.

**`apply_user_preferences`** `[POLICY]`
- explicit `AttributePreference.weight` → additive into `w`, then renormalise
- `AttributeBand` → ensures the attribute has non-zero weight and attaches a soft target
- explicit `min_value` → attaches a hard floor (eligibility, §5), *and* non-zero weight

### 2.3 λ

`[POLICY]` Default `λ = 0.6`. Per-request overridable via `specialisation_preference ∈ {balanced, specialist, generalist} → λ ∈ {0.6, 0.75, 0.45}`.

`[MEASURED]` Justification: all six adversarial cases pass for `λ ∈ [0.3, 1.0]`; margins are thin at 0.3 (min 0.0136) and position knowledge vanishes at 1.0. Real-pool top-10 overlap across tactic pairs: 5.5/10 at λ=0.5, 4.7/10 at λ=0.7.

**Open obligation:** λ=0.6 real-pool discrimination is interpolated, not measured. It must be measured before the value is frozen in `v3_config`.

---

## 3. Attribute normalisation

```
s(v, a) = v / 99                                  if v ≤ knee(a)
          (knee(a) + (v − knee(a))·φ) / 99        if v > knee(a)
```

`φ = SATURATION_EXCESS_FACTOR = 0.35` `[POLICY]`, `knee(a)` from `SATURATION_KNEES` `[POLICY]`.

`[MATH]` `s` is continuous, strictly increasing in `v`, and bounded in `[0,1]`. Strict monotonicity is required by §8.1 and is the reason a piecewise-linear knee is used rather than a cap.

`[POLICY]` Saturation is **always on** in v3. In v2 it was opt-in `[IMPL]`, so the default path treated 99 pace as 4.4% better than 95 pace with no diminishing return.

### 3.1 Constrained attributes

When a user attaches a target or band to attribute `a`:

```
band target T:     s_eff = 1                       if v ≥ T
                           max(0, 1 − (T−v)/ρ)     otherwise      ρ = BAND_RAMP_POINTS = 25
target value T:    s_eff = max(0, 1 − |v−T|/99)
hard minimum m:    eligibility gate (§5); within scoring, s_eff = s(v,a)
```

`[MATH]` The band ramp is monotone non-decreasing in `v`. The *target* form is **not** monotone — it peaks at `T` and falls either side. This is intended (a user asking for "around 75 strength" means it), and it is the single declared exception to §8.1. It applies only to attributes the user explicitly targeted, and the exception must be recorded in the scoring context so the monotonicity test can exempt exactly those attributes and no others.

---

## 4. Capability and the evidence interval

This replaces weight redistribution entirely.

### 4.1 Definition

For demand support `D`, published set `K`:

```
covered(c)   = D ∩ K(c)
κ(c,w)       = Σ_{a ∈ covered} w_a

C_lo(c,w)    = Σ_{a ∈ covered} w_a · s_eff(v_a, a)  +  Σ_{a ∈ D∖K} w_a · s(q_lo(a), a)
C_hi(c,w)    = Σ_{a ∈ covered} w_a · s_eff(v_a, a)  +  Σ_{a ∈ D∖K} w_a · s(q_hi(a), a)
```

`q_lo(a)`, `q_hi(a)` are the **frozen reference quantiles** for attribute `a` (§4.3).

`[MATH]` Properties, all required:

1. `C_lo ≤ C_hi`, both in `[0,1]`, with equality iff `κ = 1`.
2. `C_lo` is non-decreasing in every published demanded attribute value.
3. Publishing a previously-unknown attribute whose value exceeds `q_lo(a)` **raises** `C_lo`; publishing a value below `q_lo(a)` lowers it. **Missing data therefore cannot be an advantage.**
4. `C_lo` and `C_hi` depend only on `(c, w, reference distribution)` — **not on the other candidates in the request.**

Property 4 is the formal statement of pool independence and is what makes golden scenarios stable. `[MEASURED]` The rejected z-score formulation fails it: max |Δscore| = 0.0154 and top-20 churn 19/20 when the pool changed.

### 4.2 Why the lower bound is the ranking quantity

`[POLICY]` **Rank on `C_lo`.** Pessimism under uncertainty.

`[MATH]` Ranking on `C_hi` or on the covered-weight mean `Σ_{covered} w·s / κ` both make missing data profitable: a candidate can raise its score by *not* publishing a weak attribute. Ranking on `C_lo` makes the direction strictly the other way. This is the formal fix for the measured v2 pathology where a one-attribute candidate outranked a fully documented one.

`C_hi` is still computed and exposed — it is what lets the product say "unproven upside" honestly rather than either hiding or fabricating it.

### 4.3 Frozen reference quantiles

`[POLICY]` `q_lo(a) = P10`, `q_hi(a) = P90` of attribute `a`, computed per `(game_version, position_group)` from the canonical pool, **frozen into a versioned reference table** and republished only on an explicit ingestion event.

Frozen, not live, for three reasons: `[MATH]` live quantiles reintroduce pool dependence; they make scores irreproducible after any data refresh; and they let a large ingest silently shift every historical recommendation.

`P10` rather than the minimum: `[POLICY]` the minimum is a single outlier and would make any missing attribute catastrophic. `P10` states "assume this is poor unless shown otherwise" without being absurd.

### 4.4 Coverage floor

```
κ(c,w) < κ_min  ⟹  status = NOT_EVALUABLE
```

`[POLICY]` `κ_min = 0.60`. Candidate leaves the ranking, is reported in a separate `not_evaluable` array with `coverage`, `missing_attributes`, and both bounds. It is explicitly **not** ranked last — it is not ranked at all, because we do not know that it is bad.

`[MEASURED]` Validation on the exact candidates that broke v2:

| Candidate | OVR | κ | `C_lo` | `C_hi` | Status |
|---|---|---|---|---|---|
| WellDocumented84 | 84 | 1.00 | 0.8544 | 0.8544 | RANKED #1 |
| PartialGoodEvidence | 84 | 0.85 | 0.8030 | 0.8552 | RANKED #2 |
| UndocumentedSameOVR | 84 | 0.16 | 0.5257 | 0.7371 | NOT_EVALUABLE |
| UndocumentedLowOVR | 80 | 0.16 | 0.5177 | 0.7292 | NOT_EVALUABLE |

v2 ranked `UndocumentedSameOVR` **first**.

---

## 5. Eligibility gate

Runs before scoring. Produces `ELIGIBLE` or an exclusion with a class and a machine-readable reason.

### 5.1 Exclusion classes

`[POLICY]` Three classes, never conflated in the API:

| Class | Meaning |
|---|---|
| `FAILED` | Verified to violate a stated requirement |
| `UNVERIFIABLE` | Requirement could not be checked because the fact is `⊥` |
| `NOT_EVALUABLE` | Evidence coverage below `κ_min` |

"We checked and it fails" and "we could not check" are different statements to a user and must stay different in the payload.

### 5.2 Gates, in order

```
G1  version          c.game_version ≠ req.game_version           -> FAILED
G2  synthetic        c.is_synthetic or SYNTHETIC_TEST            -> raise (data-boundary violation)
G3  gk_boundary      GK ⊻ outfield mismatch                      -> FAILED (absolute)
G4  position         position_eligibility(c, req) < θ_pos        -> FAILED
                     c.position_primary is ⊥                     -> UNVERIFIABLE
G5  explicit minima  v_a ≠ ⊥ and v_a < min_a                     -> FAILED
                     v_a is ⊥                                    -> no exclusion; reduces κ
G6  required PS      playstyle_data_published = false            -> UNVERIFIABLE
                     PS not held                                 -> FAILED
G7  links            league/club/nation mismatch                 -> FAILED
                     link fact is ⊥                              -> UNVERIFIABLE
G8  budget           verified price > budget_coins               -> FAILED
                     price is ⊥                                  -> no exclusion; BUDGET_UNVERIFIED
G9  coverage         κ(c,w) < κ_min                              -> NOT_EVALUABLE
```

### 5.3 Position eligibility — new in v3

`[POLICY]` **G3 and G4 are engine-level hard constraints.** This is the fix for the measured defect where a 91 striker was a ranked CB candidate with `excluded_hard: []`. Repository pre-filtering is a performance optimisation and must never be the only correctness mechanism.

```
position_eligibility(c, target) =
    1.00                       if primary = target
    0.85                       if target ∈ secondary_positions
    adjacency(primary,target)  if present in POSITION_ADJACENCY
    0.00                       otherwise
```

`[POLICY]` `θ_pos = 0.40`, matching the existing `compatible_positions` adjacency bar so the gate and the pre-filter agree by construction. Overridable per request by `allow_out_of_position: true`, which lowers `θ_pos` to 0 and flags every affected row.

`[POLICY]` Position eligibility is a **gate only**. It does not contribute to the score. v2's `position_fit` component was near-constant within a position pool and therefore acted as pure OVR amplification under redistribution — one of the two components that absorbed all redistributed weight.

---

## 6. Modifiers

`[POLICY]` Modifiers adjust capability. They are bounded, individually capped, and individually logged. **The total modifier can never invert a capability gap larger than `M_max − M_min`.**

```
M(c, req) = clamp( 1 + Σ_i m_i(c, req),  M_min,  M_max )
M_min = 0.85,  M_max = 1.15
```

| Modifier | Cap | Source | Status |
|---|---|---|---|
| `m_playstyle` | ±0.10 | contextual PlayStyle value (§6.1) | `[POLICY]` bound; effect size `[UNKNOWN]` |
| `m_role` | ±0.05 | role familiarity | inactive — Role data `[UNKNOWN]` |
| `m_squad` | ±0.05 | squad structural fit | P2, off by default |
| `m_interaction` | ±0.10 | attribute interaction features | `[IMPL]` retained |

`[POLICY]` Bounds are deliberately tight because the underlying effect sizes are `[UNKNOWN]`. A wide bound would be fabricated precision. They are versioned configuration and revisable when evidence arrives.

### 6.1 PlayStyle modifier

```
m_playstyle = 0.10 · ( Σ_ps value(ps) · tier(ps) ) / ( Σ_desired demand(ps) )     clamped to ±0.10
value(ps)   = 1.00  profile-valued | 0.75  position-useful | 0.35  neutral
tier(ps)    = 1.00  held at + tier | 0.60  held at base when + requested | 1.00 base when base requested
```

`[IMPL]` Tiers and values from the existing `playstyle_context` module, promoted from opt-in to default.

`playstyle_data_published = false` ⟹ `m_playstyle = 0`, coverage annotated, confidence reduced. **Never** "has no PlayStyles".

### 6.2 Archetype as demand, not modifier

`[POLICY]` A requested archetype composes its attribute weights into `w` at stage `w¹` as an additional demand source, sharing λ with the tactical demand. It is **not** a scored component and **not** a modifier. `[IMPL]` This removes `ARCHETYPE_WEIGHT = 0.10` and its renormalisation of the base table.

Archetype *detection* (`dominant_archetype`, `gameplay_profile`, `versatility`) remains derived analytics on the top-N, unchanged and clearly marked `ENGINE_DERIVED`.

---

## 7. Ranking

```
R(c) = C_lo(c, w) · M(c, req)
```

### 7.1 Sort order

```
sort key = ( −R(c),  −κ(c,w),  entity_id )
```

`[POLICY]` Justification for each term, per the mandate's requirement that tie-breaks be explicitly justified:

1. `−R` — the contextual objective.
2. `−κ` — when two candidates are contextually indistinguishable, prefer the one we actually have evidence about. This is a *statement about certainty*, not about quality, and it is the only tie-break that adds information.
3. `entity_id` — final deterministic, unbiased tie-break.

**Explicitly removed:**
- `−overall_rating` `[IMPL]` v2 main sort and `pareto.best_overall`. Capability already contains quality; re-entering OVR at tie-break double-counts it, and it is the mechanism that decided the measured failing adversarial cases.
- `candidate.name` `[IMPL]` v2 sorts on name before `entity_id`, which is alphabetical bias. In the measured PRESSING/POSSESSION failure the winner `Poss` beat `Press` partly on alphabetical order after the scores tied at 0.8919.

### 7.2 Indistinguishability

`[POLICY]` `|R(a) − R(b)| < ε`, `ε = 0.005`, marks a *reported tie*. Tied candidates are surfaced as "effectively equivalent for this request" rather than silently ordered, and the differentiating evidence is shown. `[IMPL]` `SENSITIVITY_MIN_SWING` already uses 0.005 as its noise threshold; reusing it keeps one definition of noise.

### 7.3 Tactical floor

`[POLICY]` The v2 `tactical_floor` mechanism is **removed**. With tactical demand composed into `w`, a tactically unsuitable candidate already scores low — a separate floor double-penalises and creates a second, opaque exclusion path. `strict_tactics` becomes a threshold on `R` (`min_fit`), expressed in the same units as everything else.

---

## 8. Required invariants

Each is a build-blocking test in the test matrix.

### 8.1 Monotonicity `[MATH]`

> For any attribute `a ∈ D` not carrying an explicit user *target* (§3.1), increasing `v_a` must not decrease `R`.

Holds because `s` is strictly increasing, `w_a ≥ 0`, `C_lo` is a non-negative combination, and modifiers do not depend on unconstrained attribute levels.

`[MEASURED]` Capability-only: **0 violations in 3,360 perturbations**. The rejected z-score formulation: **1,321 / 3,360 = 39.3%**.

### 8.2 Pareto dominance `[MATH]`

> If `v_a(A) ≥ v_a(B)` for all `a ∈ D` and `K(A) ⊇ K(B)`, then `R(A) ≥ R(B)`.

`[MEASURED]` Capability-only: **0 violations in 17,465 dominating pairs**. Rejected formulation: 2.

### 8.3 Irrelevance `[MATH]`

> Attributes outside `D` do not affect `R`.

Holds by construction — `C_lo` sums only over `D`. This is what the rejected formulation could not provide, and the direct cause of its monotonicity failures.

### 8.4 Pool independence `[MATH]`

> `R(c)` is identical whether `c` is scored alone or in any pool.

`[MEASURED]` Capability-only: max |Δ| = 0.0000, rank correlation +1.0000, top-20 stability 20/20.

### 8.5 Evidence non-reward `[MATH]`

> Removing a published demanded attribute cannot increase `R`, and cannot increase rank.

Follows from §4.1 property 3.

### 8.6 Score reconstruction `[POLICY]`

> `Σ per-attribute contributions + Σ modifier contributions == R` to 1e-9, from the `ScoringContext` alone.

### 8.7 Determinism `[POLICY]`

> Same request + same data version + same config version ⟹ byte-identical response, excluding `request_id` and timings.

---

## 9. Scoring context object

The single artifact linking scoring, explanation, sensitivity, counterfactuals and audit. `[POLICY]` The explainer may read **nothing else**.

```
ScoringContext
  config_version, engine_version, data_version, reference_table_version
  lambda, kappa_min, M_min, M_max, theta_pos
  demand_stages   [ {stage, inputs, vector, version} ]
  demand_vector   { attribute: weight }            # sums to 1
  per_attribute   [ { attribute, weight, value|UNKNOWN, s_eff,
                      contribution_lo, contribution_hi,
                      constraint: none|min|target|band,
                      source_observation_id } ]
  coverage        { kappa, missing: [attribute], missing_weight }
  modifiers       [ { name, raw, capped, cap, inputs, why } ]
  bounds          { C_lo, C_hi, M, R }
  eligibility     { status, gate, class, reason }
```

`[POLICY]` `source_observation_id` per attribute closes the provenance chain: recommendation → attribute → observation → dataset. `[IMPL]` The DB schema already supports this; the engine currently discards it.

---

## 10. Confidence

`[POLICY]` Confidence is **reported, never subtracted from the score**. The score's response to uncertainty is the interval width `C_hi − C_lo`; confidence describes how much to trust the interval itself.

```
confidence = Σ_i ω_i · f_i  /  Σ_i ω_i      over dimensions with f_i ≠ ⊥
```

| Dimension | ω | `f` | Source |
|---|---|---|---|
| evidence coverage | 0.40 | `κ` | §4 |
| source authority | 0.20 | `AUTHORITY_TIER_FACTOR` | `[IMPL]` |
| freshness | 0.15 | linear decay to floor 0.4 | `[IMPL]` |
| identity resolution | 0.15 | RESOLVED 1.0 / REVIEW 0.6 / UNRESOLVED 0.4 | `[IMPL]` |
| conflict | 0.10 | `max(0.5, 1 − 0.15·unresolved)` | `[IMPL]` |

`[MATH]` Unknown dimensions are excluded and weights renormalised — an unknown input never masquerades as a bad one. `[IMPL]` This is `confidence_v2`'s existing and correct behaviour, with coverage promoted to the dominant dimension.

`[POLICY]` Score bands are withheld when `κ < κ_band = 0.75` (raised from 0.50): a band is a qualitative claim and needs more evidence than a ranking position does.

---

## 11. Multi-objective layer

`[POLICY]` Objectives on the frontier: `capability` (`C_lo·M`), `value` (when price verified), `coverage`, `squad_structural` (when squad context exists), `versatility`.

Excluded, with reasons: **OVR** — a correlate of capability, not an objective; **price alone** — cheap is not a goal, value is; **confidence** — a property of an estimate, not a competing goal.

`[MATH]` `c` is on the frontier iff no other eligible candidate is ≥ on all admitted objectives and > on at least one. Objectives with no data are omitted from the dominance test and reported in `unavailable_dimensions` with a reason. `[IMPL]` Existing `_unavailable_dims()` behaviour is correct and retained.

---

## 12. Data dependency map

| Feature | Required fields | Availability | Confidence input | Usable now |
|---|---|---|---|---|
| Demand composition | position tables, dimension affinities | Config `[POLICY]` | n/a | **Yes** |
| Capability | detail attributes | `[MEASURED]` full coverage, 16,228 FC26 rows | coverage | **Yes** |
| Evidence interval | frozen quantiles | Derivable from foundation | coverage | **Yes** — table must be built |
| Position eligibility | `position_primary`, `secondary_positions` | Present | identity | **Yes** |
| PlayStyle modifier | `playstyles_base/plus`, `playstyle_data_published` | Present, partial | playstyles | **Yes** |
| Interactions | attribute groups | Present | coverage | **Yes** |
| Archetype demand | attributes + PlayStyles | Present | coverage | **Yes** |
| Saturation | knee table | Config `[POLICY]` | n/a | **Yes** |
| Role modifier | Role + familiarity | **`[UNKNOWN]` — none ingested** | role | **No** |
| Chemistry | verified FC26 rules | **`[UNKNOWN]`** | n/a | **No** |
| Value / budget | verified prices | **`[UNKNOWN]` — none** | price | **No** |
| Squad structural | squad members, link facts | Present when squad exists | links | **Partial** |
| Version drift | multi-version history | FC26 only | n/a | **No** |
| ML ranking | labelled preference data | **None** | n/a | **No** |

`[POLICY]` Every "No" row must return an explicit unavailability reason in the API. None may be silently skipped, and none may be approximated.

---

## 13. Migration

```
v2 baseline (preserved, read-only)
    └─ benchmarks/engine_baseline_v2_2026-09-14.json
    └─ benchmarks/V2_INVALIDATION_REGISTER.md      # new: what was wrong and the evidence
v3 contract
    └─ benchmarks/engine_contract_v3.json          # new golden set, each case carrying its WHY
```

`[POLICY]` Rules:
- The v2 baseline file is never edited or regenerated. It is a historical record.
- v2 golden scenarios are **not** migrated wholesale. Each is triaged: `CARRIED` (still correct under v3), `INVALIDATED` (encodes rejected behaviour, with the register entry naming the defect), `REPLACED` (same intent, corrected expectation).
- A v2 test is never weakened to pass. It is either carried unchanged, or invalidated with a written reason.
- `test_debug_adversarial.py` is deleted — ten `assert False` debug stubs, not tests.

`[POLICY]` v3 ships behind `engine_version=3.0.0` with v2 callable for comparison during migration only, then removed. There is no permanent dual-engine mode: v2 recommendation behaviour is known-defective and must not remain reachable in production.

---

## 14. Configuration constants

All versioned in `v3_config`. None may be literal in scoring code.

| Constant | Value | Class | Owner decision needed |
|---|---|---|---|
| `λ` | 0.60 | `[POLICY]` | **Yes — measure at 0.6 first** |
| `κ_min` | 0.60 | `[POLICY]` | **Yes** |
| `κ_band` | 0.75 | `[POLICY]` | Yes |
| `θ_pos` | 0.40 | `[POLICY]` | Yes |
| `M_min`, `M_max` | 0.85, 1.15 | `[POLICY]` | **Yes** |
| `ε` (tie) | 0.005 | `[POLICY]` | No — reuses existing noise threshold |
| `φ` saturation excess | 0.35 | `[POLICY]` | No — carried from v2 |
| `q_lo`, `q_hi` | P10, P90 | `[POLICY]` | Yes |
| `knee(a)` | per-attribute | `[POLICY]` | No — carried from v2 |
| PlayStyle values | 1.00 / 0.75 / 0.35 | `[POLICY]` | No — carried from v2 |
| Reference quantile table | per version × position group | derived | Must be built |
