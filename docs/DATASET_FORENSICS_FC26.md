# DATASET FORENSICS — FC26 REAL FOUNDATION
**Audit date:** 2026-09-14 · **Auditor:** autonomous agent · **Status:** PASSED → integrated as PRODUCTION_DATA

## 1. Source identification

| Field | Value |
|---|---|
| Dataset | "EA Sports FC 26 Player Ratings" |
| Author | justdhia (Kaggle) |
| URL | https://www.kaggle.com/datasets/justdhia/ea-sports-fc-26-player-ratings |
| Upstream | https://www.ea.com/games/ea-sports-fc/ratings (official EA SPORTS FC Ratings page) |
| License | **CC0 1.0 — Public Domain** (commercial use + redistribution permitted) |
| Game version | FC26 (men's ratings universe, source-documented scope) |
| Source scrape date | March 2026 (per dataset description) |
| Retrieval date | 2026-09-14, Kaggle public dataset download endpoint, HTTP 200, 2,719,331 bytes |
| Access method | Public download; **no authentication bypass, no scraping of EA, no private endpoints** |
| Usage status | PRODUCTION_DATA (Tier-3 carrier of Tier-1 official field values) |

Raw files (sha256 recorded in `data/fc26_real_foundation/MANIFEST.json`):
`ea_fc26_players.csv` (16,228×60 combined), `ea_fc26_outfield.csv` (14,412×56), `ea_fc26_goalkeepers.csv` (1,816×26).

## 2. Match against handoff-documented foundation

The handoff PDF documents the original foundation. Every checkable figure matched:

| Metric | Handoff | This acquisition | Verdict |
|---|---|---|---|
| Player records | 16,228 | 16,228 | MATCH |
| GK count | 1,816 | 1,816 | MATCH |
| Position distribution | CB 2,950 / ST 2,233 / CM 1,976 / GK 1,816 / RB 1,273 / CDM 1,267 / LB 1,210 / LM 971 / CAM 963 / RM 902 / RW 338 / LW 329 | identical, all 12 | MATCH |
| PlayStyle rows | 15,032 | 15,032 | MATCH |
| Unique players w/ PlayStyles | 7,339 | 7,339 | MATCH |
| Unique PlayStyles | 36 | 36 | MATCH |
| base / plus tier split | 14,913 / 119 | 14,913 / 119 | MATCH |

Conclusion: this is the same upstream source dataset the original foundation was built from (or an
identical-content re-scrape). Re-acquisition is legitimate and no data needed to be invented.

## 3. Forensic checks (per §12 requirements)

| Check | Result |
|---|---|
| Row/col counts | 16,228 rows; 60 cols combined / 56 outfield / 26 GK |
| Data types | numeric attrs parse cleanly; no mixed-type columns after trim |
| Duplicate IDs | 0 (all three files) |
| Duplicate players (name, DOB) | 0 |
| Split-vs-combined ID consistency | sets identical |
| Null percentages | commonName 85.5% (expected: nickname-style display names), alternatePositions 35.4%, playStyles 54.8%, playStylesPlus 99.3% |
| Numeric ranges | OVR 47–91; PAC 30–97; SHO 21–92; PAS 25–92; DRI 29–93; DEF 15–90; PHY 32–91; gk attrs 2–90; stamina 12–95; reactions 30–94 — all plausible |
| Invalid values | none detected (1–99 gate on all attribute columns) |
| Game-version contamination | none — 100% FC26 |
| Synthetic records | none — all rows trace to EA ratings page scrape |
| Suspicious values | GK facade mirroring (see finding F1) |
| Timestamps | source scrape: March 2026; retrieval recorded |
| PlayStyle+ ⊆ global PlayStyle set | TRUE |
| PlayStyle+ per player | max 1 across 119 holders → evidence-based FC26 cap = 1 (player scope) |

## 4. Findings materially affecting normalization

**F1 — GK facade mirroring (quality issue in combined file).** For GK rows, `pac/sho/pas/dri/def/phy` in
`ea_fc26_players.csv` are mirrors of GK attributes (Donnarumma: pac=90=gkDiving, sho=83=gkHandling,
pas=70=gkKicking, dri=90=gkReflexes, phy=87=gkPositioning; def is EA's UI value). These are EA's display
mapping, not outfield ability. **Action:** canonical foundation stores GK rows with outfield facades/details
= NULL (UNKNOWN) and the 5 true GK attributes; split files used as base.

**F2 — GK gap RESOLVED.** Handoff §20 reported missing GK technical attributes. This acquisition includes
`gkDiving/gkHandling/gkKicking/gkPositioning/gkReflexes` for all 1,816 GKs (real, source-published).
GK position-specific attribute weighting can therefore run on real data.

**F3 — Outfield GK attributes.** Outfield rows carry EA-published GK attrs (range 2–37, median 10).
Retained (real published values) but semantically unused for outfield fit.

**F4 — preferredFoot coding.** Values {1: 12,282, 2: 3,946}. Mapping 1→Right, 2→Left verified against
known players (Messi=2/left, Salah=2/left, Haaland=2/left, De Bruyne=1/right, Kane=1/right).
Evidence class: SUPPORTED. Canonicalized to strings.

**F5 — Date formats.** Combined file uses US-locale dates; split files ISO. ISO retained.

**F6 — Name variants.** Some players appear under EA-registered long names (e.g. Bernardo Silva =
"Bernardo Mota Carvalho e Silva"; Cristiano Ronaldo = "C. Ronaldo dos Santos Aveiro"). Motivates
`real_player_name_variant` usage and conservative identity resolution.

**F7 — Ambiguity case reproduced.** Bare "Ronaldo" matches ≥4 distinct real players in the foundation
(C. Ronaldo dos Santos Aveiro, Ronaldo Martínez, Ronaldo Dejesús, Ronaldo Deaconu) → identity resolver
routes to REVIEW_REQUIRED, matching the handoff's documented behavior.

## 5. Canonical outputs

- `data/fc26_real_foundation/players.csv` — 16,228 × 60 (handoff's 51-col schema + additive:
  `game_version`, `position_type`, `source_rank`, `dribbling_detail`, `gk_diving…gk_reflexes`).
- `data/fc26_real_foundation/player_playstyles.csv` — 15,032 long-format rows (player_id, playstyle, tier, game_version).
- `data/fc26_real_foundation/MANIFEST.json` — hashes, provenance, policy notes.

## 6. Remaining data gaps (NOT fabricated)

Women's FC26 universe; real UT card universe (variants/rarity/Roles/Evolutions); live market prices;
FC27 anything; operational chemistry rule data. All remain UNKNOWN / out of scope until legitimate
sources are available.
