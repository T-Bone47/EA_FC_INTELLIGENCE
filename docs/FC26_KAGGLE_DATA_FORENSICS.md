# FC26 Kaggle Data Forensics

**Retrieval date:** 2026-09-14  
**Method:** Kaggle's ordinary public CLI/API only. No CAPTCHA, authentication, rate-limit, or access-control bypass was used.

## Dataset inventory

| Dataset | Version | License | Files inspected | Rows | Outcome |
| --- | ---: | --- | --- | ---: | --- |
| `flynn28/eafc26-player-database` | 2 | GPL 3 | `EAFC26-Men.csv`, `EAFC26-Women.csv`, `EAFC26.csv` | 16,228 / 1,645 / 17,873 | Research-only forensic source |
| `rovnez/fc-26-fifa-26-player-data` | 3 | CC BY 4.0; author states research/education scope | `FC26_20250921.csv` | 18,405 | Research-only forensic source |
| `justdhia/ea-sports-fc-26-player-ratings` | 1 | CC0 | `ea_fc26_outfield.csv`, `ea_fc26_goalkeepers.csv`, `ea_fc26_players.csv` | 14,412 / 1,816 / 16,228 | Active canonical player source |
| `flynn28/complete-ea-fc26-rating-cards-database` | 1 | CC BY 4.0 | public manifest sample | image files | No structured-card ingestion |

## Player-source findings

### Flynn28 player database

The three CSVs share a 59-column schema. They include face stats, all required detailed outfield attributes, all five GK attributes, position, alternative positions, physical data, a combined `play style` field, and `card`.

- Each file has a unique `ID` per row; no duplicate IDs were observed.
- The men file is an exact 16,228-ID match to the current CC0 canonical raw universe.
- The combined file adds 1,645 women players, but GPL governance means this is useful for coverage research only—not a canonical production expansion.
- `card` is non-empty for all 17,873 combined rows and is an EA rating-card `.webp` image URL keyed by player ID. It does not prove card variants or provide a card schema.

### Rovneź player data

The 110-column snapshot has 18,405 unique `player_id` values and includes detailed attacking, skill, movement, power, mentality, defending, and goalkeeper fields. It carries comma-separated `player_positions`, so it is useful for alternate-position validation. Its 16,122-ID overlap with the canonical raw universe confirms broad correlation but does not establish field authority.

The dataset also has `value_eur`, `wage_eur`, and `release_clause_eur`. These are real-football economics, not verified FUT market prices; they are intentionally excluded from budget/value scoring.

### Active CC0 source

The canonical source's split shape remains materially important:

- `ea_fc26_outfield.csv` supplies detailed outfield attributes for 14,412 players.
- `ea_fc26_goalkeepers.csv` supplies dedicated GK attributes for 1,816 players.
- GK face statistics in a combined rendering are not used as outfield ability. For a goalkeeper, outfield details remain `UNKNOWN`, preserving honest GK scoring.
- `playStyles` and `playStylesPlus` are separately published and retained as base versus plus tiers.

## Card-source finding

The 593 MB rating-card dataset's public file manifest lists `cards/*.webp` files, not structured records. Image names are not durable card identities and contain duplicate-name suffixes. There is no observed card ID, variant attributes, price history, chemistry, roles, or Evolutions data. The existing card model receives no production rows from this source.

See the machine-readable results in `data_access_reports/FC26_KAGGLE_SOURCE_MATRIX.json`, `FC26_KAGGLE_SCHEMA_COMPARISON.json`, and `FC26_KAGGLE_CARD_ANALYSIS.json`.
