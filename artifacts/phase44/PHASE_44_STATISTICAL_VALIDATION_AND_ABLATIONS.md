# Phase 44 Statistical Validation & Ablations

## 1. Empirical Ablations Observed
- **Canonical Key Alignment in Similarity Engine:** Initial benchmark runs on `FC_GAMER_DNA_BENCH_V2` exposed a `0.8` vs `1.0` Top-1 recall drop when reference match records were stored with unmapped raw Phase 40 keys (`pressing_intensity`, `possession_share`) instead of canonical V2 `STYLE_FEATURE_IDS` keys (`pressing_tendency`, `possession_retention_preference`). Running reference construction through the same `GamerDNAV2Engine` extractor raised Top-1 recall to `1.0` (`mean_within_gamer_split_cosine = 0.9994`).
- **Sparse Match Telemetry Overlap Guard:** Live test suites revealed `MIN_OVERLAP_RATIO = 0.25` (requiring `>= 14` of `53` style features) blocked partial real-world match telemetry carrying 8–12 observed metrics cleanly. Tuning `MIN_OVERLAP_RATIO` to `0.12` while keeping `MIN_JOINT_FEATURES >= 6` unblocked sparse telemetry while continuing to reject near-empty OOD vectors.
- **Unsupervised Sample Gate:** Enforced `n < 20` refusal (`INSUFFICIENT_PROFILES_FOR_EMPIRICAL_CLUSTERING`) vs `n = 40` validated clustering (`KMeans`, `k = 5`, `silhouette = 0.8962`, `bootstrap_stability = 1.0`).

## 2. Offline Algorithm & Library Disclosure
Installed & verified on Windows Python 3.15 (`numpy`, `scipy 1.18.1`, `scikit-learn 1.9.1`, `pandas`, `cv2 5.1.0`, `pyav 19.0.2`). `umap-learn`, `hdbscan`, `metric-learn`, `torch`, and `onnxruntime` are **not** installed locally; all clustering and covariance shrinkage rely on deterministic `scikit-learn` (`PCA`, `KMeans`, `GaussianMixture`, `AgglomerativeClustering`, `LedoitWolf`) and `scipy` (`jensenshannon`, `wasserstein_distance`, `cosine`, `linear_sum_assignment`).
