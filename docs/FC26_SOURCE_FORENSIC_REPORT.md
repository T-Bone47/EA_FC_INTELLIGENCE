# FC26 SOURCE FORENSIC REPORT

Re-verified this session. Prior repository reports were treated as claims to test, not facts.

**Access ladder — each rung recorded independently:**
`DISCOVERED` → `ACCESSIBLE` → `ACTUALLY DOWNLOADED` → `ACTUALLY INSPECTED` → `FC26 VERIFIED` → `UT CARD LEVEL VERIFIED` → `LICENSE VERIFIED`

---

## 1. The decisive finding

**EA operates an official FC Community API, and it is closed to us on two independent grounds.**

Verified directly from EA's Pitch Notes (2026-07-27):

- Three approved sites only: **FUT.GG, FUTBIN, FUTWIZ**. "These are the only three approved websites at this time."
- **"Are You Accepting Requests From Other Community Sites? We are not accepting requests at this time."**
- Scope is **player account data** — "Ultimate Team data such as players, formations, tactics" belonging to the authenticated user — not the FUT card universe.
- Approved sites may retain pulled account data for **28 days**.

So even if we were approved, the API would deliver a user's own club, not a card database. There is **no EA-official route to bulk FC26 UT card evidence.** This is not a temporary blocker to engineer around; it is the shape of the market.

---

## 2. Source records

### S-01 — EA FC Community API
| Field | Value |
|---|---|
| source_type | Official first-party API |
| URL | `https://www.ea.com/games/ea-sports-fc/fc-26/news/pitch-notes-fc26-community-api-update` |
| FC_version | FC26 |
| data_scope | Authenticated user's club, squads, tactics |
| card_level | Account items, not the card universe |
| access_status | **BLOCKED** — partner programme closed |
| auth required | Yes (EA OAuth, per end user) |
| bulk access | No |
| license / redistribution | Not offered to non-partners; 28-day retention cap for partners |
| recommended_use | **NONE — unavailable** |
| legal review | N/A while closed |

### S-02 — EA Ratings website (`ea.com/games/ea-sports-fc/ratings`)
| Field | Value |
|---|---|
| source_type | Official first-party web property |
| data_scope | Base player ratings, attributes, PlayStyles, alternate positions |
| card_level | **PLAYER LEVEL ONLY** — no FUT items, no prices, no promos |
| access_status | ACCESSIBLE (human browsing) |
| bulk access | No published bulk export or documented API |
| license | Proprietary EA content; no redistribution grant located |
| recommended_use | **Upstream authority reference only.** Do not scrape |
| legal review | **REQUIRED** before any automated retrieval |

This is the true upstream of our foundation data. Its values are the **ratings database**, which is a different object from FUT item ratings — see §4.

### S-03 — FUT.GG
| Field | Value |
|---|---|
| data_scope | Full FC26 FUT card universe, prices, Evolutions, SBCs |
| card_level | **YES — exactly what the product needs** |
| access_status | Site accessible; programmatic access **prohibited** |
| ToS | Prohibits accessing any company resource "by means of any robot, spider, scraper, crawler or other automated means for any purpose", and prohibits bypassing access-restriction measures |
| bulk / API | No public data API |
| recommended_use | **RED** — reference only, human reading |
| legal review | Required if a commercial data agreement is pursued |

### S-04 — FUTBIN
| Field | Value |
|---|---|
| data_scope | Full FC26 FUT card universe, prices, market history |
| card_level | **YES** |
| access_status | Site accessible; data mining **prohibited without written permission** |
| ToS | Prohibits conducting, facilitating or organising data mining or web scraping. Narrow carve-out: students and content creators may use **pricing data** with attribution |
| carve-out applicability | **Does not cover us.** We are neither a student nor a content creator, and we need the full card universe, not pricing |
| recommended_use | **RED** — reference only |
| legal review | Required if written permission is pursued |

### S-05 — FUTWIZ
| Field | Value |
|---|---|
| data_scope | FC26 FUT cards, prices, tactics tooling |
| card_level | YES |
| access_status | ACCESSIBLE (human); terms **NOT INDEPENDENTLY VERIFIED this session** |
| recommended_use | **UNKNOWN — do not ingest pending ToS review** |
| legal review | Required |

