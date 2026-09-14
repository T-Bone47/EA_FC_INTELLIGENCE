# AUTONOMOUS_INITIAL_AUDIT.md
**Project:** EA FC Player Intelligence
**Audit date:** 2026-09-14 (Asia/Calcutta)
**Auditor:** Autonomous engineering agent (Arena.ai Agent Mode)

---

## 1. ENVIRONMENT & REPOSITORY STATE — GROUND TRUTH

### 1.1 What was actually found in the workspace

A complete filesystem inspection was performed **before any code was written**:

| Check | Result |
|---|---|
| Workspace root `/home/user` | Contained ONLY `uploads/EA_FC_Player_Intelligence_PROJECT_HANDOFF_v1.pdf` |
| Search for `*ea_fc*`, `*player_intelligence*`, `*fc26*` anywhere on disk | No project code found |
| Search for any `.zip` archives | Only `/tmp/arena-workspace/hydrate.zip`, which contains the same PDF (hash-identical) and nothing else |
| Existing backend / db / tests / data | **NOT PRESENT in this environment** |

**Conclusion:** The original archive `ea_fc_player_intelligence_LATEST(1).zip` (88 entries / 75 files) described in the
master prompt is **not present in this environment**. The only artifact provided is the 19-page handoff PDF, which was
explicitly prepared *"so a coding agent can continue development without requiring the original ZIP"* and whose
§16 Agent Continuation Contract states the agent *"should not require the original ZIP merely to understand the project
architecture and current status."*

### 1.2 Decision taken (per Autonomous Development Rules §41)

Reconstructing the project is the only non-blocked path, and the handoff document was purpose-built to authorize it.
Therefore this session proceeds as follows:

1. **Faithful reconstruction** of the documented architecture (module map §15, domain hierarchy §5, ingestion §6,
   engine V2 §7, API §8, schema §5.1, datasets §4) — same file layout, same components, same semantics.
2. **All mandated improvements baked in from the start** (production/test boundary §14, version-awareness §17,
   canonical `/api/recommendations` §24, auth §25, security §26, frontend §27).
3. **Real FC26 foundation re-acquired from the identified legitimate source** (see §3) instead of fabricated.
4. Every reconstruction-vs-original deviation is documented, not hidden.

> No original source file was deleted, because none existed here. Nothing was thrown away; the handoff contract is
> treated as the authoritative specification of the existing engine and architecture.

### 1.3 Runtime environment

| Component | Status |
|---|---|
| Python | 3.13.14 |
| Node / npm | v20.20.2 / 10.8.2 |
| PostgreSQL | 17 installed via apt during this session; cluster `17/main` **online** on port 5432 |
| CPU / RAM / Disk | 2 vCPU / 1.9 GB / ~20 GB free |
| Network | Available (pip, apt, Kaggle public download verified) |
| Docker | Not available in sandbox → deployment config will be written and validated statically, not executed |

---

## 2. ARCHITECTURE RECORDED BY THE HANDOFF (authoritative spec for reconstruction)

- **Domain hierarchy:** `RealPlayer → GamePlayer → UTCard → CardVersion` (+attributes, secondary positions,
  PlayStyles/PlayStyles+, Roles, chemistry, market observations, evidence/confidence/provenance, users/squads/feedback).
- **Database:** 29 base tables in `DATABASE_SCHEMA_V1.sql` + migrations (B1, B1-part2, goal1 attributes) + seed
  reference data. CardVersion is additive beneath UTCard with content-hash version IDs.
- **Ingestion:** provider-neutral `DataSourceAdapter` protocol (`fetch_players/fetch_cards/fetch_card/fetch_playstyles/
  fetch_prices/get_snapshot_metadata`), LocalFileAdapter implemented; EARatingsAdapter & UTMarketAdapter stubs;
  schema validation → normalization → identity resolution → deterministic ID/content-hash → canonical objects → Postgres;
  runtime legal/terms gate enforced at source registry + adapter init; idempotent re-ingestion.
