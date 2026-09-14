# CARD DATA ACQUISITION — Phase 3 (§21/§22/§24/§54)

**Bottom line:** after documented research (2026-09-14), **no legally
permitted source of structured FC26 UT promo-card data (attributes,
PlayStyles, Roles, evolutions, prices) was found**. The complete pipeline,
adapters, validators, provenance, identity resolution and activation tooling
are built and DATA-READY; production card data activates the moment a
permitted source is cleared. Availability ≠ permission.

## 1. Source research table (§22)

Every row is persisted in `source_registry` (see
`scripts/register_card_sources.py`); `legal_gate=REQUIRED` blocks fetching
until a human clears it.

| source | what it offers | license / terms | permission verdict | status |
|---|---|---|---|---|
| **EA official FUT database** (ea.com/…/fut/database) | historically: full card DB downloads | EA proprietary | URL **404 — discontinued after FIFA 23**. Current EA ratings pages publish BASE player ratings only, are JS-gated, and carry no card/promo/price feed | `UNKNOWN` (no accessible official card source) |
| **EA official ratings page** (ea.com/games/ea-sports-fc/ratings) | base player ratings | EA terms; no redistribution licence for bulk data | already used indirectly via the CC0 Kaggle mirror for PLAYERS; contains **no UT card data** | players: `LICENSED`/cleared (justdhia mirror); cards: n/a |
| **Kaggle justdhia/ea-sports-fc-26-player-ratings** | 16,228 player ratings (adopted player source) | **CC0 1.0** | ADOPTED (players only — no cards) | `LICENSED`, gate `CLEARED` |
| **Kaggle flynn28/eafc26-player-database** | player ratings incl. play styles + "card" column; api.msmc.cc | **GPL-3** compilation of scraped EA data | overlaps adopted player set; adds no verified promo-card data; GPL obligations + scraped upstream ⇒ research only | `RESEARCH_ONLY` |
| **Kaggle flynn28/complete-ea-fc26-rating-cards-database** | 17,873 card **artwork images** (.webp, 593 MB) | "CC BY 4.0" claimed by uploader over EA-copyrighted art | images, not structured data; uploader's licence claim is legally doubtful; OCR-ing artwork would be fabrication-adjacent | `RESEARCH_ONLY` (rarity/card-type vocabulary reference only) |
| **FUTBIN / FUTWIZ / FUT.GG / WeFUT** | complete card DBs + prices | ToS **prohibit scraping**; data originates from EA's private web-app API | unauthorized on both layers (ToS + private API) | `NOT_PERMITTED` |
| **futdatabase.com (FutDB)** | FC26 players/prices/card-types JSON API | proprietary ToS not reviewed; "free" tier is a funnel — stats+prices require ~€79/month; provenance unstated (likely private-API crawls) | payment + ToS review + provenance are human decisions | `UNKNOWN`, gate `REQUIRED` |
| **futdb.app** | third-party FUT API | terms/provenance unverifiable without registration | availability ≠ permission | `UNKNOWN`, gate `REQUIRED` |
| **ut_market_feed** (placeholder) | hypothetical licensed market feed | none identified | — | `NOT_PERMITTED` until a real feed is contracted |
| **synthetic_fixtures** | 63 fictional test cards | project-owned | test-only, firewalled | `SYNTHETIC_TEST`, gate `NOT_REQUIRED` |

## 2. Blockers (exact)

1. **No official machine-accessible card source** — EA discontinued the
   public FUT database; ratings pages are JS-gated and base-player only.
2. **Community card DBs are ToS-prohibited** — ingestion would require
   scraping against explicit terms and/or EA's private API. Never done.
3. **Commercial APIs (FutDB et al.)** — require payment, ToS acceptance and
   provenance verification: human decisions by policy (§60 stop-rule:
   "required human decision / legal restriction").
4. **Market prices** — no permitted feed; every price stays UNKNOWN, budget
   checks stay BUDGET_UNVERIFIED, value stays VALUE_UNAVAILABLE. Historical
   prices are never manufactured (§48).

## 3. What IS ready (build-around-the-blocker)

* Ingestion: `BaseAdapter` legal gate → `LocalFileAdapter` (CSV) →
  `Normalizer` (version firewall, deterministic + canonical ids, PS
  publication flags, content-hashed versions) → `DataQualityValidator`
  (REJECT/REVIEW rules incl. PS+ cap) → `PostgresCanonicalRepository`
  (staging temp tables, atomic flush, version-contamination block,
  observations + prices).
* Forensics: `backend/ingestion/forensics.py` + `DATASET_FORENSICS_REPORT.md`
  (§23) — mandatory pre-import analysis; REJECT verdicts abort activation.
* Activation: `scripts/activate_card_dataset.py` — one command, full chain
  (§26/§27), refuses non-permitted sources, quarantines rejects, integrity +
  golden regression gates, writes an auditable `ingestion_run` row.
* Meta signals: `backend/ingestion/meta_signals.py` (§18/§19) — schema +
  storage adapter first, hard-firewalled from canonical tables.
* A new source onboards as: registry row (license/permission research) →
  adapter (subclass `BaseAdapter`) → dry-run forensics → human clearance →
  `activate_card_dataset.py`. No engine changes required.

## 4. Re-check policy

Sources are re-checked each EA title update / promo wave. Any status change
must be recorded in `source_registry.notes` with a date, and only a human may
flip `legal_gate` to CLEARED (`cleared_by`, `cleared_at` are persisted).
