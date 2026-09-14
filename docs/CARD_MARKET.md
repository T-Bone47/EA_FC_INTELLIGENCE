# CARD MARKET & VALUE — Phase 3 (§13/§14/§48)

**Status for FC26: no permitted market feed ⇒ all prices UNKNOWN.**
Consequences, everywhere in the product: budget checks are
`BUDGET_UNVERIFIED`, value is `VALUE_UNAVAILABLE`, price filters match only
verified-price cards, and nothing is ever shown as free or as 0.

## 1. Price records (§13)

`card_price` rows are observations, never assertions:

* `price_coins` nullable — NULL/absent = UNKNOWN (never 0);
* `platform` (playstation/xbox/pc/UNKNOWN), `currency` (COINS),
  `observed_at`, `confidence`, `source_id`, `source_authority`,
  `valid_from/valid_to`;
* `source_observation_id` → the ingestion flush that produced it (provenance).

Written only by the gated pipeline (`PostgresCanonicalRepository._flush_cards`
persists a price **iff** the source published one). Reads: latest price via
indexed LATERAL join (`ix_card_price_time`); full history via
`card_value_service.price_history` → `GET /api/cards/{id}/prices`.

## 2. History is never manufactured (§48)

`price_history` returns exactly the persisted observations; an empty history
reports `NO_PRICE_HISTORY` with an explicit note. No interpolation, no
back-fill, no synthetic curves. Tested
(`test_card_value_chemistry.py::TestPriceHistory`).

## 3. Freshness (§47)

`FRESH` ≤ 14 days (`PRICE_FRESH_DAYS`), `AGING` ≤ 60 (`PRICE_STALE_DAYS`),
else `STALE`; UNKNOWN without an observation timestamp. Freshness travels with
every value/budget payload. Max(observed_at) is part of the card cache
watermark — a newly ingested price can never be served stale (§31).

## 4. Value score (§14)

```
value = (contextual_utility − reference_floor) / (max(price, VALUE_MIN_PRICE_COINS) / VALUE_PRICE_UNIT)
```

* `contextual_utility` — the engine's weighted score for THIS user request;
* `reference_floor` — lowest utility among verified-price candidates in the
  ranked set (marginal baseline; falls back to 0.0 = absolute utility/cost);
* `VALUE_PRICE_UNIT` = 1,000,000 coins (all tunables in `engine_config.py`).

Guarantees (tested): never OVR/price (OVR is not an input); no verified price
⇒ `VALUE_UNAVAILABLE` with reason; no utility ⇒ unavailable (value is
contextual); unpriced cards never rank above priced ones as if free.

## 5. Budget enforcement (§13)

`NullBudgetProvider` is the production default: it reads a candidate's
persisted price observation (coins/platform/observed_at/source/confidence) and
returns UNKNOWN when absent. `within_budget` decides WITHIN/OVER only with a
verified price AND a given budget; otherwise `BUDGET_UNVERIFIED` — the
constraint transparently does not apply, and the payload says so. When a
permitted feed is contracted, implementing `BudgetProvider.price_for` (or
ingesting prices) activates enforcement with no engine change.

## 6. Market-side meta signals

Demand/hype signals (e.g. `market_demand`) belong to the firewalled
`meta_signal` pipeline — they can never overwrite or masquerade as price
observations (§18/§19).
