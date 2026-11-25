# Phase 30 engineering report

**23 November 2026 · Local FC27 research release · External spend ₹0**

The Ultimate Team Squad Lab builds and evaluates lineups of actual card items. The user can select a formation, assign and lock exact versions, apply tactical preferences, compare candidate lineups and save the scenario privately. The product uses the existing V3.2 engine and frozen card reference. The page is available at `/cards/squad-lab` on the local research server. Enable **Use local FC27 card research**. Unticked access and public deployments cannot serve this release.

## What the product demonstrated

| Workflow | Observed result |
|---|---|
| Version identity and squad eligibility | Checks distinct card IDs, confirmed base-footballer groups, eligible positions, scope and locks. Conflicted items are excluded. Confirmed-only mode returned zero eligible items on the current release. |
| Card optimization | An exact solution over up to 50 user-selected items, ordered by scored positions, summed V3.2 fit, optional continuity and item-ID tie-break. A manually locked primary goalkeeper retained its position with a null score. |
| Tactical alternatives | A 50-item shortlist filled all ten outfield slots in 4-3-3. Five tactical objectives produced five distinct, non-dominated alternatives among the generated lineups. Switching from balanced to possession changed RB, CDM and RCM, gained 0.039035 in possession fit and gave up 0.004152 in balanced fit. Both measurements cover the same ten scored slots. |
| Replacements | On a real five-item pool the best single replacement gained 0.0075775173. The best paired change gained 0.0086977772. For a requested gain of 0.0075775273 the minimum-change solver needed exactly two incoming items. It compares the same occupied slots and tactical context. |
| Formation and Squad DNA | The browser moved a shortlisted winger from RW to RM on a 4-3-3 to 4-4-2 change while retaining a locked goalkeeper. The interface shows weakest scored slots, published field means and sample counts, individual attribute fit and contributions, PlayStyles and missing evidence. |
| Advanced comparison and feedback | Two 91-OVR Yamal items retained separate attributes and PlayStyles. Six tactical profiles and observed-position fits use independent engine contexts. Incomplete evidence, overlapping intervals and near ties suppress claims of a clear leader. Signed feedback records the owner, card, release, engine/config/reference, request hash, outcome and timestamp in the private schema. |
| Saved work | Scenario creation is atomic and retry-safe. A stale preview receipt is rejected. The owner can reopen the saved shortlist, formation, locks, exclusions and preferences. Another owner receives 404. Two concurrent identical saves returned the same scenario ID. |

## Data and database checks

A new empty PostgreSQL 16.16 database applied the base schema, migrations 002–013 and the reference seed. Its second setup skipped all applied files. The four original archives yielded three distinct tables with 19,789 player rows, 10,762 supplemental records and 9,962 card items. Two archives contain equivalent player rows. The Phase 28 staging contract already handles the player release separately. It wrote 20,724 supplemental and card observations to the fresh staging database. Replay wrote zero rows and created zero public memberships.

The crosswalk reproduced 7,698 item-ID/rating agreements and 14 direct-ID rating conflicts. The pinned membership digest and reference digest reproduced. Reference groups contain 35 attributes each at defender, midfielder and attacker scope, and zero goalkeeper distributions. In the new suite a transaction appended a test-only member, the release check rejected the changed membership, and rollback restored the original count. An invocation behind forwarding headers was also refused. No test used the owner's production database.

## Mathematical and software verification

The exhaustive oracle checked 3,000 seeded 1–4 slot problems with shared footballer identities, duplicate-group alternatives, missing slots, score ties and continuity preferences. It checked the full optimizing tuple, each change-count solution and invariance to reversed option order. A separate case requires two incoming versions to free each other's confirmed footballer groups. Dominance checks covered 162 small objective-vector sets. The exactness argument and reduction rules are in CARD_OPTIMIZER_DESIGN.md.

| Check | Result |
|---|---|
| Full backend before development | 800 passed, 24 failed, 6 skipped, 90 subtests passed |
| Full backend after development | 806 passed, 24 failed, 6 skipped, 90 subtests passed. The failing test identifiers matched the fresh baseline. |
| Focused private acceptance | 15 passed across the Phase 29/30 files, including PostgreSQL ownership, concurrent saves, disallowed identity and receipt states, data gates, optimizer and rollback checks |
| Frontend | TypeScript and Vite production build passed. 93 Vitest checks passed across 17 files, including three live API tests. |
| Live card scoring | 72 position/tactic HTTP contexts. All 66 outfield contexts ranked and reconstructed their explanations. All six goalkeeper contexts returned no evaluated card. |
| Browser | Real Chromium with PostgreSQL-backed API exercised card comparisons, feedback, partial squad, upgrades, undo, formation transformation, matrix, save/reopen, profile defaults and a deliberately delayed response. It also reopened the existing eleven-player squad workflow. The 390px Squad Lab view passed the automated axe scan with zero violations. |

