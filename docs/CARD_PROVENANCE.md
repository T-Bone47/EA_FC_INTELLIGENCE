# CARD PROVENANCE — Phase 3 (§20/§21/§47)

Every card fact must be traceable to a source observation, with authority and
freshness. No provenance ⇒ not a fact.

## 1. Chain

```
source_registry (license/permission/legal_gate, authority_tier 1-5)
  └─ source_observation (one row per ingestion flush: snapshot_date, raw_payload counts, retrieval_context)
       ├─ ut_card / ut_card_attribute_override / ut_card_playstyle / ut_card_role
       ├─ card_version (content_hash + source_observation_id)
       ├─ card_price (source_observation_id, source_id, confidence, observed_at)
       └─ ingestion_run (stage, counts, activation_status, full report JSONB)
            └─ ingestion_quarantine (rejected rows: reason + raw payload)
```

Read paths surface it: `/api/cards/{id}` returns source + source_card_id +
observation-linked price; card candidates carry `price_source_id`,
`price_observed_at`, `price_confidence`, `card_identity_status`,
`attribute_source: "ut_card"` in their evidence trail.

## 2. Authority tiers (unchanged, §20/§21)

1 OFFICIAL (EA) · 2 AUTHORIZED/LICENSED partner · 3 established reference ·
4 community dataset · 5 unverified/community evidence.

Rules enforced by `conflict_resolver.py` (tested for cards in
`test_card_scenarios.py::TestSourceConflicts`):

* higher authority wins; **recency never beats authority**;
* a source canonical *for the field* (e.g. a market feed for `price_coins`)
  beats a higher-tier source that is not authoritative for that field;
* disagreements produce a `ConflictRecord` (persisted to
  `attribute_conflict_log` during ingestion; surfaced in confidence) —
  equal-authority conflicts are logged, never silently picked without record;
* `NOT_PERMITTED`/unusable sources' claims are ignored entirely;
* lower authority never overwrites higher-authority canonical values:
  card upserts merge conservatively (`coalesce` keeps established identity
  metadata; `identity_status` only upgrades toward RESOLVED).

## 3. Freshness (§47) — component-specific

| component | freshness signal | policy |
|---|---|---|
| card attributes/version | `card_version.valid_from`, `ut_card.updated_at` | part of the card cache watermark — re-ingest invalidates immediately |
| prices | `card_price.observed_at` | FRESH ≤ `PRICE_FRESH_DAYS` (14), STALE > `PRICE_STALE_DAYS` (60) — flagged in every value assessment; part of the card watermark so updated prices are never served stale |
| chemistry rules | rule ingest | count of verified rules is part of the card watermark |
| meta signals | `meta_signal.observed_at` | separate `meta_watermark` (§28); never feeds canonical caches |

## 4. Synthetic firewall (§55)

`is_synthetic=TRUE` / `data_status=SYNTHETIC_TEST` rows are excluded from
every production read path (repository SQL filters, API 404s, engine
abort-if-reached). Synthetic data never fills missing production cards.
