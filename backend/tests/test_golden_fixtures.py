"""Phase 18 -- golden fixture drift detection. Compares live engine output
against the committed golden_fixtures.json. A failure here means a future
change moved a specific, named scenario's output -- the diff tells you
exactly which one and lets you judge whether that was intended."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_golden_fixtures_v3_1 import build_fixtures

GOLDEN_PATH = Path(__file__).resolve().parents[2] / "artifacts" / "v3_1" / "calibration" / "golden_fixtures.json"


@pytest.fixture(scope="module")
def golden():
    if not GOLDEN_PATH.exists():
        pytest.skip("golden_fixtures.json not generated -- run scripts/build_golden_fixtures_v3_1.py")
    with open(GOLDEN_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def live():
    return build_fixtures()


class TestGoldenFixtureDrift:
    @pytest.mark.parametrize("key", [
        "tactical_LOW_BLOCK", "tactical_HIGH_PRESS", "tactical_POSSESSION",
        "tactical_BALANCED", "tactical_PACE_ABUSER", "tactical_DIRECT_PLAY",
        "thin_evidence", "position_mismatch", "playstyle_relevance",
        "no_playstyle_evidence", "same_attributes_different_ovr",
        "same_ovr_different_attributes",
    ])
    def test_fixture_unchanged(self, golden, live, key):
        assert live[key]["hash"] == golden[key]["hash"], (
            f"golden fixture '{key}' changed: was top={golden[key]['top_names'][:3]}, "
            f"now top={live[key]['top_names'][:3]} -- this is not necessarily wrong, "
            f"but it is a config/engine change that must be a deliberate, reviewed decision")

    def test_pool_ordering_still_identical(self, live):
        assert live["pool_ordering_a"]["hash"] == live["pool_ordering_b"]["hash"]
