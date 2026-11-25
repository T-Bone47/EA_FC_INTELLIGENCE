# FC27 data availability and frontend integration

The running local server at `127.0.0.1:38536` uses the existing `eafc_phase32_browser_1` PostgreSQL database on port 35441. The release checks were read-only. No dataset was re-imported and no licence decision changed.

## Root cause

- The header and Discover read the FC27 legacy catalogue metadata. Its `NO_DATA` value described the unapproved public catalogue. Actual research requests use scoped membership and pinned card services.
- Discover sent the player research opt-in to search and facets. It still requested production reference metadata, so the filters could omit FC27 positions and PlayStyles.
- Research opt-in lived in individual pages. Navigating between Discover, Cards and Squad Lab could restore the restricted view even after a user opted in. Intelligence had the opposite issue and set the research flag based on the game version alone.
- `/recommend` mounted the older recommendation form. Its canonical catalogue gate produced misleading availability text even with a valid V3.2 research release.

## Verified database state

| Scope | Count derived from the database | Reference | Status |
|---|---:|---|---|
| FC27 players | 19,789 scoped members | `fc27-players-2026-09-r1` | Local research, reference valid |
| FC27 cards | 9,962 pinned items | `fc27-card-items-local-r1` | Local research, outfield reference valid |
| FC27 goalkeeper scoring | — | Card reference has no GK group | Assigned goalkeeper can remain unscored |
| FC27 production | 0 approved records in either scope | — | Production approval unavailable |

The accompanying database evidence contains the source membership, item snapshot ID and both validated reference hashes. Card metadata and serving use the same switch, loopback and forwarding checks.

## What changed

`GET /api/meta/availability` distinguishes connection failure, datasets absent from the runtime, invalid release membership, a missing or invalid reference, disabled research, an available research release, and unavailable production approval. It returns environment and per-version player/card scopes. Public-production responses omit local research counts and identifiers. The endpoint is served with `private, no-store`.

The header shows separate player and card statuses. The opt-in is shared within the browser tab and starts off in a new tab session. Turning it off clears the research views and makes the opt-in required again. The backend checks its own release and environment policy on every request.

Discover uses the same opt-in for search, detail, facets and reference metadata. The old `/recommend` URL redirects to Intelligence Studio and preserves the query. The Studio sends formation, slot, position, division, tactics and preferences to `/api/v3/recommendations` and compares under the same request. FC27 player comparisons use the Studio. Exact card comparison and Squad Lab continue to use their pinned item reference and the existing optimizer.

## Verification

- Production frontend build passed. All 95 frontend tests passed, including three live API tests.
- All 13 focused backend tests passed on disposable PostgreSQL. They covered availability states, reference loss, DB connection failure, and the existing card, squad and performance research safeguards.
- Chromium completed the full FC27 journey on the actual local API and PostgreSQL database, including research opt-out. A separate server running in production mode denied requests for research players, scoped metadata, V3.2 recommendations, cards and squad previews. The browser reported no uncaught errors.
- The complete legacy backend suite was outside this verification. The Phase 32 baseline report remains the reference for that suite.

`frontend/verification/fc27-availability.mjs` reproduces the browser checks. Configure `E2E_API_URL` and `E2E_PRODUCTION_URL` for the two loopback instances and `AVAILABILITY_RESULTS_DIR` for the outputs. Run the focused tests with `pytest` against the existing disposable research database. The ZIP overlays these changes on the existing Phase 32 checkout.
