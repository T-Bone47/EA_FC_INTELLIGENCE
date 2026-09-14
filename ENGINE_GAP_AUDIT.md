# Phase 4 Engine Gap Audit

**Audited:** 2026-09-14  
**Canonical engine:** `backend/services/recommendation_engine_v2.py`

## Result

The existing V2.1 engine already implements the primary Phase 4 architecture: deterministic candidate scoring, detailed attribute fit, dedicated GK paths, contextual PlayStyle scoring, tactical dimensions, derived archetypes/gameplay profiles, squad complementarity, explanations, sensitivity, counterfactuals, confidence, source-aware data status, and the FC26/FC27 wall.

The material functional gap found in the minimum requested formation set was `3-4-2-1`. It is now supplied by the existing formation intelligence layer and API metadata, with a regression contract confirming the flat layout and scored tactical slots agree.

## Remaining honest limitations

| Area | Status | Treatment |
| --- | --- | --- |
| FC26 canonical coverage | 16,228 CC0 players | Active and production-backed. |
| Women-universe production coverage | Not cleared for production | Flynn28 data isolated for research; no fabricated or unlicensed promotion. |
| Official EA Roles | No source | `INSUFFICIENT_EVIDENCE`; engine archetypes are clearly derived. |
| FUT cards | No structured permitted source observed | Optional architecture remains empty in production. |
| FUT prices/value | No verified source | `VALUE_UNAVAILABLE`; budgets remain unverified. |
| Chemistry/Evolutions | No verified rules/source | Structural squad fit only; no invented chemistry. |
| Live DB suite | Local PostgreSQL unavailable | Recorded as an environment prerequisite, not reported as passing. |

## Regression invariants retained

- One canonical V2 engine—no V3 or parallel scoring path.
- `UNKNOWN` is not a negative score and is explicitly surfaced through confidence/evidence.
- PlayStyle and PlayStyle+ remain distinct when source data supports the distinction.
- GK recommendations rely on `gk_*` fields rather than outfield ratings.
- Ranking remains deterministic and FC27 does not fall back to FC26.
- Synthetic fixtures remain isolated from production retrieval and scoring.
