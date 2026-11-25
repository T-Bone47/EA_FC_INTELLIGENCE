# Phase 32 handoff

Apply the Phase 32 files at the same source root as the existing Phase 31 app. This patch requires the existing database migrations, pinned source manifests and assets already used by Phase 31. It contains no raw dataset exports, paid dependencies, credentials or production configuration.

The single React app uses the Stadium shell by default. The archived source and build before migration are in `TOOLING/stitch-reference/pre-migration` on the development machine. The archive and repository artifacts capture implementation and test evidence.

## Commands

```powershell
npm.cmd --prefix frontend run build
python scripts/setup_database.py
python -m pytest backend/tests -q -p no:cacheprovider
```

Use an isolated loopback database for verification. Set `E2E_API_URL` to a local API serving the built frontend, `CHROME_PATH` to the local Chromium executable, `AXE_PATH` to axe-core and `STADIUM_RESULTS_DIR` to a writable results folder. To enable the existing local research card flow, initialize the registered, hash-pinned source releases and explicitly enable research on the local server. Each research workspace still requires its individual opt-in.

```powershell
node frontend/verification/stadium.mjs
node frontend/verification/fc27-local.mjs
node frontend/verification/fc27-performance.mjs phase31-browser.json
```

Use the existing Windows loopback preload in automated verification. The browser tests create disposable accounts and squads, so run them only against disposable data. The evidence report lists the exact results and the limitations of automated accessibility coverage.

See the route and feature parity CSVs for preservation details. Start with public Overview and Discover, then verify the gated FC27 item and performance workflows on the same app. Card pricing, chemistry and official role effects stay unavailable where unverified. The password recovery panel reports this instance's capability.
