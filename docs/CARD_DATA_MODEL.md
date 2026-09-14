# CARD DATA MODEL — Phase 3

Schema sources: `db/DATABASE_SCHEMA_V1.sql` §14–§20, `db/migrations/002_card_version.sql`,
`db/migrations/005_card_intelligence.sql` (Phase 3, additive only).

## 1. Tables

| table | purpose | key fields / constraints |
|---|---|---|
| `card_rarity` | version-scoped rarity reference (§7) | UNIQUE(game_version_id, rarity_code); data-driven, `is_promo` flag |
| `ut_card` | the card entity | UNIQUE(source_id, source_card_id, game_version_id); firewall `is_synthetic` + `data_status`; Phase 3 adds `canonical_card_id` (UNIQUE per version when set), `card_type`, `rarity_raw`, `release_date`, `release_group`, `valid_from/valid_to`, `identity_status` (RESOLVED/REVIEW_REQUIRED/UNRESOLVED), `identity_rule`, `playstyle_data_published` |
| `ut_card_attribute_override` | live card attributes | UNIQUE(ut_card_id, attribute_code); value CHECK 1–99 |
| `ut_card_playstyle` | card PlayStyles | tier CHECK base|plus; Phase 3 adds observation provenance |
| `ut_card_role` (§9, new) | card-level Roles | role_name + familiarity (ROLE/ROLE_PLUS/UNFAMILIAR), is_primary; UNIQUE(ut_card_id, role_name) |
| `playstyle_plus_cap` | version PS+ cap | scope player_base|card; FC26 card cap = 1 when published |
| `card_version` (002) | content-addressed versions (§3) | content_hash, JSONB attributes/playstyles, version_number, valid_from/valid_to, is_current; UNIQUE(ut_card_id, content_hash) ⇒ idempotent re-ingest; new content closes the previous current version (history, never overwrite) |
| `card_evolution` (§8, new) | base→evolution→result | requirements/attribute_changes/playstyle_changes/position_changes/role_changes/eligibility JSONB; UNIQUE(source_id, source_evolution_id, game_version_id) |
| `card_availability` (new) | pack/SBC/objective/market | `available` nullable — NULL = UNKNOWN, never default FALSE |
| `card_price` (§13) | market observations | price_coins nullable (NULL = UNKNOWN, never 0); platform; observed_at; source_observation_id; confidence; Phase 3 adds source_id, currency, valid_from/valid_to, source_authority |
| `chemistry_rule` (§15, new) | verified rules only | `verified` boolean — unverified rules never score; UNIQUE(game_version_id, rule_code) |
| `meta_signal` (§18/§19, new) | perception firewall | signal_type vocabulary-constrained; signal_strength/sample_size nullable (UNKNOWN, never 0); data_status CANONICAL/RESEARCH_ONLY/… |
| `ingestion_run` (§26/§27, new) | activation audit | stage RAW→STAGING→VALIDATED→PRODUCTION/FAILED/ROLLED_BACK; counts; activation_status; full report JSONB |
| `ingestion_quarantine` (new) | rejected rows | reason + raw payload retained — never silently dropped or fixed |
| `source_observation` | provenance anchor | every flush records one; prices/versions point at it |

## 2. Indexes (§49/§50)

Production-filtered partials: `ix_utcard_prod`, `ix_utcard_pos`,
`ix_utcard_ovr` (all `WHERE is_synthetic = FALSE`); lookup:
`ix_utcard_player`, `ix_utcard_rarity`, `ix_utcard_name_trgm` (GIN trigram),
`ux_utcard_canonical` (unique partial), `ix_utcard_identity`; time series:
`ix_card_price_time (ut_card_id, observed_at DESC)`, `ix_card_price_observed`;
joins: `ix_utcard_playstyle`, `ix_cardversion_card`, `ix_gp_updated`,
`ix_utcard_updated`, `ix_gp_club`. Card list/detail queries are fully
pushed-down (filters, sorting, pagination in SQL; LATERAL latest-price /
current-version joins) — no N+1: one paged query + two batched `ANY(ids)`
lookups per card-pool load.

## 3. Domain objects (`backend/domain/card_model.py`)

* `UTCard` — deterministic row id `uuid5(NS, "ut_card|source|version|source_card_id")`;
  canonical id rule in `docs/CARD_IDENTITY.md`.
* `CardVersion` — `content_hash = sha256(sorted JSON of {ovr, attributes, playstyles})`;
  identical content ⇒ idempotent no-op.
* `Candidate.from_ut_card(card, gp=None)` — §5 separation contract (see
  `docs/CARD_SCORING.md` §2); every value's origin is labelled in `extra`.

## 4. Statuses

`data_status`: CANONICAL / PENDING_REVIEW / SYNTHETIC_TEST / REJECTED.
Synthetic firewall: production reads filter `is_synthetic = FALSE` **and**
`data_status <> 'SYNTHETIC_TEST'`; the engine aborts scoring if a
SYNTHETIC_TEST candidate ever reaches it (tested).
