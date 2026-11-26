# Phase 44 Context Normalization & Data Hygiene

## 1. Synthetic Fixture & Edition Firewalls
- Every `MatchIntelligenceRecord`, `TacticalFingerprint`, and `decision_window` with `provenance == "SYNTHETIC_FIXTURE"` is rejected before feature accumulation; `synthetic_excluded_count` explicitly reports excluded fixtures.
- `game_version` strictly separates `FC26` from `FC27` records; optional `game_patch` and `gameplay_mode` filters allow patch-locked Gamer DNA profiling cleanly.

## 2. Context-Adjusted Telemetry
Inside `_extract_feature_from_match()` (`backend/services/gamer_dna_v2_engine.py`):
- **Possession under High Press:** `adj_poss = poss + max(0.0, (opp_press - 0.55) * 0.14)` prevents mistaking high-press opponent pressure (`pressing_intensity > 0.55`) for natural low-possession counter preference.
- **Directness under High Press:** `ctx_direct = direct - max(0.0, (opp_press - 0.65) * 0.10)` attenuates forced long clearances triggered purely by aggressive opposition pressing.
- **Abstention Propagated from CV Geometry:** When an attached Phase 43 `TacticalFingerprint` has `team_compactness_abstained == True` (`visible_outfield_players < 14`), `defensive_compactness_shape` and `in_possession_width_expansion` abstain unless fallback verified team compactness exists.

## 3. Recency & Quality Weighting + Leak-Free Scaling
- Each eligible match weight combines quality multiplier (`HIGH=1.0`, `MODERATE=0.82`, `LOW=0.58`, `INSUFFICIENT=0.25`) with exponential time decay `exp(-0.02 * age_days)`.
- `GamerDNAV2Engine.fit_robust_scaler_stats(train_vectors)` computes median and IQR strictly on designated training/reference cohorts (`scaler_fit_split="TRAIN_PROFILES_ONLY"` verified in `FC_GAMER_DNA_BENCH_V2`).
