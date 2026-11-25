# EA SPORTS FC 26 + FC 27 ULTIMATE TEAM DATASET ARCHITECTURE

**Document:** `FC_ULTIMATE_TEAM_DATASET_ARCHITECTURE.md`\
**Purpose:** Canonical architecture for building an evidence-backed
FC26 + FC27 Ultimate Team dataset\
**Primary Builder:** Claude\
**Independent Auditor / Secondary Data Engineer:** GLM-5.3 Flash\
**Human Authority:** Licensing, permission, and final release decisions\
**Fabrication Policy:** ZERO FABRICATION

------------------------------------------------------------------------

## 1. Purpose

Build a real, evidence-backed, card-level EA SPORTS FC Ultimate Team
dataset for FC26 and FC27 that can later support a Player/Card
Intelligence system.

The recommendation engine comes later. Data acquisition, identity,
provenance, validation, and version isolation come first.

## 2. Canonical hierarchy

``` text
Real Football Player
        |
        v
Game Player
        |
        +---- FC26
        |
        +---- FC27
        |
        v
Ultimate Team Card
        |
        v
Card Version
        |
        +-- Attributes
        +-- Positions
        +-- PlayStyles
        +-- PlayStyles+
        +-- Roles
        +-- Market Observations
```

A player is not a card. One real player can have separate FC26/FC27
game-player records and multiple cards in each version.

## 3. Non-negotiable rules

1.  **Zero fabrication.** Unknown data stays `NULL`/`UNKNOWN` with a
    reason.
2.  **FC26/FC27 version wall.** Never transfer ratings, attributes,
    cards, PlayStyles, Roles, prices, or mechanics between versions.
3.  **Evidence first.** Important production fields must trace back to
    source observations.
4.  **Public does not mean licensed.** Access and reuse rights are
    separate questions.
5.  **Fail closed.** Unclear evidence or rights never silently become
    approved.
6.  **No bypassing restrictions.** No CAPTCHA, paywall, authentication,
    rate-limit, anti-bot, robots, or other access-control circumvention.

## 4. Two-model architecture

``` text
                    DATA SOURCES
                         |
             +-----------+-----------+
             |                       |
             v                       v
        CLAUDE                    GLM-5.3
     PRIMARY BUILDER           FLASH AUDITOR
             |                       |
             +-----------+-----------+
                         |
                         v
                  EVIDENCE LEDGER
                         |
                         v
                  CANONICAL DATASET
                         |
                         v
                     GLM AUDIT
                         |
                         v
               CLAUDE RECONCILIATION
                         |
                         v
                    FINAL DATASET
```

### Claude owns

-   architecture
-   source-research coordination
-   ingestion design
-   canonical schema
-   identity resolution
-   normalization
-   provenance
-   conflict resolution
-   integration
-   final reconciliation and release candidate

Claude must verify GLM findings against evidence rather than accepting
them automatically.

### GLM-5.3 Flash owns

-   independent source discovery
-   dataset/schema inspection
-   processing and validation scripts
-   duplicate detection
-   FC26/FC27 contamination detection
-   missingness/provenance audits
-   suspicious-record detection
-   adversarial audit of Claude's dataset

During independent discovery, GLM should not initially receive Claude's
conclusions.

### Human owns

-   accepting terms
-   provider outreach
-   permission decisions
-   commercial/redistribution approval
-   final production release

## 5. Source ledger

Create `SOURCE_LEDGER.csv` with:

``` text
source_id
source_name
source_url
game_version
data_type
player_data
game_player_data
ut_card_data
card_ids
attributes
detailed_attributes
positions
playstyles
playstyles_plus
roles
prices
historical_prices
api_available
download_available
authentication_required
automation_allowed
bulk_access
redistribution_allowed
commercial_use
derived_use
license_status
access_status
legal_status
evidence_url
evidence_notes
decision
discovered_by
last_verified
```

Source status values:

`VERIFIED | PARTIAL | UNVERIFIED | UNKNOWN | BLOCKED`

Unknown must never silently become allowed.

## 6. Storage layers

