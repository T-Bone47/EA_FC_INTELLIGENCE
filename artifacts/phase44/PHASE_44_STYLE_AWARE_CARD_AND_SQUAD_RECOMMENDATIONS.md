# Phase 44 Style-Aware Card & Squad Recommendations

## 1. Frozen V3.2.1 Preservation (`backend/services/style_squad_training_bridge.py`)
- `StyleAwareRecommendationService.recommend_players()` calls `RecommendationServiceV3().recommend(...)` verbatim without touching a single constant inside `recommendation_engine_v3.py` or `v3_config.py` (`frozen_v321_weights_altered = False`).
- Computes an **additive advisory layer** (`StyleAwareRecommendationAdjustment`) across two selectable modes:
  - `SUPPORT_NATURAL_STYLE`: `0.68 * base_v321 + 0.24 * (style_align * 100) + 0.08 * (weak_comp * 100)` boosting PlayStyles matching the user's archetype (`Tiki Taka` / `Incisive Pass` for `Possession Architect`, `Quick Step` / `Rapid` for `Counter-Attacking Specialist`, etc.).
  - `COMPENSATE_WEAKNESS`: `0.65 * base_v321 + 0.12 * (style_align * 100) + 0.23 * (weak_comp * 100)` elevating defensive/retention PlayStyles (`Intercept`, `Anticipate`, `Press Proven`, `Jockey`) linked to Group G priority gaps.
- Live market price honesty: sets `market_price_status = "MARKET_PRICE_UNAVAILABLE"` consistently across responses.

## 2. Style-Compatible Formation Alignment
`StyleAwareRecommendationService.recommend_formations()` pairs Phase 43 `PersonalFormationEngine` (correct argument signature `(p40_repo, p43_repo, p41_repo)`) with Gamer DNA V2 archetype classification cleanly.
