# FC26 REFERENCE DISTRIBUTION SPEC

Supports v3 model spec §4.3. The distribution supplies `q_lo`/`q_hi` used to charge **missing** demanded attribute weight in `C_lo`/`C_hi`.

---

## 1. Requirements

| Requirement | Mechanism |
|---|---|
| Deterministic | Fixed quantile algorithm, fixed input set, fixed ordering |
| Reproducible | Regenerable byte-identically from a pinned dataset release |
| Versioned | `reference_distribution_version` string |
| Frozen | Written once; never recomputed at request time |
| Regenerated only on explicit release | Bound to a `dataset_release_id` |
| Never live during scoring | Loaded from a table, not the candidate pool |

`[MATH]` Freezing is not hygiene, it is correctness. Live quantiles reintroduce pool dependence, which v3 invariant INV-4 forbids: the same card must score identically alone or in any pool.

---

## 2. Schema

```sql
CREATE TABLE reference_distribution (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version              TEXT NOT NULL,          -- 'fc26-players-2026-03-r1'
    game_version         TEXT NOT NULL,
    universe             TEXT NOT NULL
        CHECK (universe IN ('RATINGS_SITE_PLAYERS','UT_CARDS','UT_CARDS_BASE_ONLY')),
    position_group       TEXT NOT NULL,          -- GK | DEF | MID | ATT
    attribute_code       TEXT NOT NULL,
    n                    INT  NOT NULL CHECK (n >= 50),
    p10 NUMERIC(5,2) NOT NULL, p25 NUMERIC(5,2), p50 NUMERIC(5,2) NOT NULL,
    p75 NUMERIC(5,2), p90 NUMERIC(5,2) NOT NULL,
    mean NUMERIC(5,2), stddev NUMERIC(5,2),
    dataset_release_id   TEXT NOT NULL,
    content_hash         TEXT NOT NULL,
    generated_at         TIMESTAMPTZ NOT NULL,
    frozen               BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (version, position_group, attribute_code)
);
```

`universe` is the field that prevents contradiction C-1 in the data→v3 mapping. **The engine must refuse to apply a `RATINGS_SITE_PLAYERS` distribution to a `ut_card` candidate.**

---

## 3. Algorithm

```
for each position_group g in {GK, DEF, MID, ATT}:
    for each attribute a in universe_attributes(g):
        vals = sorted([v for candidates in g if v is not NULL])
        if len(vals) < MIN_N (=50):  emit no row  ->  attribute is UNKNOWN for g
        q(p) = linear interpolation between order statistics:
               f = p*(len-1); lo = floor(f); r = f - lo
               q = vals[lo]*(1-r) + vals[lo+1]*r
content_hash = sha256(canonical_json(all rows sorted by (group, attribute)))
```

`[POLICY]` Linear interpolation is fixed by specification. Changing the estimator changes every score, so it is versioned, not configurable.

**Position groups:** `GK = {GK}` · `DEF = {CB,LB,RB}` · `MID = {CDM,CM,CAM,LM,RM}` · `ATT = {LW,RW,ST}`.

`[POLICY]` Groups rather than positions: they keep n high, and per-position quantiles would encode positional stereotypes into the missing-data penalty. GK is separate because GK attributes are a disjoint universe.

---

## 4. Is the 16,228-row foundation sufficient? — **Yes, measured**

| Group | n | Attributes with n ≥ 50 | Min n per attribute | Example: short_passing P10 / P50 / P90 |
|---|---|---|---|---|
| GK | 1,816 | **5 / 5** | 1,816 | n/a (GK outfield facades correctly NULL) |
| DEF | 5,433 | **29 / 29** | 5,433 | 50 / 62 / 72 |
| MID | 6,079 | **29 / 29** | 6,079 | 58 / 67 / 77 |
| ATT | 2,900 | **29 / 29** | 2,900 | 49 / 61 / 72 |

Every group clears the minimum by 36× or more. Sample size is **not** a constraint.

Generated content hash for the current foundation: `9eebaab261c5d300a873041dae1b511a134dbb4c573db56138f3d4beb2f93137` (92 rows: 5 GK + 29×3 outfield).

**The constraint is universe, not size.** This distribution describes ratings-site player items. `[MEASURED]` Foundation values diverge from reported in-season FC26 values by up to 11 OVR points, and a FUT card universe additionally contains TOTW, promo, Icon and Hero items that shift the upper tail. Labelling it `UT_CARDS` would be fabrication.

---

## 5. Version identifier

```
{game_version}-{universe}-{snapshot}-{revision}
    fc26-players-2026-03-r1
    fc26-cards-2026-09-r1        (does not exist)
```

Every recommendation response carries `reference_distribution_version`. A stored recommendation is replayable only if that exact row set is retrievable — so frozen rows are **never deleted**, only superseded.

---

## 6. Regeneration triggers

Permitted: a new dataset release; a new game version; a position-group definition change; a corrected estimator.

`[POLICY]` **Forbidden:** regeneration because scores "look wrong". That is fitting the reference to a desired outcome, and it would silently rewrite every historical score.

Each regeneration emits a diff report: per-attribute P10/P50/P90 deltas, and the count of candidates whose `C_lo` moves by more than 0.01. A regeneration that moves more than 30% of top-10 results requires a changelog entry, matching drift monitor DR-6.

---

## 7. Open decisions

| Decision | Default | Owner needed |
|---|---|---|
| `q_lo` percentile | P10 | **Yes** — P05 is harsher, P25 more forgiving |
| `q_hi` percentile | P90 | Yes |
| MIN_N | 50 | No — 36× headroom |
| Position grouping | 4 groups | Yes |
| Universe when card data arrives | separate distribution | No — forced by C-1 |
