# Phase 26 defect register

| Inspection ID | Change or finding | Evidence and remaining work |
|---|---|---|
| P26-01 | Required checks, empty suites, missing screenshots and infrastructure errors fail the browser process. Critical and serious axe WCAG findings block. | Node subprocess regression tests and startup JSON. Actual journey and CI blocked locally. |
| P26-02/03 | Both reference paths now use the same registered, version-scoped licence gate. Production and staging refuse the shipped FC26 and FC27 datasets. | Licence matrix passed locally. Full route and alternate deployment regressions require the backend dependencies. |
| P26-04 | Card ingest requires independently reviewed permission, a pinned file inventory and hash/count/identity validation. Existing snapshot content is preserved. | Local refusal and file checks passed. Approved full package and disposable DB absent. |
| P26-05 | V2 ranked recommendation and comparison routes are restricted to development/research deployments. | Production HTTP contract regression prepared. Legacy callers using these routes in production receive HTTP 410. |
| P26-06 | Added release-runner JSON, assertion checks, real response/render comparison and CI wiring. | Live browser/API/database certification remains blocked. |
| P26-07 | Migration 010 adds a transactional candidate-generation counter for joined sources. | Integration test available against disposable CI database. Update propagation and write contention remain unmeasured. |
| P26-08 | V3 rejects a non-null squad ID and duplicate compare identifiers. | New contract tests require backend dependencies. |
| P26-09 | What-if reports candidate counts and correlates each variant with its parent. Late comparison results are discarded. | Source changes in place. Frontend and API tests require dependencies. |
| P26-10 | Gzip and response contract remain in place. | Full-response timings and owner payload budgets are unresolved. |
| P26-11 | Existing tests and threshold files retained. | Calibration measurements reproduced. Current full failure list remains unavailable. |
| P26-12 | CI workflow added. Recommendations and refresh remain user-initiated HTTP. | CI has yet to run on a Git host. |
| Phase 26 review | Engine checks scope and statuses, including inconsistent synthetic flags. Player PlayStyle evidence is version-isolated. | Independent offline engine invariants verified. DB-backed PlayStyle and confidence cases need integration evidence. |
