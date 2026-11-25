# EA FC Intelligence Phase 28 checkpoint

## What changed

- Shared catalogue reads now require an eligible release and matching row membership. Player, card and linked data keep their own scopes. Current source clearance and release decisions are preserved.
- V3 recommendations, comparisons and what-if queries accept supported formation slots and pass their demand to the existing scoring engine. A typed intent draft endpoint validates supported parser output.
- Account holders can save a stated position and tactical style and explicitly apply them. The studio and catalogue reject stale responses after request context changes.
- Card browsing reports unavailable releases. The scoped availability response counts observed attributes independently of card identity.

## Verification

- PostgreSQL 16.16 applied the complete chain through migration 011 on a clean disposable database, and its repeat setup skipped tracked migrations.
- Final focused backend run passed 91 tests and 66 subtests. The earlier full run passed 772, skipped 8 and had the same 24 failure IDs as the Phase 27 baseline. It preceded the final card-status check.
- TypeScript and production build passed. Vitest passed 92 tests, including three against the loopback API and database.
- The real-browser harness passed 10 self-tests. Both real-browser launch paths timed out before running journeys.

## Release verdict

**NOT_CERTIFIED.** Public catalogue approval, historical calibration and legacy test failures, real-browser verification and later product phases remain open. Formation weights are application-defined. Card scope, squad optimization and feedback-origin verification require further development.

See [development state](../../docs/development/MASTER_DEVELOPMENT_STATE.md) and [test evidence](../../docs/development/TEST_EVIDENCE_INDEX.md).
