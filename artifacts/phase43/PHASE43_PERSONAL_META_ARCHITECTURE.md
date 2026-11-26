# Phase 43J Personal Meta Intelligence Architecture

## 1. Edition- & Patch-Partitioned Empirical Aggregation
`PersonalMetaService` (`backend/services/personal_meta_service.py`) constructs and persists `PersonalMetaProfile` objects keyed strictly by composite key `"{user_id}:{game_version}:{game_patch}"` into `public.phase43_personal_meta`.

### Hard Isolation Guarantees
- **User Isolation:** Scoped strictly to authenticated `user_id`.
- **Edition Wall:** `FC26` and `FC27` records are never pooled together.
- **Patch Isolation:** Filters `matches` strictly to `m.game_patch == patch` and `exps` strictly to `e.baseline_patch == patch` so gameplay balance updates (e.g. `PATCH_1.03` vs `PATCH_1.04`) never contaminate each other.
- **Synthetic Firewall:** Counts and strips `SYNTHETIC_FIXTURE` records (`synthetic_excluded_count`) prior to computing win/draw/loss tallies, `mean_conceded_transition_rate`, or `mean_defensive_compactness`.
- **Frozen V3.2.1 Preservation:** Reports `frozen_v321_weights_altered = False` identically on every profile; V3.2.1 player ranking weights remain untouched.

## 2. Empirical Formation Scoring & Vulnerability Profiling
- Computes per-formation `win_share = (wins + 0.5 * draws) / max(1, matches)` and defensive transition stability `(1.0 - mean_conceded_transition_rate)` with composite stability score `0.55 * stab + 0.45 * win_share`.
- Only nominates `strongest_system` once a formation reaches `>= 2` verified matches on that exact patch, avoiding single-match flukes.
- Aggregates recurring losses by `opponent_context["archetype"]` alongside verified `coaching_findings` codes into `vulnerable_matchups`.
- **Verified Test Behavior:**
  - `test_phase43b_to_e` proved `PATCH_1.04` aggregated `6` verified matches (`strongest_system="4-2-3-1"`, `frozen_v321_weights_altered=False`) while `PATCH_1.03` remained completely isolated at `eligible_match_count=0`.
