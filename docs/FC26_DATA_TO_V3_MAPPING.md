# FC26 DATA → V3 INTELLIGENCE CONTRACT MAPPING

Per Session 1's rule: **missing data stays missing.** Nothing below proposes weakening the v3 architecture to fit the evidence we happen to have.

Scope classes: `PLAYER` = works on the 16,228-row player foundation · `CARD` = requires card-level evidence we do not have.

---

## 1. Feature-by-feature

| v3 feature | Required fields | Available | Coverage | Confidence input | Usable now |
|---|---|---|---|---|---|
| **Demand composition** | position tables, dimension affinities, λ | Config only — no data dependency | n/a | n/a | **YES** |
| **Capability `C_lo`/`C_hi`** | detail attributes + saturation knees | **YES** | outfield 14,412/14,412; GK 1,816/1,816 | coverage κ | **YES (PLAYER)** |
| **Evidence interval** | frozen P10/P90 per position group | **YES — computable** | all groups n ≥ 1,816 | coverage | **YES**, but see §2 |
| **Coverage gate κ_min** | per-attribute publication variance | **NO** | κ ≡ 1.00 — gate inert | — | **MECHANISM UNTESTABLE** |
| **Position eligibility** | `position_primary`, alternates | **YES** | 16,228 primary; 10,485 alternates | identity | **YES** |
| **PlayStyle modifier** | card PlayStyles base/plus, `playstyle_data_published` | **PLAYER ONLY** | **45.2%** (7,339/16,228); PS+ 0.73% (119) | playstyles | **PARTIAL (PLAYER)** |
| **Interactions** | attribute groups, all KNOWN | **YES** | full | coverage | **YES (PLAYER)** |
| **Archetype demand** | attributes + PlayStyles | **YES / PARTIAL** | attributes full; PlayStyles 45.2% | coverage | **YES (PLAYER)** |
| **Saturation** | knee table | Config | n/a | n/a | **YES** |
| **Role modifier** | role + familiarity | **NO — zero rows, no source** | 0% | role | **NO** |
| **Chemistry** | verified FC26 rules | **NO — unverified** | 0% | n/a | **NO** |
| **Value / budget** | verified prices with provenance | **NO — zero observations** | 0% | price | **NO** |
| **Squad structural fit** | squad members, club/league/nation links | **YES** for players | link facts present | links | **PARTIAL** |
| **Version drift monitors** | multi-release history | **NO — single snapshot** | 1 release | n/a | **NO** |
| **ML ranking** | labelled preference data with context | **NO** | 0 | n/a | **NO** |

**Score: 6 usable, 3 partial, 5 blocked.**

---

## 2. Three contradictions the data reveals

Session 1's stop condition allows changing v3 only where the **data contract** exposes a contradiction. Three exist. None requires altering the ranking mathematics.

### C-1 — The reference distribution describes the wrong universe

v3 §4.3 freezes `q_lo = P10`, `q_hi = P90` per `(game_version, position_group)` and uses them to charge missing **card** attribute weight.

The only distribution we can compute comes from **ratings-site player items**. `[MEASURED]` Foundation OVRs diverge from publicly reported in-season FC26 values by up to **11 points** (Tyler Morton 72 vs 83, Oscar Bobb 72 vs 83, Cristian Romero 82 vs 87). A FUT card universe includes TOTW, promos, Icons and Heroes — its attribute distribution is shifted upward and differently shaped.

Using a player-derived P10 to penalise an unknown card attribute would systematically **over-penalise special cards**, which is the exact population the product exists to reason about.

**Resolution — no maths change.** Tag the distribution with its universe:

```
reference_distribution_version = "fc26-players-2026-03-r1"
universe = "RATINGS_SITE_PLAYERS"        # not "UT_CARDS"
```

The engine refuses to apply a `RATINGS_SITE_PLAYERS` distribution to a `ut_card` candidate and returns `REFERENCE_DISTRIBUTION_UNAVAILABLE` for that scope. Player-scope recommendations continue to work.

### C-2 — κ_min cannot be calibrated from evidence

`[MEASURED]` κ = 1.00 at P01 for all seven position/profile cells tested. Every threshold in [0.40, 0.90] evaluates 100% of candidates.

The gate is correct and currently unexercised. **Resolution:** mark κ_min = 0.60 `PLACEHOLDER_UNCALIBRATED` in config, and add a release monitor that alerts when the κ distribution first becomes non-degenerate — that is the moment the value starts to matter and must be set on evidence.

### C-3 — The PlayStyle+ cap is scoped to the wrong entity if reused

`[MEASURED]` Exactly 119 players hold exactly one PS+; 16,109 hold zero. The cap of 1 is well evidenced — **for ratings-site base items**.

`[VERIFIED — schema]` `playstyle_plus_cap.scope` already distinguishes `player_base` from `card`, and only `player_base` is seeded. The architecture is right.

**Resolution:** keep `scope='card'` **absent = UNKNOWN**, and add a blocking test that card validation never rejects on a cap that was measured on players. The synthetic fixture "Too Many Plus Case" currently exercises a cap that has no card-level evidence behind it.

---

## 3. What the engine can honestly serve today

**Player-scope contextual recommendation** (`entity_scope='game_player'`), with:
- capability over composed demand across 34 attributes, full coverage;
- position eligibility;
- interactions and saturation;
- archetype demand;
- PlayStyle modifier for the 45.2% of players with published PlayStyles, absent (not zero) for the rest;
- squad structural fit where a squad exists;
- confidence reflecting coverage, freshness, authority and identity.

**Explicitly withheld, with reasons in the payload:** Role modifier · chemistry · value and budget · card-scope anything · version-drift monitors · ML.

`[POLICY]` The product must not describe player-scope output as card intelligence. The thesis is that a player is not a card. Serving player data under a card promise would contradict the thesis in the product's own voice.

---

## 4. Release gate

A card-scope release requires **all** of:

1. A `GREEN` or written-permission source for card-level evidence.
2. ≥ 1 verified external card identifier per card, or an explicit `REVIEW_REQUIRED`.
3. `field_provenance` rows for every served field.
4. A card-universe reference distribution.
5. κ measured against real card publication rates, and κ_min set from it.
6. Synthetic firewall verified closed.
7. Conflict resolver able to emit `UNRESOLVED`.

**Currently 0 of 7 are met.** Card scope stays disabled.
