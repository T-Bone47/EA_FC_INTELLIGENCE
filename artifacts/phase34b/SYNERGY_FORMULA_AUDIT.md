# EA FC INTELLIGENCE — PHASE 34B
# MATHEMATICAL AUDIT: WHOLE-XI TACTICAL SYNERGY & ALIGNMENT INDEX

**Status:** Certified & Deterministically Reconstructable  
**Engine Baseline:** V3.2.1 Frozen Deterministic Core  
**Card Research Release:** `fc27-card-items-local-r1`  
**Classification:** Research & Evaluation / Engineering Audit  

---

## 1. Executive Summary & Audit Scope

This audit investigates the mathematical foundations of squad synergy calculations within EA FC Intelligence. Prior frontend iterations featured an intuitive "Whole-XI Cohesion Index" and channel grouping heuristics. However, rigorous mathematical scrutiny revealed that several numerical claims were artificially clamped, lacked formal statistical dispersion penalties, and did not guarantee complete or disjoint channel partitioning across all 12 supported formations.

In Phase 34B, the index has been formally audited, eliminated of arbitrary clamping (such as the legacy 15%–99% bounding), relabeled as the **Experimental Tactical Alignment Index**, and grounded upon a fully reconstructable mathematical formula:

$$I_{\text{align}} = \max\left(0.0, \min\left(1.0, \bar{r} - 0.5 \cdot \sigma_r - \delta_{\text{friction}}\right)\right)$$

Every deduction, channel partition, and alert provenance is now deterministically verifiable down to specific player card attributes and empirical gameplay benchmarks.

---

## 2. Critique of Legacy Heuristics

The initial implementation in `WholeXISynergyDashboard.tsx` had several mathematical limitations that did not meet the standard of reproducible football intelligence:

1. **Arbitrary Numerical Clamping (`15% – 99%`):**
   - The legacy calculation utilized:  
     `Math.max(15, Math.min(99, Math.round((avgScore / 0.88) * 100 - penalty)))`
   - *Audit Finding:* Imposing an artificial floor of 15% hid near-zero or catastrophic tactical collapses. Capping at 99% gave an illusion of modesty without mathematical basis. The denominator of 0.88 was an uncalibrated scaling factor that inflated lower-rated lineups.

2. **Incomplete Channel Partitioning:**
   - The legacy channels assumed hardcoded slot strings:  
     `leftSlots = ['LB', 'LWB', 'LCM', 'LM', 'LW']`  
     `centerSlots = ['GK', 'CB', 'LCB', 'RCB', 'CM', 'CDM', 'CAM', 'ST', 'CF']`  
     `rightSlots = ['RB', 'RWB', 'RCM', 'RM', 'RW']`
   - *Audit Finding:* When evaluating formations like `3-4-2-1` (`LF`, `RF`), `4-2-3-1` (`LAM`, `RAM`, `LDM`, `RDM`), or `4-4-2` (`LST`, `RST`), slots were either omitted completely or miscategorized.

3. **Absence of Variance / Dispersion Penalty:**
   - Aggregating individual slot suitabilities by a simple arithmetic mean created the "Galácticos Illusion": a lineup with ten 0.95-rated superstars and one 0.30-rated liability would report a misleadingly high aggregate cohesion (~0.89), ignoring the fatal tactical bottleneck created by the weak link.

4. **Undocumented Friction Arbitrage:**
   - Dissonance deductions were calculated as `Math.min(30, dissonances.length * 7)`, regardless of whether the dissonance was an empirically verified tactical bottleneck or a minor heuristic preference.

---

## 3. Formalized Mathematical Architecture

The certified Phase 34B architecture formalizes collective alignment as a multi-term deterministic function:

### 3.1 Mean Suitability ($\bar{r}$)
For a lineup with scored outfield slots $S_{\text{scored}}$ (excluding locked/unscored goalkeepers):

$$\bar{r} = \frac{1}{|S_{\text{scored}}|} \sum_{s \in S_{\text{scored}}} r_s$$

Where $r_s \in [0.0, 1.0]$ is the deterministic V3.2.1 suitability score for slot $s$ under tactical profile $\mathcal{T}$.

