# ENGINE BASELINE — recorded before any upgrade work

**Date:** 2026-09-14 · **Engine:** `backend/services/recommendation_engine_v2.py` (single engine; no v3/new variants)
**Rule:** nothing in this file's behavior may be destroyed by the intelligence upgrade without evidence the new
implementation is superior (§69/§70 of the upgrade mandate). This document + `benchmarks/engine_baseline_v2_2026-09-14.json`
are the regression contract.

## 1. Test baseline (live runs, 2026-09-14)

| Suite | Result |
|---|---|
| `python3 -m pytest backend/tests -q` | **161 passed**, 3 warnings, ~23 s |
| `frontend npm run test` | **33 passed** (5 files) |
| `npx tsc --noEmit` | clean |
| `verification/post_build_verify.py` (API/engine/security) | 64/64 PASS |
| `verification/browser_verify.mjs` (real browser) | 21/21 PASS on :8000 and :5173 |

## 2. Performance baseline (live, `benchmarks/reaudit_2026-09-14.json`)

| Scenario | Evaluated | Cold (ms) | Warm p50 (ms) |
|---|---|---|---|
| CM/4-2-3-1/PRESSING/stamina≥85/budget 100k | 10,275 | 1,256.9 (fresh process) | 494–581 |
| ST plain | 5,241 | 375.6 | 264.5 |
| GK plain | 1,816 | 78.8 | 83.0 |
| Full pool (no position) | 16,228 | 766.7 | 748.8 |

RSS: 65 MB idle → 186 MB after first request → 575 MB after full sweep. Candidate pool: TTL cache (120 s) with
DB watermark invalidation (`CandidateRepository`), position pre-filter via `compatible_positions` (adjacency ≥ 0.4).

## 3. Golden scenario outputs (exact, pre-upgrade)

All against the running production server; full JSON incl. component values, ranked order, confidence, weights
in `benchmarks/engine_baseline_v2_2026-09-14.json`.

| ID | Request summary | Winner | Score | Conf | Evals |
|---|---|---|---|---|---|
| S1 | CM, 4-2-3-1, PRESSING, stamina≥85, budget 100k | Federico Valverde | 0.95789 | 0.78 | 10,275 |
| S2 | GK, gk_diving≥85 | Alisson | 0.97973 | 0.72 | 1,816 |
| S3 | ST, COUNTER_ATTACK, pace≥90 | Kylian Mbappé | 0.97775 | 0.825 | 5,241 |
| S4 | CB, POSSESSION, short_passing≥80 | Virgil van Dijk | 0.93872 | 0.825 | 6,324 |
| S5 | RW, CROSSING, desired Whipped Pass | Mohamed Salah | 0.91362 | 0.93 | 7,988 |
| S6 | full pool, BALANCED | Kylian Mbappé | 0.93146 | 0.615 | 16,228 |
| S7 | CAM, POSSESSION | Jude Bellingham | 0.92492 | 0.825 | 10,230 |
| S8 | LB, BALANCED | Nuno Mendes | 0.88375 | 0.72 | 8,322 |
| W  | FC27 CM request | **HTTP 404 NO_DATA wall** (exact copy preserved) | — | — | — |

## 4. Architecture as-is (inspected 2026-09-14)

```
POST /api/recommendations (routes/recommendations.py)
  → RecommendationService.recommend (services/recommendation_service.py)
      → CandidateRepository.load_for_position / load_candidates (data_access, TTL+watermark cache, synthetic firewall)
      → RecommendationEngineV2.recommend (services/recommendation_engine_v2.py)
          per candidate → evaluate():
            components (services/fit_components.py, each → FitValue KNOWN/UNKNOWN/INSUFFICIENT_EVIDENCE):
              overall_quality  OVR normalized [55,92] absolute curve
              position_fit     exact 1.0 / alternate 0.85 / adjacency table / fallback 0.05
              attribute_fit    user prefs else POSITION_ATTRIBUTE_WEIGHTS profile; min-ramp(25)/target/linear-99
                               coverage gate: <0.5 of required weight ⇒ INSUFFICIENT_EVIDENCE
              tactical_fit     TACTICAL_ATTRIBUTE_WEIGHTS (11 profiles; BALANCED/CUSTOM-empty ⇒ UNKNOWN)
              playstyle_fit    desired base ×1.0 / plus ×1.5 (base-tier-only ⇒ 0.75); unpublished ⇒ INSUFFICIENT
              role_fit         ADVISORY (not weighted); no Role data ⇒ INSUFFICIENT_EVIDENCE, never penalty
              team_fit         verified club/league/nation link facts; chemistry rules unverified ⇒ INSUFFICIENT
            hard constraints:  min/max OVR, attribute min_value floors, budget (only when price KNOWN)
            weighted score:    unknown-weight redistributed proportionally across KNOWN components
            confidence:        0.7×component coverage + 0.3×entity data confidence
                               (identity/attrs coverage/playstyles/provenance/price dims)
          → ranking (-score, -OVR, name, entity_id); strict_tactics ⇒ tactical floor 0.35 exclusion, else down-rank
          → Pareto: best_overall/attribute/tactical/playstyle/chemistry/value + unavailable_dimensions w/ honest reasons
      → explanation_service (deterministic why_this / why_not_alternatives / strengths / weaknesses / summary)
      → data_freshness (source_observation max) + candidate_pool meta + timing_ms
POST /api/recommendations/parse-intent — deterministic regex/word-table parser → draft (never invents values)
```

