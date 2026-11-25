# Phase 26 release certification

**BLOCKED_PENDING_ENVIRONMENT. Production certification is withheld.**

The tested revision is an exported working tree. SHA-256 revision fingerprint: `2ed6d0c74153a385d6b9bcd3f4bd5ee138aee9e98ae063e4753430e8bf7eee0d`. The working-tree diff covers 25 project files. Source hashes and the exact command results ship with this report.

## Verified in this environment

- Six Python licence and ingestion checks passed, including 24 reference-policy combinations.
- Ten subprocess scenarios verified browser runner exit handling. The live CLI exited 1 and wrote diagnostics when Puppeteer could not start.
- V3.2 ranked 192 FC26 position/tactic combinations and 144 FC27 division/position/tactic combinations in offline research. Reversing candidate order preserved the rankings, and the explanations reconstructed measured scores. FC26 also passed repeatability, pool independence and OVR independence checks.
- All 32 historical V3.1/V3.2 fingerprints matched. Eight isolated mixed scoring jobs per worker mode matched sequential execution.
- Three offline calls over 16,228 FC26 players had a median of 828.8 ms. The 24-candidate matrix median was 2.44 ms across 192 cases. These measurements cover the engine. HTTP, PostgreSQL and rendering latency are unmeasured.

## Remaining gates

Full backend and frontend tests stopped before collection or build because their required packages are unavailable. No isolated PostgreSQL, real browser E2E result, CI execution, device result, deployed security measurement or complete independent runtime sign-off is available. The cache-generation and research-spine migrations are staged for disposable-database verification. User data was never contacted.

Production V3 rejects the current FC26 UNVERIFIED dataset and the FC27 RESEARCH_ONLY snapshot. Card ingest correctly refused the CLI-only approval attempt. Production rights and approved card package bytes remain unresolved. Legacy V2 recommendation and comparison are disabled in production-like environments. V3 refuses non-null squad context.

The current engine calibration still exceeds the RD-3 OVR correlation ceiling in CB, CM and ST. The CB RD-4 spread is 0.093761 against a floor of 0.10. The scoring formula and registered thresholds were preserved.

User-facing recommendations, comparison and what-if are HTTP operations initiated by the user. The frontend displays the engine response. Candidate updates are intended to become visible on the next request after a database commit when migration 010 is applied. That propagation remains unmeasured.

## Contents

- Source and tests overlay plus before/after diff
- Original and final hashes
- Exact command output, historical failure references and offline reproduction scripts
- API, browser, database, security and ingestion evidence with unresolved checks
- Independent review findings and handoff
