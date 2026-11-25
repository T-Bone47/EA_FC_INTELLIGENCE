# PHASE 20 TEST RESULTS

```
545 passed, 24 failed, 1 skipped
```
(up from 515 passed / 24 failed / 1 skipped at the Phase 20 baseline — **+30 new passing tests, 0 new failures, 0 regressions**, confirmed by diffing the failure list before and after: identical 24 test IDs.)

## New tests added this phase (35 total, confirmed by `pytest --collect-only`)

| File | Count | Covers |
|---|---|---|
| `test_data_license_gate.py` (extended) | 13 | `PARTIAL` status, `evaluate_dataset_release()` decision rule, `ProductionOverrideForbidden`, unmeasured-coverage fail-closed fix |
| `test_no_fabrication_firewall.py` | 22 | Exact named tests from the mandate (`test_player_cannot_become_card_implicitly`, `test_missing_card_id_blocks_publication`, `test_missing_card_version_blocks_publication`, `test_unverified_card_field_is_not_served`, `test_synthetic_card_never_enters_production`, `test_fc25_card_cannot_enter_fc26_scope`), plus CARD/REFERENCE/LEGAL/RELEASE categories from §23 |

35 tests now exist across both files, but the net passed-count delta from baseline was +30 (515→545): `test_data_license_gate.py` had 5 pre-existing tests (from the V3.1 session) that were modified in place for the new `gate_or_raise(environment=...)` signature — same test names, updated bodies, not net-new passes — plus 8 genuinely new tests (13 − 5 = 8). Combined with 22 new tests in `test_no_fabrication_firewall.py`: 8 + 22 = 30, matching the observed delta exactly.

## Full classification of all 24 remaining failures

### EXPECTED HISTORICAL (9)
`test_engine_adversarial_phase7.py` — v2's known-defective behaviour, preserved unchanged per the Session-1 migration decision. Untouched this phase.

### OUT-OF-SCOPE / PRE-EXISTING (11)
`test_integration_production.py` — pre-existing test/implementation drift unrelated to demand composition, capability, gating, provenance, conflict resolution, or (this phase's additions) card licensing/publication. Individually re-verified in the V3.1 calibration session; not touched or re-touched this phase.

### POLICY_OWNER_REQUIRED (4)
`test_engine_v3_real_data.py::TestRD3OvrCorrelationBand` (CB, ST, CM) and `TestRD4TacticalResponsiveness` (CB) — real, structurally-explained measurements against thresholds never empirically calibrated or owner-approved (see `V3_1_CALIBRATION_REPORT.md`). Unrelated to this phase's scope; left exactly as found.

### NEW REGRESSION (0)
None. Confirmed by exact-match diff of the failing-test-ID list before and after this phase's changes.

### NEW DATA/LICENSING FINDING (0 test failures, but real findings nonetheless)
No test failure represents a data/licensing finding — the findings from this phase (FutDB's downgrade, the FUT-DB.com naming collision, FUTWIZ remaining unresolved) are documentation/research findings, not code defects, and are reported in `PHASE_20_SOURCE_FORENSICS.md` and `PHASE_20_LEGAL_REVIEW.md` rather than encoded as failing tests (there is no card dataset to write a failing ingestion test against).

### GENUINE ENGINE FAILURE (0)

**Unresolved production-contract failures introduced by this phase: zero.**
