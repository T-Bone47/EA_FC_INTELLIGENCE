# Phase 43 Limitations, Epistemic Boundaries & Non-Claims

## 1. Statistical & Causal Boundaries
- **Observational Confounding:** N-of-1 gamer match trials remain unblinded; opponent matchmaking ELO, server input delay/ping spikes, stamina exhaustion, custom controller settings, and intra-match momentum cannot be randomized or eliminated passively.
- **Small Sample Sensitivity:** When an arm has `< 3` eligible matches, paired/Welch inference and bootstrap CIs have low power; any single-match leave-one-out sign reversal forces `StatisticalVerdict.INCONCLUSIVE`.
- **Match-Cluster Unit Only:** Correlated video frames are never treated as independent statistical samples (`unit_of_analysis = "MATCH_CLUSTER_AGGREGATE"`).

## 2. Optional Binary Dependencies Not Installed Offline
Verified absent in local Python `3.15` runtime (`backend.cv_training.benchmark_cv` & environment checks):
- `torch`, `torchvision`, `onnxruntime`, `ultralytics` — no neural detector weights are present (`NO_TRAINED_WEIGHTS_PRESENT`), so vision perception runs via `CV_CLASSICAL_HSV_CONTOUR` + ByteTrack with calibrated ECE (`0.0643`) evaluated only on `SYNTHETIC_CALIBRATED_GEOMETRY_PROXY`.
- `statsmodels`, `pymc`, `dowhy`, `ortools` — pure NumPy/SciPy equivalents execute exact analytical Normal-Normal Bayes updates, stratified confounder checks, `linear_sum_assignment`, and exhaustive small-pool parity checks instead.

## 3. Visibility & Data Coverage Abstentions
- **Broadcast Field-of-View Crop:** If fewer than `14` outfield players are visible (`visible_outfield_players < 14`) or coverage `< 35%`, `TacticalFingerprintEngine` explicitly sets `team_compactness_abstained = True` and nulls compactness/width metrics rather than extrapolating off-screen players.
- **Zero Invented Market Prices:** Neither replacement triage nor multi-objective squad optimization fabricates FUT/UT coin prices (`MARKET_PRICE_UNAVAILABLE`). Budget limits apply strictly when verified costs exist.
- **Pro Gameplay Separation:** Pre-existing `test_engine_adversarial_phase7.py` (`9 failed`) and `test_engine_v3_real_data.py` (`4 failed`) reflect frozen V3.2.1 math behavior and were left unaltered.
