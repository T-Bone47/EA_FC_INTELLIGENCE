# Phase 24 — interim progress (NOT the final report)
Updated 2026-10-06. Sandbox rebuild; branch `phase24-v32-api-ui`. Nothing here has run on the owner's machine.

## Done and verified
- Baseline (662/24/1, failing IDs identical to Phase 23); pristine-tree lab re-run reproduces Phase 23 except the sampled missing-data probe counts (pool order depends on DB text collation).
- V3.2 engine/config change, V3.1 reproducible; goldens deliberately regenerated (7 named / 8 fingerprints).
- FC27 card identity research layer (migration 009, gated ingest, 16 tests).
- Plan A (API v3, 8 tasks + gzip) and Plan B (frontend, 7 tasks): all ledgered, TDD, gated commits.
- Frontend: 79 tests (76 + 3 live UI<->API) pass; production build OK. API transfer 786 KB -> 145 KB gzip.

## NOT done
- V3.2 lab run (sandbox kept stopping Postgres/background jobs) -> no V3.2 lab metrics; PHASE_24_ENGINE_RESULTS.json and PHASE_24_BASELINE.json not written.
- Real-browser verification of the UI; accessibility/mobile audit. Plan C: security audit, rate-limit decision, latency budget, final report.

## Awaiting owner decisions
- Registry policy for the fut.gg-derived card package (futgg is NOT_PERMITTED).
- Cap the response `excluded` list? Latency budget before any engine optimisation?
