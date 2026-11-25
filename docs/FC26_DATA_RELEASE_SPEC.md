# FC26 DATA RELEASE SPEC

A release is the unit of reproducibility. A recommendation is auditable only if the exact dataset behind it can be reconstructed.

---

## 1. Structure

```
fc26-data/
  release_2026_09_16_r1/
    dataset_manifest.json          <- the contract
    dataset_statistics.json
    checksums/SHA256SUMS
    raw/                           <- source bytes AS RETRIEVED, unmodified
      <source_id>/<file>           <- currently MISSING: the fatal gap today
    canonical/
      players.csv  game_players.csv  cards.csv  card_versions.csv
      card_attributes.csv  card_positions.csv  card_playstyles.csv
      card_roles.csv  card_market.csv
    provenance/
      source_provenance.csv  field_provenance.csv
    reports/
      validation_report.csv  conflict_report.csv
      duplicate_report.csv   missingness_report.csv
    reference_distributions/
      fc26-players-2026-03-r1.json
```

`[POLICY]` `raw/` is mandatory. Without the retrieved bytes a hash proves nothing — which is precisely the position the current foundation is in: `MANIFEST.json` records sha256 for three files that are **not in the repository**.

Where a licence forbids redistributing raw bytes, `raw/` stores a retrieval descriptor (URL, dataset version, file name, hash, retrieved_at, licence at retrieval) instead — enough to re-fetch and verify, without republishing.

---

## 2. `dataset_manifest.json`

```json
{
  "release_id": "fc26-2026-09-16-r1",
  "game_version": "FC26",
  "generated_at": "...",
  "generator": { "script": "...", "git_commit": "...", "python": "3.12.x" },
  "supersedes": "fc26-2026-03-14-r1",
  "sources": [{
      "source_id": "...", "dataset_version": "...",
      "license_at_retrieval": "CC0-1.0", "legal_gate": "GREEN",
      "retrieved_at": "...", "files": [{"name": "...", "sha256": "...", "rows": 0}],
      "raw_bytes_included": true
  }],
  "outputs": [{ "path": "canonical/players.csv", "sha256": "...", "rows": 16228, "columns": 60 }],
  "reference_distributions": [
    { "version": "fc26-players-2026-03-r1", "universe": "RATINGS_SITE_PLAYERS", "content_hash": "..." }
  ],
  "entity_counts": { "real_player": 20, "game_player": 16228, "ut_card": 0,
                     "card_version": 0, "card_price": 0, "card_role": 0 },
  "validation": { "status": "PASS|FAIL", "blocking_failures": [], "warnings": [] },
  "scope_flags": { "player_scope_enabled": true, "card_scope_enabled": false,
                   "card_scope_blocked_reason": "no permitted card-level source" },
  "synthetic": { "rows_in_release": 0, "firewall_verified": true },
  "policy_notes": []
}
```

`scope_flags` is load-bearing: it is how the API knows it may not serve card intelligence, encoded in the data rather than in a code branch someone can forget.

---

## 3. Pipeline

```
SOURCE ADAPTER        legal gate checked BEFORE fetch; BLOCKED -> stop, record
      ↓
RAW OBSERVATION       bytes stored/descriptor; source_observation row; hash
      ↓
NORMALIZATION         types, names, positions, vocabularies; UNKNOWN preserved;
                      observed_value retained pre-normalisation
      ↓
IDENTITY RESOLUTION   RESOLVED | REVIEW_REQUIRED | UNRESOLVED; never guessed
      ↓
CONFLICT RESOLUTION   RESOLVED* | CONFLICT | UNRESOLVED -> UNKNOWN
      ↓
CANONICAL ENTITY      staged, not yet production
      ↓
FIELD PROVENANCE      one row per claim, winners AND losers
      ↓
VALIDATION            blocking + warning gates
      ↓
VERSIONED RELEASE     manifest, checksums, reports
      ↓
REFERENCE DISTRIBUTION  frozen, universe-tagged
      ↓
ACTIVATION            explicit; ingestion_run.activation_status PENDING -> ACTIVE
      ↓
V3 ENGINE
```

`[IMPLEMENTED]` adapter, normalise, identity, staging, activation. `[MISSING]` raw retention, field provenance, conflict `UNRESOLVED`, release packaging.

---

## 4. Operational semantics

| Property | Rule |
|---|---|
| **Idempotency** | Re-ingesting identical bytes is a no-op. Enforced by `(source, version, entity, content_hash)` |
| **Incremental** | New/changed rows create new `card_version` rows; unchanged rows untouched |
| **Re-ingestion** | Never destructive. Corrections supersede; they do not overwrite |
| **Source refresh** | New `source_observation` rows; conflict resolution re-run; previous values retained |
| **Historical preservation** | No release is deleted. `card_price` and `card_version` are append-only |
| **Rollback** | Point `ACTIVE` at the prior `release_id`. Data is never deleted to roll back |
| **Schema migration** | Numbered, forward-only, additive. Releases record the schema version they were built under |

---

## 5. Release gates

**Blocking:** all `B` checks in the quality spec pass · zero synthetic rows · every served field has provenance · every source `GREEN` or written-permission · raw bytes or descriptors present and hash-verified · reference distribution generated and universe-tagged · manifest complete · counts match the canonical files.

**Warning:** missingness delta > 5pp vs prior release · conflict rate delta > 2pp · snapshot age approaching the staleness limit.

---

## 6. Current release readiness

| Gate | Status |
|---|---|
| Raw bytes present and hash-verified | **FAIL** — three files named in `MANIFEST.json` are absent |
| Field provenance | **FAIL** — table does not exist |
| Licence chain verified | **UNVERIFIED** — production foundation is an exact ID match to a GPL-3 `RESEARCH_ONLY` dataset |
| Synthetic firewall | **FAIL** — see quality spec §5 |
| Conflict `UNRESOLVED` path | **FAIL** — unreachable |
| Reference distribution | **PASS (player universe only)** |
| Entity counts | PASS |
| Card scope | **DISABLED** — no source |

**A compliant release cannot be cut today.** Four blocking gates fail, and all four are fixable without new data.
