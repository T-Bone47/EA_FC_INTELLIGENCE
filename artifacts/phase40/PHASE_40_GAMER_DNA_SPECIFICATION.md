# PHASE 40C: Gamer DNA Mathematical & Epistemic Specification

**Implementation:** [gamer_dna_engine.py](../../backend/services/gamer_dna_engine.py)

## 1. Strict 4-Layer Separation
1. **Playing Style (8 dimensions):** `attacking_directness`, `possession_preference`, `passing_tempo`, `passing_risk`, `wing_utilization`, `central_progression`, `dribbling_tendency`, `pressing_intensity`.
2. **Playing Proficiency (8 dimensions):** `chance_creation`, `finishing_decisions`, `defensive_compactness`, `defensive_transition_management`, `tactical_discipline`, `adaptability`, `decision_making_under_pressure`, `match_to_match_consistency`.
3. **Tactical Suitability:** Formation + Tactical Profile + FC IQ Role alignment scored cleanly from style + compensating for weak proficiency metrics.
4. **Improvement Potential:** Ranked `(gap * confidence_factor)` intervention levers.

## 2. Mathematical Formulation

### Within-Match Cluster Weighting & Recency Decay
Thousands of consecutive 10 Hz video frames inside one match are strongly autocorrelated and are **never treated as independent samples**. Each eligible match $i$ contributes a capped cluster weight:

$$w_i = \exp(-\lambda \cdot \text{age\_days}_i) \cdot q_i \cdot \text{cov}_i \cdot d_i \cdot \min\left(4.0, \sqrt{C_i}\right)$$

where $\lambda = 0.035\,\text{day}^{-1}$ (provisional heuristic until empirically calibrated), $q_i \in \{1.0, 0.82, 0.58\}$ maps `HIGH/MODERATE/LOW` quality, $\text{cov}_i \in [0.4, 1.0]$, $d_i = 0.7$ for partial matches, and $C_i$ is sequence clusters.

### Kish Effective Sample Size & Bayesian Beta-Binomial Intervals
$$n_{\text{eff,kish}} = \frac{(\sum_i w_i)^2}{\sum_i w_i^2}$$

Posterior estimate with symmetric prior $\text{Beta}(\alpha_0=2, \beta_0=2)$ yields shrunk posterior mean $\mu = \frac{\alpha}{\alpha+\beta}$ and 95% normal-Beta credible bounds $[\mu - 1.96\,\sigma, \mu + 1.96\,\sigma]$.

### Suppression & Cold-Start Rules
- **`SYNTHETIC_FIXTURE` Firewall:** Excluded unconditionally before aggregation (`synthetic_excluded_count` incremented openly).
- **Sparse Evidence Suppression:** `relevant_match_count == 0` -> `INSUFFICIENT_EVIDENCE` (`estimated_value = None`); `match_to_match_consistency` requires `>= 3` verified matches.
- **Cold-Start Questionnaire:** Self-reported tempo/pressing/width hints render under `UNCERTAIN_COLD_START` / `has_cold_start_preferences = True` without fabricating numeric skill estimates.

## 3. Mixed Archetype System & Feature-Gated Pro DNA Schema (Phase 40L)
Evaluates 10 tactical archetypes (`Possession Controller`, `Vertical Playmaker`, `Counter-Attack Specialist`, `High-Press Aggressor`, `Technical Dribbler`, `Wing Play Specialist`, `Central Combination Player`, `Defensive Organizer`, `Balanced Tactical Player`, `Direct Attacking Specialist`), emitting `MIXED_PROFILE` when secondary affinity lies within `0.10` of primary. Named pro-gamer percentage matching remains strictly disabled (`feature_enabled = False`) pending verified pro datasets.
