# Baseline report (Phase 2) — 2026-10-27

**Commit** `ba5c5c0` on `phase25-restored`. **Result: 748 passed, 24 failed, 1 skipped across 44 test modules.** The 24 failures are the same set Phase 23 recorded
(compared by test id, path separators normalised); none is new. Per-failure verdicts: `BASELINE_FAILURES.csv`.

## Environment (measured)
Python 3.12.3 · Node v22.22.2 / npm 10.9.7 · psql (PostgreSQL) 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1) · "Ubuntu 24.04.4 LTS" · 1 CPU, 3995 MB RAM (shared sandbox; absolute timings do not transfer).
Python packages (unpinned `requirements.txt`, resolved today): fastapi==0.143.1, numpy==2.5.4, pandas==3.0.6, psycopg==3.3.6, psycopg-pool==3.3.3, pydantic==2.14.1, pytest==9.1.1, starlette==1.8.0, uvicorn==0.54.0.

## Commands
```
python -m pytest backend/tests/<module>.py -q -p no:cacheprovider -rfEs     # once per module, via a resumable driver (44 modules)
cd frontend && npx tsc --noEmit && npx vitest run && npm run build
python -m ruff check backend scripts --statistics
```
Why per module: the sandbox kills processes (and Postgres) at random; a single 4-minute run was destroyed three times. Each module's raw output is kept in `reports/e2e/evidence/baseline_chunks/`.
A module is retried once if its output shows DB-connection loss (no module needed a retry in the final pass). **No single uninterrupted full-suite run was achieved in this session.**

## Other gates
| Gate | Result |
|---|---|
| Frontend types (`tsc --noEmit`) | clean |
| Frontend tests (vitest) | 82 passed, 3 skipped (the 3 live UI<->API tests skip unless `E2E_API_URL` is set) |
| Frontend build | ✓ built in 3.24s |
| Migrations | 002-009 applied on a freshly built DB (base schema + seed applied by `setup_database.py`) |
| Backend lint (ruff) | **833 findings (707 auto-fixable)** — long-standing style debt; not gated anywhere |
| Backend type-check | none configured |
| Coverage | not measured (pytest-cov not installed) |
| CI | **none**: there is no `.github/workflows`; deployment files exist (`deploy/`) |

## The 24 failures (details and evidence in the CSV)
| Class | Count | Meaning here |
|---|---|---|
| POLICY_REQUIRED | 13 | 9 legacy-V2-engine adversarial tests + 4 stale V3 OVR-correlation thresholds. A human decision is needed (see below). |
| PRE_EXISTING | 5 | Stale tests whose *property of interest* was verified separately (rate limiting works; SQL input is inert; version wall passes). |
| UNCLASSIFIED | 6 | 3 formation-slot tests, confidence_v2, a tactical-combo status, a budget decision. Root cause NOT investigated; all v2-only. |
| NEW_REGRESSION / ENVIRONMENT_BLOCKED | 0 | see the contamination incident |

**Do these affect the production contract?** Yes in one place: **v2 `/api/recommendations` is still mounted** and the 9 legacy-engine failures show that engine can rank a generic high-OVR player above a specialist.
V3 (`/api/v3/*`) is unaffected. Decision for the human owner: retire or disable v2 recommendations in production, or label them legacy.

## Incident: a contaminated first aggregate (25 failures)
The first complete pass reported a 25th failure, `test_postgres_integration::test_production_counts_unchanged`. Cause: a *killed* run left the deliberately inserted `SYNTHETIC_TEST` player "Integration Testee" in the shared database (36,018 vs 36,017 players).
Verified: after deleting that one row and re-running the module to normal completion the count returned to 36,017 and the module passed; the contaminated output is kept as `*.CONTAMINATED_BY_RESIDUE.txt`.
**Finding (test isolation):** the suite writes to the shared development database; a normal run cleans up, an interrupted run does not. Not a production defect — the same test proves production scope excludes that row.

## Verified while classifying (reproducible)
* Login throttling: 15 wrong-password logins -> `401 x10, 429 x5` (limit 10/min). `test_rate_limiting` fails only because `conftest.py` relaxes every limit to 1,000,000 and the test never requests `strict_rate_limits`.
* SQL injection: 7 payloads against `/api/players?q=` -> `200`, 0 rows, no SQL text in responses, `pg_sleep` payload not executed, `game_player` 36,017 -> 36,017. Wildcards `%`/`_` match broadly but results are capped at 25.
* With the database down, `/api/auth/login` blocks for the 30 s pool timeout and then returns an unhandled 500 (see Phase 5).
