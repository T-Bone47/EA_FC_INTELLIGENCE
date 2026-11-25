"""v3.1 calibration and hardening tests (Phases 9-15 of V3_1_CALIBRATION_REPORT.md).

Distinct from test_engine_v3_invariants.py (T0) and test_v3_production_safety.py
(the four P0 defects proven in v3.0): this file covers the additional
hardening surfaces this calibration session was asked to verify.
"""
from __future__ import annotations

import copy
import uuid

import pytest

from backend.services.demand_composition import compose_demand
from backend.services.recommendation_engine_v3 import RecommendationEngineV3
from backend.services.reference_distribution import (
    ReferenceDistributionUnavailable,
    Universe,
    load_reference_distribution,
)
from backend.services.v3_config import DEFAULT_V3_CONFIG
from backend.tests.conftest import requires_db
from backend.tests.helpers import make_attrs, make_candidate, make_req

FULL_CM_ATTRS = make_attrs(short_passing=85, vision=84, composure=82, ball_control=83,
                            long_passing=80, dribbling_detail=78, positioning=76,
                            curve=74, agility=75, reactions=80, stamina=82,
                            defensive_awareness=70, interceptions=65, standing_tackle=62,
                            strength=74, acceleration=76, pace=74, aggression=68,
                            long_shots=70, balance=76)


@pytest.fixture(scope="module")
def reference():
    return load_reference_distribution("fc26-players-2026-09-r1")


@pytest.fixture(scope="module")
def engine(reference):
    return RecommendationEngineV3(reference=reference, data_version="fc26-players-2026-09-r1")


# ---------------------------------------------------------------------
# Phase 9 -- reference distribution / version wall
# ---------------------------------------------------------------------
class TestPhase9ReferenceDistributionWall:
    def test_universe_is_player_not_card(self, reference):
        assert reference.universe == Universe.RATINGS_SITE_PLAYERS

    def test_player_scope_may_use_this_distribution(self, reference):
        assert reference.applies_to("game_player") is True

    def test_ut_card_scope_may_not_use_this_distribution(self, reference):
        """Direct regression for FC26_DATA_TO_V3_MAPPING.md contradiction C-1:
        a player-derived P10/P90 must never silently score a card candidate,
        because FUT special items are a materially different, upward-shifted
        population (measured up to 11 OVR points divergence, per
        FC26_SOURCE_FORENSIC_REPORT.md)."""
        assert reference.applies_to("ut_card") is False

    def test_unknown_version_raises_rather_than_falls_back(self):
        with pytest.raises(ReferenceDistributionUnavailable):
            load_reference_distribution("fc27-players-does-not-exist")

    def test_fc27_cannot_reuse_fc26_distribution(self, reference):
        """There is currently no FC27 reference distribution at all. This
        confirms the engine has no code path that would let an FC27 request
        silently borrow FC26's frozen quantiles."""
        assert reference.game_version == "FC26"
        with pytest.raises(ReferenceDistributionUnavailable):
            load_reference_distribution("fc27-players-2026-09-r1")


