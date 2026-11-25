"""Phase 41F & 41G: Possession Value Engine (Stage 1 Heuristic + Stage 2 Markov xT + Stage 3 Calibrated Gate).

Strictly separates heuristic scores from calibrated match outcome probabilities:
  - Stage 1: HeuristicPossessionValue (corridor clearance, kinematic arrival, xT progression, turnover risk)
  - Stage 2: ExpectedThreatEngine (configurable Markov transition grid solved via iterative Bellman recursion)
  - Stage 3: CalibratedEPVInterface (explicitly gated until empirical tracking cohort reaches calibrated threshold)
  - Stage G: Risk-Adjusted Utility keeps reward_component and risk_component separately inspectable.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np

from backend.domain.phase41_models import (
    DefensiveDecisionEval,
    PossessionValueBreakdown,
    PassingCorridorEval,
    ShootingDecisionEval,
    ValuationStage,
)
from backend.services.spatial_intelligence import PITCH_LENGTH_M, PITCH_WIDTH_M, _XT_MATRIX_12X8


class ExpectedThreatEngine:
    """Configurable iterative Markov Expected Threat (xT) grid solver (Karun Singh formulation)."""

    def __init__(self, cols: int = 12, rows: int = 8) -> None:
        self.cols = cols
        self.rows = rows
        self.xt_grid = np.array(_XT_MATRIX_12X8, dtype=np.float64) if (cols == 12 and rows == 8) else self._init_default_grid(rows, cols)
        self.is_empirical_fit = False

    def _init_default_grid(self, rows: int, cols: int) -> np.ndarray:
        x_norm = np.linspace(0.05, 0.98, cols)[None, :]
        y_center = np.abs(np.linspace(-1.0, 1.0, rows))[:, None]
        return np.clip(0.008 + 0.22 * (x_norm ** 3.2) * (1.0 - 0.55 * (y_center ** 2)), 0.005, 0.40)

    def fit_markov_surface(
        self,
        move_counts: np.ndarray,
        shot_counts: np.ndarray,
        goal_counts: np.ndarray,
        *,
        smoothing_alpha: float = 0.5,
        max_iter: int = 30,
        tol: float = 1e-6,
    ) -> Dict[str, float]:
        """Solves xT(z) = s(z)*g(z) + (1 - s(z)) * sum_{z'} T_{z->z'} * xT(z') cleanly with Dirichlet smoothing."""
        n_zones = self.rows * self.cols
        assert move_counts.shape == (n_zones, n_zones)
        assert shot_counts.shape == (n_zones,)
        assert goal_counts.shape == (n_zones,)

        total_moves = move_counts.sum(axis=1)
        total_actions = total_moves + shot_counts + 2.0 * smoothing_alpha
        p_shoot = (shot_counts + smoothing_alpha) / total_actions
        p_goal = np.where(shot_counts > 0, (goal_counts + 0.1 * smoothing_alpha) / (shot_counts + smoothing_alpha), 0.02)

        # Transition probabilities T_{z -> z'} smoothed gently with Karun baseline prior
        row_sums = move_counts.sum(axis=1, keepdims=True) + smoothing_alpha * n_zones
        trans = (move_counts + smoothing_alpha) / row_sums

        xt = np.zeros(n_zones, dtype=np.float64)
        deltas: List[float] = []
        for _ in range(max_iter):
            next_xt = p_shoot * p_goal + (1.0 - p_shoot) * (trans @ xt)
            delta = float(np.max(np.abs(next_xt - xt)))
            deltas.append(delta)
            xt = next_xt
            if delta < tol:
                break

        self.xt_grid = xt.reshape(self.rows, self.cols)
        self.is_empirical_fit = True
        return {
            "iterations": len(deltas),
            "final_max_delta": round(deltas[-1] if deltas else 0.0, 8),
            "max_xt": round(float(self.xt_grid.max()), 5),
            "min_xt": round(float(self.xt_grid.min()), 5),
        }

    def value_at(self, x_m: float, y_m: float, attacking_right: bool = True) -> float:
        x = max(0.0, min(PITCH_LENGTH_M - 1e-4, x_m))
        y = max(0.0, min(PITCH_WIDTH_M - 1e-4, y_m))
        if not attacking_right:
            x = PITCH_LENGTH_M - x
        col = min(self.cols - 1, int((x / PITCH_LENGTH_M) * self.cols))
        row = min(self.rows - 1, int(((PITCH_WIDTH_M - y) / PITCH_WIDTH_M) * self.rows))
        return round(float(self.xt_grid[row, col]), 4)


class CalibratedEPVInterface:
    """Future Stage 3 V(s) = P(score|s) - P(concede|s) contract gated until calibrated dataset exists."""

    def __init__(self, brier_score: Optional[float] = None, sample_matches: int = 0) -> None:
        self.brier_score = brier_score
        self.sample_matches = sample_matches

    @property
    def is_ready(self) -> bool:
        return self.sample_matches >= 25 and self.brier_score is not None and self.brier_score <= 0.20

    def status_report(self) -> Dict[str, object]:
        return {
            "stage": ValuationStage.STAGE_3_CALIBRATED_EPV_INTERFACE.value,
            "calibrated_ready": self.is_ready,
            "sample_matches": self.sample_matches,
            "brier_score": self.brier_score,
            "reason": (
                "Empirically calibrated EPV unlocked."
                if self.is_ready
                else "Gated: requires >= 25 calibrated EA FC matches with Brier <= 0.20; Stage 1/2 Heuristic & Markov xT active."
            ),
        }


class PossessionValueEngine:
    """Computes risk-adjusted decision utility keeping reward and risk components explicitly visible."""

    def __init__(
        self,
        xt_engine: Optional[ExpectedThreatEngine] = None,
        risk_aversion_lambda: float = 0.52,
    ) -> None:
        self.xt = xt_engine or ExpectedThreatEngine()
        self.risk_aversion_lambda = risk_aversion_lambda
        self.calibrated_gate = CalibratedEPVInterface()

    def score_pass(
        self,
        pass_eval: PassingCorridorEval,
        *,
        origin_xy: Tuple[float, float],
        rest_defense_count: int = 3,
        attacking_right: bool = True,
        pressure_near_carrier_m: float = 4.0,
    ) -> PossessionValueBreakdown:
        xt_orig = self.xt.value_at(origin_xy[0], origin_xy[1], attacking_right=attacking_right)
        xt_targ = self.xt.value_at(pass_eval.target_xy_m[0], pass_eval.target_xy_m[1], attacking_right=attacking_right)
        prog_val = (xt_targ - xt_orig) * 2.2

        # Corridor openness & receiver space bonus
        lane_bonus = max(-0.15, min(0.32, 0.22 * min(1.0, pass_eval.dynamic_interception_margin_sec / 0.85)))
        space_bonus = max(0.0, min(0.18, pass_eval.receiver_space_radius_m / 36.0))
        retention_bonus = 0.14 if (pass_eval.is_backward_or_lateral and pressure_near_carrier_m < 3.2 and pass_eval.dynamic_interception_margin_sec > 0.4) else 0.0

        reward = max(-0.08, prog_val + lane_bonus + space_bonus + retention_bonus)

        rest_mult = 1.25 if rest_defense_count < 3 else 0.90
        turnover_pen = pass_eval.turnover_exposure * 0.55 * rest_mult
        def_exposure = 0.10 if (pass_eval.distance_m > 22.0 and rest_defense_count <= 2) else 0.02
        risk = self.risk_aversion_lambda * (turnover_pen + def_exposure) / 0.52

        utility = round(reward - risk, 4)
        stage = ValuationStage.STAGE_2_MARKOV_XT if self.xt.is_empirical_fit else ValuationStage.STAGE_1_HEURISTIC_UTILITY
        return PossessionValueBreakdown(
            valuation_stage=stage,
            is_calibrated_probability=False,
            markov_xt_origin=xt_orig,
            markov_xt_target=xt_targ,
            raw_progression_value=round(prog_val, 4),
            lane_control_reward=round(lane_bonus + retention_bonus, 4),
            space_creation_bonus=round(space_bonus, 4),
            reward_component=round(reward, 4),
            turnover_risk_penalty=round(turnover_pen, 4),
            defensive_exposure_penalty=round(def_exposure, 4),
            risk_component=round(risk, 4),
            risk_adjusted_utility=utility,
        )

    def score_carry(
        self,
        origin_xy: Tuple[float, float],
        target_xy: Tuple[float, float],
        *,
        nearest_opp_to_target_m: float,
        rest_defense_count: int = 3,
        attacking_right: bool = True,
    ) -> PossessionValueBreakdown:
        xt_orig = self.xt.value_at(origin_xy[0], origin_xy[1], attacking_right=attacking_right)
        xt_targ = self.xt.value_at(target_xy[0], target_xy[1], attacking_right=attacking_right)
        prog_val = (xt_targ - xt_orig) * 1.8
        space_bonus = min(0.16, max(0.0, nearest_opp_to_target_m / 40.0))
        reward = max(0.02, prog_val + space_bonus + 0.09)
        risk = max(0.05, min(0.45, (4.5 - min(4.5, nearest_opp_to_target_m)) / 9.5)) * (1.15 if rest_defense_count < 3 else 0.92)
        return PossessionValueBreakdown(
            valuation_stage=ValuationStage.STAGE_1_HEURISTIC_UTILITY,
            is_calibrated_probability=False,
            markov_xt_origin=xt_orig,
            markov_xt_target=xt_targ,
            raw_progression_value=round(prog_val, 4),
            lane_control_reward=0.09,
            space_creation_bonus=round(space_bonus, 4),
            reward_component=round(reward, 4),
            turnover_risk_penalty=round(risk, 4),
            defensive_exposure_penalty=0.03,
            risk_component=round(risk + 0.03, 4),
            risk_adjusted_utility=round(reward - (risk + 0.03), 4),
        )

    def score_retain(
        self,
        origin_xy: Tuple[float, float],
        *,
        pressure_near_carrier_m: float,
        rest_defense_count: int = 3,
        attacking_right: bool = True,
    ) -> PossessionValueBreakdown:
        xt_orig = self.xt.value_at(origin_xy[0], origin_xy[1], attacking_right=attacking_right)
        reward = 0.24 if pressure_near_carrier_m < 3.5 else 0.19
        risk = 0.04 if rest_defense_count >= 3 else 0.07
        return PossessionValueBreakdown(
            valuation_stage=ValuationStage.STAGE_1_HEURISTIC_UTILITY,
            is_calibrated_probability=False,
            markov_xt_origin=xt_orig,
            markov_xt_target=xt_orig,
            raw_progression_value=0.0,
            lane_control_reward=round(reward, 4),
            space_creation_bonus=0.02,
            reward_component=round(reward + 0.02, 4),
            turnover_risk_penalty=round(risk, 4),
            defensive_exposure_penalty=0.01,
            risk_component=round(risk + 0.01, 4),
            risk_adjusted_utility=round(reward + 0.02 - (risk + 0.01), 4),
        )

    def score_shot(self, shoot_eval: ShootingDecisionEval) -> PossessionValueBreakdown:
        reward = round(shoot_eval.heuristic_shot_quality * 0.62, 4)
        risk = round(min(0.45, 0.10 + 0.05 * shoot_eval.defenders_in_shot_cone + max(0.0, shoot_eval.shot_distance_m - 16.0) * 0.012), 4)
        return PossessionValueBreakdown(
            valuation_stage=ValuationStage.STAGE_1_HEURISTIC_UTILITY,
            is_calibrated_probability=False,
            raw_progression_value=reward,
            lane_control_reward=0.0,
            space_creation_bonus=0.0,
            reward_component=reward,
            turnover_risk_penalty=risk,
            defensive_exposure_penalty=0.02,
            risk_component=round(risk + 0.02, 4),
            risk_adjusted_utility=round(reward - (risk + 0.02), 4),
            valuation_disclaimer=(
                "HEURISTIC_SHOT_UTILITY (NOT calibrated xG): reflects shot geometry, blocker cone, "
                "and possession-loss risk relative to extra pass/carry alternatives."
            ),
        )

    def score_defensive_option(self, def_eval: DefensiveDecisionEval) -> PossessionValueBreakdown:
        reward = round(0.32 * def_eval.central_channel_protection_score + 0.25 * def_eval.ball_carrier_exposure_score, 4)
        risk = round(0.42 * def_eval.displacement_risk + max(0.0, def_eval.line_integrity_delta_m) * 0.015, 4)
        return PossessionValueBreakdown(
            valuation_stage=ValuationStage.STAGE_1_HEURISTIC_UTILITY,
            is_calibrated_probability=False,
            raw_progression_value=round(def_eval.central_channel_protection_score * 0.32, 4),
            lane_control_reward=round(def_eval.ball_carrier_exposure_score * 0.25, 4),
            space_creation_bonus=0.0,
            reward_component=reward,
            turnover_risk_penalty=0.0,
            defensive_exposure_penalty=risk,
            risk_component=risk,
            risk_adjusted_utility=round(reward - risk, 4),
            valuation_disclaimer="HEURISTIC_DEFENSIVE_UTILITY: team-shape containment & Zone 14 protection balance.",
        )