### S-06 — FutDB / futdatabase.com (`futdb.app`)
| Field | Value |
|---|---|
| source_type | Third-party commercial FUT API |
| data_scope | Players, prices, clubs, nations, leagues, card types |
| card_level | **YES (claimed)** — not verified by us; no key obtained this session |
| access_status | **AUTH_REQUIRED** — free API key, premium tier for full data |
| documented limits | Full player statistics are **premium-gated**; prices are **premium-gated**; **no bulk price endpoint** ("no way to get multiple player prices with one request, and there will be no way in the future"); >20,000 requests/day requires contacting them |
| price freshness | Vendor-stated 30 min – 24 h, varying by rating and rarity |
| license / redistribution | **UNKNOWN.** No published grant allowing a third party to redistribute the data inside a commercial product |
| recommended_use | **YELLOW — the single most promising candidate**, conditional on a written commercial agreement |
| legal review | **REQUIRED — this is the highest-value legal question in the project** |

Engineering note: the per-card price endpoint makes a full-universe price refresh arithmetically incompatible with a 20k/day cap. Any real deployment needs a negotiated bulk arrangement, not a louder client.

### S-07 — Third-party "FUTBIN API" resellers (e.g. parse.bot marketplace listing)
| Field | Value |
|---|---|
| access_status | Commercially available, credit-metered |
| nature | Unofficial scraping wrapper around FUTBIN |
| recommended_use | **RED.** Purchasing this would be "facilitating" the data mining FUTBIN's terms prohibit. Paying a third party does not transfer a permission the third party does not hold |

### S-08 — `futapi/fut`, `InkedCurtis/FUT-API` and similar web-app clients
| Field | Value |
|---|---|
| nature | Libraries driving the official FUT Web App / Companion App endpoints |
| observed features | Cookie persistence, proxy configuration, anti-captcha integration |
| access_status | **BLOCKED — will not be used** |
| reason | These exist to automate authenticated game endpoints and defeat access controls. Out of scope under the project's own rules, independent of legality |

### S-09 — Kaggle `justdhia/ea-sports-fc-26-player-ratings` *(current production foundation)*
| Ladder rung | Result |
|---|---|
| DISCOVERED | **YES** — dataset page verified to exist: "Complete player stats, ratings, and attributes for all 16,000+ players in EA FC" |
| ACCESSIBLE | YES (page) |
| ACTUALLY DOWNLOADED | **NOT THIS SESSION.** The derived foundation is in-repo; the three raw files named in `MANIFEST.json` are **absent** |
| ACTUALLY INSPECTED | **Derived output inspected** — 16,228 rows × 60 columns, measured |
| FC26 VERIFIED | YES — `game_version = FC26` on every row; EA FC26 item-id URL pattern confirmed |
| UT CARD LEVEL VERIFIED | **NO — player level** |
| LICENSE VERIFIED | **NO.** CC0 is a repository claim; not re-verified against the dataset page this session, and the raw files whose hashes would prove the chain are missing |

### S-10 — Kaggle `flynn28/eafc26-player-database`
| Ladder rung | Result |
|---|---|
| ACTUALLY INSPECTED | **YES** — `EAFC26-Men.csv` 16,228 rows, `EAFC26-Women.csv` 1,645, `EAFC26.csv` 17,873 |
| FC26 VERIFIED | YES — `card` column is an EA FC26 item-art URL (`ratings-images-prod.pulse.ea.com/FC26/components/items/{id}_en.webp`) |
| UT CARD LEVEL VERIFIED | **NO.** The `card` column is **artwork for the ratings-site base item**, keyed by player ID. It is not a card ID, card type, price, release date or variant record |
| LICENSE | **GPL-3** (repo-recorded) → `RESEARCH_ONLY` |
| Measured relationship to production | **Exact 16,228 ID-set match with the production foundation; 4,000/4,000 sampled OVR values identical.** See defect D-3 |
| PlayStyle+ evidence | 119 players hold exactly one PS+; 16,109 hold zero. Max 1 per player **for base ratings-site items** |

