# UT PLAYER & CARD INTELLIGENCE ENGINE — ARCHITECTURE (v2.2.0)

Status: IMPLEMENTED · Engine version: **2.1.0** · Date: 2026-09-14
Supersedes: none — V2 was **evolved in place** (no v3, no parallel engine).
Baseline contract: `docs/ENGINE_BASELINE.md` + `benchmarks/engine_baseline_v2_2026-09-14.json`
(legacy requests produce **bit-identical** scores — verified by regression).

The engine answers one question: **which player/card is best for THIS user's
exact context?** — with evidence for every claim and honest UNKNOWNs for
everything else. Scores are engine suitability scores, never probabilities.

---

> **Phase 3 (v2.2.0):** the same engine now serves two entity scopes —
> `game_player` (legacy, bit-identical) and `ut_card` (card-level attributes,
> PlayStyles, Roles, prices; §5 separation enforced). Card layers are
> documented in `docs/CARD_INTELLIGENCE.md` and siblings; everything below
> remains authoritative for the shared decision pipeline.

## 1. Layered decision system (§4)

Every stage is inspectable; there is no giant opaque formula.

```
natural language ──► INTENT PARSER (intent.py / intent_parser.py)
                      structured intent: fields with source/confidence/explicit,
                      hard constraints vs soft preferences, unrecognized fragments
                                   │
                                   ▼
                     USER REQUIREMENTS (domain/user_model.py, validated)
                                   │
                     ┌─────────────▼──────────────┐
                     │ RETRIEVAL (§56)             │  position prefilter BEFORE scoring
                     │ candidate_repository        │  cache keyed by version+position+
                     └─────────────┬──────────────┘  data-watermark; hard filters first
                                   ▼
              ┌────────────────────────────────────────────┐
              │ ENGINE V2.1 (recommendation_engine_v2.py)  │
              │  1. version guard (FC26 ≠ FC27, §20/§61)   │
              │  2. synthetic firewall (§13)               │
              │  3. HARD CONSTRAINTS (§19) — exclude+report│
              │  4. component fits (KNOWN/UNKNOWN/INSUFF.) │
              │  5. effective weights (bias, archetype)    │
              │  6. weighted score (UNKNOWN redistributed) │
              │  7. tactical floor / strict mode           │
              │  8. deterministic ranking                  │
              │  9. enrichment: bands, intelligence,       │
              │     constraints report (top-25)            │
              │ 10. pareto fronts (§29)                    │
              │ 11. sensitivity + counterfactuals (§35/36) │
              │ 12. replacement analysis (§28)             │
              └────────────────────┬───────────────────────┘
                                   ▼
        SERVICE (recommendation_service.py): explanations (§34),
        confidence + confidence_v2 (§24), freshness (§26), provenance (§25),
        telemetry (§59), squad/replacement resolution
                                   ▼
        API (schemas additive, response backward-compatible) → UI
```

## 2. Hard constraints vs soft preferences (§2/§19)

Never treated equally. Hard constraints **eliminate with a reason** (or report
"cannot verify" when data is UNKNOWN — an unverifiable constraint never passes
silently and never excludes silently):

| kind | data source | when unverifiable |
|---|---|---|
| GAME_VERSION / POSITION / SLOT | canonical | n/a |
| MIN_OVR / MAX_OVR / ATTRIBUTE_MIN | canonical attributes | UNKNOWN → listed, not violated |
| REQUIRED_PLAYSTYLE | published playstyles | unpublished → "cannot verify" exclusion |
| REQUIRED_LEAGUE / CLUB / NATION | canonical | NULL field → "cannot verify" exclusion |
| BUDGET | verified prices only | no price → **BUDGET_UNVERIFIED**, never assumed affordable |

Soft preferences shape the score: attribute bands (soft targets, §11),
weights, tactical/archetype/playstyle context, quality bias, complement hint.

## 3. Modules (all deterministic, all config-driven)

