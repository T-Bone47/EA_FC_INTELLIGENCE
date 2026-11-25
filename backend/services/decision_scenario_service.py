"""Phase 41R: Multi-Answer Decision Training Scenario Generator (Phase 42 Bridge).

Converts evaluated pre-action Decision Windows & Counterfactual Comparisons into interactive
blind-review Training Scenarios (`hide_outcome_by_default=True`) supporting multiple defensible answers.
"""
from __future__ import annotations

from typing import Dict, List

from backend.domain.phase41_models import (
    CounterfactualComparison,
    DecisionTrainingScenario,
    FootballDecisionState,
)
from backend.services.decision_state_builder import strip_hindsight


class DecisionScenarioService:
    """Generates multi-option tactical training scenarios without hindsight leakage."""

    def build_scenario(
        self,
        raw_state: FootballDecisionState,
        comparison: CounterfactualComparison,
    ) -> DecisionTrainingScenario:
        state = strip_hindsight(raw_state)
        assert state.post_action_outcome is None

        cands = comparison.candidates or []
        best_u = comparison.best_alternative_utility or 0.0

        options_payload: List[Dict[str, object]] = []
        defensible_ids: List[str] = []
        margins: Dict[str, float] = {}
        expls: Dict[str, str] = {}

        for c in cands[:5]:
            u = c.value_breakdown.risk_adjusted_utility if c.value_breakdown else 0.0
            reg = max(0.0, round(best_u - u, 4))
            margins[c.action_id] = reg
            if reg <= 0.045 or c.action_id == comparison.best_alternative_id:
                defensible_ids.append(c.action_id)

            expls[c.action_id] = (
                f"{c.label}: pre-action utility {u:+.3f} (regret {reg:.3f}). "
                + (
                    f"Interception margin {c.passing_eval.dynamic_interception_margin_sec:+.2f}s, "
                    f"xT delta {c.passing_eval.xt_delta:+.3f}."
                    if c.passing_eval
                    else (
                        f"Defensive central cover {c.defensive_eval.central_channel_protection_score:.2f}."
                        if c.defensive_eval
                        else "Pre-action heuristic estimate."
                    )
                )
            )
            options_payload.append({
                "action_id": c.action_id,
                "action_family": c.action_family,
                "label": c.label,
                "target_slot": c.target_slot,
                "target_xy_m": c.target_xy_m,
                "feasibility": c.feasibility.value,
                "epistemic_tag": c.epistemic_tag.value,
            })

        reg_est = comparison.regret_estimate or 0.0
        difficulty = "ADVANCED" if reg_est >= 0.12 else ("INTERMEDIATE" if reg_est >= 0.05 else "FUNDAMENTAL")

        prompt = (
            f"At {state.action_timestamp_sec:.1f}s (Zone {state.pitch_zone}, {state.decision_type.value.replace('_', ' ').lower()}), "
            f"choose the highest-balance pre-action option before outcome occurs."
        )

        # Compact safe snapshot (outcome explicitly excluded)
        safe_snap = {
            "window_id": state.window_id,
            "match_id": state.match_id,
            "timestamp_sec": state.action_timestamp_sec,
            "ball_xy": (state.pre_action_ball.x_m, state.pre_action_ball.y_m),
            "possession_team": state.pre_action_ball.possession_team,
            "players": [
                {
                    "track_id": p.track_id,
                    "team": p.team,
                    "player_slot": p.player_slot,
                    "x_m": p.x_m,
                    "y_m": p.y_m,
                    "is_goalkeeper": p.is_goalkeeper,
                }
                for p in state.pre_action_players
            ],
        }

        return DecisionTrainingScenario(
            scenario_id=f"SCN-{state.window_id}",
            match_id=state.match_id,
            window_id=state.window_id,
            action_timestamp_sec=state.action_timestamp_sec,
            skill_dimension=state.decision_type.value,
            provenance=state.provenance,
            hide_outcome_by_default=True,
            pre_action_snapshot=safe_snap,
            prompt=prompt,
            candidate_options=options_payload,
            defensible_option_ids=defensible_ids,
            best_option_id=comparison.best_alternative_id,
            utility_margins=margins,
            explanation_by_option=expls,
            difficulty_level=difficulty,
        )
