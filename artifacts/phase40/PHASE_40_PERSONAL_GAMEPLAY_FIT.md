# PHASE 40G: PersonalGameplayFit Advisory Intelligence

**Implementation:** [personal_gameplay_fit.py](../../backend/services/personal_gameplay_fit.py)

## 1. Preservation of Frozen V3.2.1 Baseline
The deterministic V3.2.1 core (`recommendation_engine_v3.py`, `v3_config.py`) remains completely unmodified (`frozen_v321_untouched = True`). `PersonalGameplayFitService` operates purely as an advisory layer combining canonical player suitability with personal gameplay context.

## 2. Tactical-First Intervention Gate
Before recommending any player acquisition, `diagnose_intervention` maps observed recurring mistakes and Gamer DNA into:
1. `INSUFFICIENT_EVIDENCE` (cold start / zero real gameplay -> fallback to static suitability only)
2. `NO_SQUAD_CHANGE_NEEDED`
3. `GAMEPLAY_PRACTICE`
4. `TACTICAL_INSTRUCTION_ADJUSTMENT`
5. `FORMATION_ADJUSTMENT`
6. `ROLE_ADJUSTMENT`
7. `PLAYER_REPLACEMENT` (triggered only when structural mistake rate clears thresholds or capability bottlenecks persist)

## 3. Advisory Shadow Scoring Formula & Coefficient Disclosure
$$\text{fit\_score} = 0.50 \cdot \text{v321\_suitability} + 0.18 \cdot \text{style\_compatibility} + 0.17 \cdot \text{weakness\_coverage} + 0.15 \cdot \text{cohesion\_and\_role\_fit}$$

- Explicitly labeled `ADVISORY_SHADOW_HEURISTIC_UNOPTIMIZED` (never misrepresented as empirically optimized match-win probabilities).
- Sensitivity & Fallback: When `eligible_match_count == 0`, automatically switches to `mode = "STATIC_SUITABILITY_ONLY"` returning frozen base suitability alone.
- Market & Chemistry Honesty: Absent live prices always stamp `market_price_status = "MARKET_PRICE_UNAVAILABLE"`; unverified chemistry never fabricates numeric chemistry scores.
