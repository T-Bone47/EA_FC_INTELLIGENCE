# EA FC INTELLIGENCE — PHASE 35
# PARTNERSHIP INTELLIGENCE V2: TACTICAL COMPLEMENTARITY & SPATIAL DYNAMICS

**Engine Component:** `backend/services/partnership_intelligence.py`  
**Test Suite:** `backend/tests/test_partnership_intelligence.py` (7 Passed)  
**Baseline Engine:** V3.2.1 Frozen Deterministic Core  
**Classification:** Tactical Science, Partnership Dynamics & Decision Modeling  

---

## 1. Executive Summary

In conventional football simulation engines and commercial squad builders, inter-player relationships are simplified into cosmetic "chemistry lines" derived from arbitrary league, club, or nationality overlaps. These lines produce zero tactical insight: two identical poaching strikers or two slow central defenders receive maximum "green chemistry" despite sharing severe functional bottlenecks.

**Partnership Intelligence V2** introduces a mathematically grounded, non-cosmetic evaluation of two-player micro-units. The engine evaluates **Capability Complementarity** ($C_{\text{comp}}$), **Responsibility Overlap** ($O_{\text{resp}}$), and **Tactical Friction** ($F_{\text{part}}$) across five tactical couplings without inventing chemistry ratings.

---

## 2. Mathematical Architecture

For any candidate pairing $(c_1, c_2)$ occupying tactically coupled slots $(s_1, s_2)$ under tactical profile $\mathcal{T}$:

### 2.1 Mean Suitability ($\bar{r}_{1,2}$)
$$\bar{r}_{1,2} = \frac{r(c_1, s_1, \mathcal{T}) + r(c_2, s_2, \mathcal{T})}{2}$$

### 2.2 Capability Complementarity ($C_{\text{comp}}$)
Complementarity captures whether the two players symmetrically cover distinct, required responsibilities for that tactical coupling. Because tactical imbalance (e.g. an elite creator with a non-finisher, or an elite dribbler with zero wide defensive cover) bottlenecks the unit, $C_{\text{comp}}$ is computed as the **harmonic mean** of the two complementary capabilities $K_1$ and $K_2$:

$$C_{\text{comp}} = \mathcal{H}(K_1, K_2) = \frac{2 \cdot K_1 \cdot K_2}{K_1 + K_2}$$

Where $K_1, K_2 \in [0.01, 1.0]$. The harmonic mean ensures that a deficiency in either capability heavily depresses the complementarity score.

### 2.3 Responsibility Overlap ($O_{\text{resp}}$)
Responsibility Overlap measures spatial congestion, redundant role demands, or mutual exclusion in the same zone:
$$O_{\text{resp}} \in [0.0, 0.40]$$
- High overlap occurs when both players demand the exact same phase of play (e.g. two pure target men competing for the same central aerial cross, or two touchline crossers on the same flank vacating the defensive half-space).

### 2.4 Tactical Friction Deductions ($F_{\text{part}}$)
$$F_{\text{part}} = \sum_{f \in \mathcal{F}_{\text{active}}} \delta_f$$
Deductions ($\delta_f \in [0.015, 0.025]$) trigger when individual player capabilities directly violate system demands (e.g., low defending forward in a High Press, or slow fullback lacking recovery speed in a high line).

### 2.5 Net Partnership Synergy Score ($S_{\text{part}}$)
$$S_{\text{part}} = \max\left(0.0, \min\left(1.0, \bar{r}_{1,2} + 0.15 \cdot (C_{\text{comp}} - 0.50) - 0.10 \cdot O_{\text{resp}} - F_{\text{part}}\right)\right)$$

---

## 3. Evaluation Across Five Core Partnerships

```
+----------------------------------------------------------------------------------------------------+
|                                    5 CORE TACTICAL PARTNERSHIPS                                    |
+----------------------------------------------------------------------------------------------------+
| 1. ST + CAM          | Vertical Spacing, Creator-Finisher Harmonic Balance, Supply Channel         |
| 2. WINGER + FULLBACK | Flank Width, Inverted Cut vs Overlap Mechanics, Defensive Transition Cover   |
| 3. CM + CDM          | Central Pivot Balance, Defensive Screening vs Box-to-Box Progression        |
| 4. TWO STRIKERS      | Strike Partnership, Aerial / Hold-up Anchor vs Behind-the-Defense Separation|
| 5. CB + CB           | Central Defensive Spine, Aggressive Stopper vs Recovery Sweeper Balance     |
+----------------------------------------------------------------------------------------------------+
```

### 3.1 Striker + Central Attacking Midfielder (`ST_CAM`)
- **Primary Complementarity:** Creation Capacity ($K_1 = 0.55 \cdot \text{Vision} + 0.45 \cdot \text{Short Passing}$) paired with Finishing Capacity ($K_2 = 0.60 \cdot \text{Finishing} + 0.40 \cdot \text{Positioning}$).
- **Benchmark Evaluation:**
  - *Haaland (ST) + De Bruyne (CAM):* $K_1 = 93.5\%$, $K_2 = 93.4\% \implies C_{\text{comp}} = 93.4\%$. Zero overlap. Net Synergy: **$87.8\%$ (Elite Harmony)**.
  - *Mbappé (ST) + Bruno Fernandes (CAM) in High Press:* Mbappé defending ($29$) triggers `RULE-PART-ST-PRESS-DEF` ($-0.020$). Net Synergy: **$81.2\%$ (Strong Cohesion)**.

