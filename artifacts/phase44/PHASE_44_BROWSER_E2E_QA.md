# Phase 44 Browser E2E & Stadium 3.0 Visual QA

## 1. Live Bugs Surfaced by First Pass & Fixed
During the initial live Chromium QA sweep against PostgreSQL on `127.0.0.1:8010`, the server uncovered and we resolved three real integration issues:
1. PostgreSQL FK violation (`phase44_style_similarity_run_profile_version_id_fkey`) on `GET /api/phase44/similarity` — fixed by persisting `profile_version_id` idempotently (`ON CONFLICT DO NOTHING`) before inserting similarity runs.
2. `TrainingPlanService.generate_plan()` keyword-only argument mismatch (`TypeError`) on `GET /api/phase44/training-pathway` and `PersonalFormationEngine` argument order mismatch on `GET /api/phase44/recommendations/formations` — fixed in `backend/services/style_squad_training_bridge.py`.
3. `GamerDNAStudio.tsx` `Promise.all` cascade dropping all panels on single endpoint error — hardened with per-request `.catch(() => null)` isolation and upgraded UI polish (fixed invalid `'chart'` icon to `'zap'`, applied `btn primary sm` / `btn ghost sm` Stadium 3.0 button styling, added `overflow-wrap: anywhere` for long uppercase enum strings).

## 2. Final Re-Verified Playwright Chromium Pass (`1440x900` & `390x844`)
Executed against `http://localhost:5173` backed by PostgreSQL + FastAPI (`127.0.0.1:8010`) after all UI & backend fixes:
- **Authentication & SPA Flow:** Signed up fresh `@example.com` user (`201`) and navigated via `<Nav>` (`Play & Improve -> Gamer DNA`) preserving in-memory JWT across routes.
- **Desktop (`1440x900`) Measurements:**
  - `scrollWidth == 1440 == innerWidth` (`0px` horizontal overflow)
  - `Inspect All 60 Features` expanded all **60** feature rows (`feature_matrix_rows = 60`)
  - `Pro Style Matching` rendered the fail-closed Abstention Banner + all **8** EA FC Pro candidate rows (`pro_candidate_rows = 8`, `metadata_only_badges = 8`)
  - `Elite Skill Gaps`, `Style Evolution`, `Squad & Style Sandbox` (`Preview Sandbox XI` utility `0.74819` + `MARKET_PRICE_UNAVAILABLE`), `Governance & Controls` (`Accept Style Assessment` -> `STYLE_IDENTITY_PROFILE` saved), and `Ask AI Coach` Co-Pilot drawer verified cleanly.
- **Mobile (`390x844`) Measurements:**
  - `/gamer-dna`: `scrollWidth == 390 == innerWidth` (`0px` horizontal overflow)
  - `/tactical-lab`: `scrollWidth == 390 == innerWidth` (`0px` horizontal overflow)
- **Runtime Hygiene Counts:** `console_errors = 0`, `page_errors = 0`, `http_5xx = 0`, `http_4xx_post_auth = 0`.
- Screenshots visually inspected via `read_file`: `phase44_gamer_dna_identity_desktop.png`, `phase44_gamer_dna_pro_matching_desktop.png`, `phase44_gamer_dna_sandbox_desktop.png`, `phase44_gamer_dna_mobile.png`.
