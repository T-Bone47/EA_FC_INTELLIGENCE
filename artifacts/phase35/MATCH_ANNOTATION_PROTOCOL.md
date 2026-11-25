# EA FC INTELLIGENCE — PHASE 35
# MATCH ANNOTATION & OBSERVER TELEMETRY PROTOCOL

**Protocol Document:** MAP-2026-v1  
**Target Trial:** EXP-ST-PRESS-001  
**Applicability:** Human Tactical Observers & Video OCR Systems  

---

## 1. Pre-Match Verification Procedure

Before initiating any match in an experimental session block, the observer must record a 5-second video pan of the settings menu verifying:

1. **Title & Patch Verification:** Game version title screen displaying `FC27` and active patch identifier `Patch 1.04`.
2. **Controller Configuration:**
   - Defending Mode: `Tactical Defending` (Legacy Defending is strictly forbidden).
   - Pass Receiver Lock: `Late` or `Animation Start`.
   - Analog Sprint: `On`.
3. **Match Environment:**
   - Difficulty: `Legendary` (or `Ultimate`).
   - Half Length: `6 Minutes`.
   - Game Speed: `Normal`.
   - Injuries: `Off` (to avoid substitution distortions).
   - Bookings / Offsides: `On`.
4. **Squad Roster Invariance:**
   - Verify all 10 surrounding positions match the frozen manifest (`EXPERIMENT_ASSIGNMENT_MANIFEST.json`).
   - Verify candidate card item ID and chemistry style (Basic chemistry style applied to all cards).

---

## 2. Event Taxonomy & Operational Definitions

To guarantee objectivity across independent human observers and automated OCR pipelines, all recorded events are governed by strict operational definitions:

### 2.1 Final-Third Turnover Forced (`turnovers_forced_final_third`)
- **Spatial Criterion:** Occurs entirely within the opponent's defensive third (the final 35 meters of the pitch from the opponent's goal line).
- **Causal Criterion:** The striker directly wins a tackle, makes an interception, or applies proximity pressure ($< 2.0\text{m}$) within 3.0 seconds prior to an opponent misplaced pass, out-of-bounds clearance, or lost ball.
- **Exclusion:** Routine opponent goal kicks or unpressured clearances do NOT count as forced turnovers.

### 2.2 Box Entry Completed (`box_entries_completed`)
- **Spatial Criterion:** Ball successfully travels from outside the 18-yard penalty box to a teammate or the candidate inside the box.
- **Action Criterion:** Completed via pass, cross, dribble carry ($> 3\text{m}$ into the box), or shot rebound retained by the attacking team.
- **Exclusion:** Overhit crosses caught cleanly by the goalkeeper.

### 2.3 Transition Sprint Recovery (`transition_recoveries`)
- **Context:** Following an offensive turnover, the team shifts into defensive transition.
- **Criterion:** The striker sprints backwards behind the ball line ($> 15\text{m}$) and disrupts the opponent's counterattack (via foul, tackle, or forced sideways pass).

---

## 3. Post-Match Data Logging & Evidence Staging

1. **Full-Time Summary Screen:** Capture uncropped, 1080p minimum screenshot of:
   - Match Facts (Possession, Shots, xG, Tackles, Passing %).
   - Player Performance Tab highlighting the subject card's individual rating, minutes, and events.
2. **Telemetry Ingestion:**
   - Observer enters event tallies into the staging form or runs the automated video extractor.
   - Record created with status `SUBMITTED`.
3. **Inter-Observer Reliability (IRR):**
   - 10% of all submitted matches are independently dual-annotated by a Senior Tactical Reviewer.
   - Inter-rater agreement must satisfy Cohen's Kappa $\kappa \ge 0.85$. If $\kappa < 0.85$, the observer's session is flagged for retraining and placed in `UNDER_REVIEW`.
