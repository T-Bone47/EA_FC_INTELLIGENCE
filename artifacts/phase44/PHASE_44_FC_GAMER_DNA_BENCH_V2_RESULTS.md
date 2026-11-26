# FC_GAMER_DNA_BENCH_V2 Results

Executed via `C:\Python315\python.exe -m verification.fc_gamer_dna_bench_v2` (results persisted to `artifacts/phase44/fc_gamer_dna_bench_v2_results.json`).
Note: Section C authorized pro profiles exist **exclusively** in an isolated in-memory harness (`Phase44Repository(force_memory=True)`) to validate math, edition isolation, and revocation logic; the live/DB EA FC Pro registry remains strictly `0` authorized profiles (`METADATA_ONLY`).

| Benchmark Pillar | Verified Result | Status |
|---|---|---|
| A. Feature Correctness & Group G Isolation | `total_features=60` (`53` style + `7` Group G), `missing_stays_null=True`, `synthetic_excluded=True`, `group_g_isolated=True` | PASSED |
| B. Style Identity Separability & Leak-Free Split | `40` gamers evaluated (`5` archetypes x `8`), `archetype_top1_accuracy=1.0`, `mean_within_gamer_split_cosine=0.9994`, `scaler_fit_split=TRAIN_PROFILES_ONLY` | PASSED |
| C. Similarity Ranking & Fail-Closed Governance | `real_registry_zero_auth_abstained=True`, controlled in-memory `controlled_pro_top1_recall=1.0`, `edition_firewall_fc26_vs_fc27_abstained=True`, `revocation_immediate_invalidation=True` | PASSED |
| D. Unsupervised Clustering Gate (`n >= 20`) | `small_n10_gate_status=INSUFFICIENT_PROFILES_FOR_EMPIRICAL_CLUSTERING`; `full_n40_status=VALIDATED_EMPIRICAL_CLUSTERING` (`KMeans`, `k=5`, `silhouette_score=0.8962`, `bootstrap_stability=1.0`) | PASSED |
| E. Style-Aware Recommendation & Sandbox Parity | `frozen_v321_weights_altered=False`, `market_price_status=MARKET_PRICE_UNAVAILABLE`, `sandbox_non_mutating=True`, all 6 hard XI constraints `True` | PASSED |
