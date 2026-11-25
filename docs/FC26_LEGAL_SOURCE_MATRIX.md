# FC26 LEGAL SOURCE MATRIX

**This is not legal advice.** It is an engineering classification that decides what the pipeline is allowed to fetch, store and ship, and what must go to a lawyer first.

Three properties are kept strictly separate:

```
ACCESSIBLE       we can reach it
PERMITTED        we may use it for our purpose
REDISTRIBUTABLE  we may ship it inside our product
```

A source can be all three, or accessible and neither of the others. **Accessible ≠ shippable.**

---

## 1. Classification

`GREEN` clearly permitted · `YELLOW` possibly usable, legal review required · `RED` do not ingest or redistribute · `UNKNOWN` insufficient licensing information

| Source | Accessible | Permitted | Redistributable | Gate |
|---|---|---|---|---|
| EA FC Community API | **NO** — programme closed | No | No | **RED (unavailable)** |
| EA Ratings website | Yes (human) | No automated grant found | No | **RED for automation** |
| FUT.GG | Yes (human) | **No** — ToS bars all automated access | No | **RED** |
| FUTBIN | Yes (human) | **No** without written permission | No | **RED** |
| FUTWIZ | Yes (human) | **UNKNOWN** — terms not verified | UNKNOWN | **UNKNOWN** |
| FutDB / futdatabase | Yes (API key) | Free + premium tiers | **UNKNOWN** | **YELLOW — highest priority review** |
| Third-party FUTBIN API resellers | Yes (paid) | **No** — facilitates prohibited mining | No | **RED** |
| FUT Web App automation libs | n/a | No — defeats access controls | No | **RED — out of scope by policy** |
| Kaggle `justdhia` (production foundation) | Yes | CC0 **claimed, unverified** | Yes **if CC0 confirmed** | **YELLOW — verify before release** |
| Kaggle `flynn28` player DB | Yes | GPL-3 | **Copyleft risk** | **RED for production, GREEN for research** |
| Kaggle `flynn28` rating-cards (images) | Yes | CC BY 4.0 on the compilation | Image IP separate | **RED** |
| Kaggle `rovnez` (sofifa scrape) | Yes | CC BY 4.0 on the compilation; **upstream permission UNKNOWN** | UNKNOWN | **YELLOW — reference only** |

---

## 2. Reasoning on the contested entries

**EA Community API — RED (unavailable).** Verified from EA's own Pitch Notes: three approved partners, "We are not accepting requests at this time", and the scope is a user's own account data with a 28-day retention cap. Not a database route.

**FUTBIN — RED.** Terms prohibit conducting, facilitating or organising data mining or web scraping without written permission. The carve-out for students and content creators covers **pricing data with attribution** and does not reach a commercial product ingesting the card universe.

**FUT.GG — RED.** Terms prohibit access "by means of any robot, spider, scraper, crawler or other automated means for any purpose" and bar bypassing access restrictions. There is no ambiguity to interpret around.

**Resellers — RED.** Buying scraped FUTBIN data does not create a permission the seller never had, and paying for it is closer to "facilitating" than to arm's length.

**flynn28 player DB — RED for production.** GPL-3 on a dataset raises copyleft questions about anything built from it. `[MEASURED]` This matters concretely: the production foundation is an **exact 16,228 ID-set match** with 4,000/4,000 sampled OVR agreement, and the CC0 raw files that would prove independent provenance are **missing from the repository**. The licence chain is currently indeterminate.

**rovnez — YELLOW, reference only.** A CC BY 4.0 licence applied by a scraper governs the scraper's compilation, not the scraped site's terms. `[MEASURED]` It also fails the version-vocabulary check: `player_traits`/`player_tags` are the pre-FC mechanic, and it has no PlayStyles column. Correctly held RESEARCH_ONLY.

**FutDB — YELLOW, and the decisive question.** It is the only identified route to card-level FC26 evidence that does not require violating someone's terms. Two things must be established in writing before a single row is ingested:

1. May we store the data and serve derived recommendations in a commercial product?
2. What is FutDB's own right to relicense data derived from EA's game?

Question 2 is the one that gets skipped and is the one that matters. A vendor agreement that does not survive it is a liability, not an asset.

---

## 3. Pipeline enforcement

`source_registry.legal_gate` already exists. It must become **executable**, not documentary:

```
GREEN   -> ingest, store, serve, redistribute in releases
YELLOW  -> ingest to RESEARCH schema only; never reaches canonical;
           never leaves the release boundary
RED     -> adapter refuses to fetch. The refusal is logged
UNKNOWN -> treated as RED
```

`[POLICY]` The adapter checks the gate **before** the network call, and `UNKNOWN` defaults to `RED`. A source whose terms we have not read is a source we do not fetch.

---

## 4. Attribution obligations

| Source | Obligation |
|---|---|
| CC0 | None required; attribution retained anyway for provenance |
| CC BY 4.0 | Attribution **required** in any surface presenting derived data |
| GPL-3 | Copyleft implications — **do not link into production** |
| FUTBIN pricing carve-out | Attribution required, and the carve-out does not apply to us |

`[POLICY]` Attribution strings are stored in `source_registry` and rendered from data, not hard-coded. A release that includes a CC BY source and omits its attribution is a **blocking** validation failure.

---

## 5. Legal-review queue

| # | Question | Blocks |
|---|---|---|
| 1 | Can we license card-level FC26 data from FutDB for commercial use, and what is their right to relicense? | **All card intelligence** |
| 2 | Is the production foundation genuinely CC0, given the exact match to a GPL-3 dataset and the missing raw files? | **Current production release** |
| 3 | Does EA's IP position permit a derived contextual-recommendation product over FC26 attribute data at all? | The product |
| 4 | Is a written data agreement obtainable from FUT.GG, FUTBIN or FUTWIZ? | Card intelligence (alternative to 1) |
| 5 | What are FUTWIZ's actual terms? | Their classification |

`[POLICY]` Questions 1 and 2 are **blocking**. Question 3 is strategic and should be asked before further engineering investment, not after.
