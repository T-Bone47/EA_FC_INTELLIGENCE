"""T0 — mathematical invariants for the v3 engine.

Per INTELLIGENCE_TEST_MATRIX.md S3. These are build-blocking: a v3 release
that fails any of these has not merely regressed a feature, it has broken a
property the whole architecture is built on. No database required — pure
math against in-memory candidates and (where noted) the real foundation
pool via foundation_loader.
"""
from __future__ import annotations

import copy
import random
import uuid

import pytest

from backend.data_access.foundation_loader import load_foundation_candidates
from backend.domain.card_model import DETAIL_ATTRS, GK_ATTRS, PlayerAttributes
from backend.domain.user_model import UserRequirements
from backend.services.capability_model import compute_capability
from backend.services.demand_composition import compose_demand
from backend.services.recommendation_engine_v3 import RecommendationEngineV3
from backend.services.reference_distribution import load_reference_distribution
from backend.services.scoring_context import reconstruct_score, reconstruct_score_hi
from backend.services.v3_config import DEFAULT_V3_CONFIG
from backend.tests.helpers import make_attrs, make_candidate, make_req


@pytest.fixture(scope="module")
def reference():
    return load_reference_distribution("fc26-players-2026-09-r1")


@pytest.fixture(scope="module")
def engine(reference):
    return RecommendationEngineV3(reference=reference, data_version="fc26-players-2026-09-r1")


@pytest.fixture(scope="module")
def cm_pool():
    return load_foundation_candidates("FC26", positions={"CM", "CDM", "CAM"})


def _bump(candidate, attr, delta=5):
    c2 = copy.copy(candidate)
    pa = PlayerAttributes()
    pa.values = dict(candidate.attributes.values)
    if pa.values.get(attr) is None:
        return None
    pa.values[attr] = min(99, pa.values[attr] + delta)
    c2.attributes = pa
    return c2


class TestINV1Monotonicity:
    """Raising a demanded attribute (with no explicit user target) must not
    lower R. Session 1 measured 0/3360 violations for capability-only scoring
    and 1321/3360 (39.3%) for the rejected LEVEL x SHAPE prototype — this is
    the test that told the two designs apart."""

    def test_real_pool_sample(self, engine, cm_pool):
        req = make_req(position="CM", tactical_profile="POSSESSION")
        demand = compose_demand(position="CM", tactical_profile="POSSESSION",
                                 lam=DEFAULT_V3_CONFIG.lam_default.value).vector
        rng = random.Random(7)
        sample = rng.sample(cm_pool, min(80, len(cm_pool)))
        checked = violations = 0
        for c in sample:
            for attr in list(demand)[:8]:
                bumped = _bump(c, attr)
                if bumped is None:
                    continue
                r1 = compute_capability(demand=demand, attributes={a: c.attributes.get(a) for a in demand},
                                         position="CM", reference=engine.reference).c_lo
                r2 = compute_capability(demand=demand, attributes={a: bumped.attributes.get(a) for a in demand},
                                         position="CM", reference=engine.reference).c_lo
                checked += 1
                if r2 < r1 - 1e-12:
                    violations += 1
        assert checked > 0
        assert violations == 0, f"{violations}/{checked} monotonicity violations"

    def test_single_case(self, engine):
        req = make_req(position="CM", tactical_profile="PRESSING")
        c = make_candidate(name="X", position="CM", attrs=make_attrs(stamina=70, short_passing=70))
        bumped = _bump(c, "stamina", 10)
        res1 = engine.recommend([c], req)
        res2 = engine.recommend([bumped], req)
        r1 = res1.ranked[0].context.r if res1.ranked else -1
        r2 = res2.ranked[0].context.r if res2.ranked else -1
        assert r2 >= r1 - 1e-9


