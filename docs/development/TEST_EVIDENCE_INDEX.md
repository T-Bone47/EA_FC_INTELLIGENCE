# Phase 28 test evidence

Evidence in [artifacts/full_development](../../artifacts/full_development/) is from the current source patch unless marked historical.

| Artifact | Verification |
| --- | --- |
| DATA_POLICY_TEST_RESULTS.json | Mixed-release fixture, exact row visibility, scoped cards and cache invalidation after commit and rollback. |
| DATABASE_INTEGRATION_RESULTS.json | Clean disposable PostgreSQL 16 migration through 011, isolated seed and restart tracking. |
| ENGINE_REGRESSION_RESULTS.json | Full backend counts and failure-ID comparison to the Phase 27 baseline. |
| TACTICAL_INTELLIGENCE_RESULTS.md | Formation options, slot-aware scores, V3 comparison and what-if, and stated account preferences. |
| FRONTEND_TEST_RESULTS.json | TypeScript, production assets and Vitest with the loopback backend. |
| BROWSER_E2E_RESULTS.json | Launch outcomes and verification still required. |

Source hashes are in the archive’s `SHA256SUMS`. The delta starts from the Phase 27 workspace snapshot and preserves unchanged files.
