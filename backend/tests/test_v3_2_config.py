"""V3.2 (Phase 24): versioned-config registry, version stamping, experiment boundary.

V3.2 differs from V3.1 in exactly one calibrated value: missing_value_charge
P10 -> ZERO (Phase 23 finding F-1: under P10, hiding a low published attribute
could RAISE C_lo). V3.1 stays reproducible as a frozen historical config.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from backend.services import v3_config as C
from backend.services.recommendation_engine_v3 import ENGINE_VERSION, RecommendationEngineV3
from backend.tests._v32_support import fc26_pool, fc26_reference
from backend.tests.helpers import make_req

V3_1_VERSION = "v3-2026-09-17-r1"


def test_v3_1_config_is_frozen_and_historical():
    cfg = C.V3_1_CONFIG
    assert cfg.config_version == V3_1_VERSION
    assert cfg.missing_value_charge == "P10"
    assert cfg.lam_default.value == 0.70
    assert cfg.tie_epsilon.value == 0.005
    assert dataclasses.is_dataclass(cfg) and cfg.__dataclass_params__.frozen


def test_v3_2_differs_from_v3_1_in_exactly_one_value_plus_its_version():
    a, b = C.V3_1_CONFIG, C.V3_2_CONFIG
    changed = {f.name for f in dataclasses.fields(a) if getattr(a, f.name) != getattr(b, f.name)}
    assert changed == {"config_version", "missing_value_charge"}, changed
    assert b.missing_value_charge == "ZERO"
    assert b.config_version != a.config_version


def test_default_config_is_v3_2():
    assert C.DEFAULT_V3_CONFIG is C.V3_2_CONFIG
    assert C.DEFAULT_V3_CONFIG.missing_value_charge == "ZERO"


def test_registry_resolves_both_versions_and_rejects_unknown():
    assert C.get_config(V3_1_VERSION) is C.V3_1_CONFIG
    assert C.get_config(C.V3_2_CONFIG.config_version) is C.V3_2_CONFIG
    with pytest.raises(KeyError):
        C.get_config("v3-does-not-exist")


def test_unknown_missing_charge_is_rejected_at_construction():
    with pytest.raises(ValueError):
        C.V3Config(missing_value_charge="P25")


def test_snapshot_reports_the_config_it_was_given():
    assert C.config_snapshot()["config_version"] == C.V3_2_CONFIG.config_version
    hist = C.config_snapshot(C.V3_1_CONFIG)
    assert hist["config_version"] == V3_1_VERSION
    assert hist["missing_value_charge"]["value"] == "P10"


@pytest.mark.parametrize("cfg", [C.V3_1_CONFIG, C.V3_2_CONFIG], ids=["v3.1", "v3.2"])
def test_engine_stamps_the_version_of_the_config_it_ran(cfg):
    engine = RecommendationEngineV3(config=cfg, reference=fc26_reference(),
                                    data_version=fc26_reference().version)
    res = engine.recommend(fc26_pool(), make_req(position="CM", tactical_profile="BALANCED", limit=5))
    assert res.config_version == cfg.config_version
    assert res.engine_version == ENGINE_VERSION
    assert {rc.context.config_version for rc in res.ranked} == {cfg.config_version}


def test_engine_version_identifies_v3_2():
    assert ENGINE_VERSION == "3.2.1"


def test_interaction_modifier_remains_disabled():
    engine = RecommendationEngineV3(reference=fc26_reference(), data_version=fc26_reference().version)
    res = engine.recommend(fc26_pool(), make_req(position="CM", tactical_profile="HIGH_PRESS", limit=25))
    assert res.ranked
    for rc in res.ranked:
        inter = [m for m in rc.context.modifiers if m.name == "interaction"]
        assert len(inter) == 1
        nums = {k: v for k, v in dataclasses.asdict(inter[0]).items()
                if isinstance(v, (int, float)) and "cap" not in k}
        assert all(v == 0.0 for v in nums.values()), nums


def test_no_production_module_imports_the_experiment_lab():
    """Experiment boundary (GK signed-pole, complementarity live ONLY in the lab)."""
    root = Path(__file__).resolve().parents[1]
    offenders = [str(p.relative_to(root)) for p in root.rglob("*.py")
                 if "tests" not in p.parts and p.name != "intelligence_lab.py"
                 and "intelligence_lab" in p.read_text(encoding="utf-8")]
    assert offenders == [], offenders
