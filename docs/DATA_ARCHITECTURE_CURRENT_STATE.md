# DATA ARCHITECTURE — CURRENT STATE

Forensic audit of the data layer as it exists in the repository. Every line was read from source or measured; nothing is carried over from prior reports.

**Status vocabulary:** `IMPLEMENTED` · `PARTIAL` · `STUB` · `MISSING` · `BROKEN` · `UNVERIFIED`

---

## 1. Headline

The data layer is **well-designed and largely implemented at the schema level, and almost entirely unpopulated at the card level.**

| | |
|---|---|
| Real FC26 **game_player** records | **16,228** |
| Real FC26 **UT card** records | **0** |
| Synthetic UT card fixtures | 63 (`SYNTHETIC_TEST`) |
| Real **RealPlayer** identities | **20** |
| Card prices | **0** |
| Role records | **0** |

The engine v3 contract is written for card-level evidence. The repository contains none. Everything below follows from that.

---

## 2. Component classification

### 2.1 Canonical entities

| Component | Status | Evidence |
|---|---|---|
| `game_version` | IMPLEMENTED | FC26/FC27 partition enforced at schema and engine level |
| `real_player` | **STUB** | Table + resolver exist; `data/real_player_identities.csv` holds **20 rows** against 16,228 game_players. `real_player_id` is NULL for ~99.9% of records |
| `real_player_name_variant` | IMPLEMENTED (unpopulated) | Schema + index present |
| `game_player` | IMPLEMENTED | 16,228 FC26 rows, full attribute coverage |
| `game_player_attributes` | IMPLEMENTED | 29 detail + 5 GK attributes, NULL-preserving |
| `game_player_position_secondary` | IMPLEMENTED | 10,485 / 16,228 rows carry alternates |
| `game_player_playstyle` | PARTIAL | 15,032 rows / 7,339 players (45.2% of the universe) |
| `game_player_role_familiarity` | **MISSING (schema only)** | Table exists, zero rows, no source |
| `ut_card` | **STUB** | Schema complete; zero real rows |
| `card_version` | IMPLEMENTED (unpopulated) | Content-hash versioning, correct design |
| `ut_card_attribute_override` | IMPLEMENTED (unpopulated) | |
| `ut_card_playstyle` | IMPLEMENTED (unpopulated) | |
| `ut_card_role` | IMPLEMENTED (unpopulated) | |
| `card_evolution` | IMPLEMENTED (unpopulated) | |
| `card_availability` | IMPLEMENTED (unpopulated) | |
| `card_price` | IMPLEMENTED (unpopulated) | NULL-preserving, `price_coins` never defaults to 0 |
| `card_rarity` | PARTIAL | Seeded reference only |
| `chemistry_rule` | **MISSING (schema only)** | No verified FC26 rules exist |
| `meta_signal` | IMPLEMENTED | Carries `CHECK (data_status <> 'CANONICAL')` — meta can never become canonical. Good design |

### 2.2 Evidence and provenance

| Component | Status | Evidence |
|---|---|---|
| `source_registry` | IMPLEMENTED | authority_tier, license, usage_status, legal_gate, canonical_fields |
| `source_observation` | IMPLEMENTED | raw_payload JSONB + retrieval_context |
| `claim` | IMPLEMENTED | field-level claim rows with status |
| `evidence` | IMPLEMENTED (unpopulated) | |
| `confidence_score` | IMPLEMENTED | |
| **Field-level provenance surfaced to the engine** | **MISSING** | The DB can store `source_observation_id` per attribute; the engine discards it. No attribute in any API response traces to an observation |
| `attribute_conflict_log` | **BROKEN — see 2.4** | |
| `ingestion_run` / `ingestion_quarantine` | IMPLEMENTED | Staged activation (`PENDING`/`ACTIVE`/`REJECTED`) |

### 2.3 Ingestion

| Component | Status | Evidence |
|---|---|---|
| `adapter.py` (abstract) | IMPLEMENTED | legal-gated fetch contract |
| `local_file_adapter.py` | IMPLEMENTED | CSV ingest for players and cards |
| **Remote/API adapters** | **MISSING** | No adapter exists for any live source. All ingestion is local-file |
| `normalizer.py` | IMPLEMENTED | NULL-preserving, name normalisation |
| `identity_resolver.py` | IMPLEMENTED | Conservative: exact name-form match + nationality/DOB; ambiguity → `REVIEW_REQUIRED`. Correct design, starved of reference data |
| `data_quality.py` | PARTIAL | `validate_player` / `validate_card` reject invalid rows. Coverage of the Phase-10 check list is incomplete (see `FC26_DATA_QUALITY_SPEC.md`) |
| `pipeline.py` | IMPLEMENTED | fetch → normalize → validate → persist, with rejection records |
| `forensics.py` | IMPLEMENTED | Dataset profiling with verdicts |
| `run_tracker.py` | IMPLEMENTED | |
| `meta_signals.py` | IMPLEMENTED | Research-only, DB-constrained out of canonical |

