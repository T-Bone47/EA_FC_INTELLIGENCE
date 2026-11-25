# PHASE 20 DATA ACQUISITION BASELINE

## Repository state
```
git: no .git directory exists in this repository (confirmed both this
     session and prior sessions) -- source-tree content hash used instead
     as the reproducibility anchor, per artifacts/v3_1/baseline/ precedent.
Python:      3.12.3
PostgreSQL:  16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)
```

## Database state (before any Phase 20 change)
```
game_player:       16,228 (FC26, 0 rejected)
ut_card:           60 total, 0 with is_synthetic=false
field_provenance:  585,560 rows
real_player:       20
```

## Config / reference distribution
```
config_version:                  v3-2026-09-17-r1
reference_distribution_version:  fc26-players-2026-09-r1
reference_distribution_universe: RATINGS_SITE_PLAYERS
```

## Data license gate status (before any change)
```
DataLicenseStatus("fc26-players-2026-09-r1") = UNVERIFIED
reason: exact 16,228/16,228 ID-set match to a GPL-3, RESEARCH_ONLY dataset;
        raw CC0 files named in the original manifest are not present in
        the repository (FC26_DATA_GAPS.md G-10) -- unresolved, unchanged
        since the v3.1 session.
```

## UT-card API behaviour (before any change)
`POST /api/v3/recommendations` with `entity_scope="ut_card"` → HTTP 422 at
Pydantic validation (the schema declares `Literal["game_player"]`); the
handler is never reached.

## Test suite (before any change)
```
515 passed, 24 failed, 1 skipped
```
Classification unchanged from `V3_1_CALIBRATION_REPORT.md` Section U:
9 expected-historical, 11 out-of-scope/pre-existing, 4 policy, 0 genuine.

This baseline is frozen and was not modified by this phase's work. All
Phase 20 additions are additive (new modules, new tests, new documents);
nothing above this line was changed.
