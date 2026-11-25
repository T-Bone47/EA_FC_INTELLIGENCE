# EA FC Phase 27 audit remediation

**NOT CERTIFIED for production.** Phase 27 closes the known data-release gap for the bundled snapshots and verifies the application against a disposable PostgreSQL database and a real local browser. FC26 release rights remain unverified, FC27 remains research-only, and the existing calibration failures remain open.

## Changes

- Browse, detail, facets, card history, card values and data-bearing metadata now use the same version- and entity-scoped release registry as V3. Production readiness omits dataset counts, and unapproved data is withheld from saved-player and squad responses.
- Card search, detail and linked cards require canonical, non-synthetic rows. Cross-version joins are constrained, and the diagnostic synthetic path is explicit.
- The FC26 seed now records UNKNOWN rights with local packaged-file processing only. The import script checks the release gate. The Docker build configuration excludes local data and validation artifacts. The image itself was not built.
- The legacy intent parser and squad evaluation/replacement are local research tools. Results identify their submitted inputs and ignore a superseded recommendation or what-if response.
- Apply migration 010 before starting the API. The readiness endpoint now checks the generation table. The migration runner refuses changes to applied schema migrations.

## Executed verification

| Check | Result |
|---|---|
| Live local production-mode HTTP | 22 denied requests across browse, detail, metadata, and V3 with the fixture data loaded |
| PostgreSQL 16.16 | Fresh setup, migration 009 to 010, repeat migration tracking, changed-checksum refusal, and targeted commit/rollback passed |
| Database and backend targeted run | 102 passed, 5 skipped because approved FC27 cards were unavailable |
| Backend full rerun | 756 passed, 24 failed, 6 skipped, 0 errors, and 90 passing subtests. 0 new failure IDs relative to the baseline |
| Final focused policy and service contracts | 12 passed after the container and reference-loader changes |
| Frontend | TypeScript and production build passed. All 88 Vitest cases passed, including three with live FastAPI and PostgreSQL |
| Local browser | FC27 research recommendation, comparison and what-if passed. FC26 rendered ten ranked results with no horizontal page overflow at widths 1280, 768, and 390 px |
| Browser automation | 10 runner exit tests passed. Chromium headless startup was blocked in this Windows environment. Hosted CI, automated axe, Tab order, and touch gates were not executed |

The live research HTTP probes returned consistent FC26 and FC27 rankings across eight concurrent requests. Median warm recommendation latency was 884 ms for FC26 and 1114 ms for FC27, with six sequential samples per version. The controlled update changed the comparison score on the first request after commit in 2.52 s. The tests verified that uncommitted and rolled-back changes stayed invisible. They restored the original value. No user database was accessed.

## Remaining release gates

The scoring weights and thresholds are unchanged. The historical RD-3 CB, CM, and ST cases still exceed the correlation ceiling. CB RD-4 remains 0.093761 against 0.10. Public serving also requires approved rights evidence and a deployment manifest tying approved releases to the exact imported rows and files. An approved FC27 card ingest, hosted CI, automated accessibility and touch checks, and independent production verification remain open.

The bundle contains a source overlay over the Phase 26 working tree, a before/after diff, exact backend failure IDs, and runtime evidence. SHA-256 revision fingerprint `fc2876b0630d5025db6e705ede5b09af613aa0958ea550187a8742a5aa4430c9`.