**Weights (BASELINE V1 — treated as fixed until validated otherwise, §47):**
`overall_quality 0.15 · attribute_fit 0.30 · position_fit 0.15 · tactical_fit 0.15 · playstyle_fit 0.15 · team_fit 0.10` (sum = 1.0 asserted); `role_fit` advisory.

**Config surface today (`services/scoring_config.py`):** COMPONENT_WEIGHTS, TACTICAL_FIT_FLOOR 0.35, OVR curve 55–92,
ATTRIBUTE_EVIDENCE_MIN_COVERAGE 0.5, position fit ladder, POSITION_ADJACENCY, POSITION_ATTRIBUTE_WEIGHTS (12 positions),
TACTICAL_ATTRIBUTE_WEIGHTS (11 profiles), TACTICAL_PROFILE_PLAYSTYLES (advisory), VersionConfig per game version
(FC26 populated; FC27 NO_DATA empty — never substituted).

**Formations today (`api/routes/meta.py FORMATIONS`):** 10 formations as flat position lists — used for the squad
builder UI and parse-intent validation, but **not** consumed by scoring.

## 5. Gap analysis vs. the upgrade mandate (what is missing today)

| Mandate area | Status in V2 baseline |
|---|---|
| Hard vs soft constraint taxonomy (§2) | Partial: hard = min/max OVR, attr mins, budget-when-known; soft = weights. Not first-class in schema/response |
| Structured intent w/ source+confidence+explicit-vs-inferred (§3) | Missing: parser emits flat draft, no per-field provenance |
| Semantic football language / archetypes (§4/§15) | Missing entirely |
| Position intelligence: eligibility vs fit vs role/formation-conditioned fit (§5) | Partial: single `position_fit` scalar |
| Formation intelligence (§6) | Missing in scoring (FORMATIONS exists as reference only) |
| Tactical combos (HIGH_PRESS+FAST_BUILD_UP) (§7) | Missing: single-profile enum |
| Attribute interaction features (§9) | Missing: attributes scored independently |
| Diminishing returns / saturation (§10) | Partial: linear v/99 + min-ramp; OVR absolute curve only |
| Qualitative target bands (§11) | Missing: only numeric min/target |
| Contextual PlayStyle value (§12/§13) | Partial: TACTICAL_PROFILE_PLAYSTYLES exists but advisory-only, not scored |
| Role intelligence (§14) | Scaffolded: RoleFitService returns INSUFFICIENT (no data) — honest, awaiting data |
| Gameplay profile / versatility (§16/§17) | Missing |
| Squad fit / complementarity / replacement (§18–20) | Partial: team_fit link facts only; no duplicate-archetype or complementarity logic |
| Value intelligence (§21) | Correctly withheld (no prices) — architecture (BudgetProvider) ready |
| Multi-objective (§22) | Partial: Pareto by single-component maxima only |
| Score calibration bands (§23) | Missing: raw 0–1 floats |
| Confidence 2.0 (freshness/authority/identity) (§24) | Partial: coverage+data dims; no freshness/authority inputs |
| Evidence graph (§25) | Partial: evidence strings per component; no source-linked refs |
| Counterfactuals / sensitivity / what-if (§37–39) | Missing |
| Engine versioning / observability / experiments (§48/§59/§60) | Missing: no engine_version field, no telemetry, no experiment records |
| Robustness/adversarial/fairness tests (§40–42) | Partial: version-wall + firewall + determinism tests exist; no OVR-trap battery, stability, or bias tests |

## 6. Invariants that must survive the upgrade (checked by existing tests)

1. Weights echo exactly (`weights_used`), sum 1.0.
2. UNKNOWN/INSUFFICIENT never penalize; weight redistribution; "Not scored" honesty lines in explanations.
3. Deterministic ranking incl. tie-break; identical requests ⇒ identical output.
4. FC26/FC27 never mix; FC27 = 404 NO_DATA wall with exact copy.
5. Synthetic firewall: engine raises if a SYNTHETIC_TEST candidate reaches it.
6. GK scores only `gk_*` attributes; outfield detail attrs withheld for GK.
7. Budget unenforceable without prices ⇒ `BUDGET_UNVERIFIED` (never "affordable").
8. Pareto withholds best_value/best_chemistry with reasons.
9. Production code never imports tests; no duplicate engines.
10. API response fields are additive-only for compatibility (§61).
