"""V3.2 missing-data invariant + regression safety on real FC26 and FC27 data.

INV (missing data): hiding a published demanded attribute can NEVER raise C_lo.
Under the historical V3.1 charge (P10) it can (Phase 23 F-1); V3.2 (ZERO) cannot.
"""
from __future__ import annotations

import pytest

from backend.services.capability_model import compute_capability
from backend.services.demand_composition import compose_demand
from backend.services.recommendation_engine_v3 import RecommendationEngineV3
from backend.services.v3_config import DEFAULT_V3_CONFIG, V3_1_CONFIG, V3_2_CONFIG
from backend.tests._v32_support import (fc26_pool, fc26_reference, fc27_midfield_pool,
                                        fc27_reference)
from backend.tests.helpers import make_req

LAM = DEFAULT_V3_CONFIG.lam_default.value


def _probe(pool, position, profile, reference, charge, n=150):
    demand = compose_demand(position=position, tactical_profile=profile, lam=LAM).vector
    sample = [c for c in pool if c.position_primary == position][::7][:n]
    probes = violations = 0
    for c in sample:
        full = {a: c.attributes.get(a) for a in demand}
        base = compute_capability(demand=demand, attributes=full, position=position,
                                  reference=reference, missing_charge=charge).c_lo
        for a in demand:
            if full[a] is None:
                continue
            hidden = dict(full); hidden[a] = None
            hc = compute_capability(demand=demand, attributes=hidden, position=position,
                                    reference=reference, missing_charge=charge).c_lo
            probes += 1
            violations += hc > base + 1e-12
    return violations, probes


@pytest.mark.parametrize("profile", ["BALANCED", "HIGH_PRESS", "LOW_BLOCK"])
def test_v3_2_hiding_an_attribute_never_raises_c_lo(profile):
    v, n = _probe(fc26_pool(), "CM", profile, fc26_reference(), V3_2_CONFIG.missing_value_charge)
    assert n > 500, n
    assert v == 0, f"{v}/{n} missing-data violations under V3.2"


def test_v3_1_historical_config_still_exhibits_the_documented_defect():
    """Reproducibility of V3.1: the frozen config must still show F-1."""
    v, n = _probe(fc26_pool(), "CM", "BALANCED", fc26_reference(), V3_1_CONFIG.missing_value_charge)
    assert v > 0, f"expected the V3.1 (P10) defect to reproduce; got {v}/{n}"


def test_capability_default_charge_follows_the_default_config():
    demand = compose_demand(position="CM", tactical_profile="BALANCED", lam=LAM).vector
    c = next(x for x in fc26_pool() if x.position_primary == "CM")
    attrs = {a: c.attributes.get(a) for a in demand}
    ref = fc26_reference()
    implicit = compute_capability(demand=demand, attributes=attrs, position="CM", reference=ref)
    explicit = compute_capability(demand=demand, attributes=attrs, position="CM", reference=ref,
                                  missing_charge=DEFAULT_V3_CONFIG.missing_value_charge)
    assert implicit.c_lo == explicit.c_lo


def _ranking(cfg, pool, reference, position, profile, game_version, limit=50):
    eng = RecommendationEngineV3(config=cfg, reference=reference, data_version=reference.version)
    res = eng.recommend(pool, make_req(game_version=game_version, position=position,
                                       tactical_profile=profile, limit=limit))
    return [(str(rc.context.candidate_entity_id), rc.context.r, rc.context.coverage_kappa)
            for rc in res.ranked]


@pytest.mark.parametrize("position", ["CM", "ST", "CB", "GK"])
@pytest.mark.parametrize("profile", ["BALANCED", "HIGH_PRESS", "LOW_BLOCK"])
def test_fc26_rankings_identical_v3_1_vs_v3_2(position, profile):
    a = _ranking(V3_1_CONFIG, fc26_pool(), fc26_reference(), position, profile, "FC26")
    b = _ranking(V3_2_CONFIG, fc26_pool(), fc26_reference(), position, profile, "FC26")
    assert a and a == b
    assert all(k == 1.0 for _, _, k in a), "premise: complete evidence on the top-50"


@pytest.mark.parametrize("profile", ["BALANCED", "HIGH_PRESS"])
def test_fc27_rankings_identical_v3_1_vs_v3_2(profile):
    ref = fc27_reference()
    a = _ranking(V3_1_CONFIG, fc27_midfield_pool(), ref, "CM", profile, "FC27")
    b = _ranking(V3_2_CONFIG, fc27_midfield_pool(), ref, "CM", profile, "FC27")
    assert a and a == b
