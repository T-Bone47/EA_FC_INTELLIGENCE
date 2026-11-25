"""Unit and integration tests for Phase 33 Empirical Evaluator."""
import csv
import json
from pathlib import Path
import pytest

from backend.services.empirical_evaluator import (
    EmpiricalEvaluator,
    compute_bootstrap_ci,
    compute_paired_effect_size,
    compute_paired_t_test,
    compute_wilcoxon_signed_rank,
)
from verification.evaluate_fc27_striker_pilot import load_predictions
from verification.prepare_fc27_striker_pilot import OUT, schedule


@pytest.fixture
def pilot_setup():
    pred_path = OUT / "FROZEN_PREDICTIONS.json"
    predictions = load_predictions(pred_path)
    rows = list(schedule(predictions))
    return pred_path, predictions, rows


def write_csv(path: Path, rows: list) -> Path:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def fill_controlled_data(rows: list, press_diff: int = 2, counter_diff: int = -2):
    """Fill controlled match data conforming to SOP-33-01."""
    for row in rows:
        is_a = row["card"] == "A"
        tactic = row["tactical_profile"]
        
        # Primary endpoints
        if tactic == "HIGH_PRESS":
            tackles = 3 if is_a else (3 - press_diff)
            sot = 1 if is_a else 1
        else: # COUNTER_ATTACK
            tackles = 0 if is_a else 0
            sot = 1 if is_a else (1 - counter_diff)
            
        row.update({
            "match_date": "2026-11-20",
            "game_patch": "1.2.0",
            "role": "advanced forward",
            "game_mode": "friendly",
            "platform": "pc",
            "opponent_context": "legendary ai",
            "skill_context": "pilot operator a",
            "setup_key": "standard-preset",
            "minutes": "90",
            "evidence_locator": f"sha256:test-{row['match_key']}",
            "tackles_won": str(tackles),
            "interceptions": "2" if is_a else "0",
            "shots": str(sot + 1),
            "shots_on_target": str(sot),
            "goals": "1" if sot > 1 else "0",
        })


def test_statistics_helpers():
    diffs = [2.0, 2.0, 2.0]
    eff = compute_paired_effect_size(diffs)
    assert eff["mean_diff"] == 2.0
    assert eff["n_pairs"] == 3
    
    diffs_var = [1.0, 2.0, 3.0]
    eff_var = compute_paired_effect_size(diffs_var)
    assert eff_var["mean_diff"] == 2.0
    assert eff_var["std_diff"] == 1.0
    assert eff_var["cohens_d"] == 2.0
    
    ci = compute_bootstrap_ci(diffs_var, n_resamples=500)
    assert ci["ci_lower"] is not None
    assert ci["ci_upper"] is not None
    assert ci["ci_lower"] <= 2.0 <= ci["ci_upper"]

    t_res = compute_paired_t_test(diffs_var)
    assert t_res["t_statistic"] is not None
    assert t_res["degrees_of_freedom"] == 2
    assert t_res["p_value"] is not None

    diffs_wilc = [1.0, 2.0, 1.5, 3.0, 2.5, 1.8]
    w_res = compute_wilcoxon_signed_rank(diffs_wilc)
    assert w_res["w_statistic"] == 0.0
    assert w_res["p_value"] is not None


def test_empirical_evaluator_blank_sheet(pilot_setup, tmp_path):
    pred_path, _, rows = pilot_setup
    sheet = write_csv(tmp_path / "blank.csv", rows)
    evaluator = EmpiricalEvaluator(pred_path)
    res = evaluator.evaluate_sheet(sheet)
    
    assert res["total_matches_ingested"] == 0
    assert res["evidence_status"] == "NO_DATA"
    for tac in res["tactics"].values():
        assert tac["status"] == "INSUFFICIENT_GAMEPLAY_EVIDENCE"


def test_empirical_evaluator_full_matches(pilot_setup, tmp_path):
    pred_path, _, rows = pilot_setup
    fill_controlled_data(rows, press_diff=2, counter_diff=-2)
    sheet = write_csv(tmp_path / "full.csv", rows)
    evaluator = EmpiricalEvaluator(pred_path)
    res = evaluator.evaluate_sheet(sheet)
    
    assert res["total_matches_ingested"] == 8
    assert res["evidence_status"] == "DESCRIPTIVE_EVALUATION_COMPLETE"
    
    # High press evaluation
    hp = res["tactics"]["HIGH_PRESS"]["strata"][0]
    assert hp["prediction_agreement"] == "AGREES"
    assert hp["direction"] == "A"
    assert hp["observed_delta_per_90"] == 2.0
    assert hp["effect_size"]["mean_diff"] == 2.0
    assert hp["predicted_leader"] == "A"
    
    # Counter attack evaluation
    ca = res["tactics"]["COUNTER_ATTACK"]["strata"][0]
    assert ca["prediction_agreement"] == "AGREES"
    assert ca["direction"] == "B"
    assert ca["observed_delta_per_90"] == -2.0
    assert ca["effect_size"]["mean_diff"] == -2.0
    assert ca["predicted_leader"] == "B"
    
    # Secondary metrics check
    assert "interceptions" in hp["secondary_metrics"]
    assert hp["secondary_metrics"]["interceptions"]["direction"] == "A"