Two browser checks exposed issues during implementation. Adjacent React components shared a key and could leave duplicate formation controls after repeated edits. A dropdown could render briefly before its options arrived. Distinct component keys and an explicit loading state fixed both. Browser acceptance now checks for a single formation editor and waits on the actual preference-loaded form. A development test run also encountered an external telemetry attempt. The local QA setup includes a Node loopback guard, and Chromium rejects external origins. Automated accessibility coverage applies to the tested rendered view. Manual assistive-technology and hosted CI certification remain open.

## Performance

On Windows 11 with 12 logical CPUs, the final 50-item, five-tactic, ten-outfield-slot preview returned 17,934 bytes. Across 25 warm sequential HTTP requests the median was 206.3 ms and p95 was 238.5 ms. Twelve requests at concurrency four measured 823.0 ms median and 1,202.1 ms p95. Cold release load, validation and construction took 2.11 seconds. The per-request Python peak was approximately 3.53 MB, excluding the cached release. Sample sizes are too small for a useful p99.

Three development runs measured sequential p50/p95 of 91.4/220.6 ms, 115.6/251.1 ms and 78.6/102.9 ms. Background activity varied between runs. The final verification did not establish a latency improvement. Implementation changes retained only the best options for identities restricted to a single slot and avoided converting the UUID of every release item on each shortlist request. All four samples are preserved. The response timings show scope for further profiling under controlled load.

## Reproduction

From the application root, use the declared Python and frontend dependencies, the four owner archives, the existing FC26/FC27 player releases, and a disposable local PostgreSQL database. Set `DATABASE_URL` explicitly before setup. The private acceptance runner checks for the loopback test database named `eafc_ci`. Start it with the Phase 29 prerequisites documented in `artifacts/phase29/ZERO_BUDGET_STATUS.md`.

```powershell
$env:ENVIRONMENT = 'test'
$env:FC27_CARD_RESEARCH_ENABLED = 'true'
python scripts/setup_database.py
python scripts/setup_database.py
python scripts/stage_fc27_evidence.py "$env:USERPROFILE/Downloads" --received 2026-11-23 --out ".phase27-runtime/stage-$([guid]::NewGuid())" --stage
python -m scripts.build_fc27_card_research "$env:USERPROFILE/Downloads"
npm.cmd --prefix frontend run build
$env:FRONTEND_DIST = (Resolve-Path frontend/dist).Path
python -m uvicorn backend.api.main:create_app --factory --host 127.0.0.1 --port 38532 --no-proxy-headers
```

Use the following in a second terminal targeting the same test database. For an installed Chrome build, set `CHROME_PATH` to its executable. Set `AXE_PATH` to the local axe-core script to include the accessibility check.

```powershell
python -m pytest -q backend/tests --basetemp ".phase27-runtime/check-$([guid]::NewGuid())" --junitxml="$env:TEMP/phase30.xml"
python verification/run_phase30_local.py --api http://127.0.0.1:38532 --out ".phase27-runtime/qa-$([guid]::NewGuid())"
python -m verification.phase30_upgrades http://127.0.0.1:38532 artifacts/phase30/UPGRADE_ENGINE_RESULTS.json
python -m verification.phase30_benchmark http://127.0.0.1:38532 artifacts/phase30/PERFORMANCE_RELEASE.json
```

For this Windows host the frontend build used the same TypeScript and Vite executables through a temporary drive mapping to avoid a parent-directory ACL issue. Vitest used jsdom, two workers, the project setup file, a loopback API and Node 26's experimental Web Storage disabled. A test-environment warning about an ephemeral JWT secret applies to this disposable server. Its sessions and signed feedback receipts expire across restarts.

## Availability and next milestone

Availability is recorded per feature in FEATURE_COMPLETION_MATRIX.csv. The current release can be used privately for exploratory item squads. It has zero resolved base-footballer links, so it cannot certify that an XI contains eleven different footballers. Goalkeeper card evidence, official chemistry, price freshness and Evolution eligibility remain unavailable. The optimizer proves optimality within the submitted shortlist. The matrix reports non-dominance within generated alternatives. The product has no demonstrated catalogue-wide optimum, exhaustive global Pareto frontier, or learned personalization.

The highest-value data milestone is a reviewed, versioned item-to-footballer evidence release followed by an item-scoped goalkeeper reference where adequate observations exist. The 20 historical V2/integration failures and four FC26 calibration-policy failures remain visible. Public production remains uncertified.
