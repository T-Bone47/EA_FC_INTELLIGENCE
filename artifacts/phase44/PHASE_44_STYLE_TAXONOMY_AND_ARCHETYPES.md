# Phase 44 Dual-Layer Playing Style Taxonomy & Archetypes

## 1. Ten Provisional Archetype Prototypes (`ARCHETYPES_V2`)
1. `Possession Architect`
2. `Direct Attacking Specialist`
3. `Counter-Attacking Specialist`
4. `High-Pressing Aggressor`
5. `Defensive Controller`
6. `Wing-Based Creator`
7. `Central Combination Specialist`
8. `Balanced Tactical Generalist`
9. `High-Risk Creative Attacker`
10. `Adaptive Tactical Strategist`

## 2. Layer 1: Interpretable Rule & Softmax Mixed Affinity
- `StyleArchetypeEngine.classify_layer1()` scores L1 similarity (`1 - mean(|obs - proto|)`) over overlapping anchor features in Groups A–F, applying temperature-scaled softmax (`exp(score * 6.0)`) for mixed membership weights.
- Distinguishes `COLD_START_HINT`, `INSUFFICIENT_EVIDENCE`, `SINGLE_DOMINANT`, `MIXED_PROFILE`, and `OUT_OF_DISTRIBUTION`.
- On `0` non-synthetic matches without cold-start tags, abstains cleanly as `Undetermined (Cold Start)` with empty archetype affinities (`status = "INSUFFICIENT_EVIDENCE"`).

## 3. Layer 2: Empirical Unsupervised Clustering Gate (`>= 20` Profiles)
- `StyleArchetypeEngine.evaluate_unsupervised_clusters()` strictly refuses empirical clustering (`INSUFFICIENT_PROFILES_FOR_EMPIRICAL_CLUSTERING`) when sample count `< 20`.
- When `n >= 20`, executes PCA dimensionality reduction (auxiliary noise filtering only) + evaluates `KMeans`, `GaussianMixture`, and `AgglomerativeClustering` across `k in (2, 3, 4, 5)` on Silhouette score, Davies-Bouldin index, and 5-subsample co-clustering bootstrap stability.
- Offline capability disclosure: `umap-learn` and `hdbscan` are not installed in the Python 3.15 environment; scikit-learn PCA/KMeans/GMM/Agglomerative provides validated offline clustering.
