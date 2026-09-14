# FC26 Kaggle Field Authority

## Authority rule

Canonical values are chosen field by field, never by bulk overwrite. The active CC0 source is eligible for production after existing validation. GPL, CC BY with stated research scope, and unclear sources remain isolated as comparison evidence. A disagreement is a conflict to record and resolve—not permission to pick the most convenient number.

| Field group | Active authority | Research comparison sources | Production rule |
| --- | --- | --- | --- |
| Identity, name, club, league, nation | Justdhia CC0 | Flynn28, Rovneź | Resolve using the existing identity/conflict path; preserve source observations. |
| Overall and six face stats | Justdhia CC0 | Flynn28, Rovneź | Do not overwrite active values from restricted sources. |
| Detailed outfield attributes | Justdhia CC0 outfield split | Flynn28, Rovneź | Use only real published values; missing remains `UNKNOWN`. |
| GK diving/handling/kicking/positioning/reflexes | Justdhia CC0 goalkeeper split | Flynn28, Rovneź | GK-specific source shape wins; never infer outfield ability from GK facades. |
| Primary/alternate positions | Justdhia CC0 | Flynn28 `Alternative positions`, Rovneź `player_positions` | Research sources can identify discrepancies; promotion requires clearance. |
| Preferred foot, weak foot, skill moves, height, weight, age | Justdhia CC0 | Flynn28, Rovneź | Preserve existing source conversion and provenance. |
| PlayStyles / PlayStyle+ | Justdhia CC0 separate fields | Flynn28 combined `play style`; Rovneź does not expose observed PlayStyle fields | Never infer a plus tier from a combined style list. |
| Roles | No source | None observed | `INSUFFICIENT_EVIDENCE`; never invent official roles. |
| FUT price/value | No verified source | Rovneź football-economics fields are non-equivalent | `VALUE_UNAVAILABLE`, `BUDGET_UNVERIFIED`. |
| Card variants | No structured source | Flynn28 image URLs and image archive only | No card records created. |
| Chemistry / Evolutions | No verified source | None | Remain unknown and optional. |

## Conflict handling

1. Store the incoming source observation with source ID, retrieval date, license, and field payload.
2. Run identity resolution before comparing player fields.
3. Apply the existing field-level authority tier and usage-status gate.
4. Preserve unresolved conflicts as evidence and lower confidence where relevant; never convert a conflict into an invented value.
5. Re-evaluate a research source only after an explicit clearance decision, without rewriting history.

## Scope conclusion

The active foundation fully supports the player engine's required detailed attribute, GK, position, and PlayStyle layers for 16,228 FC26 players. Research sources add validation breadth and a visible women-universe gap, but do not change production scope under the approved governance policy.
