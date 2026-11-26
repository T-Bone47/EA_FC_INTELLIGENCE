# Phase 44 Style Feature Architecture (60-Feature Epistemic Vector)

## 1. Strict Separation Principle
- Implemented in `backend/services/gamer_dna_v2_engine.py` (`FEATURE_CATALOG_V2`, `STYLE_FEATURE_IDS`, `PROFICIENCY_FEATURE_IDS`).
- Total canonical features: **60**, strictly partitioned:
  - **Groups A–F (53 Playing-Style Features):** Tactical tendencies, pitch zone choices, pressing aggression, build-up tempo, decision preference, and state/pressure adaptability. Used exclusively in distance & archetype classification.
  - **Group G (7 Technical Execution Features):** `pass_success_rate`, `possession_loss_rate`, `shooting_execution_quality`, `defensive_recovery_success`, `decision_regret_inverse`, `execution_consistency`, `opportunity_conversion_rate`. Flagged with `is_proficiency_only = True` and **strictly excluded** from all playing-style distance computations.

## 2. Feature Groups Summary
| Group | Enum (`FeatureGroup`) | Count | Primary Signals |
|---|---|---|---|
| A | `POSSESSION_BUILDUP` | 10 | `possession_duration_norm`, `pass_frequency`, `short_pass_preference`, `long_pass_preference`, `backward_pass_frequency`, `lateral_circulation`, `progressive_passing_preference`, `direct_progression`, `possession_retention_preference`, `build_up_speed` |
| B | `ATTACKING_IDENTITY` | 10 | `central_attacking_preference`, `wide_attacking_preference`, `through_ball_preference`, `crossing_preference`, `carrying_frequency`, `counter_attacking_behaviour`, `attacking_transition_speed`, `shot_selection_preference`, `chance_creation_pattern_directness`, `risk_taking_preference` |
| C | `DEFENSIVE_IDENTITY` | 10 | `defensive_line_depth`, `defensive_compactness_shape`, `pressing_tendency`, `containment_behaviour`, `midfield_recovery`, `centre_back_displacement_tendency`, `central_protection`, `wide_defensive_coverage`, `transition_recovery_speed`, `defensive_player_selection_activity` |
| D | `SPATIAL_TACTICAL` | 10 | `attacking_width`, `average_team_depth`, `midfield_spacing`, `half_space_occupation`, `preferred_progression_central_zone`, `passing_network_density`, `overload_creation`, `formation_fluidity`, `in_possession_width_expansion`, `out_of_possession_block_height` |
| E | `DECISION_PREFERENCE` | 6 | `safer_alternative_preference`, `progressive_action_preference`, `pass_vs_shoot_preference`, `risk_reward_tendency`, `maintain_possession_preference`, `defensive_contain_vs_step_preference` |
| F | `TACTICAL_ADAPTABILITY` | 7 | `pressure_response_shift`, `leading_state_control`, `trailing_state_directness`, `compact_block_patience`, `vs_high_press_adaptation`, `confirmed_formation_switching_rate`, `cross_match_tactical_variance` |
| G | `TECHNICAL_EXECUTION` | 7 | Proficiency/execution-only metrics (`is_proficiency_only = True`); isolated to Elite Skill-Gap diagnostics |

## 3. Non-Imputation & Compositional Distributions
- Absent observations remain `raw_value = None` and `normalized_value = None` with `source_type = UNKNOWN` — zero-imputation is strictly prohibited.
- Compositional distributions (`pass_direction_distribution`, `possession_duration_distribution`) are normalized simplex probability maps computed when supporting telemetry signals exist.
