# DATASET FORENSICS REPORT — Phase 3

Generated 2026-09-14T11:39:31.754737+00:00 by `backend/ingestion/forensics.py` (deterministic, read-only).

Policy (§23): every dataset is forensically analysed BEFORE import. REJECT-level findings block
activation (`scripts/activate_card_dataset.py` aborts); REVIEW findings are flagged and quarantined
rows are persisted with reasons. No FC26 UT promo-card dataset was adopted — see
docs/CARD_DATA_ACQUISITION.md for the per-source legal research.

Note on identity columns: the justdhia player files key rows by `id` (EA database id);
## Summary

| dataset | rows | verdict | findings |
|---|---|---|---|
| ea_fc26_outfield.csv (justdhia, CC0 — ADOPTED player source) | 14412 | REVIEW | 1 |
| ea_fc26_goalkeepers.csv (justdhia, CC0 — ADOPTED player source) | 1816 | REVIEW | 1 |
| fictional_ut_cards.csv (SYNTHETIC_TEST fixtures — firewalled) | 63 | REVIEW | 2 |

the synthetic card fixtures key by `source_card_id`. Forensics is run with the dataset's
actual identity column — a REJECT for `missing_identity` below would be a real finding.

## ea_fc26_outfield.csv (justdhia, CC0 — ADOPTED player source)


* entity: `player` · game_version: `FC26`
* analyzed_at: 2026-09-14T11:39:31.888902+00:00
* rows: **14412** · columns: 56
* verdict: **REVIEW**

## Metrics

| metric | value |
|---|---|
| duplicate_rate | 0.0 |
| identity_coverage | 1.0 |
| attribute_completeness | 1.0 |
| timestamp_coverage | None |

## Findings

* **REVIEW** `no_timestamp_column` — dataset carries no observed/retrieved timestamp column — freshness will be UNKNOWN

Raw stats: `json` block below.

```json
{
  "entity": "player",
  "game_version": "FC26",
  "analyzed_at": "2026-09-14T11:39:31.888902+00:00",
  "row_count": 14412,
  "column_count": 56,
  "columns": [
    "acceleration",
    "age",
    "aggression",
    "agility",
    "alternatePositions",
    "balance",
    "ballControl",
    "birthdate",
    "commonName",
    "composure",
    "crossing",
    "curve",
    "def",
    "defensiveAwareness",
    "dri",
    "dribbling",
    "finishing",
    "firstName",
    "freeKickAccuracy",
    "headingAccuracy",
    "height",
    "id",
    "interceptions",
    "jumping",
    "lastName",
    "leagueName",
    "longPassing",
    "longShots",
    "nationality",
    "overallRating",
    "pac",
    "pas",
    "penalties",
    "phy",
    "playStyles",
    "playStylesPlus",
    "position",
    "positionType",
    "positioning",
    "preferredFoot",
    "rank",
    "reactions",
    "sho",
    "shortPassing",
    "shotPower",
    "skillMoves",
    "slidingTackle",
    "sprintSpeed",
    "stamina",
    "standingTackle",
    "strength",
    "team",
    "vision",
    "volleys",
    "weakFootAbility",
    "weight"
  ],
  "null_rate": {
    "acceleration": 0.0,
    "age": 0.0,
    "aggression": 0.0,
    "agility": 0.0,
    "alternatePositions": 0.2725,
    "balance": 0.0,
    "ballControl": 0.0,
    "birthdate": 0.0,
    "commonName": 0.8533,
    "composure": 0.0,
    "crossing": 0.0,
    "curve": 0.0,
    "def": 0.0,
    "defensiveAwareness": 0.0,
    "dri": 0.0,
    "dribbling": 0.0,
    "finishing": 0.0,
    "firstName": 0.0,
    "freeKickAccuracy": 0.0,
    "headingAccuracy": 0.0,
    "height": 0.0,
    "id": 0.0,
    "interceptions": 0.0,
    "jumping": 0.0,
    "lastName": 0.0,
    "leagueName": 0.0,
    "longPassing": 0.0,
    "longShots": 0.0,
    "nationality": 0.0,
    "overallRating": 0.0,
    "pac": 0.0,
    "pas": 0.0,
    "penalties": 0.0,
    "phy": 0.0,
    "playStyles": 0.5378,
    "playStylesPlus": 0.9924,
    "position": 0.0,
    "positionType": 0.0,
    "positioning": 0.0,
    "preferredFoot": 0.0,
    "rank": 0.0,
    "reactions": 0.0,
    "sho": 0.0,
    "shortPassing": 0.0,
    "shotPower": 0.0,
    "skillMoves": 0.0,
    "slidingTackle": 0.0,
    "sprintSpeed": 0.0,
    "stamina": 0.0,
    "standingTackle": 0.0,
    "strength": 0.0,
    "team": 0.0,
    "vision": 0.0,
    "volleys": 0.0,
    "weakFootAbility": 0.0,
    "weight": 0.0
  },
  "duplicate_rate": 0.0,
  "identity_coverage": 1.0,
  "range_violations": {},
  "attribute_completeness": 1.0,
  "invalid_positions": {},
  "unknown_playstyles": {},
  "timestamp_coverage": null,
  "findings": [
    {
      "severity": "REVIEW",
      "code": "no_timestamp_column",
      "message": "dataset carries no observed/retrieved timestamp column \u2014 freshness will be UNKNOWN",
      "count": 1
    }
  ],
  "verdict": "REVIEW"
}
```


## ea_fc26_goalkeepers.csv (justdhia, CC0 — ADOPTED player source)