``` text
EA_FC_ULTIMATE_TEAM_DATASET/
├── FC26/
│   ├── raw/
│   ├── processed/
│   ├── schemas/
│   ├── provenance/
│   └── validation/
├── FC27/
│   ├── raw/
│   ├── processed/
│   ├── schemas/
│   ├── provenance/
│   └── validation/
├── reports/
├── collaboration/
├── DATASET_MANIFEST.json
└── README.md
```

Raw source files are immutable. Every acquired artifact records source,
URL, retrieval time, file size, SHA256, game version, and license
status.

## 7. Canonical entities and core files

Entities: `RealPlayer`, `GamePlayer`, `UTCard`, `CardVersion`,
`CardAttribute`, `CardPosition`, `CardPlayStyle`, `CardRole`,
`MarketObservation`, `Club`, `League`, `Nation`, `Source`,
`SourceObservation`, `FieldProvenance`, and `Conflict`.

Core files:

``` text
players.csv
game_players.csv
cards.csv
card_versions.csv
card_attributes.csv
card_positions.csv
card_playstyles.csv
card_roles.csv
card_market.csv
clubs.csv
leagues.csv
nations.csv
player_aliases.csv
source_provenance.csv
field_provenance.csv
conflict_report.csv
duplicate_report.csv
missingness_report.csv
validation_report.csv
```

## 8. Card identity

`cards.csv` should support:

``` text
card_id
game_version
player_id
game_player_id
card_version_id
card_name
card_type
rarity
overall_rating
release_date
expiry_date
preferred_position
source_id
source_card_id
```

Multiple cards for the same player must remain distinct. Never equate
player-row count with card count.

## 9. Attributes, positions, PlayStyles and Roles

`card_attributes.csv`:

``` text
card_id
game_version
attribute_name
attribute_value
source_id
source_record_id
verified
```

`card_positions.csv`:

``` text
card_id
game_version
position
position_type
source_id
verified
```

`card_playstyles.csv`:

``` text
card_id
game_version
playstyle
playstyle_plus
source_id
source_record_id
verified
```

`card_roles.csv`:

``` text
card_id
game_version
role
role_level
position
source_id
source_record_id
verified
```

Do not infer positions, PlayStyles, PlayStyles+, or Roles from
real-world reputation, OVR, attributes, or model knowledge.

## 10. Market observations

`card_market.csv`:

``` text
card_id
game_version
platform
price
currency
observed_at
source_id
source_record_id
```

Prices are timestamped observations, not permanent card metadata.

## 11. Provenance

`field_provenance.csv`:

``` text
entity_type
entity_id
field_name
value
game_version
source_id
source_record_id
source_url
retrieved_at
verification_status
```

Required chain:
`Canonical field -> Source observation -> Original source`.

## 12. Conflicts and identity resolution

Never silently overwrite disagreements. Create `conflict_report.csv`
with:

``` text
entity
field
source_a
value_a
source_b
value_b
resolution
resolution_reason
```

Resolution states: `RESOLVED | UNRESOLVED | PENDING_HUMAN_REVIEW`.

Maintain separate `real_player_id`, `game_player_id`, `card_id`,
`card_version_id`, and `source_record_id`. Never merge records solely
because names are similar.

## 13. Source observations vs canonical records

Multiple observations can represent one canonical card:

``` text
Source A observation ---+
Source B observation ---+--> Canonical Card X
Source C observation ---+
```

Preserve all observations and provenance.

## 14. Synthetic-data firewall

Synthetic fixtures may exist only in test areas such as
`tests/fixtures/`. They must never enter processed, production, or
release datasets.

## 15. Mandatory validation

Automate:

-   version isolation
-   synthetic firewall
-   card uniqueness
-   player identity consistency
-   attribute bounds
-   missingness
-   provenance coverage
-   duplicate detection
-   conflict detection
-   market timestamps
-   no-fabrication checks

Any cross-version contamination is a release blocker.

## 16. Coverage and completeness

Measure separately:

``` text
player coverage
game-player coverage
card coverage
attribute coverage
PlayStyle coverage
PlayStyle+ coverage
Role coverage
price coverage
provenance coverage
```

Never report player coverage as card coverage.

Distinguish:

``` text
discovered_universe
accessible_universe
verified_universe
canonical_universe
```

All counts must be measured.

## 17. Release gates

A production-ready claim requires:

``` text
G1  Source access verified
G2  Usage rights verified
G3  Game version verified
G4  Card identity verified
G5  Provenance available
G6  No synthetic records
G7  Conflicts resolved or quarantined
G8  Duplicate checks passed
G9  Version isolation passed
G10 Missingness reported
G11 Data manifest generated
G12 Validation suite passed
```

Failed mandatory gates prevent a production-ready claim.

## 18. Claude ↔ GLM handoff

Claude to GLM:

``` text
HANDOFF_TO_GLM.md
DATASET_SNAPSHOT.json
SOURCE_LEDGER.csv
DATASET_MANIFEST.json
```

GLM to Claude:

``` text
GLM_AUDIT_REPORT.md
GLM_SOURCE_DISCOVERIES.csv
GLM_CONFLICT_QUEUE.csv
GLM_VALIDATION_RESULTS.csv
GLM_PROVENANCE_AUDIT.csv
```

GLM findings use:
`CONFIRMED_ERROR | LIKELY_ERROR | UNVERIFIED | FALSE_POSITIVE`.

Claude verifies each significant finding, fixes confirmed issues,
rejects unsupported findings, documents disputes, reruns validation, and
versions the next release.

## 19. Conflict-resolution priority

When Claude and GLM disagree, do not majority-vote:

``` text
Primary/authorized evidence
        ↓
Direct source observation
        ↓
Verified downloadable dataset
        ↓
Secondary corroborated source
        ↓
Unverified claim
        ↓
Model inference
```

Model inference cannot establish production data.

## 20. Versioned reference distributions

Future statistical distributions must be version and universe specific:

``` text
fc26_players
fc27_players
fc26_ut_cards
fc27_ut_cards
```

Never use FC26 distributions for FC27 or player distributions as UT-card
distributions.

## 21. Reports

Generate:

``` text
RESEARCH_REPORT.md
VERSION_COMPARISON.md
DATASET_STATISTICS.md
SOURCE_EVALUATION.csv
CONFLICT_REPORT.csv
DUPLICATE_REPORT.csv
VALIDATION_REPORT.csv
LICENSE_NOTES.md
KNOWN_LIMITATIONS.md
```

## 22. Dataset versioning

Each release records:

``` text
dataset_version
schema_version
game_version
source_snapshot
build_timestamp
manifest_hash
```

Example: `FC27_UT_DATASET_V0.1` → `FC27_UT_DATASET_V0.2` →
`FC27_UT_DATASET_V1.0`.

## 23. Future intelligence layer

The future product may use:

``` text
User
 -> Request
 -> Context
 -> Candidate Cards
 -> Eligibility
 -> Capability
 -> Tactical Fit
 -> PlayStyle/Role Modifiers
 -> Evidence/Confidence
 -> Recommendation
```

Recommendation logic must never fabricate or repair source data.

## 24. Definition of success

Success does not mean every field exists. A valid result could be:

``` text
FC27 player data = AVAILABLE
FC27 card data = PARTIAL
FC27 PlayStyles = PARTIAL
FC27 Roles = UNVERIFIED
FC27 prices = BLOCKED
```

The project fails only if unsupported data is represented as verified.

## 25. Final workflow

``` text
RESEARCH
   ↓
ACQUIRE
   ↓
INSPECT
   ↓
NORMALIZE
   ↓
PROVENANCE
   ↓
VALIDATE
   ↓
HAND OFF TO GLM
   ↓
GLM ADVERSARIAL AUDIT
   ↓
CLAUDE EVIDENCE-BASED RECONCILIATION
   ↓
REVALIDATE
   ↓
VERSION
   ↓
RELEASE
```

## 26. Final principle

Prefer:

-   10,000 verified cards over 50,000 fabricated cards.
-   `NULL + documented reason` over guessed values.
-   `PARTIAL` over false `COMPLETE`.
-   `BLOCKED` over illegally acquired data.
-   provenance over unsupported claims.

Never silently mix FC26 and FC27. Never confuse a football-player
dataset with an Ultimate Team-card dataset. Never treat public
visibility as permission for bulk reuse. Never fabricate missing data.
Never claim completeness without evidence.

**BUILD FROM EVIDENCE. PRESERVE RAW DATA. TRACK PROVENANCE. VALIDATE
EVERYTHING. FAIL CLOSED. REPORT REALITY.**