| module | responsibility | key contract |
|---|---|---|
| `engine_config.py` | every tunable in one explicit place (§46) | bands, knees, caps, bias factors, confidence levels |
| `formations.py` | slots, duties, tactical dimension vectors (§6/§7) | CAM ≠ CM; combos merge dimensions; weights derived, never hardcoded per-combo |
| `intent.py` / `intent_parser.py` | NL → structured intent (§3) | never invents facts; provenance per field; clause-scoped mandatory markers |
| `archetypes.py` | 17 computed archetypes, gameplay profile, versatility (§12/§14/§32) | no player names in source (AST-greppable); GK-isolated; labels capped at 4 + disclosure |
| `attribute_model.py` | bands, saturation, interactions, intelligence attribute fit (§8-§11) | interactions need ALL inputs KNOWN; saturation knee per attribute; coverage gate 0.5 |
| `playstyle_context.py` | contextual PlayStyle value (§11/§12) | PS+ never an automatic win; position affinity uses the real 36-PS vocabulary only; unpublished → INSUFFICIENT |
| `squad_intelligence.py` | structural fit + replacement analysis (§22/§28) | ADVISORY only, "NOT a chemistry score"; verdicts never OVR-based; OVR honesty note attached |
| `counterfactual.py` | sensitivity + what-if re-scores (§35/§36) | noise threshold 0.005; mirrors the engine ordering contract exactly |
| `confidence_v2.py` | 4-factor confidence composition (§24) | legacy confidence preserved untouched; unknown inputs renormalize |
| `engine_evaluation.py` | 12-scenario qualitative suite (§49) | DB-free fixtures; expectations are behavioral, never "player X must win" on real data |
| `engine_experiments.py` | offline config experiments (§48) | never mutates production; persisted to `experiment`/`experiment_result` |
| `feedback_analytics.py` | label measurement (§33) | phase 1-2 only; NO ML until ≥500 labels + 80% context coverage |

## 4. Scoring math (§9-§11, §46)

BASELINE V1 weights (unchanged, protected by golden regression):
`overall .15 / attribute .30 / position .15 / tactical .15 / playstyle .15 / team .10`

* UNKNOWN/INSUFFICIENT components are **excluded and their weight
  redistributed** — missing data never lowers a score (pinned by tests).
* `overall_quality_bias` scales the overall-quality weight (low ×0.5,
  normal ×1.0, high ×1.5) then renormalizes — OVR is a component, never the decider.
* `archetype_fit` enters at **0.10 only when an archetype is requested**;
  remaining components keep proportions on 0.90.
* Combo tactics (secondary profile): demand weights derived from the merged
  dimension vector (`|v−0.5|×2 × attribute affinity`, normalized).
  HIGH_PRESS+FAST_BUILD_UP ≠ HIGH_PRESS+POSSESSION (tested).
* Interactions: min/geo aggregation with an all-KNOWN gate, blended
  `(1−iw)·base + iw·interaction`, capped by `INTERACTION_TOTAL_CAP`.
* Saturation: per-attribute knee (default 85; pace-family 90), excess ×0.35.
* Bands: soft ramp to the configured target; reaching the target saturates
  ("enough", not "more"); UNKNOWN attribute → band skipped, never 0.

### Score bands (§23) — with the §51 honesty gate

`90-100 EXCEPTIONAL_FIT · 80-89.9 STRONG_FIT · 70-79.9 SOLID_FIT ·
60-69.9 SITUATIONAL_FIT · <60 WEAK_FIT` — plus **INSUFFICIENT_EVIDENCE**
whenever the score rests on < `MIN_BAND_EVIDENCE` (0.5) of component weight.
A thin-evidence candidate may keep a high legacy score (contract) but never
receives a qualitative band; its low confidence and `unknown_factors` carry
the honesty. Bands never claim probability.

## 5. Confidence (§24)

* **legacy confidence** (unchanged): 0.7×component coverage + 0.3×entity data.
* **confidence_v2** (additive): renormalized composition of
  legacy (.55) + freshness (.20, linear 180d→730d, floor .4) + source
  authority (.15, tier factor × conflict penalty) + identity (.10,
  RESOLVED/REVIEW/UNRESOLVED = 1.0/0.6/0.4). Missing inputs renormalize —
  UNKNOWN inputs never penalize. Levels HIGH/MEDIUM/LOW/VERY_LOW + reasons.

## 6. Evidence & provenance (§25/§26/§54)

recommendation → components (each with evidence strings naming exact
attributes) → source observation → dataset. Response carries `provenance`
(source registry rows: license, authority tier, usage status),
`data_freshness` (last source observation; market prices UNAVAILABLE;
chemistry UNVERIFIED), `constraints` {satisfied, failed, unknown},
`explanations` {summary, why_this, why_not_alternatives (the differentiator),
strengths, weaknesses}, `sensitivity`, `counterfactuals`, `pareto`
(quality/attribute/tactical/playstyle/chemistry/value/alternative-archetype +
unavailable dimensions with reasons), `telemetry`, `engine_version`.

## 7. Safety invariants (tested)

1. Versions never mix; FC27 = 404 wall with an honest message (§61).
2. SYNTHETIC_TEST candidates abort the production engine (§13).
3. No fabricated data anywhere: UNKNOWN / INSUFFICIENT_EVIDENCE / CONFLICTED.
4. Card-level data never substituted by base-player data (§30).
5. Deterministic: same input → same output; pool order irrelevant; no randomness.
6. Baseline weights and legacy scores frozen by golden regression (§46/§47).
7. Experiments never touch production config; ML gated behind label sufficiency.
8. Personalization/preference layers never override explicit hard constraints.
