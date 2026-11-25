# PHASE 20 CHANGELOG

## New files

```
backend/services/card_publication_gate.py       PUBLISHABLE/REVIEW_REQUIRED/NOT_PUBLISHABLE
                                                  gate; CardCandidate; player_cannot_become_card()
backend/tests/test_no_fabrication_firewall.py    32 tests: no-fabrication firewall (exact names
                                                  from the mandate), card version wall, reference
                                                  universe wall, field-level legality, release gate
artifacts/phase20/source_registry.json           7 sources, machine-readable
artifacts/phase20/baseline/                      Phase 20 baseline lock
```

## Modified files

```
backend/services/data_license_gate.py
    + DataLicenseStatus.PARTIAL
    + evaluate_dataset_release() -- full machine-readable release evaluation
    + Environment enum (LOCAL/RESEARCH/PRODUCTION)
    + ProductionOverrideForbidden -- structural refusal, not a convention
    ~ gate_or_raise() signature changed: `environment` is now a required
      keyword argument (BREAKING for any external caller -- none exist yet
      in this codebase; the two existing call sites were both test-only)

backend/tests/test_data_license_gate.py
    ~ updated for the new gate_or_raise() signature
    + 8 new tests: evaluate_dataset_release() decision rule, production
      override enforcement
```

## What was explicitly NOT changed

Per the mandate's own prohibition list: no recommendation-algorithm change, no lambda change, no PlayStyle/interaction model change, no chemistry engine, no ML, no frontend, no scraping, no price prediction. The V3.1 engine's scoring behaviour is byte-for-byte unchanged — confirmed by the final regression run showing the exact same 24 pre-existing failures, zero new ones, zero regressions.

## Bug found and fixed within this session's own new code

`evaluate_dataset_release()`'s first draft treated unmeasured (`None`) coverage as a passed check rather than missing evidence, which would have made VERIFIED reachable by *not measuring* rather than by measuring and clearing. Fixed before being reported as done; see `PHASE_20_RELEASE_GATE.md`.

## Net data acquisition outcome

No FC26 UT card data was ingested. No dataset moved from UNVERIFIED/UNKNOWN to VERIFIED. The one previously-most-promising candidate (FutDB) was downgraded on closer inspection (no published terms found at all, versus the prior YELLOW-pending-review classification). This is reported as the honest outcome of the investigation, not as a shortfall in the engineering work.
