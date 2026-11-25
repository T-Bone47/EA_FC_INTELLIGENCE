# FC26 CONFLICT RESOLUTION SPEC

---

## 1. Audit of the current resolver — it is broken

`backend/services/conflict_resolver.py`

**What works `[IMPLEMENTED]`:** claims filtered to production-permitted sources; ranking by field-authority → authority tier → recency → deterministic tiebreak; conflicts recorded rather than silently overwritten.

**What is broken `[BROKEN]`:**

`ConflictRecord.resolution` defaults to `"UNRESOLVED"` (`evidence_model.py:122`), but `resolve()` only ever emits `"SOURCE_A_WINS"` (`conflict_resolver.py:64`). **There is no code path that produces `UNRESOLVED`.**

When two sources tie on field-authority, tier and recency, `_rank` falls through to `source_id` — so a genuine, unresolvable disagreement is settled **alphabetically by source name** and reported as a clean win.

**Downstream consequence:** `confidence_v2.authority_factor` reduces confidence based on `unresolved_conflicts`, read from `attribute_conflict_log WHERE resolution = 'UNRESOLVED'`. Since nothing ever writes that value, the count is permanently `0` and **the conflict dimension of confidence is inert by construction.** The system displays a conflict-awareness feature that cannot fire.

No test asserts `UNRESOLVED`.

---

## 2. Required resolution model

Five inputs, in strict precedence:

1. **Field authority** — is this source canonical *for this field*? (EA is authoritative for attributes; a market site is not. A market site may be authoritative for price.)
2. **Source authority tier** — 1 official … 5 community discussion.
3. **Field reliability** — per (source, field) empirical agreement rate, measured over time. `[MISSING]` — needs building.
4. **Source scope** — does the source claim to cover this entity class at all?
5. **Identity confidence** — a conflict between two observations that may not be the same card is an *identity* problem, not a value problem. Resolve identity first.

---

## 3. Decision procedure

```
resolve(entity, field, claims):
    usable = [c for c in claims if c.source.production_permitted]
    if not usable:                       -> NO_PERMITTED_CLAIM ; value = UNKNOWN

    if identity_confidence(entity) < IDENTITY_MIN:
                                         -> IDENTITY_UNRESOLVED ; value = UNKNOWN

    if all values agree (after normalisation):
                                         -> RESOLVED (agreement) ; confidence unchanged

    ranked = sort by (field_authority, tier, field_reliability, recency)

    if ranked[0] strictly dominates ranked[1] on the first differing key:
                                         -> RESOLVED (authority) ; value = winner
                                            confidence reduced by CONFLICT_PENALTY
                                            losing claims stored as SUPERSEDED

    if values are numeric and |a - b| <= FIELD_TOLERANCE[field]:
                                         -> RESOLVED (within tolerance) ; value = higher-authority
                                            flagged MINOR_DISAGREEMENT

    otherwise:                           -> UNRESOLVED ; value = UNKNOWN
                                            both claims stored as CONFLICT
```

`[POLICY]` The last branch is the one that does not exist today and is the whole point: **equal authority + material disagreement ⟹ the field is UNKNOWN.** Not source A, not an average, not the higher number.

`[MATH]` Under v3 this is safe: UNKNOWN reduces evidence coverage κ and widens the interval, and `score_lo` ranking guarantees it can only lower a candidate's rank. The system has somewhere honest to put uncertainty, which is exactly why it can afford to admit it.

---

## 4. Statuses

| Status | Value served | Confidence | Stored |
|---|---|---|---|
| `RESOLVED_AGREEMENT` | agreed value | unchanged | winner |
| `RESOLVED_AUTHORITY` | higher authority | reduced | winner + SUPERSEDED losers |
| `RESOLVED_TOLERANCE` | higher authority | reduced | both, flagged |
| `CONFLICT` | **UNKNOWN** | reduced | all claims |
| `UNRESOLVED` | **UNKNOWN** | reduced | all claims |
| `IDENTITY_UNRESOLVED` | **UNKNOWN** | reduced | all claims, entity flagged |
| `NO_PERMITTED_CLAIM` | **UNKNOWN** | reduced | claims retained, not served |

---

## 5. Field tolerances `[POLICY — needs an owner]`

| Field class | Tolerance | Rationale |
|---|---|---|
| Detail attributes | **0** | Integers. 91 ≠ 92. A one-point tolerance would quietly erase real disagreement |
| Facades (PAC/SHO/…) | 0 | Derived, but published |
| `overall_rating` | 0 | |
| `price_coins` | **±10%** | Genuinely time-varying; two observations minutes apart legitimately differ |
| `release_date` | ±1 day | Timezone artifacts |
| Categorical (position, type, club, nation, PlayStyle) | exact after normalisation | |

The worked example in the mandate — source A says 91, source B says 92 — resolves as: **not within tolerance → authority decides if one source is canonical for attributes, otherwise UNRESOLVED and the value is UNKNOWN.**

---

## 6. Field reliability learning `[P2]`

Once two permitted sources overlap, record per `(source, field)`: observations, agreements, disagreements, authority-loss rate. Feed the agreement rate into ranking as input 3.

`[POLICY]` Reliability is **measured, never assumed**. It requires ≥ 1,000 overlapping observations per (source, field) before it may influence ranking. Below that it is reported and ignored.

`[CURRENT]` Not possible — only one production-permitted source exists, so there is nothing to conflict with. The resolver is untested against real disagreement.

---

## 7. Required tests

| ID | Assertion |
|---|---|
| CR-1 | Equal authority + material disagreement ⟹ `UNRESOLVED`, value UNKNOWN — **fails today** |
| CR-2 | `UNRESOLVED` rows reach `attribute_conflict_log` and are counted by `confidence_v2` — **fails today** |
| CR-3 | Alphabetical `source_id` never decides a material conflict — **fails today** |
| CR-4 | Losing claims are stored `SUPERSEDED`, never discarded |
| CR-5 | Price conflict within ±10% resolves; beyond it does not |
| CR-6 | Identity-unresolved entities never reach conflict resolution |
| CR-7 | Resolution is deterministic and replayable from stored claims |