* entity: `player` · game_version: `FC26`
* analyzed_at: 2026-09-14T11:39:32.161385+00:00
* rows: **1816** · columns: 26
* verdict: **REVIEW**

## Metrics

| metric | value |
|---|---|
| duplicate_rate | 0.0 |
| identity_coverage | 1.0 |
| timestamp_coverage | None |

## Findings

* **REVIEW** `no_timestamp_column` — dataset carries no observed/retrieved timestamp column — freshness will be UNKNOWN

Raw stats: `json` block below.

```json
{
  "entity": "player",
  "game_version": "FC26",
  "analyzed_at": "2026-09-14T11:39:32.161385+00:00",
  "row_count": 1816,
  "column_count": 26,
  "columns": [
    "age",
    "alternatePositions",
    "birthdate",
    "commonName",
    "firstName",
    "gkDiving",
    "gkHandling",
    "gkKicking",
    "gkPositioning",
    "gkReflexes",
    "height",
    "id",
    "lastName",
    "leagueName",
    "nationality",
    "overallRating",
    "playStyles",
    "playStylesPlus",
    "position",
    "positionType",
    "preferredFoot",
    "rank",
    "skillMoves",
    "team",
    "weakFootAbility",
    "weight"
  ],
  "null_rate": {
    "age": 0.0,
    "alternatePositions": 1.0,
    "birthdate": 0.0,
    "commonName": 0.8678,
    "firstName": 0.0,
    "gkDiving": 0.0,
    "gkHandling": 0.0,
    "gkKicking": 0.0,
    "gkPositioning": 0.0,
    "gkReflexes": 0.0,
    "height": 0.0,
    "id": 0.0,
    "lastName": 0.0,
    "leagueName": 0.0,
    "nationality": 0.0,
    "overallRating": 0.0,
    "playStyles": 0.6289,
    "playStylesPlus": 0.9945,
    "position": 0.0,
    "positionType": 0.0,
    "preferredFoot": 0.0,
    "rank": 0.0,
    "skillMoves": 0.0,
    "team": 0.0,
    "weakFootAbility": 0.0,
    "weight": 0.0
  },
  "duplicate_rate": 0.0,
  "identity_coverage": 1.0,
  "range_violations": {},
  "invalid_positions": {},
  "unknown_playstyles": {},
  "timestamp_coverage": null,
  "findings": [
    {
      "severity": "REVIEW",
      "code": "no_timestamp_column",
      "message": "dataset carries no observed/retrieved timestamp column \u2014 freshness will be UNKNOWN",
      "count": 1
    }
  ],
  "verdict": "REVIEW"
}
```


## fictional_ut_cards.csv (SYNTHETIC_TEST fixtures — firewalled)


* entity: `card` · game_version: `FC26`
* analyzed_at: 2026-09-14T11:39:32.166480+00:00
* rows: **63** · columns: 18
* verdict: **REVIEW**

## Metrics

| metric | value |
|---|---|
| duplicate_rate | 0.0 |
| identity_coverage | 1.0 |
| attribute_completeness | 0.9955 |
| playstyle_coverage | 1.0 |
| price_coverage | 1.0 |
| timestamp_coverage | None |
| version_consistency | `{"FC26": 63}` |
| data_statuses | `{"SYNTHETIC_TEST": 63}` |

## Findings

* **REVIEW** `playstyle_plus_cap` — 1 rows list more than one PlayStyle+ (cap is version-specific — verify)
* **REVIEW** `no_timestamp_column` — dataset carries no observed/retrieved timestamp column — freshness will be UNKNOWN

Raw stats: `json` block below.

```json
{
  "entity": "card",
  "game_version": "FC26",
  "analyzed_at": "2026-09-14T11:39:32.166480+00:00",
  "row_count": 63,
  "column_count": 18,
  "columns": [
    "card_id",
    "data_status",
    "defending",
    "dribbling",
    "game_version",
    "overall_rating",
    "pace",
    "passing",
    "physicality",
    "player_name",
    "playstyles",
    "playstyles_plus",
    "position",
    "price_coins",
    "rarity",
    "shooting",
    "source",
    "source_card_id"
  ],
  "null_rate": {
    "card_id": 0.0,
    "data_status": 0.0,
    "defending": 0.0,
    "dribbling": 0.0,
    "game_version": 0.0,
    "overall_rating": 0.0159,
    "pace": 0.0,
    "passing": 0.0,
    "physicality": 0.0,
    "player_name": 0.0,
    "playstyles": 0.0,
    "playstyles_plus": 0.6667,
    "position": 0.0,
    "price_coins": 0.0,
    "rarity": 0.0,
    "shooting": 0.0,
    "source": 0.0,
    "source_card_id": 0.0
  },
  "duplicate_rate": 0.0,
  "identity_coverage": 1.0,
  "version_consistency": {
    "FC26": 63
  },
  "range_violations": {},
  "attribute_completeness": 0.9955,
  "invalid_positions": {},
  "unknown_playstyles": {},
  "playstyle_coverage": 1.0,
  "multi_plus_rows": 1,
  "price_coverage": 1.0,
  "timestamp_coverage": null,
  "data_statuses": {
    "SYNTHETIC_TEST": 63
  },
  "findings": [
    {
      "severity": "REVIEW",
      "code": "playstyle_plus_cap",
      "message": "1 rows list more than one PlayStyle+ (cap is version-specific \u2014 verify)",
      "count": 1
    },
    {
      "severity": "REVIEW",
      "code": "no_timestamp_column",
      "message": "dataset carries no observed/retrieved timestamp column \u2014 freshness will be UNKNOWN",
      "count": 1
    }
  ],
  "verdict": "REVIEW"
}
```

