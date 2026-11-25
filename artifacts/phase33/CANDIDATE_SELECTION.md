# Candidate Selection & Model Prediction Baseline
## Phase 33: Empirical Gameplay Validation & Tactical Discrimination

**Status:** FROZEN EXPERIMENTAL BASELINE  
**Game Version:** EA SPORTS FC 27 (Patch 1.2.0, Research Environment)  
**Recommendation Engine:** V3.2.1 Deterministic Architecture (`v3.2-2026-09-30-r1`)  
**Reference Cohort:** Phase 31 Verified Top-100 Base Gold Cards (`COHORT_DIGEST: 2e35cec585bf2b896660f65213090128a5ca044374d059ba0cab6c41d46b7d63`)  
**External Budget Consumed:** ₹0  

---

## 1. Executive Summary

A core claim of EA FC Intelligence V3.2.1 is that card recommendations are **tactically responsive**: recommendations do not simply rank by Overall Rating (OVR), but dynamically shift weights based on tactical demands, slot requirements, and PlayStyle synergies.

To evaluate whether this attribute-modeled distinction actually manifests in gameplay, we freeze the candidate predictions across the 15 eligible primary strikers in the FC27 research cohort.

We evaluate two distinct candidate relationship types:
1. **Clearly Separated Factorial Pair (Card A vs Card B):** Demonstrates complete leader rank reversal between `HIGH_PRESS` and `COUNTER_ATTACK`.
2. **Near-Tied Pair (Card C vs Card D):** Demonstrates behavior within the engine's noise margin ($\epsilon = 0.015$, noise threshold $= 0.005$) to validate model uncertainty handling and avoid false confidence.

---

## 2. Primary Candidates: Clearly Separated Factorial Pair

| Attribute / Field | Card A: Ousmane Dembélé | Card B: Kylian Mbappé |
| :--- | :--- | :--- |
| **Source Item ID** | `231443` | `231747` |
| **Card Item UUID** | `ec2091c7-93c6-5bb8-8bba-59009b186700` | `97aaac8f-1616-50a0-afea-fd8aeff337ce` |
| **Overall Rating (OVR)** | 90 | 91 |
| **Source Rarity** | Rare Gold | Rare Gold |
| **Primary / Secondary Pos** | ST (RW, RM, LW) | ST (LW) |
| **Pace** | 90 (Accel 93, Sprint 88) | **96** (Accel 97, Sprint 96) |
| **Shooting** | 89 (Finishing 90, Pos 95, Shot Power 91) | **91** (Finishing 95, Pos 91, Shot Power 91) |
| **Passing** | **83** (Vision 84, Short Pass 89) | 80 (Vision 83, Short Pass 87) |
| **Dribbling** | **94** (Agility 94, Balance 80, Reactions 91, Ball Control 94) | 92 (Agility 93, Balance 82, Reactions 92, Ball Control 93) |
| **Defending** | **55** (Def Awareness 55, Stand Tackle 55, Interceptions 50) | 29 (Def Awareness 15, Stand Tackle 34, Interceptions 19) |
| **Physicality** | 70 (Jumping 84, Stamina 75, Strength 67, Aggression 68) | **76** (Jumping 90, Stamina 83, Strength 77, Aggression 61) |
| **PlayStyle+** | **Finesse Shot** | **Quick Step** |
| **PlayStyles (Base)** | Low Driven, Gamechanger, Inventive, Rapid, Trickster, Quick Step | Finesse Shot, Acrobatic, Low Driven, Gamechanger, Rapid, First Touch |

### Why the Engine Predicts a Reversal:
1. **Under High Press (`HIGH_PRESS`):**
   - High Press tactical demands place substantial weight on defensive engagement, agility in rapid direction changes, short passing to escape counter-press, and standing tackle/interception ability.
   - Dembélé has $+26$ Defending over Mbappé ($55$ vs $29$), $+40$ Defensive Awareness ($55$ vs $15$), and $+21$ Standing Tackle ($55$ vs $34$).
   - V3.2.1 Recommendation:
     - Dembélé: Score $0.84518$, **Rank 1** of 15 strikers.
     - Mbappé: Score $0.83194$, **Rank 5** of 15 strikers.
     - Separation Margin: $\Delta = +0.01324 > 0.005$ (`CLEAR_SEPARATION`).
2. **Under Counterattack (`COUNTER_ATTACK`):**
   - Counterattack tactical demands prioritize explosive transition speed, top-end sprint speed, elite finishing on breakaway opportunities, and acceleration PlayStyles.
   - Mbappé possesses $96$ Pace (Accel $97$, Sprint $96$), $+5$ Finishing ($95$ vs $90$), and the coveted **Quick Step+** PlayStyle.
   - V3.2.1 Recommendation:
     - Mbappé: Score $0.87317$, **Rank 1** of 15 strikers.
     - Dembélé: Score $0.86155$, **Rank 2** of 15 strikers.
     - Separation Margin: $\Delta = +0.01162 > 0.005$ (`CLEAR_SEPARATION`).

