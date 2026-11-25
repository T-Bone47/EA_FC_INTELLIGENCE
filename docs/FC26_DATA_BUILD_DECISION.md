# FC26 DATA BUILD DECISION

```
DATA_BUILD_STATUS   = PARTIAL
DATA_ACCESS_STATUS  = BLOCKED   (for card-level evidence)
                      PARTIAL   (for player-level evidence)
```

---

## Dataset ladder

```
TOTAL_DATASETS_DISCOVERED          12   (4 Kaggle, 5 live services, 2 API vendors, 1 official EA API)
TOTAL_DATASETS_ACCESSIBLE           7
TOTAL_DATASETS_ACTUALLY_INSPECTED   4   (justdhia-derived foundation, flynn28 x3 files,
                                         rovnez, synthetic fixtures)
TOTAL_DATASETS_USED                 1   (justdhia-attributed foundation — licence UNVERIFIED)
TOTAL_UNUSABLE_DATASETS             11
```

## Entity census — measured, not estimated

```
TOTAL_UNIQUE_PLAYERS         20        (real_player identities; 0.12% of game players)
TOTAL_UNIQUE_GAME_PLAYERS    16,228    (FC26)
TOTAL_UNIQUE_UT_CARDS        0
```

## Card breakdown

```
TOTAL_BASE_CARDS             0
TOTAL_SPECIAL_CARDS          0
TOTAL_PROMO_CARDS            0
TOTAL_TOTW_CARDS             0
TOTAL_ICON_CARDS             0
TOTAL_HERO_CARDS             0
TOTAL_EVOLUTION_CARDS        0
TOTAL_UNKNOWN_CARD_TYPES     0
                             (63 SYNTHETIC_TEST fixtures exist; they are not cards
                              and are excluded from every count above)
```

## Field coverage

```
CARDS_WITH_OVR                    0
CARDS_WITH_DETAILED_ATTRIBUTES    0
CARDS_WITH_PLAYSTYLES             0
CARDS_WITH_PLAYSTYLE_PLUS         0
CARDS_WITH_ROLES                  0
CARDS_WITH_PRICES                 0
CARDS_WITH_VERIFIED_CARD_ID       0
CARDS_WITH_VERIFIED_PLAYER_ID     0
```

Player-level, for contrast — this is what does exist:

```
PLAYERS_WITH_OVR                    16,228  (100%)
PLAYERS_WITH_DETAILED_ATTRIBUTES    14,412 / 14,412 outfield  (100%)
GKS_WITH_GK_ATTRIBUTES               1,816 / 1,816            (100%)
PLAYERS_WITH_PLAYSTYLES              7,339   (45.2%)
PLAYERS_WITH_PLAYSTYLE_PLUS            119   (0.73%, exactly 1 each)
PLAYERS_WITH_ROLES                       0
PLAYERS_WITH_PRICES                      0
PLAYERS_WITH_VERIFIED_EXTERNAL_ID   16,228  (EA ratings item id)
PLAYERS_WITH_ALTERNATE_POSITIONS    10,485  (64.6%)
```

---

## Verdict

```
CAN_REAL_FC26_UT_DATA_BE_INGESTED = NO
```

Not "not yet" as a scheduling statement — **no, on present permissions.** Every source that holds FC26 UT card data is either closed by EA, prohibited by its own terms, or of unverified licence. This is a legal and commercial blocker, not an engineering one, and no pipeline work changes it.

```
CAN_REAL_FC26_PLAYER_DATA_BE_INGESTED = YES, WITH A LICENCE CAVEAT
```

16,228 fully-attributed FC26 players are already ingested and are sufficient to run the v3 engine at player scope. The caveat is G-10: the production foundation's licence chain is unverified.

---

## Source strategy

```
RECOMMENDED_PRIMARY_SOURCE
    Kaggle justdhia/ea-sports-fc-26-player-ratings  (carrier of EA official ratings)
    scope: PLAYER LEVEL ONLY
    status: ACTIVE, licence claimed CC0, VERIFICATION REQUIRED before release

RECOMMENDED_SECONDARY_SOURCE
    NONE AVAILABLE.
    The intended secondary layer is card-level evidence. No permitted source exists.

RECOMMENDED_VALIDATION_SOURCE
    Kaggle rovnez/fc-26-fifa-26-player-data   (sofifa-derived, CC BY 4.0)
    use: schema and alternate-position cross-checks ONLY
    never promoted to canonical; upstream permission UNKNOWN

RECOMMENDED_MARKET_SOURCE
    NONE AVAILABLE.
    FutDB is the only candidate and is YELLOW pending legal review; it has no bulk
    price endpoint and a 20k/day request ceiling, which is arithmetically
    incompatible with refreshing a full card universe.

REFERENCE_ONLY_SOURCES
    flynn28/eafc26-player-database              (GPL-3, RESEARCH_ONLY)
    flynn28/complete-ea-fc26-rating-cards-database  (images only, no structured data)
    FUT.GG · FUTBIN · FUTWIZ                    (human reading only)
    EA Ratings website                          (upstream authority reference)

LEGAL_REVIEW_REQUIRED
    1. FutDB commercial licence AND their right to relicense EA-derived data   [BLOCKING]
    2. Foundation CC0 chain, given the exact ID match to a GPL-3 dataset       [BLOCKING]
    3. EA IP position on a derived FC26 recommendation product                 [STRATEGIC]
    4. Written data agreement with FUT.GG / FUTBIN / FUTWIZ                    [ALTERNATIVE]
    5. FUTWIZ terms — unread                                                   [CLASSIFICATION]

MAIN_REMAINING_GAPS
    G-01  no FC26 UT card data of any kind
    G-05  no Role data anywhere, at any level
    G-06  no market prices
    G-07  no verified chemistry rules
    G-10  foundation licence chain unverified
    G-11  synthetic firewall not enforced in production SQL
    G-12  conflict resolver cannot emit UNRESOLVED
    G-13  no field-level provenance
    G-16  foundation ~6 months stale; diverges from live by up to 11 OVR
```

---

## The honest summary

The project can build a **trustworthy contextual FC26 player intelligence system today**, at player scope, using data it already holds — once the licence chain is verified and three safety defects are fixed.

It **cannot** build card intelligence. Not because the model is wrong — the canonical model handles cards, versions, evolutions, roles, prices and chemistry correctly — but because no permitted source of FC26 card evidence has been found, and EA's own partner programme is explicitly closed.

The gap between what the architecture can express and what the evidence can support is now the defining fact of this project. The correct response is to ship the scope that has evidence, label it accurately, and treat card-level access as a commercial negotiation rather than an engineering backlog item.

**Do not ship player data under a card promise.** The product thesis is that a player is not a card. Blurring that at the data layer would contradict the thesis in the product's own voice.
