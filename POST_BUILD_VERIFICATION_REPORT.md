# POST-BUILD VERIFICATION REPORT — EA FC Player Intelligence

**Audit date:** 2026-09-14 (Asia/Calcutta) · **Auditor:** autonomous agent (independent re-verification pass)
**Method:** every claim in `AUTONOMOUS_DEVELOPMENT_FINAL_REPORT.md` was re-checked by EXECUTING live checks
against the running production stack (uvicorn :8000, ENVIRONMENT=production, PostgreSQL 17, built SPA from
`frontend/dist`) and the dev server (vite :5173, proxied). No historical results were accepted as evidence.

**Headline result:**

| Suite | Result |
|---|---|
| Backend pytest (live re-run) | **161 / 161 passed** |
| Frontend vitest (live re-run) | **33 / 33 passed** (24 original + 9 new regression tests from this audit) |
| TypeScript `tsc --noEmit` | clean |
| Production build `vite build` | succeeds (dist served by API on :8000) |
| `verification/post_build_verify.py` (§4–§9, API/engine/security/auth/firewall) | **64 / 64 PASS** |
| `verification/browser_verify.mjs` (§10, real Chromium via Playwright) | **21 / 21 PASS on :8000** and **21 / 21 PASS on :5173** |
| DB counts (§2) | 23 / 23 checks (16,228 FC26 game_players · 15,032 playstyle links · 36 tables · 60 synthetic-only ut_cards) |
| Benchmark re-run (§11) | all winners/scores/counts reproduce the documented baseline exactly; warm p50 at or better than baseline |
| Secret scan (§15) | clean — no `.env` tracked, no hardcoded secrets, production refuses to boot without `JWT_SECRET` |

**Failures found by this audit: 5 real product defects (1 HIGH, 3 MEDIUM, 1 LOW) — ALL FIXED and regression-tested.**
Plus 2 wrong audit-script expectations (product was correct; scripts patched) and several test-harness/rate-limit
artifacts (documented below, not product failures).

---

## Failure log (audit-first, as required)

