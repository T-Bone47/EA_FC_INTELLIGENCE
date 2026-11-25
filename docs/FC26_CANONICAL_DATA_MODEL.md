# FC26 CANONICAL DATA MODEL

Audit and specification of the canonical hierarchy. The existing schema is largely correct; this document fixes the gaps and states the invariants that must hold.

---

## 1. Hierarchy

```
RealPlayer                      the human being. Identity facts only, no ratings
   │  1:N
GamePlayer                      that human as represented in ONE game version
   │  1:N                       (FC26 ratings-database item)
UTCard                          ONE Ultimate Team item: base, TOTW, promo,
   │  1:N                       Hero, Icon, Evolution, special
CardVersion                     the stats of that item at a point in time
   │                            (Evolutions and live upgrades create versions)
   ├── CardAttributes           1..99 or UNKNOWN, card-published only
   ├── CardPositions            primary + alternates, card-published only
   ├── CardPlayStyles           base / plus, card-published only
   ├── CardRoles                role + familiarity
   └── MarketObservation        price at a timestamp, per platform
          │
   FieldProvenance / SourceObservation      attached at every level
```

`[VERIFIED — schema]` All eight entity levels exist in `DATABASE_SCHEMA_V1.sql` + migrations 002 and 005. The model is **not** collapsed.

---

## 2. Invariants

These are non-negotiable and each needs an enforcing test.

**INV-D1 — No level collapse.** A `UTCard` is never merged into its `GamePlayer`, and a `GamePlayer` is never merged into its `RealPlayer`. A 91 base Salah and a 94 TOTW Salah are two `ut_card` rows sharing one `game_player_id`.

**INV-D2 — No attribute inheritance.** A card's attributes, positions and PlayStyles come **only** from card-published evidence. Missing card attributes are UNKNOWN; they are never backfilled from the base player. `[IMPLEMENTED]` — enforced in `UTCard.attribute_overrides` and documented at `card_model.py`.

This is the single most important invariant in the model. Violating it would make every special card look like its base player and destroy the product thesis at the data layer.

**INV-D3 — One canonical card, many observations.**

```
CanonicalCard(canonical_card_id)
   ├── Observation from source A
   ├── Observation from source B
   └── Observation from source C
```

never

```
Card A · Card B · Card C
```

unless evidence proves they are distinct items. `[PARTIAL]` — `ut_card.canonical_card_id` and `ux_utcard_canonical` exist; the derivation rule has collision risk (see `FC26_IDENTITY_RESOLUTION_SPEC.md` §4).

**INV-D4 — A source row is not a canonical card.** Every ingested row is first a `source_observation`. Promotion to canonical is a separate, recorded decision. `[IMPLEMENTED]` via `ingestion_run` staging.

**INV-D5 — Version partition.** `game_version` is part of every identity preimage and every config lookup. FC26 and FC27 records never share a row, a config or a reference distribution. `[IMPLEMENTED]`

**INV-D6 — UNKNOWN preservation.** No factual field may be coerced to 0, mean, median or default at any layer. `[IMPLEMENTED]`

**INV-D7 — Synthetic isolation.** No `SYNTHETIC_TEST` or `is_synthetic` row may be readable by a production query. `[BROKEN]` — see `FC26_DATA_QUALITY_SPEC.md` §5.

---

## 3. Required schema changes

### 3.1 Close the synthetic firewall — P0

```sql
-- 1. make the two synthetic markers logically inseparable
ALTER TABLE ut_card ADD CONSTRAINT synthetic_status_consistent
  CHECK ( (is_synthetic = TRUE)  = (data_status = 'SYNTHETIC_TEST') );

-- 2. give production a single object it cannot forget to filter
CREATE OR REPLACE VIEW ut_card_production AS
  SELECT * FROM ut_card
  WHERE is_synthetic = FALSE AND data_status <> 'SYNTHETIC_TEST';
```

`[POLICY]` Production read paths query the **view**, never the table. The current defect is a missing `AND` that a reviewer cannot see; a view removes the class of error rather than the instance.

### 3.2 Field-level provenance — P0

`source_observation_id` already exists on `card_version`, `ut_card_playstyle` and `card_price`. It is **missing** on the attribute tables and is discarded by the engine. Add:

```sql
ALTER TABLE ut_card_attribute_override
  ADD COLUMN source_observation_id UUID REFERENCES source_observation(id);
ALTER TABLE game_player_attributes
  ADD COLUMN source_observation_id UUID REFERENCES source_observation(id);
```

plus the `field_provenance` table specified in `FC26_PROVENANCE_SPEC.md`.

### 3.3 Card-scoped PlayStyle+ cap — P1

`playstyle_plus_cap` already carries `scope IN ('player_base','card')`. Only `player_base = 1` is seeded, from measured evidence (119 players × exactly 1 PS+).

`[CRITICAL]` That cap is **evidence for ratings-site base items only**. Applying it to special cards would be fabrication — FUT special items are widely understood to carry more. Until card evidence exists, `playstyle_plus_cap(scope='card')` must stay **absent = UNKNOWN**, and card validation must not reject on it.

### 3.4 `real_player` population — P1

20 identities against 16,228 game players makes the top of the hierarchy decorative. Either populate it from a permitted identity source, or mark `RealPlayer` explicitly `NOT_POPULATED` in the API so consumers do not read `real_player_id IS NULL` as "unknown human".

---

## 4. Entity field contracts

### GamePlayer `[POPULATED: 16,228]`
Required: `game_version`, `source_id`, `source_player_id`, `display_name`, `position_primary`.
Optional/UNKNOWN-able: everything else, including `overall_rating`.
Measured coverage: OVR 100%; outfield detail attributes 14,412/14,412; GK attributes 1,816/1,816; alternate positions 10,485; PlayStyles 7,339 (45.2%).

### UTCard `[POPULATED: 0 real]`
Required: `game_version`, `source_id`, `source_card_id`, `card_name`, `position`.
UNKNOWN-able: `overall_rating`, `card_type`, `rarity`, `release_date`, `release_group`, `game_player_id`, every attribute, every PlayStyle, every role, price.

`[POLICY]` `card_type` must never be inferred from `overall_rating` or `rarity` colour. An 86 gold and an 86 TOTW are different items; guessing type from rating is exactly the fabrication the project forbids.

### CardVersion `[POPULATED: 0]`
`content_hash = sha256(canonical stat payload)`, `UNIQUE (ut_card_id, content_hash)` — idempotent re-ingestion by construction. `[IMPLEMENTED, good]`

Evolutions are modelled as **new versions of the same card**, not new cards, when the source confirms the item identity is preserved. When the source does not confirm it, identity is `REVIEW_REQUIRED` rather than assumed either way.

### MarketObservation `[POPULATED: 0]`
`price_coins` NULL = UNKNOWN, never 0. Platform-scoped. Every row carries `observed_at`. No interpolation, no carry-forward, no back-fill.

---

## 5. What the model cannot currently express, for lack of data

| Concept | Schema | Data | Net |
|---|---|---|---|
| Base vs special card distinction | present | **absent** | cannot distinguish |
| Evolution lineage | present | **absent** | cannot trace |
| Card-level PlayStyles | present | **absent** | cannot serve |
| Roles / familiarity | present | **absent** | cannot serve |
| Chemistry | present | **absent (unverified rules)** | withheld |
| Price / value | present | **absent** | withheld |
| Version drift over a season | present | **single snapshot** | cannot measure |

The canonical model is ready. Seven of its concepts have no evidence behind them.