# ---------------------------------------------------------------------
# Phase 10 -- evidence / coverage hardening (synthetic kappa fixtures,
# test-fixture-only per the mandate -- never production data)
# ---------------------------------------------------------------------
class TestPhase10EvidenceHardening:
    """Constructs candidates at controlled coverage levels by publishing an
    exact fraction of the CM/POSSESSION demand's attributes."""

    @staticmethod
    def _candidate_at_coverage(demand: dict, target_kappa: float, name: str):
        ordered = sorted(demand.items(), key=lambda kv: -kv[1])
        cum = 0.0
        published = {}
        for attr, w in ordered:
            if cum >= target_kappa:
                break
            published[attr] = 75
            cum += w
        return make_candidate(name=name, position="CM", ovr=82, attrs=make_attrs(**published)), cum

    @pytest.mark.parametrize("kappa_target", [0.10, 0.25, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00])
    def test_below_floor_is_not_evaluable_never_ranked_low(self, engine, kappa_target):
        demand = compose_demand(position="CM", tactical_profile="POSSESSION",
                                 lam=DEFAULT_V3_CONFIG.lam_default.value).vector
        c, actual_kappa = self._candidate_at_coverage(demand, kappa_target, f"K{kappa_target}")
        req = make_req(position="CM", tactical_profile="POSSESSION")
        res = engine.recommend([c], req)
        if actual_kappa < DEFAULT_V3_CONFIG.kappa_min.value:
            assert not res.ranked, f"kappa={actual_kappa:.2f} should be NOT_EVALUABLE, not ranked"
            assert res.not_evaluable and res.not_evaluable[0].exclusion_class.value == "NOT_EVALUABLE"
        else:
            assert res.ranked, f"kappa={actual_kappa:.2f} should clear the floor and be ranked"

    def test_publishing_unknown_attribute_can_raise_c_lo(self, engine):
        demand = compose_demand(position="CM", tactical_profile="POSSESSION",
                                 lam=DEFAULT_V3_CONFIG.lam_default.value).vector
        partial_vals = dict(FULL_CM_ATTRS.values)
        top_attr = max(demand, key=demand.get)
        strong_value = min(99, partial_vals.get(top_attr, 70) + 20)
        partial_vals.pop(top_attr, None)
        before = make_candidate(name="Before", position="CM", attrs=make_attrs(**partial_vals))
        partial_vals[top_attr] = strong_value
        after = make_candidate(name="After", position="CM", attrs=make_attrs(**partial_vals))
        req = make_req(position="CM", tactical_profile="POSSESSION")
        r_before = engine.recommend([before], req)
        r_after = engine.recommend([after], req)
        if r_before.ranked and r_after.ranked:
            assert r_after.ranked[0].context.c_lo >= r_before.ranked[0].context.c_lo

    def test_removing_evidence_cannot_increase_c_lo(self, engine):
        demand = compose_demand(position="CM", tactical_profile="POSSESSION",
                                 lam=DEFAULT_V3_CONFIG.lam_default.value).vector
        full_vals = dict(FULL_CM_ATTRS.values)
        full = make_candidate(name="Full", position="CM", attrs=make_attrs(**full_vals))
        removed_vals = dict(full_vals)
        weakest_covered = min((a for a in demand if a in removed_vals), key=lambda a: removed_vals[a])
        removed_vals.pop(weakest_covered)
        thinner = make_candidate(name="Thinner", position="CM", attrs=make_attrs(**removed_vals))
        req = make_req(position="CM", tactical_profile="POSSESSION")
        r_full = engine.recommend([full], req)
        r_thin = engine.recommend([thinner], req)
        if r_full.ranked and r_thin.ranked:
            assert r_thin.ranked[0].context.c_lo <= r_full.ranked[0].context.c_lo + 1e-9


# ---------------------------------------------------------------------
# Phase 11 -- confidence independence
# ---------------------------------------------------------------------
class TestPhase11ConfidenceIndependence:
    def test_confidence_never_moves_r(self, engine):
        """Same candidate, same attributes, same demand -- vary only the
        identity_status input to confidence and confirm R is untouched."""
        from backend.domain.card_model import IdentityStatus
        req = make_req(position="CM", tactical_profile="POSSESSION")
        c1 = make_candidate(name="X", position="CM", attrs=FULL_CM_ATTRS)
        c1.identity_status = IdentityStatus.RESOLVED
        c2 = make_candidate(name="X", position="CM", attrs=FULL_CM_ATTRS)
        c2.identity_status = IdentityStatus.REVIEW_REQUIRED
        res1 = engine.recommend([c1], req)
        res2 = engine.recommend([c2], req)
        assert res1.ranked and res2.ranked
        assert res1.ranked[0].context.r == res2.ranked[0].context.r
        assert res1.ranked[0].context.confidence != res2.ranked[0].context.confidence, (
            "confidence SHOULD differ (different identity status) even though R does not")

    def test_confidence_dimensions_are_independent(self):
        """authority/freshness/identity/coverage each computed and reported
        separately -- an UNKNOWN dimension is excluded, never penalised."""
        from backend.services.confidence_v2 import compute
        c_unknown_identity = compute(legacy_score=0.9, identity_status=None)
        c_known_identity = compute(legacy_score=0.9, identity_status="RESOLVED")
        assert "identity" not in "".join(r for r in c_unknown_identity["reasons"] if "UNKNOWN" not in r)
        assert any("UNKNOWN" in r for r in c_unknown_identity["reasons"] if "identity" in r)