class TestINV2ParetoDominance:
    """A >= B on every demanded attribute, K(A) superset of K(B) => R(A) >= R(B)."""

    def test_dominating_pair(self, engine):
        req = make_req(position="CB", tactical_profile="LOW_BLOCK")
        base = make_attrs(defending=80, standing_tackle=78, strength=76, interceptions=74,
                           defensive_awareness=75, heading_accuracy=72, jumping=70)
        weaker = make_candidate(name="Weaker", position="CB", attrs=base)
        stronger_vals = {k: v + 5 for k, v in base.values.items()}
        stronger = make_candidate(name="Stronger", position="CB", attrs=make_attrs(**stronger_vals))
        res = engine.recommend([weaker, stronger], req)
        by_name = {rc.context.candidate_name: rc.context.r for rc in res.ranked}
        assert by_name["Stronger"] >= by_name["Weaker"] - 1e-9

    def test_real_pool_random_pairs(self, engine, cm_pool):
        demand = compose_demand(position="CM", tactical_profile="PRESSING",
                                 lam=DEFAULT_V3_CONFIG.lam_default.value).vector
        rng = random.Random(3)
        sample = rng.sample(cm_pool, min(150, len(cm_pool)))
        pairs_found = violations = 0
        for a in sample:
            for b in sample:
                if a is b:
                    continue
                dominates = True
                any_strict = False
                for attr in demand:
                    va, vb = a.attributes.get(attr), b.attributes.get(attr)
                    if va is None or vb is None:
                        dominates = False
                        break
                    if va < vb:
                        dominates = False
                        break
                    if va > vb:
                        any_strict = True
                if not (dominates and any_strict):
                    continue
                pairs_found += 1
                ra = compute_capability(demand=demand, attributes={x: a.attributes.get(x) for x in demand},
                                         position="CM", reference=engine.reference).c_lo
                rb = compute_capability(demand=demand, attributes={x: b.attributes.get(x) for x in demand},
                                         position="CM", reference=engine.reference).c_lo
                if ra < rb - 1e-9:
                    violations += 1
                if pairs_found >= 200:
                    break
            if pairs_found >= 200:
                break
        assert pairs_found > 0, "no dominating pairs found in sample -- widen the sample"
        assert violations == 0, f"{violations}/{pairs_found} dominance violations"


FULL_ST_ATTRS = make_attrs(finishing=85, positioning=84, shot_power=83, pace=88,
                            composure=82, heading_accuracy=76, volleys=80, long_shots=78,
                            strength=75, agility=84, ball_control=85, acceleration=86,
                            reactions=83, dribbling_detail=82, sprint_speed=87,
                            defensive_awareness=35, standing_tackle=30, stamina=72,
                            long_passing=65, vision=68, jumping=70, short_passing=72)

FULL_CM_ATTRS = make_attrs(short_passing=85, vision=84, composure=82, ball_control=83,
                            long_passing=80, dribbling_detail=78, positioning=76,
                            curve=74, agility=75, reactions=80, stamina=82,
                            defensive_awareness=70, interceptions=65, standing_tackle=62,
                            strength=74, acceleration=76, pace=74, aggression=68,
                            long_shots=70, balance=76)


class TestINV3Irrelevance:
    def test_attribute_outside_demand_never_moves_score(self, engine):
        req = make_req(position="ST", tactical_profile="COUNTER_ATTACK")
        demand = compose_demand(position="ST", tactical_profile="COUNTER_ATTACK",
                                 lam=DEFAULT_V3_CONFIG.lam_default.value).vector
        irrelevant = [a for a in DETAIL_ATTRS if a not in demand]
        assert irrelevant, "expected at least one attribute outside the ST/COUNTER_ATTACK demand set"
        attr = irrelevant[0]
        base_vals = dict(FULL_ST_ATTRS.values)
        base_vals[attr] = 40
        c_before = make_candidate(name="X", position="ST", attrs=make_attrs(**base_vals))
        base_vals[attr] = 80
        c_after = make_candidate(name="X", position="ST", attrs=make_attrs(**base_vals))
        r_before = engine.recommend([c_before], req).ranked[0].context.r
        r_after = engine.recommend([c_after], req).ranked[0].context.r
        assert abs(r_before - r_after) < 1e-9, f"{attr} is outside demand but moved R"


