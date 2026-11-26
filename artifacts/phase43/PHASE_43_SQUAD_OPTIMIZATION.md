# Phase 43 Multi-Objective Squad Optimization Specification

## 1. Utility Formulation
`MultiObjectiveSquadOptimizer` (`backend/services/multi_objective_squad_optimizer.py`) solves constrained 11-player lineup selection maximizing:

$$U(S) = w_{\text{base}}\text{BaseFit} + w_{\text{personal}}\text{PersonalFit} + w_{\text{cohesion}}\text{RoleCohesion} + w_{\text{partner}}\text{Partnership} + w_{\text{dna}}\text{PlaystyleDNA} - w_{\text{weak}}\text{WeaknessExposure} - w_{\text{cost}}\text{ReplacementCost}$$

across 7 selectable objectives (`PERSONALIZED`, `BALANCED`, `ATTACKING`, `DEFENSIVE`, `POSSESSION`, `COUNTER_ATTACK`, `PRESSING`) while generating up to 3 diverse alternative XIs (`alternatives`) and keeping frozen `V3.2.1` scoring weights untouched (`frozen_v321_weights_altered = False`).

## 2. Hard Constraints Enforced
- `exact_11_players`: 11 slots matching `slots_for(formation)` across all 12 formations.
- `single_gk`: Exactly 1 goalkeeper strictly assigned to slot `0`.
- `all_players_unique`: Zero duplicate footballer entities.
- `position_slots_valid`: Candidate primary or secondary positions match `_POS_COMPAT` unless explicitly pinned in `locked_slots`.
- `edition_isolated`: Candidate pool strictly partitioned by `FC26` vs `FC27`.
- `budget_verified_only`: Cost penalty and budget filter apply strictly when verified `coin_cost` values are present; unpriced players report `MARKET_PRICE_UNAVAILABLE`.

## 3. Solver & Exact Combinatorial Parity
Uses `scipy.optimize.linear_sum_assignment` on the feasible `(11 x N)` slot-utility cost matrix, then runs an exact exhaustive enumeration check (`itertools.product`, top-3 per slot when combinations <= 12,000, else top-2 <= 2,048) to report `exact_parity_checked` and `exact_optimal_gap` (`0.0` in `FC_TACTICAL_EXPERIMENT_BENCH_V1` Category E).