### 2.4 Defects found

**D-1 — Synthetic firewall is not enforced on the production read path. `BROKEN`**

`backend/data_access/candidate_repository.py::_load_cards` builds:

```sql
WHERE c.data_status <> 'SYNTHETIC_TEST' OR %(synth_flag)s AND c.is_synthetic = FALSE
```

SQL binds `AND` tighter than `OR`, so in production (`synth_flag = FALSE`) this reduces to:

```sql
WHERE c.data_status <> 'SYNTHETIC_TEST'
```

`is_synthetic` is **never enforced**. A row with `is_synthetic = TRUE` and `data_status = 'CANONICAL'` reaches production reads. The schema comment at `DATABASE_SCHEMA_V1.sql:301` states "production queries MUST filter is_synthetic = FALSE" — the production query does not. There is also no DB-level constraint tying the two columns together.

**D-2 — The conflict resolver can never emit `UNRESOLVED`. `BROKEN`**

`ConflictRecord.resolution` defaults to `"UNRESOLVED"` (`evidence_model.py:122`), but `ConflictResolver.resolve()` only ever emits `"SOURCE_A_WINS"` (`conflict_resolver.py:64`). When two sources have equal field-authority, equal tier and equal recency, `_rank` falls through to `source_id` — so a genuine tie is **resolved alphabetically and reported as a win**. No test asserts `UNRESOLVED`.

Downstream consequence: `confidence_v2` reads `unresolved_conflicts` from `attribute_conflict_log WHERE resolution = 'UNRESOLVED'`, which is permanently `0`. The conflict dimension of confidence is **inert by construction**.

**D-3 — Foundation provenance cannot be verified from inside the repository. `UNVERIFIED`**

`data/fc26_real_foundation/MANIFEST.json` attributes the 16,228 rows to `kaggle_justdhia_ea_fc26_player_ratings` and records sha256 hashes for three raw files (`ea_fc26_players.csv`, `ea_fc26_outfield.csv`, `ea_fc26_goalkeepers.csv`). **None of those three files is present in the repository**, so the hashes cannot be checked.

Measured independently: the foundation's 16,228 player IDs are an **exact set match** to `data_acquisition/research/flynn28_eafc26_player_database/EAFC26-Men.csv`, with 4,000/4,000 sampled OVR values agreeing. flynn28 is licensed **GPL-3** and classified `RESEARCH_ONLY` in the repo's own source matrix; justdhia is claimed CC0 and `PRODUCTION_DATA`.

The two datasets are almost certainly independent scrapes of the same EA ratings site, but **the repository cannot demonstrate which carrier produced the production bytes.** Until the raw CC0 files are restored and hashed, the production licence chain is `UNVERIFIED`.

**D-4 — Card-layer `playstyle_data_published` semantics are ambiguous. `UNVERIFIED`**

`foundation_loader` sets `playstyle_data_published` from the presence of playstyle rows. 45.2% of players have rows; 54.8% have none. On the EA ratings site, low-rated players genuinely hold no PlayStyles, so absence conflates "source published nothing" with "player has none". The engine treats the flag as "source did not publish", which is the safe reading but is not evidence-backed per row.

**D-5 — `team_fit` league comparison is a no-op. `BROKEN`** *(carried from Session 1)*

`fit_components.py:277` — `slot.league == slot.league` is always true.

### 2.5 API exposure

| Component | Status |
|---|---|
| `/api/recommendations` provenance block | PARTIAL — names sources for the version, not per-attribute |
| `data_freshness` block | PARTIAL — reports last observation timestamp; market and chemistry hard-coded to UNAVAILABLE |
| Card endpoints (`routes/cards.py`) | IMPLEMENTED but serve an empty table |
| `ENGINE_DERIVED` labelling | IMPLEMENTED |

---

## 3. What is genuinely strong

Stated plainly because it should be preserved, not rebuilt:

- **UNKNOWN discipline.** `None` is never coerced to 0, mean or default, at schema, domain and engine level. This is rare and correct.
- **FC26/FC27 wall.** Version is part of every identity preimage and every config lookup; FC27 is `NO_DATA` rather than a copy of FC26.
- **`meta_never_canonical` constraint.** Meta/popularity signals are structurally barred from canonical data.
- **Staged ingestion.** `ingestion_run` + `ingestion_quarantine` with explicit activation is the right shape for reproducible releases.
- **Conservative identity resolution.** Refusing to merge on name similarity alone is the correct default.

The problem is not the architecture. The problem is that the card layer has nothing in it, and three mechanisms that were believed to be protecting production are not.