- **Recommendation Engine V2:** deterministic; components `overall_quality, position_fit, attribute_fit, tactical_fit,
  playstyle_fit, role_fit, team_fit`; weights `0.15/—/0.30/0.15/0.15/0.15/0.10` (role_fit not in top-level weight
  table); `FitValue` with `KNOWN / UNKNOWN / INSUFFICIENT_EVIDENCE`; position-specific attribute weighting; tactical
  profiles `PACE_ABUSER, COUNTER_ATTACK, POSSESSION, DRIBBLE_HEAVY, PRESSING, CROSSING, LONG_SHOT, DIRECT_PLAY,
  BUILD_UP, BALANCED, CUSTOM`; tactical alignment floor; Pareto alternatives `best_overall, best_attribute_fit,
  best_tactical_alignment`; deterministic explanations; evidence-driven confidence; unknown components redistributed,
  never penalized as 0.
- **API (old state):** `POST /api/v1/recommendations`, `POST /api/v1/players/compare`, `GET /api/v1/health`,
  `GET /api/v1/players`, `POST /api/v2/recommendations` — V2 hardcoded FC26, candidates loaded through
  `backend/tests/real_data_loader.py` (production→test coupling, P0).
- **Tests:** ~20 modules; project-reported 124 passed / 96% coverage at Goal-1 stage.
- **Benchmarks (project-reported):** ~16,228 candidates in ~925.61 ms (~0.057 ms/candidate); to be re-measured here.

## 3. DATA AUDIT — REAL FC26 FOUNDATION RE-ACQUISITION

The handoff's foundation (16,228 players; 51 cols; position distribution CB 2,950 / ST 2,233 / CM 1,976 / GK 1,816 /
RB 1,273 / CDM 1,267 / LB 1,210 / LM 971 / CAM 963 / RM 902 / RW 338 / LW 329; PlayStyles 15,032 rows, 7,339 players,
36 styles, 14,913 base / 119 plus) was matched against legitimate public datasets.

**Identified source (exact match):** Kaggle `justdhia/ea-sports-fc-26-player-ratings` — *"Player ratings and attributes
for 16,228 players scraped from the official EA Sports FC 26 ratings page"*, license **CC0: Public Domain**.

Downloaded 2026-09-14 via Kaggle's public dataset download endpoint (HTTP 200, no auth bypass, no scraping of EA).
Forensics results:

| Check | Result |
|---|---|
| Rows | 16,228 combined = 14,412 outfield + 1,816 GK — **exact handoff match** |
| Duplicate ids | 0 |
| Duplicate (name, DOB) | 0 |
| Position distribution | **Exact handoff match on all 12 positions** |
| Unique PlayStyles | 36 (exact match); PlayStyle+ holders 119 (exact match); players with PlayStyles 7,335 (handoff said 7,339 — minor scrape-date drift, recorded honestly) |
| Rating range | OVR 47–91; facades PAC 30–97, SHO 21–92, PAS 25–92, DRI 29–93, DEF 15–90, PHY 32–91 |
| Nations / teams / leagues | 156 / 642 / 45 |
| Nulls | commonName 85.5% (normal), alternatePositions 35.4%, playStyles 54.8%, playStylesPlus 99.3% |
| PlayStyle+ ⊆ PlayStyles | TRUE for all rows |
| Game-version contamination | None (all FC26) |

### 3.1 Data-quality findings (materially affect normalization)

1. **GK facade mirroring artifact:** In `ea_fc26_players.csv` (combined), GK rows' `pac/sho/pas/dri/def/phy` values are
   mirrors of their GK attributes (verified: Donnarumma pac=90=gkDiving, sho=83=gkHandling, pas=70=gkKicking,
   dri=90=gkReflexes, phy=87=gkPositioning). These are EA's UI mapping, **not** outfield ability. Canonical foundation
   therefore stores for GK rows: OVR + 5 GK attributes (DIV/HAN/KIC/POS/REF); detailed outfield attributes = NULL/UNKNOWN.
2. **GK gap RESOLVED:** the handoff reported GK technical attributes missing from the foundation. This (newer, March-2026)
   scrape of the same official-EA-derived dataset **includes** `gkDiving/gkHandling/gkKicking/gkPositioning/gkReflexes`
   for all 1,816 GKs. GK support can be implemented on real data instead of UNKNOWN.
