# Phase 29 · FC27 local intelligence

**23 November 2026 · external data spend ₹0.** The local application can search 9,962 item observations, rank outfield cards for a formation slot, explain differences between special versions, and recompute the ranking under a change of tactics. The squad builder can optimize a lineup of distinct game players and save it as a new squad. Both workflows ran against the actual PostgreSQL database through the built React application.

## Feature status

| Capability | Verdict | Demonstrated behavior or boundary |
|---|---|---|
| Acquisition and staging | INTEGRATED_AND_VERIFIED | All four archive hashes checked. Two copies describe the same 19,789-player snapshot. The 10,762 October rows and 9,962 card rows remain separate observations. A PostgreSQL replay inserted zero rows and created zero public memberships. |
| FC27 player suitability, comparisons and replacements | RESEARCH_ONLY | Existing V3.2 player reference, squad slot scoring, replacements and feedback remain available with research opt-in. The PostgreSQL tests exercised assignments, replacement and feedback receipts. |
| Card reference and identity | RESEARCH_ONLY | Release `fc27-card-items-local-r1` pins the source, all 9,962 normalized observations and their identity reviews, plus the frozen UT card quantiles. The original 7,698 item/rating agreements and 14 direct-ID rating conflicts remain recorded. Each version has its own identifier. |
| Card search and tactical ranking | RESEARCH_ONLY | Search by item ID or name, inspect rarity and observed positions, rank eligible versions using the existing V3.2 demand, coverage and scoring routines. The live API exercised all 12 positions under six tactics. |
| Formation and PlayStyle intelligence | RESEARCH_ONLY | A formation and named slot feed the existing demand composer. A preferred PlayStyle+ uses the existing bounded modifier. The UI shows the underlying tier and explicitly labels editorial role-fit observations. |
| Card comparison, explanations and tactical stability | RESEARCH_ONLY | The two 91-OVR Yamal items have distinct attributes, tiers and scoring contexts. The browser verified item-specific stamina of 78 and 80, a why-not explanation and a tactical rerank. Changing settings invalidates the previous result. |
| Saved squad builder and optimizer | INTEGRATED_AND_VERIFIED | For an owned squad, the optimizer can rearrange its visible players or select from the eligible game-player catalogue. It maximizes filled slots, then the sum of V3.2 slot scores, using each player once. Saving recomputes the preview and creates the new squad and its assignments in one transaction. An obsolete receipt is rejected. |
| Goalkeeper card scoring | RESEARCH_ONLY · insufficient item evidence | Of 1,102 records listing GK, 1,100 lack sufficient goalkeeper attributes and two are outfield-primary items excluded by the goalkeeper boundary. The October table has keeper fields, but this card release does not establish a reviewed relationship for transferring them. |
| Prices, chemistry and official role effects | Unavailable | No verified price or chemistry inputs enter the optimizer. Missing prices remain null. Official eligibility and effects remain unknown. |
| Complete UT card XI, including shared-footballer constraints | NOT_IMPLEMENTED | Exact lineup optimization currently works on game-player IDs. Unresolved base relationships and unavailable goalkeeper card scores prevent certification of a full legal UT card XI. |
| Personalization and feedback | INTEGRATED_AND_VERIFIED for players | Existing stated preferences and signed player recommendation feedback remain available. This release adds card PlayStyle preferences per request. Longitudinal learning and signed research-card feedback remain unimplemented. |
| Public FC27 card release | BLOCKED_BY_DATA_RIGHTS | The dedicated research route needs explicit opt-in, local deployment settings, a loopback database and local HTTP access. The current release grants no public usage scope. |
| Whole-platform certification | Open | The full suite retains 24 baseline failures. The new workflows pass the specified local acceptance checks. |

The card reference has 35 populated attribute distributions in each of the defender, midfielder and attacker groups. The goalkeeper group has none. Only attributes from each card row enter its score. Player attributes and editorial role-fit numbers do not enter the card reference. For the optimizer, uniqueness applies to the selected game-player identifier. The objective covers individual slot scores and slot coverage. Team interactions and transfer affordability are outside this objective.