class TestINV4PoolIndependence:
    """R(c) must be identical whether c is scored alone or inside any pool.
    This is what a frozen reference distribution buys: the rejected z-score
    prototype could not have this property (measured max delta 0.0154)."""

    def test_alone_vs_in_large_pool(self, engine, cm_pool):
        req = make_req(position="CM", tactical_profile="POSSESSION", limit=1)
        target = cm_pool[42]
        r_alone = engine.recommend([target], make_req(position="CM", tactical_profile="POSSESSION", limit=1))
        r_alone_val = r_alone.ranked[0].context.r if r_alone.ranked else None

        pool_with_target = cm_pool[:400]
        if target not in pool_with_target:
            pool_with_target = pool_with_target + [target]
        res_pool = engine.recommend(pool_with_target, make_req(
            position="CM", tactical_profile="POSSESSION", limit=len(pool_with_target)))
        match = [rc for rc in res_pool.ranked if rc.context.candidate_entity_id == target.entity_id]
        assert match, "target excluded from pool run -- test setup issue"
        r_pool_val = match[0].context.r

        assert r_alone_val is not None
        assert abs(r_alone_val - r_pool_val) < 1e-9


class TestINV5EvidenceNonReward:
    """Removing a published demanded attribute must never raise R or rank.
    Direct regression test for the measured V2-3 defect."""

    def test_removing_attribute_cannot_help(self, engine):
        req = make_req(position="CM", tactical_profile="POSSESSION")
        full = make_attrs(short_passing=88, vision=86, long_passing=85, stamina=90,
                           ball_control=87, composure=86, defensive_awareness=80,
                           interceptions=78, positioning=80, dribbling_detail=82)
        c_full = make_candidate(name="Full", position="CM", ovr=84, attrs=full)
        thin_vals = dict(full.values)
        thin_vals.pop("vision")
        c_thin = make_candidate(name="Thin", position="CM", ovr=84, attrs=make_attrs(**thin_vals))
        res = engine.recommend([c_full, c_thin], req)
        by_name = {rc.context.candidate_name: rc.context.r for rc in res.ranked}
        if "Thin" in by_name:
            assert by_name["Full"] >= by_name["Thin"] - 1e-9

    def test_v2_pathology_case_inverted(self, engine):
        """The exact case that broke v2: a one-attribute candidate must not
        beat a fully-documented one of the same OVR."""
        req = make_req(position="CM", tactical_profile="POSSESSION")
        full = make_attrs(short_passing=88, vision=86, long_passing=85, stamina=90,
                           ball_control=87, composure=86, defensive_awareness=80,
                           interceptions=78, positioning=80, dribbling_detail=82,
                           strength=80, long_shots=78, curve=80, agility=80,
                           balance=80, reactions=84, acceleration=76, pace=74,
                           aggression=70, standing_tackle=70)
        c_full = make_candidate(name="WellDocumented84", position="CM", ovr=84, attrs=full)
        c_thin = make_candidate(name="UndocumentedSameOVR", position="CM", ovr=84,
                                 attrs=make_attrs(short_passing=60))
        res = engine.recommend([c_full, c_thin], req)
        ranked_names = [rc.context.candidate_name for rc in res.ranked]
        not_evaluable_names = [e.candidate_name for e in res.not_evaluable]
        assert "UndocumentedSameOVR" in not_evaluable_names, (
            "thin-evidence candidate must be NOT_EVALUABLE, not ranked ahead of "
            "a fully-documented one (v2 ranked it #1 at score 0.8919)")
        assert ranked_names and ranked_names[0] == "WellDocumented84"


