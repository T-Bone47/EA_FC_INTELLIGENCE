# EA FC INTELLIGENCE — PHASE 34B
# EMPIRICAL EVIDENCE STATUS & STAGING BASELINE REPORT

**Status:** Certified Empirical Audit  
**Accepted Production Gameplay Records:** 0 (Frozen Staging Baseline)  
**Research Staging Snapshot:** `SNAPSHOT = fc27-` + `SOURCE.sha`  
**Card Item Release:** `fc27-card-items-local-r1` (9,962 staged cards)  
**Phase 31 Frozen Cohort:** `TOP_100_BASE_CARDS.csv` (100 candidates)  

---

## 1. Executive Summary & Epistemic Honesty Constraint

In accordance with EA FC Intelligence Core Rule #3 (*"DO NOT fabricate data or conceal NO_DATA states"*), this document records the exact state of empirical gameplay evidence in the system.

**Current Production Gameplay Observations:** **0 Accepted Records**  
There are currently zero verified gameplay match records admitted into the production serving database. All tactical synergy calculations, channel evaluations, and counterfactuals operate exclusively on:
1. Pinned owner-supplied card releases (`fc27-card-items-local-r1`).
2. Frozen V3.2.1 deterministic attribute-demand matching algorithms.
3. Explicit tactical rules categorized transparently by epistemic status.

---

## 2. Evidence Classification Hierarchy

Every rule and conclusion in Phase 34B carries one of two explicit classifications:

### A. `EMPIRICALLY_SUPPORTED`
- **Definition:** The rule threshold and tactical effect are grounded in controlled match observations from Phase 33 Pilot Protocols (`CONTROLLED_TEST_PROTOCOL.md` and `MATCH_OBSERVATION_SCHEMA.md`).
- **Active Rule Example:** `RULE-HP-FWD-DEF`
  - *Context:* `HIGH_PRESS`
  - *Target Positions:* `ST`, `CF`, `LW`, `RW`, `LF`, `RF`
  - *Attribute:* `defending < 40`
  - *Friction Penalty:* `-0.025` (-2.5% to Whole-XI Index)
  - *Empirical Basis:* Phase 33 Experiment 001 recorded that pressing forwards with $\ge 50$ defending (e.g. Dembélé, 55 Defending) produced $+2.0$ tackles won per 90 and $+2.0$ interceptions per 90 compared to low-defending finishers (e.g. Mbappé, 29 Defending), who were repeatedly bypassed during high-block trapping sequences.

### B. `MODELED_HEURISTIC`
- **Definition:** The rule threshold is derived from theoretical tactical demands and deterministic weight profiles, but has not yet undergone 20+ controlled human-annotated match sessions in Phase 33 infrastructure.
- **Active Rules:**
  - `RULE-CB-PACE-ACCEL`: Central defender acceleration $< 65$ under high defensive line.
  - `RULE-WB-STA-WORK`: Fullback stamina $< 75$ under counter-attacking overlap demands.
  - `RULE-CM-PAS-SHORT`: Central midfielder short passing $< 80$ under possession buildup.
  - `RULE-WP-FLK-CRO`: Wide flank crossing $< 75$ under wing-play delivery requirements.

---

## 3. Staging and Ingestion Pipeline Status

1. **Owner-Supplied Archives:**
   - `archive (5).zip` (`fc27_players_database.csv`, SHA-256 `c472b9b3...`, 9,962 rows) verified.
   - Digest: `7ea30715c31dc9effc47452b61b7a64b875efa852684d34bb6292d82c18780c1`.
2. **Reference Distribution:**
   - UT Cards reference distribution `fc27-card-items-local-r1` checksum `54e60afe5b60c4db28a425b266153c5dd320773887188a5bac821268526239ff` frozen.
3. **Missing Data & Fail-Open Convention:**
   - Goalkeeper cards: Goalkeeper items lack outfield attribute distributions and are scored exclusively under dedicated goalkeeper models. Primary locked goalkeepers are preserved as unscored in outfield synergy channels without penalty.
   - Unobserved Card Attributes: If a third-party card export omits individual attributes (e.g. agility or crossing), the rule fails open to `missing_data_limitation` with 0 friction deduction. Fabricated values are strictly prohibited.

---

## 4. Path to Empirical Validation Phase 35

To transition `MODELED_HEURISTIC` rules into `EMPIRICALLY_SUPPORTED` status:
1. Conduct Phase 33 Experiment 002 (Midfield Pivot Resistance under Pressing).
2. Collect 40 controlled match logs adhering to `MATCH_OBSERVATION_SCHEMA.md`.
3. Require paired-difference $t$-test significance ($p < 0.05$) before altering friction penalties.
