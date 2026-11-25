# Database certification

**BLOCKED.** No disposable PostgreSQL service was available. No production or user database was touched.

Migration 009 is preserved. Migration 010 adds a transactional generation for candidate inputs and a conflict marker on the existing FC27 spine. Distinct linked player IDs now produce a null link and a conflict flag. Approved snapshot digests distinguish replays from conflicting or historical imports. Child-table commit/rollback and cache refresh have a staged CI regression. Migration 009 guard tests are wired into CI, with audited-package-dependent tests skipped when no package has been ingested.

Fresh installation, upgrade, PostgreSQL trigger/view semantics, card-package replay, rollback, migration idempotency and cross-worker visibility need isolated execution. The singleton generation counter can serialize concurrent writes. Measure contention on the supported ingestion workload before release.