## Use the local application

In **UT Cards**, select **FC27**, enable **Use local FC27 card research**, and search for Yamal. Select the Team of the Week and Star Performer versions. Choose RW, a tactical profile and optionally a preferred PlayStyle+. **Compare selected versions** shows the published fields and ranking explanation. **Test tactical change** recomputes the ranking under the alternative profile.

In **Squads**, open an owned FC27 squad and enable **Include FC27 research players**. Choose **Players in this squad** to rearrange the roster, or **Available player catalogue** for a fresh XI. Preview the lineup, name it and save the copy.

## Reproduce from the Phase 28 project

The delivery ZIP is a source update for the existing project. Its paths are relative to the application root containing `backend`, `frontend` and `db`. Use the existing dependencies and point `DATABASE_URL` at a local, disposable PostgreSQL instance with the Phase 28 migrations and player release installed. The archive directory must contain the four original ZIPs. The staging command needs a new output directory on each invocation.

```powershell
$env:ENVIRONMENT = 'test'
$env:FC27_CARD_RESEARCH_ENABLED = 'true'
python scripts/stage_fc27_evidence.py "$env:USERPROFILE/Downloads" --received 2026-11-23 --out "qa/stage-$([guid]::NewGuid())" --stage
python -m scripts.build_fc27_card_research "$env:USERPROFILE/Downloads"
npm.cmd --prefix frontend run build
$env:FRONTEND_DIST = (Resolve-Path frontend/dist).Path
python -m uvicorn backend.api.main:create_app --factory --host 127.0.0.1 --port 38529 --no-proxy-headers
```

With the local API running, the browser runner uses an installed Chromium browser. On a fresh machine install the repository's declared dependencies first. This development path requires no external dataset or API account.

```powershell
$env:E2E_API_URL = 'http://127.0.0.1:38529'
$env:CHROME_PATH = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
node frontend/verification/fc27-local.mjs
python verification/check_local_card_release.py $env:E2E_API_URL artifacts/phase29/CARD_CHECKS.json
python -m pytest -q backend/tests
npm.cmd --prefix frontend test
```

## Verification and remaining findings

| Check | Observed result |
|---|---|
| Backend regression on PostgreSQL | 800 passed, 24 failed, 6 skipped. All 24 failing IDs matched the Phase 28 baseline. An additional 90 subtests passed. |
| Outstanding failures | 20 legacy engine/integration checks and four FC26 calibration checks. The calibration checks cover score-to-OVR correlation at CB, ST and CM and tactical spread at CB. Calibration constants were preserved. |
| Skips | Five checks target a separate earlier card-identity package absent from the database. One is a pre-existing placeholder. |
| TypeScript and frontend | Type checking and Vite build passed. All 93 Vitest tests passed, including three live-API tests. |
| Browser | The built app passed four grouped journeys covering exact-version comparison, PlayStyle preference, formation, tactical change, mobile width, unavailable goalkeeper scoring and saving a distinct-player XI. Zero uncaught browser errors. This run did not include a new screen-reader audit. |
| Card API matrix | 72 sequential loopback HTTP requests. All 66 outfield contexts returned rankings with reconstructible explanations. Six goalkeeper contexts returned explicit insufficient evidence or ineligibility. Median 120 ms and observed p95 255 ms. Measurements describe this machine and this request mix. |
| Runtime recovery | Initial Windows tool runs hit a Vite path-resolution issue and an automatic approval rejection for an unexpected external telemetry request. The completed browser verification restricted traffic to loopback. Backend regression used an offline runner and a writable temporary directory. Vitest used the repository's jsdom settings and disabled Node 26's experimental Web Storage to use jsdom storage. |

Machine-readable evidence includes the full list of failed and skipped tests, browser outcomes and each live tactical context. [Verification results](VERIFICATION.json) · [Card API measurements](CARD_CHECKS.json)