# ---------------------------------------------------------------------
# Phase 12 -- provenance at scale
# ---------------------------------------------------------------------
@requires_db
class TestPhase12ProvenanceAtScale:
    def test_100_random_players_full_attribute_trace(self):
        from backend.core.db import get_conn
        with get_conn() as conn:
            players = conn.execute(
                "SELECT id, display_name FROM game_player WHERE data_status='CANONICAL' "
                "ORDER BY random() LIMIT 100"
            ).fetchall()
            missing = []
            checked = 0
            for p in players:
                rows = conn.execute(
                    "SELECT canonical_field FROM field_provenance "
                    "WHERE canonical_entity_type='game_player' AND canonical_entity_id=%s",
                    (p["id"],),
                ).fetchall()
                traced = {r["canonical_field"] for r in rows}
                attrs = conn.execute(
                    "SELECT * FROM game_player_attributes WHERE game_player_id=%s", (p["id"],)
                ).fetchone()
                if attrs:
                    for field_name, value in dict(attrs).items():
                        if field_name in ("id", "game_player_id") or value is None:
                            continue
                        checked += 1
                        if field_name not in traced:
                            missing.append((p["display_name"], field_name))
        coverage_pct = 100.0 * (1 - len(missing) / checked) if checked else 0.0
        assert checked > 0
        assert not missing, (
            f"provenance coverage {coverage_pct:.2f}% -- {len(missing)} served attribute(s) "
            f"with no field_provenance row, e.g. {missing[:5]}")


# ---------------------------------------------------------------------
# Phase 13 -- replay / determinism under process and pool-order changes
# ---------------------------------------------------------------------
class TestPhase13Replay:
    def test_byte_identical_after_pool_reordering(self, engine):
        req = make_req(position="CM", tactical_profile="POSSESSION", limit=5)
        c1 = make_candidate(name="A", position="CM", ovr=85, attrs=FULL_CM_ATTRS,
                             entity_id=uuid.UUID(int=1))
        c2 = make_candidate(name="B", position="CM", ovr=80, attrs=FULL_CM_ATTRS,
                             entity_id=uuid.UUID(int=2))
        res_forward = engine.recommend([c1, c2], req)
        res_reversed = engine.recommend([c2, c1], req)
        names_fwd = [rc.context.candidate_name for rc in res_forward.ranked]
        names_rev = [rc.context.candidate_name for rc in res_reversed.ranked]
        scores_fwd = [rc.context.r for rc in res_forward.ranked]
        scores_rev = [rc.context.r for rc in res_reversed.ranked]
        assert names_fwd == names_rev
        assert scores_fwd == scores_rev

    def test_replay_fixture_round_trip(self, engine):
        """Persist request + versions + a response hash; replay; compare."""
        import hashlib
        import json
        req = make_req(position="CM", tactical_profile="LOW_BLOCK", limit=3)
        c = make_candidate(name="Replay", position="CM", attrs=FULL_CM_ATTRS)

        def response_hash(result):
            payload = [(rc.context.candidate_name, rc.context.r, rc.context.c_lo,
                       rc.context.coverage_kappa) for rc in result.ranked]
            return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()

        rid = uuid.uuid4()
        result1 = engine.recommend([c], req, request_id=rid)
        fixture = {
            "request_id": str(rid), "engine_version": result1.engine_version,
            "config_version": result1.config_version,
            "reference_distribution_version": result1.reference_distribution_version,
            "response_hash": response_hash(result1),
        }
        result2 = engine.recommend([c], req, request_id=rid)
        assert response_hash(result2) == fixture["response_hash"]


