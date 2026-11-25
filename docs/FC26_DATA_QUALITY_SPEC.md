# FC26 DATA QUALITY SPEC

---

## 1. Gate model

```
RAW  ──[G1 structural]──  STAGING  ──[G2 semantic]──  VALIDATED
                                                          │
                                              [G3 release gate]
                                                          │
                                                     PRODUCTION
```

A release passes only if **every** BLOCKING check passes. `[POLICY]` No manual override without a recorded, signed exception in the release manifest.

---

## 2. Checks

`B` = blocking · `W` = warning

### Identity and uniqueness
| ID | Check | Sev | Threshold | Current |
|---|---|---|---|---|
| Q-01 | Every row has a source-local id | B | 100% | **PASS** 16,228/16,228 |
| Q-02 | `(source_id, game_version, source_entity_id)` unique | B | 0 dupes | **PASS** |
| Q-03 | `canonical_card_id` unique per version | B | 0 collisions | **N/A** — no cards |
| Q-04 | No canonical card created without a discriminator | B | 100% | **FAILS BY DESIGN** — see identity spec §4.1 |
| Q-05 | Identity status distribution reported | W | — | 20 RealPlayers vs 16,228 GamePlayers |

### Attributes
| ID | Check | Sev | Threshold | Current |
|---|---|---|---|---|
| Q-10 | Every attribute ∈ [1,99] **or NULL** | B | 100% | **PASS** |
| Q-11 | No UNKNOWN → 0/mean/median/default anywhere | B | 100% | **PASS** |
| Q-12 | GK rows: GK attributes present | B | ≥ 99% | **PASS** 1,816/1,816 |
| Q-13 | Outfield rows: detail attributes present | W | ≥ 95% | **PASS** 14,412/14,412 |
| Q-14 | Facade vs detail internal consistency | W | report | **NOT IMPLEMENTED** |
| Q-15 | Card attributes never inherited from base player | B | 100% | **N/A** — no cards |

### Positions, PlayStyles, Roles
| ID | Check | Sev | Threshold | Current |
|---|---|---|---|---|
| Q-20 | `position_primary` ∈ version position set | B | 100% | **PASS** |
| Q-21 | Alternates ∈ position set, ≠ primary | B | 100% | 10,485 populated |
| Q-22 | PlayStyle names ∈ ingested vocabulary | B | 100% | **PASS** — 36 names |
| Q-23 | PlayStyle+ ⊆ PlayStyles held | B | 100% | **PASS** |
| Q-24 | PS+ count ≤ version cap **for that scope** | B | scope-aware | **PASS** for `player_base` (max 1, n=119) |
| Q-25 | Role names ∈ role vocabulary | B | 100% | **N/A** — zero role rows |
| Q-26 | `playstyle_data_published` reflects source publication, not row absence | B | 100% | **UNVERIFIED** — defect D-4 |

### Reference integrity
| ID | Check | Sev | Current |
|---|---|---|---|
| Q-30 | Club/league/nation resolve to reference tables | B | PARTIAL |
| Q-31 | League ↔ club consistency | W | NOT IMPLEMENTED |
| Q-32 | Nation values normalised | W | PARTIAL |

### Version firewall
| ID | Check | Sev | Threshold | Current |
|---|---|---|---|---|
| Q-40 | Every row carries an explicit `game_version` | B | 100% | **PASS** |
| Q-41 | Dataset is version-homogeneous, or explicitly partitioned | B | 100% | **PASS** — rovnez is uniformly `fifa_version=26` |
| Q-42 | No FC25 artifacts (schema, date, vocabulary) | B | 0 | **PASS** — but see Q-43 |
| Q-43 | Source vocabulary matches the version's mechanics | B | 100% | **FAIL for rovnez** — carries `player_traits`/`player_tags` (pre-FC mechanic), no PlayStyles. Correctly held RESEARCH_ONLY |
| Q-44 | Snapshot date recorded and within the release window | B | 100% | **FAIL** — foundation is a March 2026 snapshot with no staleness gate |

### Synthetic firewall
| ID | Check | Sev | Threshold | Current |
|---|---|---|---|---|
| Q-50 | Zero synthetic rows readable by production queries | B | 0 | **FAIL** — see §5 |
| Q-51 | `is_synthetic` ⟺ `data_status='SYNTHETIC_TEST'` | B | 100% | **NOT ENFORCED** — no constraint |
| Q-52 | Synthetic fixtures confined to test paths | B | 100% | PARTIAL |
| Q-53 | Production release contains zero synthetic rows | B | 0 | enforced at release only |

