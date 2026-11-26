# Phase 44 Uncertainty & Rank Stability Engine

## 1. Match-Level Resampling & Confidence Intervals
Implemented inside `ProfessionalGamerSimilarityEngine.compare()` (`backend/services/professional_similarity_engine.py`):
- Extracts match-level feature vectors cleanly across non-synthetic matches in the active edition.
- When `n_matches >= 2`, performs **24 seeded match-level bootstrap resamples** (`rng = np.random.default_rng(44)`), recomputing weighted RMS similarity across resampled user match sets to obtain empirical 10th–90th percentile confidence bands (`confidence_band = [p10, p90]`) and top-rank persistence percentages (`rank_stability_pct`).
- When `n_matches >= 3`, performs **Leave-One-Match-Out (LOMO)** sensitivity analysis and records exact `lomo_top_rank_flips` in `uncertainty_summary`.

## 2. Indistinguishable Rank Guardrail
For adjacent ranked candidates `(rank_k, rank_{k+1})`:
- Whenever `|similarity_a - similarity_b| < 5.0` points OR their confidence bands overlap within `< 8.5` points (`a.confidence_band[0] <= b.confidence_band[1]`), sets explicit `indistinguishable_note` informing the user that exact ordering is statistically non-definitive.
