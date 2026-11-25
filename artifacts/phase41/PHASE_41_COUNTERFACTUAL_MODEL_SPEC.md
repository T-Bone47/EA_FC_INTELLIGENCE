# PHASE 41K/41L: Counterfactual Football Engine & Decision Regret Index Specification

**Module:** `backend/services/counterfactual_football_engine.py`

## 1. Counterfactual Valuation Tiers
| Tier | Scope | Implementation State |
| :--- | :--- | :--- |
| **Tier 1 (`TIER_1_GEOMETRIC`)** | Point-to-segment corridor clearance & geometric space availability | **Implemented** (`_closest_point_on_segment`) |
| **Tier 2 (`TIER_2_HEURISTIC_TACTICAL`)** | Kinematic time-to-intercept margin $M$, Markov xT progression delta, defensive central protection, and transition risk penalty | **Active Default** (`CounterfactualFootballEngine`) |
| **Tier 3 (`TIER_3_CALIBRATED_GATE`)** | Empirical EPV ($P(\text{score}\mid s) - P(\text{concede}\mid s)$) calibrated on verified tracking cohorts | **Gated Contract** (`CalibratedEPVInterface` requires $\ge 25$ calibrated matches, Brier $\le 0.20$) |
| **Tier 4 (`TIER_4_SIMULATOR_CONTRACT`)** | Controlled tactical counterfactual rollout experiment interface | **Contract Hooked** |

## 2. Decision Regret Index
$$R(s, a) = \max\Big(0,\; \max_{a' \in \mathcal{A}_{\text{feasible}}(s)} Q_{\text{pre}}(s, a') - Q_{\text{pre}}(s, a)\Big)$$
- Guaranteed non-negative ($R(s, a) \ge 0$).
- Normalized regret band maps into `OPTIMAL` ($\le 0.025$), `MARGINAL` ($\le 0.06$), `MODERATE_REGRET` ($\le 0.14$), `HIGH_REGRET` ($> 0.14$).
- Cluster-deduplicated aggregation prevents slow continuous dribble/screen intervals from compounding into artificial regret spikes.