class TestINV6BoundsOrdering:
    def test_c_lo_le_c_hi(self, engine, cm_pool):
        req = make_req(position="CM", tactical_profile="POSSESSION")
        rng = random.Random(1)
        for c in rng.sample(cm_pool, 60):
            res = engine.recommend([c], req)
            if not res.ranked:
                continue
            ctx = res.ranked[0].context
            assert ctx.c_lo <= ctx.c_hi + 1e-9

    def test_equality_at_full_coverage(self, engine):
        req = make_req(position="CM", tactical_profile="POSSESSION")
        c = make_candidate(name="Full", position="CM", attrs=FULL_CM_ATTRS)
        res = engine.recommend([c], req)
        ctx = res.ranked[0].context
        if ctx.coverage_kappa >= 0.999:
            assert abs(ctx.c_lo - ctx.c_hi) < 1e-6


class TestINV7ModifierBound:
    def test_modifier_within_configured_range(self, engine, cm_pool):
        req = make_req(position="CM", tactical_profile="POSSESSION",
                        desired_playstyles=["Tiki Taka", "First Touch"], limit=30)
        res = engine.recommend(cm_pool[:200], req)
        for rc in res.ranked:
            assert DEFAULT_V3_CONFIG.modifier_min.value - 1e-9 <= rc.context.modifier_total \
                   <= DEFAULT_V3_CONFIG.modifier_max.value + 1e-9


class TestINV8ScoreReconstruction:
    """Direct fix for the measured V2-7 defect. Tolerance 1e-9 as specified."""

    def test_reconstruction_matches_ranking_score(self, engine, cm_pool):
        req = make_req(position="CM", tactical_profile="POSSESSION", limit=20)
        res = engine.recommend(cm_pool[:500], req)
        assert res.ranked, "need at least one ranked candidate to test reconstruction"
        for rc in res.ranked:
            recon = reconstruct_score(rc.context)
            assert abs(recon - rc.context.r) < 1e-9, (
                f"{rc.context.candidate_name}: reconstructed {recon} != ranking score {rc.context.r}")
            recon_hi = reconstruct_score_hi(rc.context)
            assert abs(recon_hi - rc.context.r_hi) < 1e-9


class TestINV9Determinism:
    def test_same_request_twice_is_identical(self, engine, cm_pool):
        req = make_req(position="CM", tactical_profile="PRESSING", limit=10)
        rid = uuid.uuid4()
        res1 = engine.recommend(cm_pool[:300], req, request_id=rid)
        res2 = engine.recommend(cm_pool[:300], req, request_id=rid)
        assert [rc.context.candidate_name for rc in res1.ranked] == \
               [rc.context.candidate_name for rc in res2.ranked]
        for rc1, rc2 in zip(res1.ranked, res2.ranked):
            assert rc1.context.r == rc2.context.r


class TestINV10DemandNormalisation:
    def test_demand_vector_sums_to_one(self):
        for position, profile in (("CM", "POSSESSION"), ("CB", "LOW_BLOCK"), ("ST", "PACE_ABUSER"), ("GK", "BUILD_UP")):
            d = compose_demand(position=position, tactical_profile=profile,
                                lam=DEFAULT_V3_CONFIG.lam_default.value)
            assert abs(sum(d.vector.values()) - 1.0) < 1e-6, f"{position}/{profile} demand does not sum to 1"


class TestINV11UnknownPreservation:
    def test_unpublished_attribute_stays_none_in_context(self, engine):
        req = make_req(position="CM", tactical_profile="POSSESSION")
        c = make_candidate(name="Partial", position="CM",
                            attrs=make_attrs(short_passing=85, vision=84, composure=82,
                                              ball_control=83, long_passing=80,
                                              dribbling_detail=78, positioning=76,
                                              curve=74, agility=75, reactions=80))
        res = engine.recommend([c], req)
        if not res.ranked:
            pytest.skip("candidate below coverage floor for this demand set")
        ctx = res.ranked[0].context
        missing = [a.attribute for a in ctx.per_attribute if not a.covered]
        for a in ctx.per_attribute:
            if not a.covered:
                assert a.value is None, f"{a.attribute} is uncovered but value is not None"
        assert set(missing) == set(ctx.missing_attributes)


