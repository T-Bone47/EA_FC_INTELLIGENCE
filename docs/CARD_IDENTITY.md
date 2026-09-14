# CARD IDENTITY — Phase 3 (§4/§24)

A card is **never** identified by name + OVR.

## 1. Two-layer identity

| layer | value | rule |
|---|---|---|
| row identity | `ut_card.id` | `uuid5(ID_NAMESPACE, "ut_card\|{source_id}\|{game_version}\|{source_card_id}")` — deterministic, idempotent; UNIQUE(source_id, source_card_id, game_version_id) blocks duplicates at the DB level |
| canonical identity | `ut_card.canonical_card_id` | `uuid5(ID_NAMESPACE, "canonical_card\|{VERSION}\|{player_key}\|{kind}\|{POSITION}\|{release_group}")` where `kind = card_type or rarity_code or 'BASE'` and `player_key = "sp:{source_player_ref}"` |

`ID_NAMESPACE = 6f1e2d3c-4b5a-4968-8776-655443322110`.

Properties (all unit-tested in `backend/tests/test_card_model.py::TestCardIdentity`):

* same card via two sources ⇒ same canonical id, different row ids (no
  duplicate merges, cross-source resolution possible);
* Gold base vs TOTW vs promo wave of the same player ⇒ distinct canonical ids;
* FC26 vs FC27 can never collide (version is in both preimages);
* same name+OVR, different players ⇒ different ids (name is not an input).

## 2. Identity resolution status (§24)

`ut_card.identity_status`:

* **RESOLVED** — the source published a stable player reference
  (`source_player_id`/`player_ref`); canonical id computed; `identity_rule`
  records the exact rule used.
* **REVIEW_REQUIRED** — ambiguous evidence (set by identity resolver during
  ingestion; goes to review, never silently into production).
* **UNRESOLVED** — no stable player reference: `canonical_card_id` stays
  NULL. **We do not guess identity from names.** Unresolved cards never
  silently merge with anything; they remain individually addressable by row id.

## 3. Duplicates & conflicts

* Re-ingesting the same file: row id + content hash make it a no-op
  (`card_version` UNIQUE(ut_card_id, content_hash)).
* Two sources disagreeing on a field: resolved by authority
  (`conflict_resolver.py`): field-canonical source first, then authority tier
  (1 highest), then recency, then deterministic source_id tie-break; every
  disagreement produces a `ConflictRecord` (logged, surfaced in confidence) —
  lower authority never silently overwrites, equal authority never silently
  picks without recording the conflict.
* Malformed identity (missing `source_card_id`) is **rejected at
  normalization** — no invented ids.

## 4. Version identity

`CardVersion.deterministic_id` + `content_hash` give every attribute/PlayStyle
state of a card its own identity; upgrades append versions (previous
`is_current` closed with `valid_to`) — history is never overwritten, and
"current" is always exactly one row per card (integrity-checked after every
activation).
