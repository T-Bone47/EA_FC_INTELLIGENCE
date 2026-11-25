# PHASE 41: Research Source Registry & Mathematical Basis

**Date:** 2026-11-25  
**Scope:** Phase 41 Decision Intelligence, Expected Possession Value, Counterfactual Valuation, Off-Policy Evaluation & Learning-to-Rank

---

## 1. Tracked Research & Algorithmic Sources

| Source / Author | Publication / Repo | Key Concept Adopted in Phase 41 | Direct Epistemic Distinction |
| :--- | :--- | :--- | :--- |
| **Javier Fernández, Luke Bornn, Dan Cervone (2019)** | MIT Sloan Sports Analytics Conference — *"Decomposing the Immeasurable Sport: A Deep Learning Expected Possession Value Framework for Soccer"* (`sloansportsconference.com`) | Decomposing instantaneous frame state $V(s)$ across action components (passes, drives/carries, shots) so decisions can be scored before outcomes occur | Stage 1 uses interpretable heuristics (`HeuristicPossessionValue`), Stage 3 provides calibrated `P(score) - P(concede)` interface gated on calibrated tracking cohorts; never mislabels heuristic utility as deep-learning EPV |
| **Karun Singh (2018/2019) & `socceraction` (`KU Leuven DTAI`)** | `socceraction.xthreat` & Karun Singh Expected Threat (xT) Markov grid (`12x8` matrix) | Value-iteration Markov progression model `xT(z)` assigning threat via move probabilities $T_{z \to z'}$ and shooting probability $s(z)$ | `ExpectedThreatEngine` implements configurable Markov solver (`12x8` or `16x12` grid) initialized from Karun Singh's matrix or learned from valid tracking transitions with smoothing & convergence tolerances |
| **Will Spearman (2018) & Laurie Shaw (`LaurieOnTracking`)** | `Metrica_PitchControl.py` — Physics-based `time_to_intercept` & anisotropic pitch control | Computing minimum kinematic arrival time (reaction delay $\tau$, current velocity $\mathbf{v}$, top sprint speed $v_{\max}$) and logistic arrival margin | Reuses `SpatialIntelligenceEngine` kinematics cleanly while extending `passing_intelligence.py` with point-to-segment interception arrival margins $M = t_{\text{opp}} - t_{\text{ball}}$ across pass-speed tiers |
| **Tom Decroos, Lotte Bransen, Jan Van Haaren, Jesse Davis (`socceraction`)** | VAEP & `atomic-vaep` (`KU Leuven`) | Pre-action state-change valuation $P(\text{scoring} \mid S_i) - P(\text{conceding} \mid S_i)$ and atomic event isolation | Phase 41 enforces strict pre-action freezing (`FootballDecisionState` cut off cleanly prior to kick/tackle timestamp $t_0$) and automated hindsight-leakage assertions |
| **XGBoost `learning_to_rank`** | XGBoost LTR Docs (`rank:ndcg`, `rank:pairwise`, query group `qid`) | Listwise / pairwise candidate ordering within each decision frame (`qid = decision_window_id`) | Provides pairwise/listwise candidate ranking structure & NDCG evaluation metrics when ranking alternative actions in each frame |
| **Ruohan Zhan, Vitor Hadad, David Hirshberg, Susan Athey, Stefan Wager (2021)** | Stanford GSB / SIGKDD / PNAS — *"Off-Policy Evaluation via Adaptive Weighting with Data from Contextual Bandits"* (`gsb.stanford.edu`) | Stabilizing counterfactual policy value estimates and confidence bounds under sparse coverage / diverging behavior policies | Phase 41 surfaces rank-stability tests, indistinguishability intervals under localization/speed noise, and high-uncertainty attenuation instead of overconfident counterfactual deltas |
| **SciPy `scipy.stats`** | `docs.scipy.org` — `spearmanr`, `kendalltau`, `wilcoxon` | Nonparametric rank agreement (`kendalltau`, `spearmanr`) and paired non-parametric difference tests (`wilcoxon`) | Used for counterfactual stability tests, sensitivity ordering comparisons, and before/after paired validation benchmarks |

---

## 2. Non-Negotiable Grounding & Honesty Guards
1. No external proprietary real-world Opta/StatsBomb/EA telemetry was ingested; Stage 1/2 valuations declare explicit provenance (`HEURISTIC_UTILITY`, `CONFIGURABLE_MARKOV_XT`, `EMPIRICAL_GATE_REQUIRED`).
2. Frozen V3.2.1 card/player recommendation engine (`recommendation_engine_v3.py`, `v3_config.py`) remains strictly unmodified.
3. Simulated/synthetic fixtures (`SYNTHETIC_FIXTURE`) never contaminate persistent Football IQ profiles or longitudinal coaching metrics.
