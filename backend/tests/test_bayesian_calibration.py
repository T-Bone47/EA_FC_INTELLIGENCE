"""Unit test suite for V3.3 Empirical Bayesian Calibration Engine (Phase 37)."""
import math
import pytest
from backend.domain.video_gameplay import EvidenceTier
from backend.services.bayesian_calibration import (
    BayesianCalibrationEngine,
    FROZEN_V321_PRIORS,
)


def test_prior_initialization():
    engine = BayesianCalibrationEngine()
    assert "weight_pace" in engine.priors
    assert "mod_high_press_forward_def" in engine.priors
    assert engine.priors["weight_pace"].v321_prior_mean == 0.22
    assert engine.priors["mod_high_press_forward_def"].v321_prior_mean == 1.15


def test_bayesian_updating_shrinkage():
    engine = BayesianCalibrationEngine()

    # Case 1: Zero observations -> Exactly prior
    cal_zero = engine.calculate_posterior_parameter("weight_pace", [])
    assert cal_zero.posterior_mean == 0.22
    assert cal_zero.shrinkage_factor == 1.0
    assert cal_zero.status == "CONSERVATIVE_PRIOR"
    assert cal_zero.sample_size == 0

    # Case 2: Small sample (2 Tier A observations pointing to 0.25)
    cal_small = engine.calculate_posterior_parameter(
        "weight_pace",
        [(0.25, EvidenceTier.TIER_A), (0.26, EvidenceTier.TIER_A)],
    )
    assert cal_small.posterior_mean > 0.22  # Shifted upwards towards 0.25
    assert cal_small.posterior_mean < 0.255 # But regularized by shrinkage
    assert cal_small.shrinkage_factor < 1.0
    assert cal_small.status == "CONSERVATIVE_PRIOR"
    assert cal_small.credible_interval_95[0] < cal_small.posterior_mean < cal_small.credible_interval_95[1]

    # Case 3: Large sample (35 Tier A observations)
    large_obs = [(0.25, EvidenceTier.TIER_A) for _ in range(35)]
    cal_large = engine.calculate_posterior_parameter("weight_pace", large_obs)
    assert cal_large.status == "FULLY_CERTIFIED"
    assert cal_large.shrinkage_factor < 0.30
    assert math.isclose(cal_large.posterior_mean, 0.25, abs_tol=0.01)


def test_calibrate_all_parameters():
    engine = BayesianCalibrationEngine()
    empirical = {
        "mod_high_press_forward_def": [
            (1.22, EvidenceTier.TIER_A),
            (1.20, EvidenceTier.TIER_A),
            (1.18, EvidenceTier.TIER_B),
        ],
        "mod_counterattack_sprint": [
            (1.30, EvidenceTier.TIER_A),
            (1.28, EvidenceTier.TIER_A),
        ]
    }
    all_cal = engine.calibrate_all_parameters(empirical)
    assert len(all_cal) == len(FROZEN_V321_PRIORS)

    hp_param = next(p for p in all_cal if p.parameter_name == "mod_high_press_forward_def")
    assert hp_param.sample_size == 3
    assert hp_param.posterior_mean > 1.15  # Shifted in direction of empirical evidence


def test_simulate_card_suitability():
    engine = BayesianCalibrationEngine()
    empirical = {
        "mod_high_press_forward_def": [
            (1.22, EvidenceTier.TIER_A),
            (1.21, EvidenceTier.TIER_A),
        ]
    }
    cal_params = {p.parameter_name: p for p in engine.calibrate_all_parameters(empirical)}

    # Dembélé with Defending 55 in High Press
    dembele_attrs = {"PAC": 93.0, "SHO": 78.0, "PAS": 82.0, "DRI": 90.0, "DEF": 55.0, "PHY": 65.0}
    comp_dembele = engine.simulate_card_suitability(
        card_name="Ousmane Dembélé",
        card_item_id="card-dembele-86",
        tactical_context="HIGH_PRESS",
        card_attributes=dembele_attrs,
        calibrated_params=cal_params,
    )

    assert comp_dembele.v321_baseline_score > 0.0
    assert comp_dembele.v33_posterior_score > comp_dembele.v321_baseline_score
    assert comp_dembele.score_delta > 0.0
    assert len(comp_dembele.shrinkage_explanation) > 10