### Provenance
| ID | Check | Sev | Threshold | Current |
|---|---|---|---|---|
| Q-60 | Every canonical field has ≥1 `field_provenance` row | B | 100% | **FAIL** — table does not exist |
| Q-61 | Every observation has retrieval context + licence at retrieval | B | 100% | PARTIAL |
| Q-62 | Raw source files hash-verifiable | B | 100% | **FAIL** — raw files absent |
| Q-63 | Source licence GREEN at release time | B | 100% | **UNVERIFIED** |

### Conflict
| ID | Check | Sev | Current |
|---|---|---|---|
| Q-70 | Conflict rate reported per field | W | **0 by construction** — one source |
| Q-71 | `UNRESOLVED` conflicts serve UNKNOWN | B | **FAIL** — unreachable code path |
| Q-72 | Losing claims retained | B | PARTIAL |

### Freshness and missingness
| ID | Check | Sev | Threshold | Current |
|---|---|---|---|---|
| Q-80 | Snapshot age ≤ `MAX_SNAPSHOT_AGE_DAYS` | B | **needs owner** | **~6 months** |
| Q-81 | Price observation age ≤ 14 days for value claims | B | — | N/A |
| Q-82 | Missingness per field reported and compared to prior release | B | Δ ≤ 5pp | first release |
| Q-83 | Coverage κ distribution reported per position group | B | — | **measured — see §4** |

---

## 3. UNKNOWN discipline

`[POLICY]` Absolute, no exceptions:

- UNKNOWN is `NULL`. Never `0`, `-1`, `""`, `"N/A"`, mean, median, mode or a neighbour's value.
- UNKNOWN never becomes a validation failure by itself — absence of evidence is not evidence of absence.
- UNKNOWN propagates: any derived value computed from an UNKNOWN input is UNKNOWN, unless the derivation explicitly excludes it and records the exclusion.
- A value imputed for **any** reason must be stored in a separate column and may never be served as observed.

`[VERIFIED]` The existing codebase honours this at schema, domain and engine level. It is the strongest property in the project.

---

## 4. Measured coverage — and why the κ gate is currently untestable

v3 defines evidence coverage `κ = Σ w_a over published demanded attributes`. Measured on the real foundation, λ = 0.6:

| Position / profile | n | \|D\| | P01 | P10 | P50 | P90 | P99 |
|---|---|---|---|---|---|---|---|
| CM / POSSESSION | 10,275 | 15 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| CM / PRESSING | 10,275 | 17 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| CB / LOW_BLOCK | 6,324 | 15 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| ST / COUNTER_ATTACK | 5,241 | 19 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| RW / CROSSING | 5,241 | 16 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| LB / BUILD_UP | 6,324 | 18 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| GK / BUILD_UP | 1,816 | 5 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

Evaluable share at each threshold:

| κ_min | 0.40 | 0.50 | 0.60 | 0.70 | 0.80 | 0.90 |
|---|---|---|---|---|---|---|
| all seven cells | 100% | 100% | 100% | 100% | 100% | 100% |

**κ = 1.00 for effectively every candidate.** Two conclusions, both important:

1. `[MEASURED]` The v3 coverage gate is **inert on current data**. Any κ_min in [0, 1.0) produces identical behaviour. The mechanism is untested against the conditions it was designed for.
2. `[POLICY]` **κ_min cannot be chosen on evidence today.** Session 1 asked for a measured decision; the honest answer is that the decision must wait for card-level data, because card-level partial publication is the only thing that generates κ < 1.

Until then κ_min = 0.60 is a placeholder with no empirical support, and should be labelled as such rather than presented as calibrated.

*(Implementation note: `Σw` can land at 0.9999999999999998, so κ comparisons must use a tolerance. A strict `κ >= 1.0` test reported 0% for one cell purely from float residue.)*

---

## 5. The synthetic firewall failure

`[MEASURED — BLOCKING]` `candidate_repository._load_cards` builds:

```sql
WHERE c.data_status <> 'SYNTHETIC_TEST' OR %(synth_flag)s AND c.is_synthetic = FALSE
```

`AND` binds tighter than `OR`. In production `synth_flag = FALSE`, so the predicate reduces to `data_status <> 'SYNTHETIC_TEST'` and `is_synthetic` is **never checked**.

A row with `is_synthetic = TRUE, data_status = 'CANONICAL'` is served to production. No DB constraint prevents that combination, and `scripts/ingest_synthetic_cards.py` writes synthetic rows into the same table production reads.

Today the blast radius is zero — there are no real cards, and the 63 fixtures carry `SYNTHETIC_TEST`. The moment either changes, fabricated cards enter recommendations.

**Fix (P0):** add the `synthetic_status_consistent` CHECK constraint, add the `ut_card_production` view, route all production reads through the view, and add a test that asserts a `(is_synthetic=TRUE, data_status='CANONICAL')` row is unreachable.