| # | Severity | Component | Defect | Evidence | Fix | Regression test |
|---|---|---|---|---|---|---|
| 1 | MEDIUM | `backend/api/main.py` | `create_app()` built an app whose security stack did not consult `effective_jwt_secret()`; a misconfigured production boot could run with a non-fail-fast secret path | found by code-path audit before live runs | wired `effective_jwt_secret()` into app creation so `ENVIRONMENT=production` without `JWT_SECRET` raises at import | `backend/tests/test_security.py` (in the 161) |
| 2 | HIGH | `frontend/src/lib/useApi.ts` (`useAction`) | Stale closure: `run()` was `useCallback(..., [])` capturing the MOUNT-TIME callback. Real user impact proven in browser: after switching to FC27, `POST /api/recommendations` still sent `game_version:"FC26"`; position/playstyle chip clicks were never applied (16,228 full-pool evals observed when 1,976 were expected) | Playwright network capture (`verification/browser_verify.mjs` first run) | `fnRef` pattern — `fnRef.current = fn` every render; `run()` invokes `fnRef.current` | `frontend/src/lib/useApi.test.tsx` (5 tests) |
| 3 | MEDIUM | `frontend/src/lib/useApi.ts` (introduced by fix #2, caught by this same audit) | `mounted` ref cleanup set `mounted=false` under React 18 StrictMode's effect→cleanup→effect cycle and never re-asserted `true` → on DEV builds every action hung at pending (spinner forever) although the POST returned 200 with a perfect body | dev-server browser run: POST 200 (Valverde 0.91853) but `score-hero` never rendered | effect body re-asserts `mounted.current = true`; cleanup sets false | `useApi.test.tsx` StrictMode test |
| 4 | MEDIUM | `frontend/src/state/session.tsx` (`refreshUser`) | ANY `/api/auth/me` failure cleared the stored token. `/me` shares the strict 10 req/min auth limiter, so a hard-reload burst (dev StrictMode double-fetches `/me` per boot) silently logged valid users out — profile/dashboard rendered logged-out with a perfectly valid token | observed `GET /api/auth/me → 429` in server log immediately followed by logged-out UI; reproduced deterministically | token is only destroyed on a definitive **401**; 429/5xx/network keep the session | `frontend/src/state/session.test.tsx` (4 tests: 429/500 keep token, 401 clears, 200 populates) |
| 5 | LOW | `frontend/src/styles.css` (Squad Builder pitch) | Decorative pitch lines (`.pitch::before/::after`, `.midline`, `.circle`) painted over the GK/ST slot buttons and intercepted pointer events → GK slot unclickable in a real browser | Playwright click retry log: "`<div class="pitch">` intercepts pointer events" ×62 | `pointer-events: none` on all four decorative layers | browser audit slot-assignment check now passes on both origins |

Non-product issues also found & handled (classified for honesty):

- **Audit-script wrong expectations (2), patched:** (a) `POST /api/squads` returns the raw squad row — slots are created lazily and appear on `GET` (repo contract; script now asserts that); (b) `why_this` legitimately contains up to ~13 evidence lines including the "Not scored (weight redistributed, no penalty)" honesty note (script now requires the note, caps at 20 lines).
- **Auth rate-limit self-DoS during audit:** the audit suite itself can exhaust the 10/min auth window (each full page load fires a boot `/me`; dev StrictMode doubles it). 429s observed during audit are the security control working AS DESIGNED. Audit scripts now back off 62 s instead of failing the product.
- **Vite HMR config:** `SANDBOX_PREVIEW=1` forced HMR to `wss://…:443`, causing console-error storms for direct-localhost dev sessions. Now opt-in via `SANDBOX_PREVIEW_HMR=1` / `VITE_HMR_CLIENT_PORT`. Dev tooling only; never shipped in the production bundle.
- Playwright `install --with-deps` fails on Debian 13 (missing font packages); manual lib list + bare chromium install works (recorded for reproducibility).

---

## A. What is production-ready (verified by executed checks)

1. **Data foundation (FC26).** 16,228 real players from a CC0 1.0 Kaggle carrier of the official EA ratings page; 15,032 PlayStyle links; 36 tables; every count re-queried live (§2, 23/23). `MANIFEST.json` sha256 hashes re-computed and matched. `docs/DATASET_FORENSICS_FC26.md` figures all reproduce.
2. **Recommendation engine (deterministic, evidence-first).** 5 live scenarios with winner/score/component breakdown/confidence/why-this/alternatives (§9). Exact weights `0.15/0.30/0.15/0.15/0.15/0.10` echoed in `weights_used`. Determinism re-proven (two identical requests → identical rankings). "Not simply highest-OVR" proven: constrained CB winner Van Dijk (0.93872) emerges from a 6,324-candidate reordering, Salah wins RW/CROSSING on PlayStyle fit 1.0 despite not topping OVR-normalized quality. Pareto withholds `best_value`/`best_chemistry_fit` with explicit "prices UNKNOWN / chemistry unverified — withheld rather than fabricated" messages.
3. **FC26/FC27 version wall.** Airtight across search, player page, recommendations, compare, reference data and squads — FC27 returns honest `NO_DATA` 404s/callouts everywhere, zero FC26 leakage, zero fabrication (§5; browser-verified on both origins).
4. **Synthetic firewall.** 60 `is_synthetic` ut_cards are invisible to every production surface, blocked from saving, 0 non-`game_player` entities in top-50 rankings; visible only under the test entity scope (§6). `ut_card` total = 60 = synthetic count (no real cards fabricated).
5. **Auth & ownership.** Full lifecycle live: signup→me→preferences PATCH→logout-all server-side revocation→401 on revoked token; no user enumeration; cross-user reads of squads/saved return 404 (§7). JWT fail-fast in production without `JWT_SECRET` (failure #1 fix) proven by test.
6. **Security posture.** Security headers + HSTS, CORS closed by default, 413 over 1 MB, safe 500s with request IDs, SQLi attempts inert, auth 429 with `Retry-After` (burst produced `[201×10, 429]`), secret scan clean (§8, §15).
7. **Frontend, in a real browser.** All 13 routes + catch-all serve the SPA (200) on :8000 and :5173; full user journeys (search→player→recommend→evidence→FC27 wall→compare→signup→dashboard→saved→squad build→evaluate→profile→404) pass with **zero pageerrors and zero unexpected console errors** on both origins (§10, 21/21 × 2).
8. **Performance.** True cold start (fresh process): 1,256.9 ms for the 10,275-candidate constrained CM scenario; warm p50 494–581 ms; GK p50 83 ms; full 16,228-pool p50 749 ms; RSS 65 MB idle → 186 MB after first request → 575 MB after the whole sweep. All baseline winners/scores/counts reproduce exactly (§11, `benchmarks/reaudit_2026-09-14.json`).
9. **Idempotent DB setup.** `scripts/setup_database.py` re-run live: every file "skip (applied)", all counts unchanged; DROP only behind explicit `--reset` (§14).

## B. Partially verified

| Item | Verified | Not verified (why) |
|---|---|---|
| `deploy/Dockerfile` + `docker-compose.yml` | compose YAML parses (services `db`,`api`, volume `pgdata`); Dockerfile reviewed line-by-line (multi-stage, non-root uid 10001, healthcheck, gunicorn+uvicorn workers) | `docker build`/`docker compose up` — **docker not installed in this sandbox** |
| `deploy/eafc-api.service` (systemd) | `systemd-analyze verify` passes; only complaint is `/opt/eafc/venv/bin/python` absent — expected, the unit targets the deploy host; hardening directives present (`NoNewPrivileges`, `ProtectSystem=strict`, `PrivateTmp`, `ProtectHome`) | actual `systemctl start` on a provisioned host |
| `deploy/nginx.conf.example` | static review: SPA try_files, /api proxy, security headers, gzip, 1 MB client_max_body_size consistent with API 413 behavior | `nginx -t` — **nginx binary not installed in this sandbox** |
| Cold-start under fully-evicted caches | fresh-process cold measured (1,256.9 ms) | PostgreSQL shared-buffer cold (DB restarted) not measured — DB was warm from the whole audit |

## C. Blocked (environment, not product)

1. **Docker image build / compose up** — no docker daemon or CLI in sandbox.
2. **nginx config live test** — no nginx binary.
3. **systemd service live start** — unit references `/opt/eafc` provisioned paths that don't exist here (correctly so; `systemd-analyze verify` used instead).
4. **FC27 real data checks** — blocked by design/decision (no authorized source; wall verified instead).

## D. Next steps

1. On a deploy host: `docker compose -f deploy/docker-compose.yml up --build` and `nginx -t && systemctl start eafc-api` to discharge the three blocked items.
2. Consider exempting `GET /api/auth/me` from the 10/min *credential* limiter (or a separate higher budget): it is a session-read, not a credential attempt; heavy hard-reload traffic currently spends the auth budget (frontend now survives this — fix #4 — but users can appear logged-out until the next fetch).
3. Optional perf headroom: numpy-vectorize the ranking loop for the full-pool scenario (~0.75 s warm) before any traffic growth.
4. When an authorized FC27 source exists: ingest through the existing pipeline; the NO_DATA wall flips automatically per `game_version.status`.

## E. Risks

- **Data freshness:** FC26 snapshot scraped March 2026 (retrieved 2026-09-14); ratings/PlayStyles can drift with EA title updates. Mitigation in place: `data_freshness` + provenance surfaced on every player page and response; `source_observation` rows record retrieval context.
- **Single-worker capacity:** benchmarks are 1-worker numbers; the compose/unit files specify 2 workers × 4 threads — not load-tested here (no load generator run this audit).
- **Dev-only StrictMode double-fetch** doubles `/me` traffic in development; production builds fire once (verified). Harmless after fix #4, but dev sessions can trip the auth limiter.
- **Playwright browser pin:** audit used chromium-1140 (ubuntu20.04 fallback build on Debian 13); upgrade before relying on newer browser features.

## F. Exact commands to reproduce

```bash
cd /home/user/ea_fc_player_intelligence

# servers (already running during this audit)
ENVIRONMENT=production JWT_SECRET=<secret> FRONTEND_DIST=$PWD/frontend/dist \
  python3 -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000     # process: production-api-8cfa1a0f
cd frontend && SANDBOX_PREVIEW=1 VITE_API_TARGET=http://127.0.0.1:8000 npm run dev   # :5173

# tests / build
python3 -m pytest backend/tests -q                 # 161 passed
cd frontend && npx tsc --noEmit && npm run test    # 33 passed (5 files)
npm run build                                      # dist rebuilt (served from disk, no API restart needed)

# API/engine/security/auth/firewall audit (§4–§9) — needs a clean 10/min auth window; ~4.5 min
sleep 65 && python3 verification/post_build_verify.py http://127.0.0.1:8000   # 64/64

# real-browser audit (§10) — run from verification/ (node_modules symlink for playwright)
cd verification && node browser_verify.mjs http://localhost:8000   # 21/21
sleep 65 && node browser_verify.mjs http://localhost:5173          # 21/21 (dev origin)

# benchmarks (§11) — see benchmarks/reaudit_2026-09-14.json for the script output
# idempotency (§14)
python3 scripts/setup_database.py                  # all "skip (applied)", counts unchanged
```

## G. Exact results (this audit, live)

- `pytest backend/tests -q` → `161 passed, 3 warnings in 22.95s`
- `npm run test` → `Test Files 5 passed (5) / Tests 33 passed (33)`; `npx tsc --noEmit` → clean; `npm run build` → `✓ built`, dist `index-CAv4gPWQ.js` 260.82 kB (gzip 78.73 kB)
- `post_build_verify.py` final clean run → **`TOTAL: 64 checks | PASS 64 | FAIL 0`** (includes: auth lifecycle + logout-all revocation + no-enumeration; cross-user 404s; FC27 wall across 6 surfaces; synthetic firewall incl. 0 non-game_player in top-50; security headers/HSTS/CORS/413/429+Retry-After `[201×10, 429]`; SQLi inert; 5 engine scenarios — Valverde 0.95789 CM/PRESSING, Alisson 0.97973 GK, Mbappé 0.97775 ST/COUNTER, Van Dijk 0.93872 CB/POSSESSION, Salah 0.91362 RW/Whipped-Pass; pareto withholding; determinism exact)
- `browser_verify.mjs` :8000 → `BROWSER TOTAL: 21 checks | PASS 21 | FAIL 0`; :5173 → `PASS 21 | FAIL 0` (one 62 s auth-window backoff logged, then pass)
- Benchmarks: true cold CM 1256.9 ms (baseline 1483.9); warm p50 — CM-constrained 494.4–581.1 (baseline 674.5), ST 264.5 (318.5), GK 83.0 (107.1), full pool 748.8 (982.0); RSS idle 65.0 MB → 186.1 MB post-cold → 574.5 MB post-sweep; winners/scores/evaluated counts identical to baseline in all 4 scenarios
- DB re-queries: game_player FC26 = 16,228 · playstyle links = 15,032 · public tables = 36 · ut_card = 60 (all `is_synthetic`) — after `setup_database.py` re-run, unchanged
- §12 greps: zero `backend/tests` imports from production code; single engine file (`recommendation_engine_v2.py`); zero TODO/FIXME/HACK in prod code
- §13: `source_registry` live rows — EA official (tier 1), Kaggle CC0 carrier (tier 3, PRODUCTION), synthetic fixtures (SYNTHETIC_TEST), FUTBIN/FUT.GG/FUTWIZ/WeFUT (tier 4, legal_gate REQUIRED, "Not ingested. No access attempted."), market feed (NOT_PERMITTED); MANIFEST sha256 all match; no scraping HTTP calls anywhere in `backend/`/`scripts/`
- §15: only `deploy/.env.example` tracked (CHANGE_ME placeholders); no hardcoded-secret grep hits; production boot without `JWT_SECRET` fails fast

**Machine-readable per-claim status:** `POST_BUILD_VERIFICATION_STATUS.json`