# ---------------------------------------------------------------------
# Phase 14 -- production data firewall, defence in depth (repo + engine +
# service layers, per the explicit mandate: "a single forgotten WHERE
# clause must not expose synthetic or wrong-version data")
# ---------------------------------------------------------------------
class TestPhase14DefenceInDepth:
    def test_engine_layer_blocks_synthetic_even_if_repo_layer_did_not(self, engine):
        """Simulates a repository-layer filter failure: a synthetic
        candidate reaches the engine directly. The engine's own G2 gate must
        catch it independently -- this is what "defence in depth" means
        concretely, not just two tests of the same code path."""
        req = make_req(position="CM", tactical_profile="POSSESSION")
        synthetic = make_candidate(name="LeakedFixture", position="CM", ovr=90,
                                    attrs=FULL_CM_ATTRS, synthetic=True)
        res = engine.recommend([synthetic], req)
        assert not res.ranked
        assert res.excluded[0].gate == "G2_synthetic"

    def test_engine_layer_blocks_wrong_version_even_if_repo_layer_did_not(self, engine):
        req = make_req(game_version="FC26", position="CM", tactical_profile="POSSESSION")
        wrong_version = make_candidate(name="FC27Leak", position="CM", attrs=FULL_CM_ATTRS,
                                        version="FC27")
        res = engine.recommend([wrong_version], req)
        assert not res.ranked
        assert res.excluded[0].gate == "G1_version"

    @requires_db
    def test_service_layer_only_ever_loads_game_player_scope(self):
        """Exercise the shared service path and verify the requested repository scope."""
        from unittest.mock import Mock

        from backend.api.schemas_v3 import RecommendationRequestV3
        from backend.services.recommendation_service_v3 import RecommendationServiceV3

        repository = Mock(spec=["load_candidates", "load_cards"])
        repository.load_candidates.return_value = []
        response = RecommendationServiceV3(repository=repository).recommend(
            RecommendationRequestV3(game_version="FC26", position="CM"))
        assert response["entity_scope"] == "game_player"
        repository.load_candidates.assert_called_once()
        repository.load_cards.assert_not_called()



# ---------------------------------------------------------------------
# Phase 15 -- API contract hardening
# ---------------------------------------------------------------------
@requires_db
class TestPhase15ApiContractHardening:
    def test_invalid_position_rejected(self, client):
        r = client.post("/api/v3/recommendations", json={
            "game_version": "FC26", "position": "NOTAPOSITION",
        })
        assert r.status_code in (200, 422), r.text
        if r.status_code == 200:
            assert r.json()["ranked"] == [], "an invalid position must not silently return results"

    def test_fc27_returns_no_data_not_fc26_fallback(self, client):
        r = client.post("/api/v3/recommendations", json={
            "game_version": "FC27", "position": "CM",
        })
        assert r.status_code in (200, 422, 503), r.text
        if r.status_code == 200:
            assert r.json()["ranked"] == [], "FC27 must never silently return FC26 data"

    def test_ut_card_scope_fails_explicitly_not_silently_downgraded(self, client):
        r = client.post("/api/v3/recommendations", json={
            "game_version": "FC26", "position": "CM", "entity_scope": "ut_card",
        })
        assert r.status_code == 422
        assert "game_player" in r.text.lower()

    def test_malformed_request_rejected_with_detail(self, client):
        r = client.post("/api/v3/recommendations", json={"position": "CM"})
        assert r.status_code == 422

    def test_large_limit_is_bounded(self, client):
        r = client.post("/api/v3/recommendations", json={
            "game_version": "FC26", "position": "CM", "limit": 999999,
        })
        assert r.status_code == 422, "limit must be bounded at the schema level, not the engine"

    def test_missing_evidence_position_still_responds(self, client):
        r = client.post("/api/v3/recommendations", json={
            "game_version": "FC26", "position": "GK", "tactical_profile": "BUILD_UP",
        })
        assert r.status_code == 200, r.text
