# FC26 PROVENANCE SPEC

The system must be able to answer, for any number it shows:

> "Why do we believe this card has 92 short passing?"

with a trace, not an assurance.

---

## 1. Required trace

```
Recommendation (request_id, engine_version, config_version)
  └─ candidate (canonical_card_id / game_player_id)
      └─ attribute contribution (short_passing, weight, s_eff, contribution)
          └─ field_provenance row
              └─ source_observation (retrieved_at, retrieval_context, raw_payload)
                  └─ source_registry (source_id, license, authority_tier, usage_status)
                      └─ dataset release (release_id, checksum)
```

`[CURRENT STATE]` Links 1–2 exist. Link 3 exists in the v3 `ScoringContext` design but carries no observation id. Links 4–6 exist in the database and are **not connected to attributes**. The chain is broken in the middle.

---

## 2. `field_provenance`

```sql
CREATE TABLE field_provenance (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_entity_type TEXT NOT NULL,      -- 'game_player' | 'ut_card' | 'card_version'
    canonical_entity_id   UUID NOT NULL,
    canonical_field       TEXT NOT NULL,      -- 'short_passing', 'card_type', 'price_coins', ...
    source_id             TEXT NOT NULL REFERENCES source_registry(source_id),
    source_record_id      TEXT,
    source_observation_id UUID NOT NULL REFERENCES source_observation(id),
    observed_value        TEXT,               -- as published, before normalisation
    normalized_value      TEXT,               -- after normalisation; NULL = UNKNOWN
    observed_at           TIMESTAMPTZ,
    retrieved_at          TIMESTAMPTZ NOT NULL,
    source_authority      INT NOT NULL,
    resolution_status     TEXT NOT NULL
        CHECK (resolution_status IN ('ACCEPTED','SUPERSEDED','REJECTED','CONFLICT','UNRESOLVED')),
    resolution_reason     TEXT NOT NULL,
    dataset_release_id    TEXT NOT NULL,
    UNIQUE (canonical_entity_type, canonical_entity_id, canonical_field,
            source_id, source_observation_id)
);
CREATE INDEX ix_fp_entity_field ON field_provenance
    (canonical_entity_type, canonical_entity_id, canonical_field);
CREATE INDEX ix_fp_unresolved ON field_provenance (resolution_status)
    WHERE resolution_status IN ('CONFLICT','UNRESOLVED');
```

`[POLICY]` **Every** competing claim gets a row, including losers (`SUPERSEDED`) and rejects. A provenance table that stores only winners cannot explain a decision — it can only restate it.

`observed_value` is kept **as published**, before normalisation, so a normaliser bug is diagnosable years later without re-fetching.

---

## 3. Mandatory provenance fields

Every one of these must have a `field_provenance` row before the value may be served:

`overall_rating` · all six facades · all 29 detail attributes · all 5 GK attributes · `position_primary` · alternate positions · PlayStyles base · PlayStyles plus · Roles · role familiarity · `card_type` · `rarity` · `club` · `league` · `nation` · `price_coins` · `release_date` · `card_version` · evolution linkage

`[POLICY]` A canonical field with no provenance row is a **bug, not a default**. Validation fails the release rather than serving an unattributed number.

---

## 4. Engine integration

The v3 `ScoringContext.per_attribute` entry gains one field:

```
{ attribute, weight, value|UNKNOWN, s_eff, contribution_lo, contribution_hi,
  constraint, source_observation_id }     <-- currently absent
```

One added field closes the whole chain, because `source_observation_id` already joins to source, licence, retrieval time and release.

`[POLICY]` Two API surfaces:
- **default** — provenance summary: which sources, how fresh, how many conflicts;
- **`?provenance=full`** — the complete per-attribute trace.

The second is what makes the product auditable. It is also what an FC26 patch-day investigation needs.

---

## 5. Retrieval context

`source_observation.retrieval_context` must record the retrieval as it actually happened:

```json
{
  "method": "kaggle_dataset_download | local_file | licensed_api",
  "source_url": "...",
  "dataset_version": "...",
  "file_name": "ea_fc26_players.csv",
  "file_sha256": "...",
  "retrieved_at": "2026-09-14T00:00:00Z",
  "retrieved_by": "scripts/build_foundation.py",
  "license_at_retrieval": "CC0-1.0",
  "legal_gate": "GREEN",
  "operator": "..."
}
```

`license_at_retrieval` is essential: licences change. A dataset that was CC0 when retrieved and is CC BY today does not retroactively taint an existing release, but only if we recorded which it was.

---

## 6. The current provenance failure

`[MEASURED]` `MANIFEST.json` records sha256 hashes for `ea_fc26_players.csv`, `ea_fc26_outfield.csv` and `ea_fc26_goalkeepers.csv`. **None of the three files is in the repository.** The hashes therefore prove nothing — they are unverifiable assertions.

Meanwhile the production foundation is an **exact ID-set match** to a GPL-3 `RESEARCH_ONLY` dataset that *is* in the repository, with 4,000/4,000 sampled OVR values identical.

The two are almost certainly independent scrapes of the same EA ratings site. But the repository cannot demonstrate that, and "almost certainly" is not a licence chain.

**Required before any production release:**
1. Re-retrieve the CC0 raw files and verify the recorded hashes, **or** mark the foundation `PROVENANCE_UNVERIFIED` and block release.
2. Store the raw files, or a manifest of them with a retrievable location, inside the release artifact.
3. Emit `field_provenance` rows for all 16,228 × ~35 attribute values during ingestion.
