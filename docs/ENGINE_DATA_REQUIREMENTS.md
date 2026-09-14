# ENGINE DATA REQUIREMENTS (v2.2.0)

What each intelligence layer consumes, what exists today, and what stays
UNKNOWN. Rule: missing data is never fabricated, never zero, never assumed —
the affected layer reports UNKNOWN/INSUFFICIENT_EVIDENCE and the response says
so (§18/§19).

## 1. Status by layer (FC26 — live)

| layer | required data | status | when missing |
|---|---|---|---|
| retrieval | `game_player` + attributes (16,228 rows, CC0 Kaggle snapshot of EA official ratings, tier-3 LICENSED) | AVAILABLE | empty pool → honest empty result |
| position/slot eligibility | positions, secondary positions, formation slots | AVAILABLE (11 formations built-in) | unknown position → position_fit UNKNOWN |
| attribute fit | 39 attributes per player | AVAILABLE | per-attribute UNKNOWN excluded, coverage gate 0.5 → INSUFFICIENT |
| tactical fit | tactical dimension tables (config, expert priors) | AVAILABLE (config-side) | combo with no demand → UNKNOWN |
| playstyle fit | 36 PlayStyles incl. base/plus tiers, published flag | AVAILABLE | unpublished → INSUFFICIENT (never "no playstyles") |
| role fit | `role_definition` + familiarity | **NOT VERIFIED for FC26** (table empty; EA role data not ingested) | UNKNOWN/INSUFFICIENT — never 0 |
| archetype fit | attributes + playstyles (computed) | AVAILABLE (derived) | thin data → INSUFFICIENT |
| squad structural | user squad slots + club/league/nation links | AVAILABLE (link facts) | unresolvable slot → skipped and reported |
| chemistry | verified EA chemistry rules | **WITHHELD — rules unverified (§22)** | team_fit INSUFFICIENT + explicit note |
| budget/value | verified market prices (`card_price`) | **UNAVAILABLE — no permitted feed** | BUDGET_UNVERIFIED; never assumed affordable |
| card-level (Phase 3 §3) | `ut_card` canonical rows + `card_version` + card attributes/PlayStyles/Roles | **PIPELINE READY, NO PRODUCTION CARD DATA** (63 SYNTHETIC_TEST fixtures firewalled; no legally permitted FC26 card source found — `docs/CARD_DATA_ACQUISITION.md`) | entity_scope=ut_card → explicit 404 refusal; `/api/cards` returns an empty list with data status |
| card identity (§4) | source_card_id + canonical id inputs (player ref, card type, position, release group) | ARCHITECTURE READY | no player ref ⇒ identity UNRESOLVED, canonical_card_id NULL — never guessed from names |
| card roles (§9) | `ut_card_role` familiarity rows | ARCHITECTURE READY (table empty) | role_fit INSUFFICIENT_EVIDENCE — never a generic "has roles" bonus |
| card evolutions (§8) | `card_evolution` rows from an authorized source | ARCHITECTURE READY (table empty) | evolution status NO_DATA; no rules invented |
| card prices (§13/§14) | `card_price` observations w/ provenance | ARCHITECTURE READY (0 production rows) | price UNKNOWN; VALUE_UNAVAILABLE; BUDGET_UNVERIFIED; history never manufactured |
| chemistry rules (§15) | `chemistry_rule` verified=TRUE | ARCHITECTURE READY (0 rows) | CHEMISTRY_UNKNOWN; only structural fit reported, labelled as not-chemistry |
| meta signals (§18/§19) | cleared meta source + `meta_signal` rows | ARCHITECTURE READY (0 rows, firewalled module) | no meta claims anywhere |
| ingestion audit (§26/§27) | `ingestion_run` + `ingestion_quarantine` | AVAILABLE (tables live; used by `activate_card_dataset.py`) | runs recorded; rejects quarantined with raw payload |
| confidence v2 | source_observation timestamps, source_registry tiers, identity_status, attribute_conflict_log | AVAILABLE | inputs renormalize out |
| gameplay profile / versatility | attributes (+ slots) | AVAILABLE (ENGINE-DERIVED) | label skipped when any input UNKNOWN |

## 2. FC27 readiness (§61)

The engine is FC27-ready **with zero data**: version config exists
(status NO_DATA), requests return a 404 wall explaining that nothing was
ingested and nothing was fabricated, and no FC26 value is ever substituted.
Tested live and in `test_engine_unknown_data.py`.

To activate FC27 intelligence, ingest in this order (each record with
`game_version` + provenance + confidence):
1. official ratings snapshot (players, positions, attributes, OVR),
2. PlayStyle/PlayStyle+ assignments (+ PS+ cap config),
3. Roles & familiarity (activates role_fit — first-class since v2.1),
4. cards/rarities (activates card-level scope),
5. verified market prices (activates budget enforcement + value pareto),
6. verified chemistry rules (activates team_fit beyond link facts).

## 3. Vocabulary discipline

Only the real FC26 vocabulary is used in code tables (verified against the
DB): 36 PlayStyles, 12 secondary positions, 11 formations. The position
PlayStyle-affinity table is unit-tested to contain **only** real PlayStyle
names. Community/meta signals would enter as `META_SIGNAL` rows separate from
`CANONICAL_PLAYER_DATA` and can never overwrite official attributes (§16/§17).

## 4. Freshness & conflicts (§26/§27)

* `data_freshness.last_source_observation` is read from `source_observation`
  on every response; confidence v2 decays linearly 180→730 days (floor 0.4).
* Source authority hierarchy: tier 1 OFFICIAL > 2 (none permitted) > 3
  LICENSED carrier (current Kaggle/EA snapshot) > 4 PUBLIC_REFERENCE
  (futbin/futgg/futwiz/wefut — reference only) > 5 SYNTHETIC_TEST.
* Conflicts resolve by authority; unresolved rows in `attribute_conflict_log`
  penalize confidence v2 (0.15/conflict, floor 0.5) and are counted live
  (currently 0 unresolved for FC26).
