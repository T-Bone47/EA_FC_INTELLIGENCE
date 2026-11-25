# Data pipeline and V3.2 verification

2026-11-23, Windows, fresh disposable PostgreSQL 16.16.

| Check | Result |
| --- | --- |
| Migrations | Applied through 012. A second setup skipped the applied files. |
| Player imports | 16,228 FC26 and 19,789 FC27 players. Consecutive FC27 imports preserved the fingerprint and data row counts. A report copied from another database did not generate a false replay comparison. |
| FC27 staging | Four archives, three distinct tables, 20,724 supplemental observations. A trial transaction rolled back. The first commit wrote all supplemental rows, and replay wrote zero. |
| Identity evidence | 7,698 item IDs with matching ratings and 14 direct-ID rating conflicts. |
| Field provenance | 585,560 FC26 attributes and 1,059,594 FC27 fields. FC27 recorded zero value mismatches, and both scans recorded zero cross-version violations. |
| Frozen references | Both rebuilt to their original SHA-256 quantile digests. A file with a modified quantile and its original digest was refused. |
| V3.2 recommendation API | 144 successful contexts covering 12 positions and the six studio tactics in each game version. Verified score and coverage bounds, explanation reconstruction, version and research labels, repeated ranking equality, and explicit FC27 opt-in. |
| Focused verification | 64 passing tests, including scoped references and provenance, the card fixture response, the version wall, and FC27 product workflows. |
| Full backend regression | Before the fixes, 777 passed, 24 failed, and 6 skipped. After the fixes, 779 passed, 24 failed, and 6 skipped. All 24 failing test IDs matched the baseline. |

## Fixes

The engine now verifies the checksum when loading a frozen distribution. FC27 reference builds take their population from the scoped research release. Field provenance selects the pinned observation used by that release and refuses incomplete membership or value mismatches before replacing evidence.

The FC27 ingestion CLI supports a separate report directory and checks the prior observation against the database before computing replay deltas. Card recommendations now identify their card-specific reference in the response. CI runs both frozen reference verification commands and the new integrity tests.

## Reproduce

Set `ENVIRONMENT=test` and point `DATABASE_URL` at a disposable local PostgreSQL database named `eafc_ci` for the guarded integration tests. Supply the four archive inputs in `$archives` and use fresh output directories.

```powershell
python scripts/setup_database.py
python scripts/setup_database.py
python scripts/ingest_fc26_foundation.py
python scripts/register_fc27_research_source.py
python scripts/ingest_fc27_research.py --artifacts-dir qa/ingest
python scripts/ingest_fc27_research.py --artifacts-dir qa/ingest
python scripts/ingest_synthetic_cards.py
python scripts/ingest_real_identities.py
python scripts/build_field_provenance_v3.py --game-version FC26 --report qa/provenance-fc26.json
python scripts/build_field_provenance_v3.py --game-version FC27 --report qa/provenance-fc27.json
python scripts/stage_fc27_evidence.py $archives --received 2026-11-23 --out qa/rollback --verify-rollback
python scripts/stage_fc27_evidence.py $archives --received 2026-11-23 --out qa/stage --stage
python scripts/stage_fc27_evidence.py $archives --received 2026-11-23 --out qa/replay --stage
python scripts/build_reference_distribution_v3.py --game-version FC26 --verify
python scripts/build_reference_distribution_v3.py --game-version FC27 --verify
python -m pytest -q backend/tests
```

## Open findings

Twenty baseline failures are in the legacy engine and its integration tests. Four FC26 real-data calibration checks remain open. The measured score-to-OVR correlations for CB, ST, and CM exceeded the 0.85 ceiling at 0.911, 0.877, and 0.863. CB tactical correlation spread measured 0.094 and missed its existing target. FC27 player data remains research-only. Public card recommendations require a verified release and a frozen card reference.
