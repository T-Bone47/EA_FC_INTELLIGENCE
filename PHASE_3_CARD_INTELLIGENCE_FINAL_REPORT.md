# PHASE 3 — REAL FUT CARD INTELLIGENCE · FINAL REPORT

**Date:** 2026-09-14 · **Engine:** v2.1.0 → **v2.2.0** (evolved in place) ·
**Status:** COMPLETE — architecture + pipeline delivered; production card data
**BLOCKED externally** (no legally permitted source; system is DATA-READY).

---

## 1. Executive summary

The verified v2.1 player-intelligence engine was upgraded to production-grade
**UT CARD intelligence** without creating Engine V3, a parallel engine, or
replacing `recommendation_engine_v2.py` (§0). One latent §5 correctness
violation was found and fixed (card candidates silently inheriting base-player
attributes/PlayStyles). The full card data model, ingestion pipeline,
forensics, one-command activation, identity resolution, value/chemistry/role
architecture, additive API and premium card UI are live. Real FC26 card data
could **not** be acquired legally: EA discontinued the official FUT database
(404), community trackers are ToS-prohibited, commercial APIs are paywalled
with unverified provenance, and the two Kaggle card datasets are artwork
images / GPL-3 player ratings. Every source's license/permission status is
researched, recorded in `source_registry` and documented. All 338 backend +
41 frontend tests pass; goldens S1–S8 + FC27 wall bit-identical; 64/64
post-build verification.

## 2. Pre-build audit (what existed)

Card schema (§14–§20 + migration 002), ingestion pipeline with legal gate,
normalizer with deterministic ids + content-hashed versions, validators,
identity resolver, staging-table repository, synthetic firewall, 60
SYNTHETIC_TEST fixture cards. Missing: card loading as candidates, card
roles/evolutions/meta/ingestion-audit tables, canonical identity layer,
value/chemistry services, card API surface, card UI — and `from_ut_card`
violated §5.

## 3. §5 fix — card attribute separation (correctness)

`Candidate.from_ut_card` now uses **card-published attributes only**;
unpublished attributes are UNKNOWN (never base-player values). PlayStyles are
used only when `playstyle_data_published`; base-player PlayStyles are never
inherited. The base GamePlayer contributes only labelled link facts
(nation/club/league/secondary positions; `extra.secondary_positions_source`).
Proof: `test_card_model.py::TestCardAttributeSeparation` (9 tests) +
`test_card_scenarios.py` engine-level evidence assertions (PAC95 card over
PAC84 base scores with 95; base-only FIN85 stays UNKNOWN).

## 4. Schema — migration `005_card_intelligence.sql` (additive, applied)

New: `ut_card_role`, `card_evolution`, `card_availability`, `chemistry_rule`,
`meta_signal`, `ingestion_run`, `ingestion_quarantine`. Extended: `ut_card`
(canonical_card_id unique-per-version, card_type, rarity_raw, release_date,
valid_from/to, identity_status/rule, playstyle_data_published), `card_price`
(source_id, currency, validity window, source_authority),
`ut_card_playstyle` (observation provenance). Indexes (§49/§50): partial
production-filtered position/OVR indexes, trigram name search, canonical-id
unique partial, price time-series, version/updated-at watermarks, join paths.
No destructive change; setup idempotent via `schema_migrations`.

## 5. Card identity (§4)

Two layers, both deterministic: row id
`uuid5(NS,"ut_card|source|version|source_card_id")` and canonical id
`uuid5(NS,"canonical_card|VERSION|player_key|kind|POSITION|release_group")`
(kind = card_type → rarity → BASE). Never name+OVR. Cross-source same-card
collapse, promo/base distinction, FC26↔FC27 collision impossibility, and
duplicate-idempotency all unit-tested. No stable player reference ⇒
`UNRESOLVED` with NULL canonical id — identity is never guessed from names.
Missing `source_card_id` now **rejected at normalization** (was: silently
derived from None — fixed).

## 6. Entity scopes & retrieval (§11/§49)

`CandidateRepository.load_cards()` loads production cards (current
`card_version` attributes via LATERAL join, latest verified price via LATERAL
join, batched playstyle/role lookups — no N+1). `entity_scope=ut_card` →
card pool; `auto/game_player` → player pool; scopes never mix silently; empty
scope → honest 404-style refusal (unchanged message, goldens safe). Mixed
player+card comparisons carry an explicit `scope_note` (§12).

## 7. Watermarks & caching (§28/§31)

