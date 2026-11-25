# Phase 26 baseline

The working tree is the nested Phase 24–25 export. Git reported no repository. BASELINE_SHA256.json fingerprints 540 files before changes. There was no branch or commit to verify. The baseline ran under Windows, Python 3.15 and Node.js 26.12.1. A bundled Python 3.12.14 runtime also lacked pytest, FastAPI, bcrypt and psycopg.

Existing commands stopped before test collection or browser launch. Local package installation attempts did not recover the missing Python and Node dependencies. PostgreSQL client/server and Docker were unavailable. WSL could not open a local logon session. No user database was contacted.

The earlier export recorded 748 backend passes, 24 failures and one skip, plus 82 frontend passes and three skips. See reports/e2e/BASELINE_FAILURES.csv for historical IDs. A Phase 26 failure-ID diff remains blocked because the full current suites stopped before collecting tests. Four calibration findings were independently reproduced.