### 3.2 Suitability Dispersion Penalty ($\sigma_r$)
To capture weak-link bottlenecks and lineup imbalance, the standard deviation of slot suitabilities is computed:

$$\sigma_r = \sqrt{\frac{1}{|S_{\text{scored}}|} \sum_{s \in S_{\text{scored}}} \left(r_s - \bar{r}\right)^2}$$

The dispersion penalty applied to the index is $0.5 \cdot \sigma_r$. This guarantees that a uniform lineup of 0.80 players achieves higher alignment than an erratic lineup with the same mean (e.g. 0.95 and 0.65).

### 3.3 Rule-Based Tactical Friction ($\delta_{\text{friction}}$)
Friction is deducted exclusively when an assigned card violates an explicit tactical rule $\rho \in \mathcal{R}_{\text{active}}$:

$$\delta_{\text{friction}} = \sum_{\rho \in \mathcal{R}_{\text{active}}} \delta_\rho$$

Where $\delta_\rho \in [0.010, 0.025]$ is the calibrated penalty associated with rule $\rho$. If an attribute is unobserved or missing from a research item, the rule fails open to `DATA_LIMITATION` and applies $0.0$ penalty, preserving the honest-data constraint.

### 3.4 Bounding and Final Percentage Representation
$$I_{\text{align}} = \max\left(0.0, \min\left(1.0, \bar{r} - 0.5 \cdot \sigma_r - \delta_{\text{friction}}\right)\right)$$

$$\text{Alignment Index \%} = \text{round}\left(100.0 \cdot I_{\text{align}}, 1\right)$$

---

## 4. Documented Classification Conventions

Rather than subjective labels, the index is classified according to documented mathematical boundaries:

| Index Range | Status Code | Display Convention | Epistemic Description |
|:---|:---|:---|:---|
| **$\ge 82.0\%$** | `HIGH_ALIGNMENT` | Elite Harmony | Lineup possesses high mean suitability, low slot dispersion, and zero critical tactical friction alerts. |
| **$72.0\% - 81.9\%$** | `MODERATE_ALIGNMENT` | Strong Cohesion | Sound tactical execution with minor dispersion or single non-critical friction. |
| **$60.0\% - 71.9\%$** | `PARTIAL_ALIGNMENT` | Partial Alignment | Functional structure with noticeable structural weaknesses or multiple rule violations. |
| **$< 60.0\%$** | `TACTICAL_DISSONANCE` | Tactical Dissonance | Severe tactical friction, extreme dispersion, or unsuitable tactical profiles. |
| **Unscored / Empty** | `INSUFFICIENT_EVIDENCE` | Insufficient Evidence | Lineup has zero scored outfield slots. |

---

## 5. Channel Partitioning Across 12 Formations

The channel partitioning engine (`FORMATION_CHANNELS`) establishes disjoint and complete sub-units across all 12 supported formations:

1. $\text{LEFT\_FLANK} \cap \text{CENTRAL\_SPINE} = \emptyset$
2. $\text{RIGHT\_FLANK} \cap \text{CENTRAL\_SPINE} = \emptyset$
3. $\text{LEFT\_FLANK} \cap \text{RIGHT\_FLANK} = \emptyset$
4. $\text{LEFT\_FLANK} \cup \text{CENTRAL\_SPINE} \cup \text{RIGHT\_FLANK} = S_{\text{formation}}$

Every formation (from `4-3-3` to `3-4-2-1` and `5-2-1-2`) has been mathematically certified in `artifacts/phase34b/CHANNEL_MAPPING_TESTS.json`.

---

## 6. Epistemic Status & Honest Data Principles

1. **No Claim of Physiological or Emotional Bonding:**  
   The index does NOT measure human psychology, team spirit, dressing-room morale, or chemistry styles.
2. **No Claim of EA FC Engine Scripting:**  
   The index does NOT manipulate gameplay difficulty, momentum scripting, or internal animation timing.
3. **Deterministic Heuristic Metric:**  
   The index is an explainable aggregation of individual candidate suitabilities, slot dispersion, and rule-based tactical friction derived from frozen V3.2.1 models.
