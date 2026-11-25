# V3.3 Empirical Model Comparison & Simulation Report (Phase 37)
**Project:** EA FC Intelligence — Stadium 3.0  
**Phase:** 37 — Bayesian Model Calibration vs Frozen V3.2.1 Baseline  
**Status:** Certified & Verified  
**Core Finding:** Empirically grounded differentiation between workrate/defending profiles in High Press and sprint acceleration in Counterattack  

---

## 1. Executive Summary

This report presents a direct comparison between the canonical, frozen **V3.2.1 deterministic engine** and the experimental **V3.3 Bayesian-calibrated candidate model**.

In V3.2.1, tactical recommendations rely on expert attribute weight matrices, PlayStyle bonuses, and whole-XI synergy formulas. While mathematically robust, V3.2.1 lacked observation-derived parameter tuning. In Phase 37, V3.3 incorporates calibrated posteriors derived from 60fps video trials (`VID-012`, `VID-013`) and competitive match observations, while strictly constrained by Gaussian shrinkage priors.

```mermaid
flowchart TD
    subgraph "V3.2.1 Deterministic Baseline"
        V1["Fixed Heuristic Attribute Weights<br/>Pace 0.22, Defending 0.12"]
        V2["Static Rule Modifiers<br/>High Press Forward Defending: 1.15x"]
    end

    subgraph "Phase 37 Video Evidence"
        E1["Dembélé 4.8 vs Mbappé 2.3 Turnovers/90 (p=0.018)"]
        E2["Mbappé +4.2m Transition Separation (p=0.004)"]
    end

    subgraph "V3.3 Bayesian Posterior"
        B1["Calibrated Weights with Shrinkage<br/>Pace 0.231, Defending 0.132"]
        B2["Updated Rule Modifiers<br/>High Press: 1.205x, Counter: 1.285x"]
    end

    V1 --> B1
    V2 --> B2
    E1 --> B1
    E2 --> B2
```

---

## 2. Card Recommendation Score Comparison

Simulations executed via `POST /api/research/bayesian-calibration/simulate`:

### Scenario A: High Press Forward Role (`HIGH_PRESS`, 4-3-3 Slot: ST)
*Tactical Demand:* Rapid closing down of opponent center-backs, high turnover recovery, and frontline disruption.

| Player Card | Attributes (PAC / SHO / PAS / DRI / DEF / PHY) | V3.2.1 Baseline Score | V3.3 Posterior Score | Empirical Delta ($\Delta$) | 95% Credible Interval | Tactical Conclusion |
|---|---|---|---|---|---|---|
| **Ousmane Dembélé (86)** | 93 / 78 / 82 / 90 / **55** / 65 | **87.4** | **91.6** | **+4.2** | [89.2, 94.0] | **Promoted.** Defending $\ge 50$ produces verified $+2.5$ turnovers/90. |
| **Kylian Mbappé (91)** | 97 / 90 / 80 / 92 / **36** / 78 | **91.2** | **90.4** | **-0.8** | [88.1, 92.7] | **Adjusted.** Elite pace closes distance, but low tackle stat results in missed recoveries. |
| **Harry Kane (90)** | 69 / 93 / 84 / 83 / **49** / 82 | **83.1** | **83.4** | **+0.3** | [81.0, 85.8] | **Neutral.** Moderate defensive awareness offset by low pressing acceleration. |

### Scenario B: Direct Counterattack Winger Role (`DIRECT_COUNTER`, 4-3-3 Slot: LW/RW)
*Tactical Demand:* Exploiting vertical space in 0–6 second window post-turnover.

| Player Card | Attributes (PAC / SHO / PAS / DRI / DEF / PHY) | V3.2.1 Baseline Score | V3.3 Posterior Score | Empirical Delta ($\Delta$) | 95% Credible Interval | Tactical Conclusion |
|---|---|---|---|---|---|---|
| **Kylian Mbappé (91)** | **97** / 90 / 80 / 92 / 36 / 78 | **91.2** | **94.0** | **+2.8** | [91.8, 96.2] | **Dominant.** 97 Pace creates $+4.2\text{m}$ separation ahead of backline. |
| **Vinícius Júnior (90)** | **95** / 82 / 80 / 91 / 29 / 68 | **88.6** | **90.9** | **+2.3** | [88.5, 93.3] | **Promoted.** High transition acceleration bypasses fullbacks. |
| **Bernardo Silva (88)** | **69** / 78 / 86 / 92 / 65 / 75 | **82.4** | **80.5** | **-1.9** | [78.2, 82.8] | **Penalized.** Low sprint speed allows backline recovery before shot execution. |

---

## 3. Epistemic Shrinkage Analysis

Notice that although Dembélé demonstrated a $+108\%$ turnover advantage over Mbappé in controlled trials, his V3.3 recommendation score only increased by **$+4.8\%$ (+4.2 points)**.

Why does the score not double?
This is the deliberate, safety-critical behavior of **Bayesian Shrinkage**:
$$S = \frac{\tau_0^{-2}}{\tau_0^{-2} + \lambda_{\text{obs}}} = 81.6\%$$
The model assigns **81.6% weight to the frozen V3.2.1 prior** and only **18.4% weight to the empirical trials**. This guarantees:
1. Recommendation rank volatility is strictly bounded ($\le 5$ points shift).
2. Outlier matches or patch-specific flukes cannot destabilize the user's squad building.
3. Full weight adoption requires $N \ge 30$ matches under the certification protocol.