### S-11 — Kaggle `rovnez/fc-26-fifa-26-player-data`
| Ladder rung | Result |
|---|---|
| ACTUALLY INSPECTED | **YES** — 18,405 rows × 110 columns |
| FC26 VERIFIED | Partial — `fifa_version = 26` and `fifa_update_date = 2025-09-19` on every row (single homogeneous partition, no FC25 contamination) |
| UT CARD LEVEL VERIFIED | **NO.** Career-mode schema: `value_eur`, `wage_eur`, `release_clause_eur`, `potential`, `player_traits`, `player_tags`. **No PlayStyles column at all** — traits/tags are the pre-FC mechanic |
| provenance | Author-stated scrape of sofifa.com; `player_url` pattern `/player/{id}/{slug}/{version}/` confirms |
| LICENSE | CC BY 4.0 (repo-recorded), but the **upstream** scrape permission is UNKNOWN — a CC licence applied by a scraper does not launder the source's terms |
| recommended_use | **REFERENCE-ONLY** — schema comparison, alternate-position cross-checks |

### S-12 — Kaggle `flynn28/complete-ea-fc26-rating-cards-database`
| Ladder rung | Result |
|---|---|
| observed content (repo-recorded) | ~593 MB of `cards/*.webp` **images**; no structured CSV/JSON, no card ID, price, PlayStyle, role or chemistry record |
| UT CARD LEVEL VERIFIED | **NO** |
| recommended_use | **NONE.** Image assets carry no attribute evidence and raise separate IP questions |

---

## 3. Multi-source architecture — necessary, and currently unsatisfiable

Phase 3 asks whether a multi-source evidence architecture beats a single source. It does, and the measured facts force it:

| Evidence layer | Best available source | Status |
|---|---|---|
| Base player identity + attributes | EA ratings (via CC0 carrier) | **AVAILABLE** |
| PlayStyles (base + plus) | Same | **PARTIAL — 45.2% coverage** |
| Special / promo / Icon / Hero cards | FUT.GG · FUTBIN · FUTWIZ · FutDB | **BLOCKED or AUTH_REQUIRED** |
| Roles + familiarity | No source identified | **MISSING** |
| Prices | FutDB (metered) · others blocked | **AUTH_REQUIRED, no bulk endpoint** |
| Chemistry rules | No source | **MISSING** |
| Cross-source validation | rovnez (sofifa), flynn28 | **RESEARCH_ONLY** |

No single source covers more than one layer. The architecture must be multi-source. **But four of the seven layers currently have no permitted source at all**, so the architecture is correct and the inputs are absent.

---

## 4. Ratings-site values are not FUT card values — measured

This is the most consequential finding after §1.

EA runs in-season **Ratings Reload** for FC26, letting the community vote players into stat upgrades. Reported October adjustments include Julián Álvarez, Michael Olise, Eberechi Eze, Hugo Ekitiké, Cristian Romero, Marc Cucurella, Pau Cubarsí, Scott McTominay, Tyler Morton, Oscar Bobb, Florian Thauvin and Anders Dreyer.

Our foundation snapshot (scraped March 2026) against publicly reported in-season FC26 values:

| Player | Foundation OVR | Reported in-season "before" | Reported "after" |
|---|---|---|---|
| Tyler Morton | **72** | 83 | 85 |
| Oscar Bobb | **72** | 83 | 85 |
| Florian Thauvin | **76** | 83 | 85 |
| Anders Dreyer | **77** | 83 | 85 |
| Cristian Romero | **82** | 87 | 89 |
| Eberechi Eze | **83** | 87 | 89 |
| Hugo Ekitiké | **83** | 87 | 89 |
| Heung Min Son | **85** | 87 | 88 |

Gaps of up to **11 OVR points**. Two readings are possible and both are damaging:

1. The ratings-site database and FUT item ratings are **different quantities** that diverge during a season; or
2. The foundation snapshot is stale relative to live values.

`[MEASURED]` The divergence is real and far too large to be noise. `[UNKNOWN]` Which of the two explanations dominates.

**Consequence:** treating the foundation as a proxy for FUT base-card values is **unsafe and currently unverified**. It also means the v3 frozen reference distributions computed from this snapshot describe the ratings universe, not the FUT universe, and must be labelled as such.

---

## 5. Access-control posture

Recorded for the red-team session. This project will not:

- bypass authentication, paywalls, CAPTCHA or anti-bot systems;
- rotate proxies or otherwise evade rate limits or access controls;
- purchase third-party access that resells data the reseller has no right to redistribute;
- use FUT Web App / Companion App automation libraries.

Where access is prohibited or unverified, the source is recorded `BLOCKED` or `UNKNOWN` and the pipeline proceeds without it. Missing layers stay missing.
