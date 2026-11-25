# FC27 four-card provider evaluation

**Decision on 23 November 2026: hold both purchases.** Three outfield items have full primary-position attribute coverage in the local card archive. Neither provider supplied a production-equivalent detail response for a target item in this run. Public release permission remains pending. The experiment ran offline against existing observations and DataFluxor's published illustrative responses.

## Four target items

| EA item | Card | Primary position | Archive 5 card fields | Archive 4 same item ID | September player context | FUT-DB schema paths | DataFluxor sandbox schema paths |
|---:|---|---|---:|---:|---:|---:|---:|
| 192119 | Thibaut Courtois, Rare | GK | 0/5 | 5/5 | 5/5 | 5/5 | 0/5 |
| 231747 | Kylian Mbappé, Rare | ST | 26/26 | 26/26 | 26/26 | 26/26 | 1/26 |
| 67386507 | Lamine Yamal, Team of the Week | RW | 26/26 | No item | 26/26 | 26/26 | 1/26 |
| 84163723 | Lamine Yamal, Star Performer | RW | 26/26 | No item | 26/26 | 26/26 | 1/26 |

Each denominator is the union of positive-weight attributes from V3.2 demand composition for the listed primary position across the registered single tactical profiles, with default lambda and no user attribute overrides. An individual tactical request can demand fewer fields. The counts describe distinct attributes, not weighted evidence coverage or a recommendation score. The goalkeeper has five demands. For both outfield positions, 25 demands are detailed attributes and one is face pace. DataFluxor's public card-search sandbox shows six face statistics. Only pace maps to these two outfield demand sets. Its one sample catalogue item is outside the four-item cohort. Actual provider coverage for these four is **unmeasured** for both feeds. [FUT-DB specification](https://api.futdatabase.com/api/doc/v1/swagger.json) · [DataFluxor sandbox catalogue](https://datafluxor.com/api/fut-sandbox/cards/search)

The CSV contains one row for each of the 83 item/attribute combinations. Local numeric values come from the three hash-pinned, distinct source tables. A blank represents a missing observation, a missing exact item, or an absent provider response as distinguished in the JSON. The September values describe the candidate base footballer. No value was copied across scopes. [Field comparison](field_comparison.csv) · [Counts, hashes, positions, PlayStyles and identity issues](observations.json)

## What the records establish

- **Courtois.** Archive 5 publishes two base PlayStyles and a plus, but has no mapped detailed goalkeeper values. It lists GK and CM. The existing adapter accepts GK and flags CM. Archive 4 has an exact item ID, base ID and matching rating, with diving 87, handling 89, kicking 78, positioning 90 and reflexes 90. This is a second source observation with its own provenance. The unresolved review concerns the alternate position and provider detail coverage.
- **Mbappé.** The item ID, rating and all 26 demanded attributes agree across Archives 4 and 5. Archive 5 lists ST and LW, six base PlayStyles and Quick Step+. It contains role-fit text for both positions. Official eligibility and official role tiers remain unknown.
- **Yamal.** Archive 5 has two independent rows with the same full name, club, primary and alternate positions and 91 OVR, under different rarities and item IDs. Nine of 26 demanded values differ, including stamina (78 and 80), crossing (89 and 90) and short passing (89 and 90). Technical+ appears on the Team of the Week item and Quick Step+ on Star Performer. The candidate base player is 277643. Archive 4 contains his base record but has neither special item ID. The shared base link remains provisional. No numeric ID arithmetic was used.

## Market reconciliation

The published sandbox returned one price row with a target item ID. It uses 231747 and 91 OVR, but the footballer and club are illustrative and conflict with Mbappé and Real Madrid. It is a console/PS list observation, marked inexact. Its observation time is 27 September at 21:52:40 UTC, outside the repository's 14-day fresh window at the replay cutoff. The provider's historical stale flag alone would miss that. No target PC observation was available. The result is **zero corroborated live prices across eight requested item/market pairs**. The PC and console quotes on the sandbox catalogue card refer to a different item. [Published sandbox prices](https://datafluxor.com/api/fut-sandbox/prices) · [Sandbox scope and production offering](https://datafluxor.com/fut-data)

## Reproduction

Run from the project root. Save the two linked, free sandbox JSON responses as `sandbox-cards.json` and `sandbox-prices.json` in a temporary directory. The replay uses an explicit UTC cutoff. Inputs that providers change later may produce different evidence.

```powershell
python -m scripts.compare_fc27_provider_sample --archives "$env:USERPROFILE/Downloads" --output artifacts/phase29/provider_sample --as-of 2026-11-23T00:00:00Z --catalogue "$env:TEMP/sandbox-cards.json" --prices "$env:TEMP/sandbox-prices.json"
python -m pytest -q backend/tests/test_phase29_provider_sample.py backend/tests/test_fc27_evidence_and_product.py
```

The sample replay completed. Tests returned **13 passed and 2 skipped**. The two existing API integration tests require PostgreSQL, which was offline. These tests cover item/base and game boundaries, duplicate sample identities, illustrative payloads, mismatched rarity, missing and out-of-range stats, exact market and platform, timezone awareness, future dates, stale observations, old upstream timestamps and unavailable prices. They do not certify a live feed.

## Complimentary evaluation request

For FUT-DB, request four FC27 `PlayerResponse` payloads for the listed EA resource IDs at production-equivalent field visibility. Ask for the item and base namespace definitions, version and rarity legends, official versus editorial role provenance, and the meaning of null versus an empty list for PlayStyles and positions. Request written scope for local evaluation, retention, transformations, derived rankings, display and downstream API responses. The free tier can return null statistics. Section 7 conditions reproduction, distribution and modification on explicit permission. [Provider access and contact](https://app.futdatabase.com/) · [Provider terms](https://fut-db.com/terms)

For DataFluxor, request the same four catalogue rows plus an exact console and PC observation for each item where a market exists. For unavailable markets, request the provider's explicit reason. Ask for item and base IDs, rarity and affiliation, platform, source type, observed and checked timestamps, age, freshness flags and evaluation retention terms. Four item IDs suffice for this trial. [Product documentation](https://datafluxor.com/fut-data)

For a permitted evaluation rerun, use a fresh output directory and the export's actual capture time. Pass `--futdb-dir` containing `<item>.json` responses, a combined four-card catalogue response with `--catalogue`, and both platform response files with `--prices`. Field counts remain descriptive when identity issues are open. Human review must resolve provider-specific names, rarity and club dictionaries, role semantics, market freshness requirements and written rights before any activation. No provider was contacted, no fee incurred and no release activated.
