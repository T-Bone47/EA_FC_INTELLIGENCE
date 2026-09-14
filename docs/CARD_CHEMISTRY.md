# CARD CHEMISTRY — Phase 3 (§15/§16)

**Status for FC26: NO VERIFIED RULES ⇒ chemistry is UNKNOWN everywhere.**
This is a deliberate, tested product decision: no chemistry score is claimed
until verified game rules exist. Nothing is approximated "to make squad
optimization work".

## 1. Two strictly separate concepts

| concept | what it is | where |
|---|---|---|
| **Structural fit** | factual overlaps between a candidate and squad members: same club / league / nation | `chemistry_service.structural_fit` — always computed from verified link facts; labelled `kind: STRUCTURAL_FIT, is_chemistry: false` |
| **Chemistry score** | the game's actual chemistry contribution | `chemistry_service.chemistry_assessment` — computed ONLY from `chemistry_rule` rows with `verified=TRUE, data_status=CANONICAL`; zero rows ⇒ `CHEMISTRY_UNKNOWN`, score `None` |

The UI and API never render structural links as chemistry. The engine's
`team_fit` component likewise uses verified link facts only (v2.1 behaviour
unchanged).

## 2. Rule application architecture (data-driven, dormant)

When verified rules are ingested, scoring activates with **no code change**:
each rule contributes per matching structural link
(`contribution.points`, `per_link`, `cap`) subject to `threshold.min_members`;
evidence lists every applied rule with matched-link counts. The numbers come
from the rule rows (authorized source) — the engine invents none. Rules can be
injected in tests (`rules=` parameter) which is how the application logic is
proven (`test_card_value_chemistry.py::TestChemistryHonesty`).

## 3. Squad optimization prep (§16)

`chemistry_service.squad_impact(candidate, squad, version, replaced, utility_delta)`:

* verdict IMPROVES / DOES_NOT_IMPROVE / NEUTRAL **only** from the engine's
  contextual utility delta (real re-evaluations, e.g. the existing
  replacement analysis / `squads/{id}/recommend-replacement`);
* no utility delta ⇒ verdict UNKNOWN ("cannot judge squad improvement from
  ratings alone");
* unknown chemistry is explicitly *not counted for or against*;
* structural links reported alongside, labelled.

Buy/replace decisions therefore rest on verified contextual utility, never on
fake chemistry.

## 4. Ingestion path for future rules

`chemistry_rule(game_version_id, rule_code, link_type, contribution,
threshold, verified, evidence_note, source_observation_id, data_status)` —
populated only through the gated ingestion pipeline from an
OFFICIAL/AUTHORIZED source; the count of verified rules is part of the card
cache watermark, so activating rules invalidates caches immediately (§31).
