# Phase 44 Professional Similarity Engine Architecture

## 1. Five-Stage Matching Pipeline (`ProfessionalGamerSimilarityEngine`)
Implemented in `backend/services/professional_similarity_engine.py`:
1. **Stage 1 — Fail-Closed Eligibility Filter:** Verifies `ReferenceRightsValidator.is_permitted(rights, purpose)`, exact `FC26`/`FC27` edition match, `is_invalidated == False`, `eligible_ref_matches >= 1`, `coverage >= 0.25`, `joint_feature_count >= 6`, and `feature_overlap_ratio >= 0.12`.
2. **Stage 2 — Weighted Reliability-Masked Distance:** Computes RMS Euclidean distance strictly across Groups A–F (`STYLE_FEATURE_IDS`) with inverse-group-size equalization (`10.0 / group_feature_count`) and user feature uncertainty attenuation (`1 / (1 + 2.5 * SE)`).
3. **Stage 3 — Comparative Metrics & Cohort Mahalanobis:** Computes centered Cosine similarity (`scipy.spatial.distance.cosine`), plus `LedoitWolf` shrinkage Mahalanobis distance whenever authorized reference cohort `n >= 6` with common features (falling back explicitly with `DIAGONAL_FALLBACK_*` when `n < 6`).
4. **Stage 4 — Compositional Distributional Distances:** Computes Jensen-Shannon divergence (`jensenshannon`) and Wasserstein earth-mover distance (`wasserstein_distance`) over shared compositional distributions (`pass_direction_distribution`, `possession_duration_distribution`).
5. **Stage 5 — Honest Abstention & Interpretable Index:**
   - When `0` rights-verified references exist (current live default) or user matches = `0` or overlap fails OOD thresholds, returns `abstained = True` with fallback archetype summary instead of fabricating pro similarities.
   - Index mapping `100 * exp(-3.15 * rms_d)` includes mandatory `scale_disclosure` clarifying similarity reflects tactical style only and **NOT** probability of equal skill or win rate.
