import csv
import json

import pytest

from verification.evaluate_fc27_striker_pilot import evaluate, load_predictions
from verification.prepare_fc27_striker_pilot import OUT, schedule


@pytest.fixture
def sheet():
    predictions = load_predictions(OUT / "FROZEN_PREDICTIONS.json")
    return predictions, list(schedule(predictions))


def write_sheet(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def fill(rows):
    for row in rows:
        row.update(match_date="2026-01-01", game_patch="1.2.0", role="advanced forward",
                   game_mode="friendly", platform="pc", opponent_context="fixed",
                   skill_context="fixed", setup_key="fixed", minutes="90", evidence_locator="test only",
                   tackles_won="2" if row["card"] == "A" else "0",
                   shots_on_target="1" if row["card"] == "A" else "3")


def test_empty_sheet_reports_no_results(sheet, tmp_path):
    predictions, rows = sheet
    result = evaluate(write_sheet(tmp_path / "blank.csv", rows), predictions)
    assert result["played_rows"] == 0
    assert all(not tactic["strata"] for tactic in result["tactics"].values())


def test_reports_expected_directions_and_preserves_zero(sheet, tmp_path):
    predictions, rows = sheet
    fill(rows)
    result = evaluate(write_sheet(tmp_path / "full.csv", rows), predictions)
    press, counter = [result["tactics"][p]["strata"][0] for p in ("HIGH_PRESS", "COUNTER_ATTACK")]
    assert result["played_rows"] == 8
    assert press["evidence"]["paired_difference_per_90"] == 2
    assert counter["evidence"]["paired_difference_per_90"] == -2
    assert press["prediction_agreement"] == counter["prediction_agreement"] == "AGREES"
    assert {x["direction"] for x in press["sessions"].values()} == {"A"}
    assert {x["direction"] for x in counter["sessions"].values()} == {"B"}


@pytest.mark.parametrize("change", ["game_patch", "tackles_won"])
def test_mixed_patches_or_missing_values_prevent_pooled_rates(sheet, tmp_path, change):
    predictions, rows = sheet
    fill(rows)
    for row in rows:
        if row["session_key"] == "s2" and row["tactical_profile"] == "HIGH_PRESS":
            row[change] = "1.3.0" if change == "game_patch" else ""
    result = evaluate(write_sheet(tmp_path / "split.csv", rows), predictions)
    strata = result["tactics"]["HIGH_PRESS"]["strata"]
    assert len(strata) == (2 if change == "game_patch" else 1)
    assert all(s["evidence"]["paired_difference_per_90"] is None for s in strata)


def test_replacement_requires_excluding_both_originals(sheet, tmp_path):
    predictions, rows = sheet
    fill(rows)
    replacements = [dict(row, match_key=row["match_key"] + "-retry") for row in rows[:2]]
    rows[0]["deviation"] = "disconnect"
    with pytest.raises(ValueError, match="both original"):
        evaluate(write_sheet(tmp_path / "rerun.csv", rows + replacements), predictions)
    rows[1]["deviation"] = "discarded block"
    result = evaluate(write_sheet(tmp_path / "rerun.csv", rows + replacements), predictions)
    assert result["played_rows"] == 8
    assert result["excluded_original_rows"] == 2


def test_rejects_modified_exact_card_or_predictions(sheet, tmp_path):
    predictions, rows = sheet
    rows[0]["source_item_id"] = rows[1]["source_item_id"]
    with pytest.raises(ValueError, match="frozen schedule"):
        evaluate(write_sheet(tmp_path / "wrong-card.csv", rows), predictions)
    path = tmp_path / "modified.json"
    path.write_text(json.dumps({**predictions, "engine": "modified"}), encoding="utf-8")
    with pytest.raises(ValueError, match="original frozen predictions"):
        load_predictions(path)