class TestINV12VersionWall:
    def test_fc27_candidate_excluded_from_fc26_request(self, engine):
        req = make_req(game_version="FC26", position="CM", tactical_profile="POSSESSION")
        c = make_candidate(name="FC27Player", position="CM", version="FC27")
        res = engine.recommend([c], req)
        assert not res.ranked
        assert any(e.gate == "G1_version" for e in res.excluded)


class TestINV13SyntheticFirewall:
    def test_synthetic_candidate_never_ranked(self, engine, cm_pool):
        req = make_req(position="CM", tactical_profile="POSSESSION", limit=10)
        synth = make_candidate(name="FabricatedSynthetic", position="CM", ovr=99,
                                attrs=make_attrs(short_passing=99, vision=99, composure=99),
                                synthetic=True)
        res = engine.recommend(cm_pool[:50] + [synth], req)
        ranked_names = [rc.context.candidate_name for rc in res.ranked]
        assert "FabricatedSynthetic" not in ranked_names
        assert any(e.candidate_name == "FabricatedSynthetic" and e.gate == "G2_synthetic"
                   for e in res.excluded)


class TestINV14Fairness:
    """Name, club, nation and price must not change R. Carried intent from
    v2's existing fairness test, re-verified against the v3 engine."""

    def test_name_does_not_affect_score(self, engine):
        req = make_req(position="CM", tactical_profile="POSSESSION")
        c1 = make_candidate(name="Aaron Zzzworth", position="CM", attrs=FULL_CM_ATTRS)
        c2 = make_candidate(name="Zinedine Aaaworth", position="CM", attrs=FULL_CM_ATTRS)
        res = engine.recommend([c1, c2], req)
        scores = {rc.context.candidate_name: rc.context.r for rc in res.ranked}
        assert abs(scores["Aaron Zzzworth"] - scores["Zinedine Aaaworth"]) < 1e-9

    def test_price_does_not_affect_score(self, engine):
        req = make_req(position="CM", tactical_profile="POSSESSION")
        cheap = make_candidate(name="Cheap", position="CM", attrs=FULL_CM_ATTRS, price=1000)
        expensive = make_candidate(name="Expensive", position="CM", attrs=FULL_CM_ATTRS, price=5_000_000)
        res = engine.recommend([cheap, expensive], req)
        scores = {rc.context.candidate_name: rc.context.r for rc in res.ranked}
        assert abs(scores["Cheap"] - scores["Expensive"]) < 1e-9


class TestINV15NoOvrChannel:
    """R must be invariant to overall_rating when every attribute is held
    fixed. This is the sharpest available test that OVR has no independent
    path into the score -- it fails immediately if a component, tie-break or
    modifier reintroduces OVR."""

    def test_ovr_alone_never_moves_score(self, engine):
        req = make_req(position="CM", tactical_profile="POSSESSION")
        low_ovr = make_candidate(name="Low", position="CM", ovr=65, attrs=FULL_CM_ATTRS)
        high_ovr = make_candidate(name="High", position="CM", ovr=99, attrs=FULL_CM_ATTRS)
        res = engine.recommend([low_ovr, high_ovr], req)
        scores = {rc.context.candidate_name: rc.context.r for rc in res.ranked}
        assert abs(scores["Low"] - scores["High"]) < 1e-9

    def test_ovr_does_not_decide_ties(self, engine):
        req = make_req(position="CM", tactical_profile="POSSESSION", limit=5)
        a = make_candidate(name="AAA_low_ovr", position="CM", ovr=70, attrs=FULL_CM_ATTRS,
                            entity_id=uuid.UUID(int=1))
        b = make_candidate(name="ZZZ_high_ovr", position="CM", ovr=95, attrs=FULL_CM_ATTRS,
                            entity_id=uuid.UUID(int=2))
        res = engine.recommend([a, b], req)
        assert len(res.ranked) == 2
        assert abs(res.ranked[0].context.r - res.ranked[1].context.r) < 1e-9
        assert res.ranked[0].context.candidate_name == "AAA_low_ovr", (
            "tied scores must break on entity_id, not OVR (a==entity_id(1) sorts before b)")