3. Outfield rows carry EA-published low GK stats (2–37, median 10). Real published values; retained with provenance but
   semantically unused for outfield fit.
4. Combined-file birthdates are US-locale (`6/15/1992 12:00:00 AM`); split files are ISO. Split files used as
   normalization base; ISO dates canonicalized.
5. This dataset covers the **men's** ratings universe (source-documented scope) → `gender='male'` is a source-stated
   fact, not a guess. Women's FC26 universe: NOT PRESENT — remains a documented data gap.

### 3.2 Licensing / usage status

- License: **CC0 1.0 (Public Domain)** → commercial use and redistribution permitted.
- Usage status: **PRODUCTION_DATA** (fields the source publishes), provenance recorded in `source_registry`.
- Chain of authority: dataset is a scrape of the official EA ratings page → Tier-3 carrier of Tier-1 (official EA)
  field values. Canonical field authority documented per-field in `docs/SOURCE_REGISTRY.md`.

### 3.3 Datasets that remain UNAVAILABLE (not fabricated)

| Data | Status |
|---|---|
| FC27 player records | NOT ACQUIRED. Handoff documents the official page requires JS execution / private endpoints — ruled out. Ingestion readiness built; data stays absent. |
| Real UT card universe (card variants, rarity, Roles, Evolutions) | NOT AVAILABLE. Only synthetic test fixtures (clearly labeled) exist. |
| Live market prices | NOT AVAILABLE → `NullBudgetProvider`, price = UNKNOWN. |
| Operational chemistry rules data | NOT VERIFIED → team_fit returns UNKNOWN unless squad context provides verifiable links. |
| Women's FC26 ratings | NOT IN SOURCE → UNKNOWN. |

## 4. COMPONENT STATUS MATRIX (post-reconstruction targets for this session)

| Component | Handoff state | This session's target |
|---|---|---|
| Domain models | Present | Reconstruct + version-aware |
| Engine V2 | Present, FC26-hardcoded in API path | Reconstruct + `game_version` first-class |
| Ingestion | Present w/ legal gate | Reconstruct + FC26 load executed on Postgres |
| Production boundary | **VIOLATED** (API imports `tests/real_data_loader`) | FIXED: `backend/data_access/` production loader; tests depend on production code only |
| Database | Postgres schema present | Reconstructed + migrated + loaded; additive auth/squad tables |
| API | 5 routes, V1 demo behavior | Canonical `/api/*` surface; V1 demo paths removed (technical reason: §24 mandate) |
| Auth | **None** | Implemented (bcrypt + JWT + sessions + ownership) |
| Security | Basic | Validation, CORS, rate limiting, safe errors, headers, secret handling |
| Frontend | **None** | Built (React/Vite/TS, served by API) — 13 screens |
| Tests | ~20 modules | Reconstructed + expanded (auth, security, versioning, search, squads, e2e) |
| Benchmarks | Reported | Re-measured in this environment |
| Deployment | None | Dockerfile/compose/.env.example/DEPLOYMENT.md |

## 5. PRODUCTION / DATA / SECURITY BLOCKERS

1. **FC27 data** — external blocker; mitigated by version-aware architecture + ingestion readiness (roadmap §42: do not stall).
2. **Real UT cards / market / chemistry / Roles** — external; UNKNOWN-by-design handling implemented.
3. **No Docker in sandbox** — deployment artifacts written + compose config validated statically; cannot execute image builds here.
4. **Secrets** — none exist yet; `.env.example` + generated dev secrets excluded from git; no secret committed at any point.

## 6. RECOMMENDED EXECUTION ORDER (adopted)

A) Audit (this document) → B) Data normalization + forensics artifacts → C) DB schema + Postgres setup →
D) Domain + Engine V2 (version-aware) + unit tests → E) Ingestion pipeline + FC26 load → F) Production data access +
repositories → G) Auth + security → H) Canonical API surface → I) Search/players/cards/compare/squads/feedback →
J) Frontend → K) Integration/E2E tests + benchmarks → L) Deployment config → M) Final report + machine-readable status.
