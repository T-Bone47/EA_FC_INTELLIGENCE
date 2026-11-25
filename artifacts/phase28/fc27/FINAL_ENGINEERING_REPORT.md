# EA FC Intelligence Phase 28 FC27 integration

## Verified product scope

| Area | Outcome |
| --- | --- |
| Data foundation | Ingested 19,789 existing, hash-pinned player records into the exact research release and reconciled 1,059,594 published fields. Audited four archives and staged 20,724 supplemental observations in PostgreSQL 16. |
| Identity | Reproduced the 7,698 item ID and rating matches and 14 direct-player-ID rating conflicts. All source item IDs retain separate base-ID evidence. |
| Player intelligence | Added opt-in FC27 search and player detail. Tactics, formation-slot ranking, comparisons and what-if reuse the same FC27 player reference and existing V3.2 engine. |
| Card contracts | Item-specific observations, side-by-side attribute differences and V3.2 scoring with an approved test release and distinct frozen card distribution. Missing card fields stay unknown. |
| Squad intelligence | Authentication and version gates apply to squad views and V3.2 slot fit. Suggestions filter existing squad players, show gain against the incumbent, and can be applied and rescored. |
| Advanced intelligence | The tactical compatibility table compares bounded variations of the submitted context and shows whether its original leader moved. Signed feedback preserves the served player, model, data release and recommendation context. |
| Provider readiness | FCData terms and published capabilities reviewed. The owner-review permission request is drafted. |

## Tests and timing

- Fresh PostgreSQL 16.16 applied migrations 001–012. Repeated setup skipped the audited files. Staging inserted 4 metadata entries and 20,724 new-source rows. A separate rollback wrote the same plan and committed nothing. Replay inserted zero.
- The focused backend run passed **105 tests and 66 subtests**. It includes the live scoped search-to-squad journey, card release and mixed-source exclusion, and feedback receipt checks.
- Full backend regression passed **777 tests**, skipped **6**, and reproduced the same **24 historical failure IDs**. There were zero new failing IDs. The outstanding failures cover legacy V2 expectations and V3 calibration thresholds.
- Production frontend build passed. Vitest passed **93 tests**, including three against the loopback API and PostgreSQL.
- The final Chromium run passed **51 checks across 15 suites**. Axe reported zero violations on three scanned states.
- Before the environment switch, the real browser opened an FC27 research player detail, ran a women's high-press 4-3-3 CDM recommendation and an RCM variation, created an FC27 squad, and applied a V3.2 replacement. The slot score moved from 0.784 to 0.875. At 390 px, the fixed squad view stayed within the viewport and Tab reached the tactical selector. The final Linux test suite re-exercised the squad workflow over the API.
- The local benchmark used 19,789 player records and 12,101 candidates in the tested position family. Warm engine p50 was 947 ms. Cold candidate loading took 2.19 s. The uncompressed response was about 865 kB. See the performance JSON for sample sizes and method.

## Reproduce

Use a disposable loopback PostgreSQL 16 database, set `ENVIRONMENT=test` and `DATABASE_URL`, then run the repository's setup, FC26 foundation, FC27 source registration, FC27 research ingestion, synthetic-card fixture and field-provenance scripts. The archive input commands are in the data source inventory.

```sh
python scripts/setup_database.py
python scripts/register_fc27_research_source.py
python scripts/ingest_fc27_research.py
python scripts/build_reference_distribution_v3.py --game-version FC27 --verify
python -m pytest -q backend/tests
npm --prefix frontend run build
E2E_API_URL=http://127.0.0.1:35428 npm --prefix frontend test
python scripts/benchmark_fc27_research.py --out /tmp/fc27-performance.json
```

The frontend live tests also require Uvicorn to be running on the indicated port. An explicit `FRONTEND_DIST` serves built assets for browser QA. Leave that variable unset during the backend-only suite so its temporary test routes are reachable.

## Release decision

**NOT_CERTIFIED.** Existing approval permits local FC27 player research. Real card publication and scoring await a verified source release and frozen UT card distribution. Official role eligibility, verified chemistry, market/budget decisions and Evolutions remain gated. Squad suggestions optimize one slot at a time. Full multi-objective optimization, preference learning and hosted certification remain open.

The data archive hashes establish input integrity. They do not establish rights. The provider request was prepared for owner review only.
