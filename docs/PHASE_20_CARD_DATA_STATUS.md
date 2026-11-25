# PHASE 20 CARD DATA STATUS

## Verdict

```
CAN_REAL_FC26_UT_CARD_DATA_BE_INGESTED = NO
```

Unchanged from the original data-forensics session. This session re-verified the legal landscape with fresh evidence rather than assuming the prior conclusion still held, and the conclusion is confirmed — if anything, on stronger evidence (FUTBIN's position is more explicitly documented; FutDB, previously the most promising candidate, is downgraded on closer inspection; a second, easily-confused FutDB-family service was found and is equally unresolved).

## Card universe measurement (actual, not estimated)

```
discovered_cards         = 0   (no legitimately-sourced card ever discovered)
verified_cards           = 0
accessible_cards         = "many, via human browsing of FUTBIN/FUT.GG/FUTWIZ -- not
                             countable as a dataset since bulk retrieval is prohibited"
legally_usable_cards     = 0
canonical_cards          = 0
unresolved_cards         = 0
duplicate_cards          = 0
missing_id_cards         = n/a
missing_attribute_cards  = n/a
missing_playstyle_cards  = n/a
missing_role_cards       = n/a
missing_price_cards      = n/a

card_coverage       = 0%
field_coverage      = 0%
provenance_coverage = 0% (nothing to trace)
legal_coverage      = 0% (nothing cleared GREEN)
```

Only `ut_card` rows in the database (60 total) are `SYNTHETIC_TEST` fixtures — confirmed via direct query this session, `is_synthetic=false` count is exactly 0.

## What blocks production card intelligence, exactly

**Not a technical blocker.** The canonical data model, identity resolution rules, provenance schema, conflict resolver, and now (this session) the executable license gate, no-fabrication firewall, and card publication gate are all built, tested, and ready to receive legitimate data the moment it exists.

**The blocker is legal evidence.** Every source with confirmed FC26 UT card-level data (FUTBIN, FUT.GG, FUTWIZ) explicitly prohibits the automated access a dataset requires, or has terms too unclear to rely on (FUTWIZ). Every source with API-based programmatic access (FutDB.app, FUT-DB.com) fails to publish the specific storage/derivative/redistribution rights a production product needs, regardless of what querying the API itself is priced at.

## Exact evidence that would unblock this

Any ONE of the following, with a specific artefact this project could point to:

1. A written agreement (email, signed terms addendum, or a published API terms page) from **FutDB.app or FUT-DB.com** explicitly granting storage, derivation, and redistribution rights for a commercial product — the single highest-value, most achievable next step given both already offer paid commercial API access.
2. A written agreement from FUTBIN, FUT.GG, or FUTWIZ granting a scraping/data-mining exception.
3. EA reopening or expanding the FC Community API programme to cover the FUT card universe rather than only user account data (monitor `ea.com/games/ea-sports-fc/fc-26/news` for programme updates).
4. FUTWIZ's actual terms of service, located and reviewed (currently a genuine research dead end after two attempts — would require direct outreach).

## Recommended next legitimate acquisition route

**Direct written outreach to FutDB.app and FUT-DB.com**, asking the three specific questions this review could not answer from their published materials: may we store your data, may we derive new datasets from it, and may we serve those derived datasets to our end users in a commercial product? This is narrower, cheaper, and more likely to succeed than pursuing FUTBIN/FUT.GG (which have unambiguous, absolute prohibitions) or waiting on EA's partner programme (explicitly closed with no stated reopening timeline).

## What remains disabled

```
entity_scope = "game_player" only, enforced at the API schema type level
UT-card recommendation: disabled
Card ingestion: disabled
Chemistry, Roles, Prices, Evolution: all UNKNOWN, none inferred
```

This is unchanged and is not modified by this phase.
