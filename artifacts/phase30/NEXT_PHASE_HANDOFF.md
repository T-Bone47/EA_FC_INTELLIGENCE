# Development handoff

## Run the delivered feature

Apply the update at the Phase 29 project root. It contains application source changes, migrations 011–013, tests, runners and the Phase 30 evidence. Existing dependencies, the base application, owner archives and private research database are separate prerequisites. Use the setup commands in FINAL_ENGINEERING_REPORT.md. Opening the local app at /cards/squad-lab requires the explicit research checkbox. Signing in enables saved scenarios and feedback.

## Verification entry points

- backend/tests/test_phase30_card_lab.py covers the exhaustive optimizer, Pareto oracle, identity conflicts, scoped owner access, signed feedback, missing locks, atomic save, release changes and rollback.
- frontend/verification/fc27-local.mjs covers browser acceptance on a loopback-only instance. The AXE_PATH environment variable enables the accessible-view scan.
- verification/run_phase30_local.py runs the private profile, including a live 72-context check. verification/phase30_upgrades.py reproduces exact live improvement values. verification/phase30_benchmark.py measures shortlist performance.
- The existing CI workflow now includes the pure optimizer and scope invariants. It can run those cases without the private archives. The private profile has been executed locally. Hosted execution remains unverified.

## Remaining work

Review footballer links and goalkeeper evidence without transferring attributes across editions or items. Version any approved identities and rebuild and verify the reference where necessary. Run manual keyboard/screen-reader acceptance across all views and remote CI on approved infrastructure. Retain present failure IDs and resolve the four calibration-policy cases through a versioned decision. Private saved feedback gives a starting point for future evaluation, with no learning claims today.
