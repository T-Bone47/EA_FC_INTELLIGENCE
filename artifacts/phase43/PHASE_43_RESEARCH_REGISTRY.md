# Phase 43 Research Registry & Technical Grounding

All external academic, open-source, statistical, optimization, and official EA SPORTS FC references are registered cleanly in `RESEARCH_SOURCE_REGISTRY` and `KNOWLEDGE_ENTRIES` inside `backend/services/football_knowledge_service.py` (exposed read-only via `GET /api/phase40/research-registry` and searchable via `GET /api/phase40/knowledge`).

## Category Summary & Adoption Decisions

| Source ID | Title & Reference URL | Category | Decision | Key Assumptions / Limitations |
| :--- | :--- | :--- | :--- | :--- |
| `RES-EPV-PAPER` | Expected Possession Value (EPV) Decomposition (`https://link.springer.com/article/10.1007/s10994-021-05989-6`, PMC8570314) | Analytics | `ADOPTED_FRAMEWORK_CONCEPTS` | Broadcast crops hide off-screen players unless `minimap_roi` active |
| `RES-XT-SINGH` | Expected Threat (xT) Grid (`https://karun.in/blog/expected-threat.html`) | Analytics | `ADOPTED_GRID_PRINCIPLES` | Stationary zone grid; no automatic fatigue/PlayStyle coeff fitting |
| `RES-FOT-TRACKING` | Friends of Tracking / Pitch Control (`https://github.com/Friends-of-Tracking-Data-FoTD/LaurieOnTracking`) | Analytics | `ADOPTED_PITCH_CONTROL_MATH` | Compactness/width require >= 14 visible outfield players |
| `RES-METRICA-SAMPLE` | Metrica Sports Open Tracking Sample (`https://github.com/metrica-sports/sample-data`) | Analytics | `BENCHMARK_FORMAT_REFERENCE` | Pro tracking kinematics never mixed into user `PersonalMetaProfile` |
| `RES-EPV-SOCCERACTION` | ML-KULeuven SoccerAction VAEP (`https://github.com/ML-KULeuven/socceraction`) | Decision | `ADOPTED_PRINCIPLES` | Pre-action state frozen cleanly before outcome realization |
| `RES-CENT-NOF1` | CONSORT Extension for N-of-1 Trials CENT 2015 (`https://www.bmj.com/content/350/bmj.h1738`) | Experimentation | `ADOPTED_TRIAL_PROTOCOL` | Single-gamer unblinded trials cannot remove expectation bias |
| `RES-CENT-EANDI` | CENT Explanation (`bmj.h1793`) & Crossover Carryover (`https://pmc.ncbi.nlm.nih.gov/articles/PMC6667942/`) | Experimentation | `ADOPTED_CARRYOVER_CONTROLS` | EA FC patch updates define strict regime boundaries |
| `RES-SCIPY-STATS` | SciPy Stats `ttest_rel`, `ttest_ind`, `bootstrap` (`https://docs.scipy.org/doc/scipy/reference/stats.html`) | Experimentation | `ADOPTED` | Match-level primary sampling unit; small-n (`<6/arm`) sensitivity risk |
| `RES-STATSMODELS-GEE` | Statsmodels Mixed-Effects / GEE (`https://www.statsmodels.org/stable/gee.html`) | Experimentation | `REFERENCED_ANALYTICAL_SUBSTITUTE` | `statsmodels` not installed offline; pure NumPy/SciPy cluster summaries used |
| `RES-SKLEARN-CAL` | Scikit-Learn Calibration (`https://scikit-learn.org/stable/modules/calibration.html`) | Experimentation | `ADOPTED_CALIBRATION_CHECK` | Zero-coverage arms abstain rather than extrapolate |
| `RES-DOWHY-CAUSAL` | DoWhy Causal & Sensitivity (`https://www.pywhy.org/dowhy/v0.11.1/`) | Experimentation | `ADOPTED_CAUSAL_DISCIPLINE` | `dowhy` not installed; patch/mode/opponent stratification enforced directly |
| `RES-N-OF-1-BAYES` | Bayesian Hierarchical Partial Pooling (`https://docs.pymc.io/`) | Experimentation | `ADOPTED_ANALYTICAL_CONJUGATE` | Closed-form Normal-Normal posterior without `pymc` binary install |
| `RES-OR-TOOLS` | Google OR-Tools Optimization (`https://developers.google.com/optimization`) | Optimization | `REFERENCED_EXACT_LOCAL_EQUIVALENT` | `ortools` not installed offline; SciPy `linear_sum_assignment` + exact small-pool check |
| `RES-SCIPY-OPTIMIZE` | SciPy Optimize (`https://docs.scipy.org/doc/scipy/reference/optimize.html`) | Optimization | `ADOPTED` | Installed in runtime (`scipy 1.18.1`) |
| `RES-EA-FC-SITE` | EA SPORTS FC Official Site (`https://www.ea.com/games/ea-sports-fc`) | Game Mechanics | `ADOPTED_EDITION_BOUNDARY` | Strictly isolates `FC26` and `FC27` |
| `RES-EA-FCIQ` | EA SPORTS FC IQ Pitch Notes (`https://www.ea.com/games/ea-sports-fc/news/fc-iq-deep-dive-pitch-notes`) | Game Mechanics | `ADOPTED_FACT_SOURCE` | Separates nominal shape vs in/out-of-possession role shape |
| `RES-EA-LEGAL` | EA User Agreement (`https://www.ea.com/legal/user-agreement`) | Compliance | `STRICT_COMPLIANCE_GUARDRAIL` | Zero memory reading, zero automated controls, user clips only |
