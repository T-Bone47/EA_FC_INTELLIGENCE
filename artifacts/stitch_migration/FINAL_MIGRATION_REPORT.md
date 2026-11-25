# EA FC Intelligence Phase 32

**Implemented and verified locally.** The existing React application now opens with the Stadium Intelligence workspace. Overview, discovery, V3.2 recommendations, exact-card comparison, Squad Lab, Squad DNA, Upgrade Studio, Evidence Lab, account and profile use the existing backend services and release policy.

## Verification

- The production build passed. Vitest passed all **94 tests**, including three against the real API.
- All three Chromium runners passed on the isolated setup. The Stadium runner checked eight views at seven widths. Its seven axe scans reported zero violations. Legacy runs also covered owned saved scenarios, signed fit feedback, stale preview rejection, and patch-aware evidence submission and withdrawal.
- The database applied migrations through 014 and replayed them idempotently. FC27 player ingestion loaded 19,789 records. Staging loaded 20,724 supplemental and card observations across the pinned archives. Replay wrote zero new staging rows and the process created zero public memberships.
- The full backend suite recorded **804 passed, 25 failed, 10 skipped** and 90 passing subtests. The Phase 31 baseline accounts for 24 matching failures. The additional Windows result is an FC26 candidate-loading test with a 2.0 s limit. It reproduced at **2.201 s** with the original API route and **2.194 s** with the migrated route on the same database. All three focused Phase 31 backend tests passed.

## Availability

FC27 item and performance evidence still require the approved local release and explicit opt-in. Live pricing, verified chemistry, password reset delivery and a private feedback-history screen are unavailable in this build. The Evidence Lab displays insufficient gameplay evidence when the available reviewed observations cannot support a comparison. Browser-local history records completed analysis settings. The account settings view links to saved work and retains current preference and session controls.

## Design and delivery

The responsive workspace uses the documented navy, lime and cyan palette, a local pitch graphic and initials where portrait rights are unavailable. Named fonts fall back to the local system stack. Squad DNA and Upgrade Studio are reachable sections of the same Squad Lab editor so the current scenario stays in place. The supplied comparison sheet shows the differences in density and data available to each screen.

See `NEXT_PHASE_HANDOFF.md` for commands and the rollback location. This delivery uses the original zero-cost input data and a local-only verification host.
