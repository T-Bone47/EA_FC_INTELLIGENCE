# PHASE 21 BASELINE

## Repository state
```
git: no .git directory exists (confirmed again this session, consistent
     with Phase 20 and earlier)
Python:      3.12.3
PostgreSQL:  16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)
```

## Data state (before any Phase 21 change)
```
game_player (FC26):            16,228
ut_card, is_synthetic=true:    60
ut_card, is_synthetic=false:   0   (production card count)
DataLicenseStatus:             UNVERIFIED (player scope)
config_version:                v3-2026-09-17-r1
config_hash:                   09a7293b21d1347e1afe724a3df64020dd7e9b42330e76e12f1419a6ded60455
reference_distribution:        fc26-players-2026-09-r1 (RATINGS_SITE_PLAYERS)
lambda:                        0.7
```

## Test suite (before any Phase 21 change)
```
545 passed, 24 failed, 1 skipped
```
Confirmed identical to the Phase 20 end-state before any Phase 21 code was written.

## What Phase 21 is and is not

This phase prepares outreach materials and builds evidence-processing infrastructure. **It does not send anything.** No email, form submission, or API request was made to any data provider during this session. Where the mandate required "provider response evidence," the honest answer is: no provider has been contacted yet, so no response exists to evaluate — the infrastructure is built and tested against real, previously-gathered evidence (published terms of service) and against constructed hypothetical scenarios, never against a fabricated response.

This baseline is frozen; all Phase 21 work is additive.
