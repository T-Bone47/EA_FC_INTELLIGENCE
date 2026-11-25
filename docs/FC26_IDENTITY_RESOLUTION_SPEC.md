# FC26 IDENTITY RESOLUTION SPEC

How a unique FUT card and a unique player are identified, and what each key is actually worth.

---

## 1. The three ID classes — never conflated

| Class | Meaning | Example in this project |
|---|---|---|
| `VERIFIED_EXTERNAL_ID` | An identifier the **source system itself** assigns and publishes | EA ratings item id (`209331` = Salah) |
| `SOURCE_LOCAL_ID` | An id unique **within one source**, meaningless across sources | FutDB player id, a CSV row key |
| `DERIVED_CANONICAL_ID` | An id **we compute** to join observations. Not an official card id | `ut_card.canonical_card_id` |

`[POLICY]` A `DERIVED_CANONICAL_ID` is never presented, exported or logged as if it were an EA card id. The API must carry the class alongside the value.

---

## 2. Identity keys evaluated

| Key | Reliability | Collision risk | Cross-source | Historical stability | Identifies Evolutions | Dedupes observations | Verdict |
|---|---|---|---|---|---|---|---|
| **EA ratings item id** | **High** | Very low | Good — shared upstream | Stable per version | No (player-level) | Yes, for players | **ADOPT for GamePlayer** |
| EA/FUT item id (in-game) | High | Very low | Would be ideal | Unknown | Likely yes | Yes | **UNAVAILABLE** — no permitted source |
| Source card id | High within source | Low within source | **None** | Source-dependent | Source-dependent | Within source only | Adopt as `SOURCE_LOCAL_ID` |
| player_id + version | Medium | **Medium** | Medium | Medium | Partially | Partially | Component only |
| name + rating + card type | **Low** | **High** | Poor | **Poor** — ratings change in-season | No | No | **REJECT** |
| Deterministic composite | Medium | **Medium — see §4** | Good | Good | No | Yes | Adopt with the §4 fix |

`[MEASURED]` "name + rating" is disqualified by evidence, not taste: FC26 runs in-season **Ratings Reload** upgrades. A key containing a rating is a key that changes under you mid-season, silently splitting one card into two.

---

## 3. GamePlayer identity `[IMPLEMENTED]`

```
game_player_id = uuid5(NS, "game_player|{source_id}|{game_version}|{source_player_id}")
```

Idempotent, version-partitioned, source-scoped. Correct.

**RealPlayer resolution** `[IMPLEMENTED, starved]` — exact normalised name-form match across display/common/first+last, corroborated by nationality and DOB. Ambiguity routes to `REVIEW_REQUIRED`; never merges on name similarity alone. The logic is right; with **20 reference identities** it resolves ~0.1% of the universe.

---

## 4. Card identity — current rule and its defect

Current `[IMPLEMENTED]`:

```
canonical_card_id = uuid5(NS,
    "canonical_card|{game_version}|{player_key}|{card_type or rarity or BASE}|{position}|{release_group}")
```

Good: deliberately excludes rating and name; version-partitioned; deterministic across sources; keeps a base gold and a TOTW distinct.

**Defect — collision under UNKNOWN.** `card_type` falls back to `rarity`, then to the literal `"BASE"`. Two genuinely different promo items for the same player, at the same position, in the same release group, both arriving with `card_type = NULL` and the same rarity, **collide into one canonical card** and their conflicting attributes are then resolved against each other as if they were the same item.

This is the worst possible failure mode: it does not error, it silently merges two cards and produces a blended phantom.

### 4.1 Required fix — `[POLICY]`

Identity may only be **asserted** from present evidence. Absent discriminators produce review, not a default.

```
if card_type is UNKNOWN and rarity is UNKNOWN:
        identity_status = REVIEW_REQUIRED
        canonical_card_id = NULL
        # the observation is retained; no canonical card is created
else:
        canonical_card_id = uuid5(...)   as today
        identity_status  = RESOLVED
```

Add a discriminator when the source provides one (`source_card_id` hash tail, release date), and record which discriminators were available in `identity_rule` — the column already exists and is currently under-used.

### 4.2 Evolution identity `[UNKNOWN]`

An Evolution changes a card's stats while the player keeps the item. Whether a source exposes a stable item id across an Evo is **unverified** for every candidate source.

Rule until evidence exists: an Evo-changed card is a **new `card_version` of the same `ut_card`** only when the source publishes an identity link. Otherwise `REVIEW_REQUIRED`. Never infer an Evo from a stat delta — a stat delta is also what a ratings update looks like.

---

## 5. Observation deduplication

```
observation_key = (source_id, game_version, entity_type, source_entity_id, content_hash)
```

Re-ingesting an unchanged row is a no-op. A changed row creates a new `card_version` with a new `content_hash`, preserving history. `[IMPLEMENTED]` via `UNIQUE (ut_card_id, content_hash)`.

---

## 6. Identity confidence

Feeds `confidence_v2.identity_factor`, already wired.

| Status | Factor | Condition |
|---|---|---|
| `RESOLVED` | 1.0 | Verified external id, or composite with all discriminators present |
| `REVIEW_REQUIRED` | 0.6 | Ambiguous match, or missing discriminator |
| `UNRESOLVED` | 0.4 | No usable key |

`[POLICY]` `REVIEW_REQUIRED` cards are ingested and stored but are **not eligible for recommendation** until a human resolves them. Storing them preserves evidence; serving them would present a guess as a fact.
