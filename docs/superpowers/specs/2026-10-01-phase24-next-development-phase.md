# CLAUDE.md — EA FC Player Intelligence — Next Development Phase

## Purpose

This file is the execution handoff for the next development phase after Phase 23.

FC26 is the established historical baseline.
FC27 is the forward target.
UT-card data is currently unavailable/not legally cleared and remains disabled.

The project should now focus on turning the validated FC27 player-intelligence foundation into a strong, production-quality intelligence API and frontend product.

---

## Current verified state

Phase 23 was measured on 2026-09-30 using the production V3.1 engine.

### Datasets

| Dataset | Rows | Status |
|---|---:|---|
| FC26 | 16,228 | CANONICAL |
| FC27 | 19,789 | RESEARCH_ONLY |
| FC27 men | 17,849 | RESEARCH_ONLY |
| FC27 women | 1,940 | RESEARCH_ONLY |

FC27 reference distribution:
`fc27-players-2026-09-r1`

FC26 reference distribution:
`fc26-players-2026-09-r1`

FC26 and FC27 must never mix.

### V3.1 invariants

Phase 23 measured:

- monotonicity: 0 violations
- Pareto: 0 violations
- irrelevance: 0 violations
- pool independence: 0 differences
- determinism: identical ranking hash
- OVR shuffle independence: identical ranking
- lambda stability: 10/10 top-10 stability
- κ = 1.00 on current real player data
- NOT_EVALUABLE = 0 on current player data

Known latent defect:
- missing-data invariant is violated under the current P10 missing-value charge.

### Important intelligence findings

1. Missing-data defect:
   Hiding a published demanded attribute below P10 can increase C_lo.
   Candidate fix: `missing_value_charge = ZERO`.
   This produced 0 missing-data violations on both FC26 and FC27 and identical rankings on current real datasets.
   It changes six synthetic golden fixtures and therefore requires deliberate golden regeneration/owner sign-off.

2. GK tactical weakness:
   Current GK demand is tactically inert.
   HIGH_PRESS and LOW_BLOCK produce identical FC27 top-10s.
   A signed-pole GK experiment improved discrimination on FC27 but was rejected on FC26 because the pre-registered near-tie rule worsened.
   Do not globally adopt this experiment without a deliberate cross-version policy decision.

3. Complementarity interaction:
   Rejected. Keep interaction modifier disabled.

4. Near ties:
   63–91% of adjacent top-10 pairs are within the 0.005 noise threshold.
   API exposes `near_tie_with_next`.
   Do not imply false precision.

5. OVR:
   Correlation is structurally high, but OVR is not a scoring channel.
   OVR shuffle proves exact ranking independence.

6. Archetypes:
   Real data shows separable archetype groups, but archetypes are not yet part of V3.
   Any archetype demand stage requires a separate experiment before adoption.

7. FC27 division:
   FC27 mixes men's and women's players.
   API supports an optional user-selected `division` filter.
   No silent default should be invented.

### Test baseline

Phase 23:
- 662 passed
- 24 failed
- 1 skipped

The 24 failures are the same classified baseline failures:
- 9 V2 historical
- 11 pre-existing integration
- 4 RD-3/RD-4 policy

Do not weaken, delete, or rewrite these failures merely to make the suite green.

---

## Non-negotiable rules

1. Zero fabrication.
2. FC26/FC27 version wall.
3. Player != UT card.
4. Public != licensed.
5. RESEARCH_ONLY data must not leak into production.
6. Fail closed on license uncertainty.
7. Do not fabricate PlayStyle mechanics, Roles, prices, chemistry, card identities, or special-card attributes.
8. V3.1 mathematical guarantees must remain protected by regression tests.
9. No independent OVR scoring channel.
10. No frontend-side ranking formula.
11. Backend ScoringContext is the single source of truth.
12. Unknown stays UNKNOWN/NULL.
13. Do not tune thresholds merely to pass tests.
14. Any model change requires measurable before/after evidence.
15. Do not block product development waiting for UT-card data.

---

# Next phase objective

Build the next version of the actual product:

FC27 player data
→ V3.2 intelligence hardening
→ recommendation API
→ frontend recommendation experience
→ comparison
→ what-if analysis
→ explanation
→ end-to-end validation

The goal is no longer just a dataset or research engine.

The goal is a usable contextual football intelligence product.

---

# V3.2 direction

## Approved/recommended candidate

`missing_value_charge = ZERO`

Reason:
- eliminates the latent missing-data advantage
- 0 violations measured on FC26
- 0 violations measured on FC27
- rankings unchanged on current complete player datasets
- passes the relevant invariant/adversarial/hardening tests