### 3.2 Winger + Fullback Flank Unit (`WINGER_FULLBACK`)
- **Primary Complementarity:** Flank Offensive Threat ($K_1 = 0.50 \cdot \text{Pace} + 0.50 \cdot \text{Dribbling}$) paired with Flank Defensive Security ($K_2 = 0.60 \cdot \text{Defending} + 0.40 \cdot \text{Stamina}$).
- **Benchmark Evaluation:**
  - *Vinicius Jr (LW) + Ferland Mendy (LB):* Threat: $94.0\%$, Security: $85.6\% \implies C_{\text{comp}} = 89.6\%$. Fast recovery cover neutralizes winger turnovers. Net Synergy: **$86.4\%$ (Elite Harmony)**.
  - *Dembélé (RW) + Alexander-Arnold (RB) in Counterattack:* Alexander-Arnold pace ($76$) triggers `RULE-PART-FB-PACE` ($-0.020$) due to wide counter isolation. Net Synergy: **$77.5\%$ (Strong Cohesion)**.

### 3.3 Central Midfield Pivot (`CM_CDM`)
- **Primary Complementarity:** Central Defensive Screening ($K_1 = 0.60 \cdot \text{Defending} + 0.40 \cdot \text{Physicality}$) paired with Vertical Progression ($K_2 = 0.50 \cdot \text{Short Passing} + 0.30 \cdot \text{Vision} + 0.20 \cdot \text{Dribbling}$).
- **Benchmark Evaluation:**
  - *Rodri (CDM) + Valverde (CM):* Screening: $88.2\%$, Progression: $85.0\% \implies C_{\text{comp}} = 86.6\%$. Rodri anchors deep zone while Valverde carries vertically. Net Synergy: **$87.5\%$ (Elite Harmony)**.
  - *Casemiro (CDM) + Palhinha (CM):* Screening: $88.0\%$, Progression: $70.5\% \implies$ Triggers Midfield Distribution Bottleneck ($O_{\text{resp}} = 0.15$) and `RULE-PART-CM-PROGRESS` ($-0.020$). Net Synergy: **$68.2\%$ (Partial Alignment)**.

### 3.4 Two Strikers (`TWO_STRIKERS`)
- **Primary Complementarity:** Pace Separation Threat ($K_1 = \max(\text{Pace}_1, \text{Pace}_2)$) paired with Physical Hold-Up / Aerial Anchor ($K_2 = \max(\text{Phy}_1, \text{Phy}_2)$).
- **Benchmark Evaluation:**
  - *Kane + Mbappé:* Pace Separation: $97.0\%$, Physical Anchor: $84.0\% \implies C_{\text{comp}} = 90.0\%$. Perfect division of offensive labor. Net Synergy: **$88.4\%$ (Elite Harmony)**.
  - *Mbappé + Werner:* Pace: $97.0\%$, Physical: $71.0\% \implies$ Triggers Lack of Physical/Aerial Anchor against Low Blocks ($O_{\text{resp}} = 0.15$). Net Synergy: **$75.1\%$ (Strong Cohesion)**.

### 3.5 Central Defensive Unit (`CB_CB`)
- **Primary Complementarity:** Recovery Pace & Sweeping ($K_1 = \max(\text{Pace}_1, \text{Pace}_2)$) paired with Physical Dominance & Stopper Engagement ($K_2 = \max(\text{Phy}_1, \text{Phy}_2)$).
- **Benchmark Evaluation:**
  - *Saliba (Sweeper) + Rúben Dias (Stopper):* Recovery Pace: $84.0\%$, Physical Dominance: $87.0\% \implies C_{\text{comp}} = 85.5\%$. Saliba cleans up through balls while Dias dominates ground challenges. Net Synergy: **$86.2\%$ (Elite Harmony)**.
  - *Dias + Hummels in High Line:* Recovery Pace: $74.0\% \implies$ Triggers `RULE-PART-CB-PACE` ($-0.025$) and High-Line Vulnerability ($O_{\text{resp}} = 0.18$). Net Synergy: **$67.4\%$ (Partial Alignment)**.

---

## 4. Status Conventions & Classification

| Synergy Range | Classification Convention | Strategic Interpretation |
|:---|:---|:---|
| **$\ge 82.0\%$** | `ELITE_PARTNERSHIP` | Flawless mutual role execution; complementary capabilities amplify both players; zero tactical friction. |
| **$72.0\% - 81.9\%$** | `COMPLEMENTARY_PARTNERSHIP` | Strong functional execution; balanced coverage with minor attribute trade-offs. |
| **$60.0\% - 71.9\%$** | `FUNCTIONAL_PARTNERSHIP` | Passable pairing but reveals noticeable asymmetry or single friction alert. |
| **$< 60.0\%$** | `ASYMMETRIC_OR_FRICTIONAL` | Severe capability bottleneck, spatial congestion, or double friction penalty. |

---

## 5. Provenance & Epistemic Status

All calculations in Partnership Intelligence V2 are classified as **`MODELED_HEURISTIC`**. While grounded in tactical domain theory and verified attribute normalizations, they represent formal hypotheses pending large-scale empirical match verification ($N \ge 30$ pairs) under the protocols established in Phase 35B.
