# Phase 43 Research Registry, Methodological Principles & Official References

## 1. Epistemic Hierarchy in `FootballKnowledgeService`
Phase 43 preserves the three-tier BM25 retrieval authority hierarchy implemented in `backend/services/football_knowledge_service.py` (`get_shared_knowledge_service()`):
1. `OFFICIAL_FACT` (highest retrieval multiplier; EA FC official Pitch Notes, FC IQ role mechanics, edition/mode mechanics).
2. `RESEARCH_METHODOLOGY` (validated statistical, ML calibration, CV, and causal experimentation methods; real-world football coefficients are never transferred numerically as EA FC parameters).
3. `COMMUNITY_OBSERVATION` (lowest multiplier; explicitly labeled non-canonical).

## 2. Phase 43 Additions to `RESEARCH_SOURCE_REGISTRY` (`26` Total Entries)
Inspecting `RESEARCH_SOURCE_REGISTRY` in `backend/services/football_knowledge_service.py` confirms 26 audited sources, including Phase 43 additions:

| Entry ID | Category | Title | License / Source Terms | Integration Decision | Implemented Role |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `RES-SCIPY-STATS` | `EXPERIMENTATION` | SciPy Statistical Hypothesis & Bootstrap Inference (`ttest_rel`, `wilcoxon`, `bootstrap`) | `BSD-3-Clause` | `ADOPTED` | Powers match-clustered paired/Welch significance tests and non-parametric percentile bootstrap CIs (`n_resamples=1500`) in `ExperimentAnalysisService`. |
| `RES-N-OF-1-BAYES` | `EXPERIMENTATION` | Bayesian Hierarchical Partial Pooling & N-of-1 Experimental Design | `Apache-2.0 / Statistical Reference` | `ADOPTED_ANALYTICAL_CONJUGATE` | Exact analytical Normal-Normal conjugate shrinkage (`prior_sd=0.25`) + leave-one-match-out sensitivity stability implemented in NumPy/SciPy without PyMC dependency. |
| `RES-EA-FCIQ` | `GAME_MECHANICS` | EA SPORTS FC IQ Official Pitch Notes (Roles, Focuses, Presets) | `EA Official Docs` | `ADOPTED_FACT_SOURCE` | Separates nominal pre-match formation from observed in-possession vs out-of-possession role shapes in `TacticalFingerprintEngine`. |

Existing companion entries actively relied upon across Phase 43 include `RES-EPV-SOCCERACTION` (`Apache-2.0 / Academic`), `RES-OWASP` (`CC BY-SA 4.0`), and `RES-WEB-INFRA` (`Apache-2.0 / MIT / BSD / W3C`).

## 3. Verified Phase 43 Knowledge Base Entries
- `KB-EA-FCIQ-TACTICS-013` (`OFFICIAL_FACT`): Documents EA Sports FC IQ role/focus assignments and the distinction between nominal formation diagrams and in-possession vs out-of-possession spatial configurations.
- `KB-RES-EXP-INFERENCE-014` (`RESEARCH_METHODOLOGY`): Documents match-clustered N-of-1 ABBA experimentation, Normal-Normal Bayesian posterior interpretation, opportunity-normalized transition denominators, and why video frames cannot be pooled as independent statistical samples.

## 4. Local Python Scientific Runtime Constraint & Resolution
- **Installed Stack Verified Locally:** `numpy 2.5.4`, `scipy 1.18.1`, `pandas 3.1.0`, `scikit-learn 1.9.1`, `opencv 5.1.0`, `pyav 19.0.2`.
- **Not Installed Locally:** `statsmodels`, `pymc`, `dowhy`, `causalml`, `ortools`, `torch`, `torchvision`, `onnxruntime`, `ultralytics`.
- **Engineering Decision:** Phase 43 statistical/Bayesian engines are built cleanly on exact `numpy` and `scipy.stats` (`ttest_rel`, `ttest_ind`, `bootstrap`, `norm.cdf`) with analytical conjugate posteriors so all production paths execute deterministically with zero brittle optional imports.