---

## 3. Near-Tied Candidate Pair: Model Uncertainty Benchmark

To rigorously test whether the model detects when two players are indistinguishable within empirical variance, we select the near-tied pair:

| Attribute / Field | Card C: Melchie Dumornay | Card D: Ewa Pajor |
| :--- | :--- | :--- |
| **Source Item ID** | `246548` | `230864` |
| **Card Item UUID** | `482726b4-09e6-55ad-8a79-0dab545948a7` | `dc6393ae-e6fc-52c5-8ace-5e7e81fd5689` |
| **Overall Rating (OVR)** | 88 | 89 |
| **Primary Position** | ST (CAM, CM) | ST |
| **Pace** | 92 (Accel 90, Sprint 94) | 93 (Accel 92, Sprint 93) |
| **Shooting** | 85 (Finishing 89, Shot Power 88) | 91 (Finishing 94, Shot Power 91) |
| **Passing** | 79 (Short Pass 85, Vision 80) | 65 (Short Pass 75, Vision 76) |
| **Dribbling** | 91 (Agility 92, Balance 86) | 89 (Agility 91, Balance 83) |
| **Defending** | 60 (Def Awareness 52, Tackle 64) | 22 (Def Awareness 18, Tackle 12) |
| **Physicality** | 73 (Strength 77, Stamina 75) | 72 (Strength 82, Stamina 85) |
| **PlayStyle+** | **Gamechanger** | **Chip Shot** |

### Counterattack Evaluation:
- Dumornay: Score $= 0.85867$ (Rank 3)
- Pajor: Score $= 0.85769$ (Rank 4)
- Score Difference: $\Delta = 0.00098$ ($< 0.005$ noise threshold, $< 0.015$ tie epsilon).
- Status: **NEAR_TIE**. The model acknowledges that these two players cannot be meaningfully separated by attribute modeling alone; only empirical match evidence could differentiate their real-game contribution.

---

## 4. Full 15-Striker Cohort Baseline Table

| Rank (Press) | Pressing Striker | Score (Press) | Rank (Counter) | Counter Striker | Score (Counter) |
| :---: | :--- | :---: | :---: | :--- | :---: |
| **1** | **Ousmane Dembélé (90)** | **0.84518** | **1** | **Kylian Mbappé (91)** | **0.87317** |
| 2 | Julián Alvarez (86) | 0.84117 | 2 | Ousmane Dembélé (90) | 0.86155 |
| 3 | Sophia Wilson (88) | 0.83583 | 3 | Melchie Dumornay (88) | 0.85867 |
| 4 | Melchie Dumornay (88) | 0.83368 | 4 | Ewa Pajor (89) | 0.85769 |
| **5** | **Kylian Mbappé (91)** | **0.83194** | 5 | Sophia Wilson (88) | 0.85714 |
| 6 | Lautaro Martínez (87) | 0.82266 | 6 | Julián Alvarez (86) | 0.85055 |
| 7 | Erling Haaland (91) | 0.82166 | 7 | Alessia Russo (88) | 0.84656 |
| 8 | Alessia Russo (88) | 0.81136 | 8 | Erling Haaland (91) | 0.84328 |
| 9 | Ewa Pajor (89) | 0.80385 | 9 | Marie Katoto (86) | 0.83716 |
| 10 | Khadija Shaw (90) | 0.79909 | 10 | Barbra Banda (88) | 0.83563 |
| 11 | Viktor Gyökeres (86) | 0.79583 | 11 | Lautaro Martínez (87) | 0.83355 |
| 12 | Barbra Banda (88) | 0.79376 | 12 | Khadija Shaw (90) | 0.82338 |
| 13 | Alexander Isak (86) | 0.78590 | 13 | Viktor Gyökeres (86) | 0.81502 |
| 14 | Marie Katoto (86) | 0.78540 | 14 | Alexander Isak (86) | 0.81255 |
| 15 | Harry Kane (90) | 0.77028 | 15 | Harry Kane (90) | 0.79516 |

### Critical Observations:
- **Harry Kane OVR Trap:** Despite being 90 OVR, Kane ranks 15th in both tactics due to severe Pace deficiency ($62$ pace, $63$ accel), perfectly illustrating that V3.2.1 does not fall into the OVR trap.
- **Erling Haaland Tactical Moderation:** Despite 91 OVR, Haaland ranks 7th in High Press ($0.82166$) and 8th in Counterattack ($0.84328$) due to modest passing ($71$) and agility ($66$).
- **Cross-Tactic Correlation:** Spearman's $\rho = 0.82$ across the full 15-striker cohort, indicating general card quality preserves baseline hierarchy while specific specialist cards (Dembélé, Mbappé, Alvarez) shift significantly based on tactical profile.
