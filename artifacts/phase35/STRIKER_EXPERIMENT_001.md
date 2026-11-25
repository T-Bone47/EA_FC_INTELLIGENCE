# EA FC INTELLIGENCE — PHASE 35
# EMPIRICAL EXPERIMENTAL DESIGN: STRIKER HIGH PRESS VS COUNTERATTACK
## PROTOCOL KEY: EXP-ST-PRESS-001

**Lead Investigator:** Principal AI/ML Research Scientist & Tactical Analytics Lead  
**Engine Baseline:** V3.2.1 Frozen Deterministic Core  
**Statistical Target:** Paired Difference Hypothesis Testing Across Tactical Systems  
**Primary Endpoint:** Final-Third Turnovers Forced Per 90 (`turnovers_forced_final_third`)  
**Secondary Endpoints:** xG Generated, Shots on Target, Sprint Recoveries, Match Rating  

---

## 1. Research Question & Tactical Hypothesis

### 1.1 The Tactical Dilemma
Conventional Ultimate Team player selection is heavily biased toward Raw Overall Rating (OVR), finishing, and raw pace. Kylian Mbappé ($91$ OVR) is widely considered universally superior to Ousmane Dembélé ($86$ OVR).

However, the **V3.2.1 Deterministic Engine** posits that player utility is fundamentally **contextual and system-dependent**:
- In a **High Press** system, forward players must aggressively close passing lanes, execute counter-pressing actions, and maintain intensity throughout 90 minutes. Mbappé's low defensive workrate, lower stamina ($78$), and absence of pressing traits trigger the active tactical friction alert `RULE-HP-FWD-DEF` ($-2.5\%$ penalty).
- Consequently, V3.2.1 predicts **Dembélé outranks Mbappé** at ST in a High Press ($0.8452$ vs $0.8319$, $\Delta = +0.0132$).
- Conversely, in a **Counterattack** system, forward defensive contribution is deprecated, and Mbappé's elite sprint speed ($97$) and finishing ($90$) dominate Dembélé ($0.8842$ vs $0.8410$, $\Delta = +0.0432$).

### 1.2 Formal Hypotheses
- **$H_{1,\text{Press}}$ (High Press Concordance):** In a 4-3-3 High Press configuration, Dembélé will force significantly more final-third turnovers per 90 minutes than Mbappé:
  $$\mu_{\Delta,\text{Press}} = \mu_{\text{Dembélé}} - \mu_{\text{Mbappé}} > 0 \quad (\alpha = 0.01)$$
- **$H_{1,\text{Counter}}$ (Counterattack Concordance):** In a 4-3-3 Counterattack configuration, Mbappé will generate significantly higher expected goals (xG) and completed fast-break entries per 90 minutes than Dembélé:
  $$\mu_{\Delta,\text{Counter}} = \mu_{\text{Mbappé}} - \mu_{\text{Dembélé}} > 0 \quad (\alpha = 0.01)$$

---

## 2. Experimental Cohort & Candidate Specifications

| Attribute / Field | Candidate Arm A: Ousmane Dembélé | Candidate Arm B: Kylian Mbappé |
|:---|:---|:---|
| **Item Identifier** | `top100-022` | `top100-001` |
| **Card Version / Group** | FC27 Base Gold Rare | FC27 Base Gold Rare |
| **Official OVR** | 86 | 91 |
| **Assigned Formation Slot** | `ST` (Central Striker) | `ST` (Central Striker) |
| **Pace / Sprint Speed** | 93 / 92 | 97 / 97 |
| **Shooting / Finishing** | 79 / 78 | 90 / 92 |
| **Passing / Vision** | 84 / 85 | 80 / 82 |
| **Stamina / Defensive Workrate** | 84 / High-Medium | 78 / High-Low |
| **Pressing PlayStyles** | Relentless, Quick Step | Rapid+, Quick Step |
| **V3.2.1 High Press Score** | **0.8452** (Rank #1 in Pair) | **0.8319** (Rank #2 in Pair) |
| **V3.2.1 Counterattack Score** | 0.8410 (Rank #2 in Pair) | **0.8842** (Rank #1 in Pair) |

---

## 3. Power Analysis & Sample Size Determination

To detect a standardized paired difference effect size of Cohen's $d = 0.55$ (medium-to-large effect) with statistical power $1 - \beta = 0.85$ and two-tailed significance level $\alpha = 0.01$:

$$N \ge \frac{(z_{\alpha/2} + z_{\beta})^2}{d^2} + \frac{z_{\alpha/2}^2}{2}$$

$$N \ge \frac{(2.576 + 1.036)^2}{0.55^2} + \frac{2.576^2}{2} = \frac{13.046}{0.3025} + 3.318 \approx 43.1 + 3.3 \approx 47 \text{ pairs}$$

- **Target Sample Size:** 50 paired sessions per tactical system ($100$ matches per candidate, $200$ matches total).
- **Minimum Reporting Gate:** An interim analysis is permitted at $N = 30$ paired sessions ($60$ matches per system) using Bonferroni-adjusted alpha $\alpha = 0.005$.

---

## 4. Controlled Experimental Protocol

1. **Paired Match Block Architecture:**
   - Every experimental session consists of exactly two consecutive matches against equivalent opposition.
   - Session Block 1: Match 1 = Candidate A, Match 2 = Candidate B.
   - Session Block 2: Match 1 = Candidate B, Match 2 = Candidate A (Counterbalanced AB/BA order to neutralize observer fatigue and warm-up effects).
2. **Identical Tactical Settings:**
   - Formation: `4-3-3 (Holding)`.
   - Tactical Profile: `HIGH_PRESS` (Defensive Depth: 72, Press After Possession Loss; Build Up: Fast Build Up).
   - Invariant Lineup: The remaining 10 positions (GK, LB, LCB, RCB, RB, CDM, LCM, RCM, LW, RW) are locked with identical cards across both matches.
3. **Opposition Environment:**
   - Mode: Squad Battles on `Legendary` difficulty (CPU AI profile standardized) or competitive Division Rivals (Division 1–2).
   - Halves: 6 minutes.
   - Controller Settings: Tactical Defending forced; Pass Assist: Semi; Shot Assist: Semi.
