# PHASE 41: Decision Regret Formal Spec & Epistemic Rules

**Modules:** `backend/services/counterfactual_football_engine.py`, `backend/services/football_iq_engine.py`

1. **Pre-Action Only Invariant:** `PostActionOutcome` cannot influence $Q(s, a')$ or $R(s, a)$. Swapping a failed pass's outcome (`TURNOVER` vs `GOAL`) leaves candidate utility ranks and Decision Regret bit-for-bit identical.
2. **Indistinguishability Tolerance:** When candidate `[q_p10, q_p90]` uncertainty bands overlap `#1` within Monte Carlo localization/coverage perturbation noise, rank differences are flagged `indistinguishable_from_best = True` rather than penalized harshly.
3. **Abstention Compliance:** Frames with `REJECTED` calibration, `UNRELIABLE` bands, or `< 40%` coverage emit `ABSTAINED_INSUFFICIENT_CONTEXT` and emit `regret_estimate = None`.
