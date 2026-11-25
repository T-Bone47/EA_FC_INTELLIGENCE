"""Phase 24 -- V3.2 golden drift + V3.1 reproducibility + the reviewed change set.

The V3.1 goldens (artifacts/v3_1/...) are NOT regenerated. They are still checked
against the HISTORICAL V3.1 config, which is what proves V3.1 is reproducible.
The V3.2 goldens live in artifacts/v3_2/... and the exact set of fixtures that
moved is pinned here on purpose: changing it needs a deliberate, reviewed edit.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.services.v3_config import V3_1_CONFIG, V3_2_CONFIG
from scripts.build_golden_fixtures_v3_1 import build_fixtures
from scripts.build_golden_fixtures_v3_2 import leaves

ROOT = Path(__file__).resolve().parents[2]
V31_GOLDEN = ROOT / "artifacts" / "v3_1" / "calibration" / "golden_fixtures.json"
V32_GOLDEN = ROOT / "artifacts" / "v3_2" / "calibration" / "golden_fixtures.json"
V32_DIFF = ROOT / "artifacts" / "v3_2" / "calibration" / "golden_diff_v3_1_to_v3_2.json"

# Reviewed in Phase 24: 6 named fixtures guarded by test_golden_fixtures.py + the
# 7th (same_player_two_tactics, 2 fingerprints) that the V3.1 test never asserted.
EXPECTED_CHANGED = {
    "no_playstyle_evidence", "playstyle_relevance", "position_mismatch",
    "same_attributes_different_ovr", "same_ovr_different_attributes", "thin_evidence",
    "same_player_two_tactics.high_press", "same_player_two_tactics.low_block",
}


def _hashes(d):
    return {p: f["hash"] for p, f in leaves(d)}


@pytest.fixture(scope="module")
def live_v31():
    return _hashes(build_fixtures(V3_1_CONFIG))


@pytest.fixture(scope="module")
def live_v32():
    return _hashes(build_fixtures(V3_2_CONFIG))


def test_v3_1_pinned_config_reproduces_the_committed_v3_1_goldens(live_v31):
    committed = _hashes(json.loads(V31_GOLDEN.read_text(encoding="utf-8")))
    assert live_v31 == committed


def test_default_builder_is_pinned_to_v3_1(live_v31):
    assert _hashes(build_fixtures()) == live_v31


def test_v3_2_engine_matches_the_committed_v3_2_goldens(live_v32):
    committed = _hashes(json.loads(V32_GOLDEN.read_text(encoding="utf-8")))
    assert live_v32 == committed


def test_v3_2_golden_declares_its_config():
    meta = json.loads(V32_GOLDEN.read_text(encoding="utf-8"))["_meta"]
    assert meta["config_version"] == V3_2_CONFIG.config_version
    assert meta["missing_value_charge"] == "ZERO"


def test_exactly_the_reviewed_fixtures_changed(live_v31, live_v32):
    changed = {p for p in live_v31 if live_v31[p] != live_v32[p]}
    assert changed == EXPECTED_CHANGED, sorted(changed ^ EXPECTED_CHANGED)


def test_change_report_shows_only_partial_coverage_candidates_move_and_c_lo_only_falls():
    rep = json.loads(V32_DIFF.read_text(encoding="utf-8"))
    assert rep["v3_1_reproduces_committed_goldens"] is True
    assert set(rep["changed"]) == EXPECTED_CHANGED
    for path in rep["changed"]:
        deltas = rep["fixtures"][path]["candidate_deltas_first5"]
        assert any(d["kappa"] < 1.0 for d in deltas), path
        for d in deltas:
            assert d["delta_c_lo"] <= 1e-12, (path, d)
            if d["kappa"] == 1.0:
                assert d["delta_c_lo"] == 0.0 and d["r_v3_1"] == d["r_v3_2"], (path, d)