Card cache namespace with its **own** watermark covering
cards×versions×prices(observed_at,count)×verified-chemistry-rules — price or
rule updates invalidate immediately (never stale). Player watermark
untouched. Cache keys include game_version + scope; TTL 120 s; `invalidate()`
wired into activation. Poisoning protection: only pipeline-written rows pass
the firewall into caches; synthetic rows can never enter production reads.

## 8. Value & prices (§13/§14/§48)

`card_value_service`: verified-price status (present + provenance), freshness
FRESH ≤14 d / AGING ≤60 d / STALE, budget statuses
WITHIN/OVER/**BUDGET_UNVERIFIED** (never silently "affordable"),
`value = (utility − pool floor) / (price / 1 000 000)` — marginal contextual
utility per verified cost, all tunables in `engine_config.py`, OVR is not an
input. `price_history` returns only persisted observations; empty →
`NO_PRICE_HISTORY` + explicit note (never manufactured). Production prices
today: **0** (no permitted feed) ⇒ every value answer is honestly
VALUE_UNAVAILABLE.

## 9. Chemistry (§15/§16)

`chemistry_service`: structural fit (factual club/league/nation links,
labelled `is_chemistry: false`) is strictly separate from chemistry score,
which computes **only** from `chemistry_rule` rows with `verified=TRUE`.
FC26 has zero verified rules ⇒ `CHEMISTRY_UNKNOWN` everywhere; no fake
chemistry was implemented to demo squad features. Rule application is
data-driven (contributions/thresholds/caps come from rule rows) and
test-proven via injection. `squad_impact` answers buy/replace questions from
real contextual utility deltas; unknown chemistry is never counted for or
against.

## 10. Roles (§9)

`ut_card_role` + `role_fit_service` extension: card-published familiarity
maps through configurable `CARD_ROLE_FAMILIARITY_SCORES` (ROLE+ 1.0 / ROLE
0.75 / UNFAMILIAR 0.15) **for the requested role only** — no generic "has
roles" bonus; cards publishing other roles get INSUFFICIENT_EVIDENCE for a
non-listed role; no role data ⇒ INSUFFICIENT. Archetypes remain a separate
engine-derived concept; both are kept.

## 11. Evolutions (§8)

`card_evolution` stores base→evolution→result with requirements, attribute/
playstyle/position/role changes, eligibility, validity window and provenance.
No FC26 evolution data ingested ⇒ NO_DATA at `/api/card-data-status`; no
evolution rules invented anywhere in the engine.

## 12. Meta signals (§18/§19)

`meta_signal` table + `backend/ingestion/meta_signals.py` (schema/adapters
first). Hard firewall by construction: no code path to canonical tables;
vocabulary-constrained signal types; strength/sample_size NULL-when-unpublished
(never 0); non-permitted sources store RESEARCH_ONLY; read path always labels
`kind: META_SIGNAL, is_canonical: false`; rejected rows quarantined. Separate
`meta_watermark`. No meta source adopted.

## 13. Ingestion governance (§23/§26/§27)

* **Forensics** `ingestion/forensics.py`: duplicates, identity coverage,
  version contamination, impossible ratings, position/PlayStyle vocabulary,
  PS+ cap, price sign, timestamp staleness → PASS/REVIEW/REJECT + markdown.
  Report: `DATASET_FORENSICS_REPORT.md` (adopted CC0 player files: REVIEW —
  no timestamp column, freshness UNKNOWN; fixtures: REVIEW by design).
* **Run tracking** `ingestion_run` + `ingestion_quarantine` with stage machine
  RAW→STAGING→VALIDATED→PRODUCTION/FAILED/ROLLED_BACK.
* **One command** `scripts/activate_card_dataset.py`: legal gate → forensics
  (REJECT aborts) → run record → normalize/validate → quarantine → atomic
  promote (single transaction) → watermark → cache invalidate → integrity
  (synthetic-in-production=0, cross-version leak=0, single current version per
  card, prices provenance-linked) → golden regression → JSON report. Refuses
  non-OFFICIAL/AUTHORIZED/LICENSED sources; `--dry-run` for research.
  Verified live: dry-run of fixtures = 60 staged / 3 rejected exactly as
  documented; full activation of the synthetic source correctly REFUSED.

## 14. Source research & legal firewall (§22/§54) — full table in
`docs/CARD_DATA_ACQUISITION.md`; persisted via
`scripts/register_card_sources.py` into `source_registry`:

| source | verdict |
|---|---|
| EA official FUT database | discontinued (404) — UNKNOWN, gate REQUIRED |
| EA ratings pages | base players only; player mirror (CC0 Kaggle) already adopted; no cards |
| Kaggle flynn28 player DB (GPL-3) | RESEARCH_ONLY |
| Kaggle flynn28 rating-card images (CC BY claim over EA art) | RESEARCH_ONLY (not structured data) |
| FUTBIN / FUTWIZ / FUT.GG / WeFUT | NOT_PERMITTED (ToS + private API) |
| futdatabase.com / futdb.app | UNKNOWN — paid, ToS/provenance unverified; human decision required |
| ut_market_feed | NOT_PERMITTED (no contracted feed exists) |
| synthetic_fixtures | SYNTHETIC_TEST — firewalled, test-only |

## 15. Data acquired (Part B outcome)

**Players (pre-existing):** 16,228 FC26 game_players (CC0). **Cards: 0
production rows** — no permitted source exists; 63 synthetic fixture rows
remain firewalled (60 valid + 3 intentional rejects for the validator).
**Prices: 60 synthetic-fixture observations only (firewalled); 0 production.**
No scraping, no ToS circumvention, no private-API access was performed or
will be. Blockers are external and precisely documented (§14 + docs).

## 16. Version firewall & FC27 (§25/§27)

FC26 data can never become FC27: normalizer raises on version contamination,
repository blocks cross-version upserts, canonical ids embed the version,
FC27 requests still hit the honest 404 NO_DATA wall (golden `FC27_wall`
bit-identical). FC27 card activation = same one command
(`--game-version FC27`) once a permitted dataset exists: validate →
provenance → identity → normalize → dedupe → conflict → quarantine → staging
→ promote → watermarks → caches → regression → integrity → report, atomic.

## 17. Precomputed features (§29)

Per-candidate `feature_cache` (archetype scores/vectors, dominant archetype,
gameplay profile, versatility, interaction features, entity data confidence)
+ memoized normalized weight tables. All non-user-specific; all pure; sharing
is mutation-safe (consumers read-only; dict results copied).

## 18. Performance (§30) — `benchmarks/ENGINE_BENCHMARKS.md` §7

Players (16,228 pool, warm, min-of-N, ±15 % machine noise): intelligence CM
854–863 → **779–806 ms**; full pool 787–880 → **792–841 ms**; archetype ST
**287–301 ms**. 10K-warm target <1000 ms **met**; preferred <500 ms not met
on this sandbox CPU (documented; correctness never traded for speed). Cards
(in-memory pools, full intelligence layers): 1K **55 ms**, 5K **284 ms**,
10K **633 ms** warm. `load_cards` DB path: 34 ms cold / 1.4 ms cached (60
rows, batched — scales via indexes/push-down, no N+1).

## 19. API changes (§41, additive only)

`GET /api/cards` (filter: q/position/rarity/card_type/playstyle/ovr range/
price_max; sort; pagination ≤100), `GET /api/cards/{id}/versions`,
`GET /api/cards/{id}/prices`, `GET /api/cards/{id}/value`,
`GET /api/card-data-status`. Pre-existing `GET /api/cards/{card_id}` and
`POST /api/compare` (now card-capable) untouched — no duplicate endpoints.
Card-scope recommendation payloads add `card_value`, `card_counterfactuals`,
`chemistry`, Pareto `best_value`/`best_within_budget` (with `unavailable`
explanations). Legacy payload keys unchanged (goldens prove it); version
string bumped to 2.2.0 in ENGINE_CHANGELOG.

## 20. Frontend (§42–§44)

`/cards` discovery (honest NO_DATA empty state, verified-price-only price
filter note, `DataQualityPanel` with availability pills) and premium
`/cards/:id` page: identity block (row/canonical id, identity status,
source + row id), card-level attributes with UNKNOWN hatching (never
base-player values), PlayStyle base/+ tiers with publication honesty,
version history, price + history (NO_PRICE_HISTORY note), base-player link
with the link-facts-only disclaimer, chemistry disclaimer. UNKNOWN renders
as UNKNOWN everywhere. Nav entry "Cards". `tsc --noEmit` clean; built bundle
served live.

## 21. Explanations & counterfactuals (§34/§35)

Existing explanation service unchanged (names concrete differentiators).
Card-scope adds `card_counterfactuals`: +100K budget (or honest "never
enforceable" when BUDGET_UNVERIFIED), top card without its PlayStyle+ (tests
whether context or the + drives the fit), alternate position, removal of up
to 3 squad members (full re-recommendation), and the chemistry variant which
answers "cannot be computed — inventing a chemistry effect is prohibited".

## 22. No-hallucination hard tests (§45)

`test_card_scenarios.py::TestNoHallucinationHard` + chemistry/value tests:
with unknown price/chemistry/roles the full engine payload contains no
"affordable"/"within budget"/"good chemistry"/"excellent fit" claims; budget
decisions are None; role_fit is UNKNOWN/INSUFFICIENT with null value; value
is VALUE_UNAVAILABLE with reason. Frontend: DataQualityPanel tests assert
NO_DATA rendering and "nothing is fabricated" notice.

## 23. Adversarial & conflict tests (§39/§46)

Duplicates (normalizer idempotency, DB unique constraints), missing fields
(UNKNOWN, never 0 — parametrized), malformed ids (rejected), wrong version
(candidate rejection + normalizer contamination raise), authority conflicts
(tier wins; recency never beats authority; field-canonical beats tier;
equal-tier logged with deterministic pick; NOT_PERMITTED claims ignored),
randomized 1,200-card pool order (identical ranking), synthetic reaching
engine (hard abort). Full-suite: **338 backend passed, 41 frontend passed**.

## 24. Regression & verification (§56/§57)

* Goldens: `scripts/verify_goldens.py` (new permanent gate) — S1–S8 +
  FC27 wall **bit-identical** after every change (run 4× during the phase).
* `verification/post_build_verify.py`: **64/64 PASS** (security, firewall,
  engine, pareto honesty, determinism).
* Live production API restarted (uvicorn :8000, ENVIRONMENT=production,
  rebuilt SPA): new endpoints verified live (`/api/cards` → honest empty,
  `/api/card-data-status` → NO_DATA availability map, ut_card scope → 404),
  legacy rec/compare → 200 unchanged.
* **Documented limitation:** Docker/nginx/systemd deployment artifacts exist
  under `deploy/` but cannot be executed in this sandbox (no Docker daemon /
  no systemd); verification covered the live uvicorn production-mode process
  instead, including security headers/HSTS/CORS checks via post_build_verify.

## 25. Deliverables, limitations & next phase

**Docs (§58):** `docs/CARD_INTELLIGENCE.md`, `CARD_DATA_MODEL.md`,
`CARD_IDENTITY.md`, `CARD_DATA_ACQUISITION.md`, `CARD_PROVENANCE.md`,
`CARD_SCORING.md`, `CARD_CHEMISTRY.md`, `CARD_MARKET.md`,
`DATASET_FORENSICS_REPORT.md` (root) + updated `ENGINE_CHANGELOG.md` (2.2.0),
`ENGINE_DATA_REQUIREMENTS.md`, `INTELLIGENCE_ENGINE_ARCHITECTURE.md`,
`benchmarks/ENGINE_BENCHMARKS.md` §7. Machine-readable status:
`PHASE_3_DATA_STATUS.json`.

**Files changed (code):** `backend/domain/card_model.py`,
`backend/data_access/candidate_repository.py`,
`backend/repositories/{postgres_canonical_repository,player_repository}.py`,
`backend/ingestion/{normalizer,local_file_adapter,forensics*,run_tracker*,meta_signals*}.py`,
`backend/services/{recommendation_service,comparison_service,chemistry_service*,card_value_service*,role_fit_service,counterfactual,archetypes,attribute_model,confidence_service,scoring_config,engine_config}.py`,
`backend/api/{main.py,routes/cards*}`, `frontend/src/{App.tsx,api/types.ts,
components/{Nav,DataQuality*}.tsx,pages/{Cards*,CardPage*}.tsx}`,
`db/migrations/005_card_intelligence.sql`,
`scripts/{activate_card_dataset*,register_card_sources*,verify_goldens*}.py`,
tests: `test_card_{model,value_chemistry,scenarios,api,ingestion_phase3}.py`,
`frontend/src/components/DataQuality.test.tsx` (* = new file).

**Limitations (external):** no permitted FC26 card/price/chemistry/evolution
data (blockers §14–§15); commercial API evaluation needs human
payment/ToS decisions; preferred <500 ms perf target unmet on sandbox CPU.

**Next phase readiness:** onboarding a cleared source requires only:
registry clearance (human) → adapter subclass (if not CSV) →
`activate_card_dataset.py`. Engine, API and UI need no changes; card
intelligence switches on with the data.