If implemented:
- update versioned config
- regenerate only the affected synthetic goldens deliberately
- document every changed golden
- rerun all regression tests
- preserve the old V3.1 configuration for reproducibility

## Not approved automatically

GK signed-pole experiment:
- adoptable on FC27
- rejected on FC26 under the fixed decision rule

Keep it as an experimental branch unless a cross-version policy is explicitly chosen.

## Keep disabled

- complementarity interaction
- arbitrary attribute interactions
- unsupported PlayStyle mechanic mappings
- LLM ranking
- price as a ranking objective
- card-scope ranking

---

# API development

Primary endpoint:

`POST /api/v3/recommendations`

The API must support:

- game_version
- position
- tactical profile
- optional division
- player preferences where supported
- result limit
- deterministic response
- score
- score interval
- coverage
- confidence
- tactical fit
- key strengths
- key weaknesses
- PlayStyles
- near-tie information
- explanation
- engine version
- dataset version

The API must never expose unsupported facts.

Research-only FC27 data must remain isolated according to the project's existing environment/release policy.

---

# Frontend development

The frontend should become a premium football analytics product rather than a generic dashboard.

Core journey:

1. Select FC27.
2. Select position.
3. Select formation/context where supported.
4. Select tactical style.
5. Select optional division.
6. Configure preferences.
7. Request recommendations.
8. Show ranked players.
9. Explain why each player fits.
10. Show evidence/coverage.
11. Allow comparison.
12. Allow controlled what-if analysis.

## Recommendation card

Show:

- player
- position
- OVR as a descriptive stat only
- Intelligence Score
- score interval
- coverage
- confidence
- key attributes
- PlayStyles
- tactical fit
- concise evidence-derived explanation
- near-tie indicator when applicable

Clearly distinguish OVR from the Intelligence Score.

---

# Comparison

Allow 2–3 players to be compared in the same context.

Compare:

- Intelligence Score
- score interval
- evidence coverage
- relevant attributes
- PlayStyles
- tactical fit
- strengths
- trade-offs
- contribution differences

Do not produce generic claims such as “Player A is better.”

Explain context-specific differences.

---

# What-if

Support deterministic recomputation for changes such as:

- possession → high press
- high press → low block
- different position
- different tactical emphasis
- different division
- supported user preference changes

Never modify scores manually in the frontend.

---

# Explanation architecture

All explanations must derive from `ScoringContext`.

Frontend and LLM layers must not invent ranking reasons.

The explanation must be reconstructible from:

- demand vector
- candidate eligibility
- capability contributions
- evidence interval
- PlayStyle modifier
- coverage
- tactical context

---

# Testing requirements

Every major change must run:

`python -m pytest backend/tests -q -p no:cacheprovider`

Also run:

- intelligence lab
- API tests
- version-wall tests
- production safety tests
- frontend/API integration tests where available
- deterministic replay tests

Compare against the Phase 23 baseline.

Track:
- test count
- pass/fail/skip
- failure IDs
- engine metrics
- recommendation deltas

---

# Required Phase 24 deliverables

Create:

`artifacts/phase24/`

with:

- `PHASE_24_BASELINE.json`
- `PHASE_24_ENGINE_RESULTS.json`
- `PHASE_24_API_RESULTS.json`
- `PHASE_24_E2E_RESULTS.json`
- `PHASE_24_FINAL_REPORT.md`

Update:

- `CLAUDE.md`
- relevant API documentation
- relevant frontend documentation
- versioned engine configuration
- tests
- goldens

---

# Completion criteria

Phase 24 is complete when:

1. V3.2 candidate changes are explicitly measured.
2. Missing-data invariant is fixed without regression.
3. FC26 and FC27 remain isolated.
4. API returns correct FC27 recommendations.
5. Frontend consumes backend ranking without duplicating scoring.
6. Explanations are evidence-derived.
7. Comparison works.
8. What-if recomputation works.
9. Near ties are communicated honestly.
10. Division handling is explicit.
11. UT-card scope remains disabled.
12. Research-only/legal gates remain intact.
13. Full regression is classified and documented.
14. End-to-end FC27 flow is verified.

---

# Future work — do not start automatically

After Phase 24, potential phases include:

- advanced archetype demand experiments
- validated GK tactical model
- legitimate UT-card data acquisition
- card-level recommendation engine
- market/value objective
- advanced PlayStyle mechanics if evidence becomes available
- personalization
- production deployment
- authentication/user profiles

Do not jump to these until the current phase is stable.

---

# Working method

Always:

baseline
→ small change
→ test
→ measure
→ compare
→ document
→ continue

Never:

guess
→ change formula
→ hide regression
→ declare success.

The deterministic intelligence engine remains the core product.
