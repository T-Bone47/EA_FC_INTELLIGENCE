# PHASE 21 PLAYER LICENSE REVIEW

Kept explicitly separate from the UT card provider question, per the mandate: two independent gates, `PLAYER_DATA_LICENSE` and `UT_CARD_DATA_LICENSE`, each clearing (or not) for its own scope.

## Player-source identity

Production foundation: 16,228 FC26 game_player rows, attributed to `kaggle_justdhia_ea_fc26_player_ratings`, claimed CC0 1.0 Public Domain.

## Dataset license (as claimed)

CC0 1.0 Public Domain, per the dataset's own listing.

## Upstream license (the actual concern)

The claimed CC0 dataset is an **exact 16,228/16,228 ID-set match** to `flynn28/eafc26-player-database`, a **GPL-3, RESEARCH_ONLY-classified** dataset, with 4,000/4,000 sampled OVR values identical between the two. Both are almost certainly independent scrapes of the same EA ratings website, but this has never been proven.

## Raw-file availability

The original ingestion manifest (`MANIFEST.json`) records sha256 hashes for three raw files (`ea_fc26_players.csv`, `ea_fc26_outfield.csv`, `ea_fc26_goalkeepers.csv`) attributed to the CC0 dataset. **None of the three files is present in the repository.** The hashes therefore cannot be independently verified — this is the single concrete, closeable gap.

## Transformation chain

Kaggle CC0 dataset (claimed) → `scripts/ingest_fc26_foundation.py` → `game_player`/`game_player_attributes` tables → `field_provenance` (585,560 rows, linked to one `source_observation` record per ingestion batch).

## Redistribution rights

CC0 grants unrestricted redistribution — **if the CC0 attribution is genuine**. This is exactly what remains unverified.

## Unresolved evidence

Re-retrieve the three named raw files from the original Kaggle listing and verify their hashes against `MANIFEST.json`. This is a bounded, concrete task (re-download, hash, compare) rather than an open-ended legal question — unlike the UT card provider situation, which requires a third party's explicit permission the project cannot obtain unilaterally.

## Separate gate status

```
PLAYER_DATA_LICENSE = UNVERIFIED   (unchanged this session; concrete, closeable gap)
UT_CARD_DATA_LICENSE = BLOCKED     (see PHASE_21_RELEASE_DECISION.md; requires third-party permission)
```

These two gates are checked independently in `data_license_gate.py` (`check_license_gate("fc26-players-2026-09-r1")` for the player scope) and are never merged into one combined status — a human resolving the player-licence gap does not, and should not, imply anything about the card-provider question, and vice versa.
