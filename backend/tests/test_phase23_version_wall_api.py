"""Phase 22/23 -- version wall, research-only firewall, licence gate, v3 API.

Pure-logic tests use synthetic fixtures (names start with "Fixture").
Everything else runs against the real ingested data (FC26 CANONICAL,
FC27 RESEARCH_ONLY) and skips cleanly without the database.
"""
from __future__ import annotations

import json
import uuid

import pytest

from backend.services.capability_model import compute_capability
from backend.services.data_license_gate import (
    DataLicenseGateFailure,
    DataLicenseStatus,
    Environment,
    ProductionOverrideForbidden,
    check_license_gate,
    gate_or_raise,
)
from backend.services.recommendation_engine_v3 import RecommendationEngineV3
from backend.services.reference_distribution import (
    ReferenceDistributionMismatch,
    ReferenceDistributionUnavailable,
    default_artifact_path,
    load_reference_for,
)
from backend.tests.conftest import requires_db
from backend.tests.helpers import make_attrs, make_candidate, make_req

FC26_REF = "fc26-players-2026-09-r1"
FC27_REF = "fc27-players-2026-09-r1"


# ---------------------------------------------------------------------- licence gate
class TestLicenceGateVersionScope:
    def test_fc27_player_dataset_is_research_only(self):
        r = check_license_gate(FC27_REF)
        assert r.status == DataLicenseStatus.RESEARCH_ONLY
        assert r.release_permitted is False

    @pytest.mark.parametrize("dataset,gv,scope", [
        (FC27_REF, "FC26", "game_player"),     # FC27 registration never covers FC26
        (FC26_REF, "FC27", "game_player"),     # and vice versa
        (FC27_REF, "FC27", "ut_card"),         # player registration never covers cards
    ])
    def test_registration_never_covers_other_version_or_scope(self, dataset, gv, scope):
        r = check_license_gate(dataset, game_version=gv, entity_scope=scope)
        assert r.status == DataLicenseStatus.BLOCKED

    def test_research_override_forbidden_in_production(self):
        with pytest.raises(ProductionOverrideForbidden):
            gate_or_raise(FC27_REF, environment=Environment.PRODUCTION, allow_research_only=True)

    def test_research_only_passes_only_with_explicit_research_override(self):
        with pytest.raises(DataLicenseGateFailure):
            gate_or_raise(FC27_REF, environment=Environment.LOCAL)
        with pytest.raises(DataLicenseGateFailure):   # allow_unverified never waives it
            gate_or_raise(FC27_REF, environment=Environment.LOCAL, allow_unverified=True)
        assert gate_or_raise(FC27_REF, environment=Environment.RESEARCH,
                             allow_research_only=True).status == DataLicenseStatus.RESEARCH_ONLY

    def test_research_override_never_waives_unverified_or_blocked(self):
        with pytest.raises(DataLicenseGateFailure):
            gate_or_raise(FC26_REF, environment=Environment.LOCAL, allow_research_only=True)
        with pytest.raises(DataLicenseGateFailure):
            gate_or_raise("nobody-registered", environment=Environment.LOCAL,
                          allow_research_only=True)


# ---------------------------------------------------------------------- distributions
class TestReferenceDistributionWall:
    def test_fc26_request_gets_fc26_distribution(self):
        d = load_reference_for("FC26")
        assert d.version == FC26_REF and d.game_version == "FC26"

    def test_fc27_distribution_unreachable_without_research_opt_in(self):
        with pytest.raises(ReferenceDistributionUnavailable):
            load_reference_for("FC27")

    def test_fc27_request_gets_fc27_research_distribution(self):
        d = load_reference_for("FC27", allow_research_only=True)
        assert (d.version, d.game_version, d.universe, d.data_status) == (
            FC27_REF, "FC27", "RATINGS_SITE_PLAYERS", "RESEARCH_ONLY")

    def test_fc27_research_artifact_is_not_in_production_directory(self):
        assert not (default_artifact_path() / f"{FC27_REF}.json").exists()

    def test_frozen_fc26_artifact_unchanged(self):
        d = json.loads((default_artifact_path() / f"{FC26_REF}.json").read_text(encoding="utf-8"))
        assert d["content_hash"].startswith("ac52f46dc8a2433d")
        assert "data_status" not in d

    def test_engine_refuses_fc26_distribution_for_fc27_request(self):
        eng = RecommendationEngineV3(reference=load_reference_for("FC26"))
        with pytest.raises(ReferenceDistributionMismatch):
            eng.recommend([make_candidate(version="FC27")], make_req(game_version="FC27", position="CM"))

    def test_engine_refuses_fc27_distribution_for_fc26_request(self):
        eng = RecommendationEngineV3(reference=load_reference_for("FC27", allow_research_only=True))
        with pytest.raises(ReferenceDistributionMismatch):
            eng.recommend([make_candidate()], make_req(game_version="FC26", position="CM"))


# ---------------------------------------------------------------------- missing evidence
class TestMissingEvidenceCharge:
    """Documents the measured V3.1 behaviour and the candidate fix."""
    DEMAND = {"short_passing": 0.5, "vision": 0.5}

    def _clo(self, attrs, charge):
        return compute_capability(demand=self.DEMAND, attributes=attrs, position="CM",
                                  reference=load_reference_for("FC26"),
                                  missing_charge=charge).c_lo

    def test_p10_lets_a_hidden_weak_value_score_higher(self):
        """Measured V3.1 defect (Phase 23 lab): a published value below P10
        is worth less than hiding it."""
        shown = self._clo({"short_passing": 20, "vision": 70}, "P10")
        hidden = self._clo({"short_passing": None, "vision": 70}, "P10")
        assert hidden > shown

    @pytest.mark.parametrize("value", [1, 20, 45, 70, 99])
    def test_zero_charge_never_rewards_hiding(self, value):
        shown = self._clo({"short_passing": value, "vision": 70}, "ZERO")
        hidden = self._clo({"short_passing": None, "vision": 70}, "ZERO")
        assert hidden <= shown

    def test_unknown_charge_rejected(self):
        with pytest.raises(ValueError):
            self._clo({"short_passing": 50, "vision": 50}, "MEAN")


# ---------------------------------------------------------------------- lab maths
class TestLabMaths:
    def test_spearman_known_values(self):
        from backend.services.intelligence_lab import spearman
        assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
        assert spearman([1, 2, 3, 4], [40, 30, 20, 10]) == pytest.approx(-1.0)
        assert spearman([1, 1, 2, 2], [1, 1, 2, 2]) == pytest.approx(1.0)   # ties

    def test_complementarity_transform_is_monotone(self):
        from backend.services.intelligence_lab import complementarity_score
        eng = RecommendationEngineV3(reference=load_reference_for("FC26"))
        req = make_req(position="ST", tactical_profile="COUNTER_ATTACK")
        prev = None
        from backend.domain.card_model import DETAIL_ATTRS, FACADE_ATTRS
        full = {a: 80 for a in DETAIL_ATTRS + FACADE_ATTRS}   # kappa = 1.0, evaluable
        for acc in (60, 70, 80, 90, 99):
            c = make_candidate(name="FixtureST", position="ST",
                               attrs=make_attrs(**dict(full, acceleration=acc)))
            ctx = eng.recommend([c], req).ranked[0].context
            s = complementarity_score(ctx, 0.05)
            assert prev is None or s >= prev
            prev = s


# ---------------------------------------------------------------------- DB: firewall
@requires_db
class TestResearchFirewallDB:
    def test_production_load_serves_no_fc27_rows(self):
        from backend.data_access.candidate_repository import CandidateRepository
        assert CandidateRepository().load_candidates("FC27") == []

    def test_research_load_serves_only_research_rows(self):
        from backend.data_access.candidate_repository import CandidateRepository
        rows = CandidateRepository().load_candidates("FC27", include_research_only=True)
        assert rows and {c.data_status.value for c in rows} == {"RESEARCH_ONLY"}
        assert {c.game_version.value for c in rows} == {"FC27"}

    def test_fc26_production_load_has_no_research_or_synthetic_rows(self):
        from backend.data_access.candidate_repository import CandidateRepository
        rows = CandidateRepository().load_candidates("FC26")
        assert rows and {c.data_status.value for c in rows} == {"CANONICAL"}
        assert not any(c.is_synthetic for c in rows)

    def test_same_ea_id_never_same_game_player(self):
        from backend.core.db import query_one
        row = query_one("""
            SELECT count(*) FILTER (WHERE a.id = b.id)::int AS same, count(*)::int AS pairs
            FROM game_player a JOIN game_version ga ON ga.id=a.game_version_id AND ga.code='FC26'
            JOIN game_player b ON b.source_player_id=a.source_player_id
            JOIN game_version gb ON gb.id=b.game_version_id AND gb.code='FC27'""")
        assert row["pairs"] > 0 and row["same"] == 0

    def test_db_trigger_refuses_promoting_research_rows(self):
        import psycopg

        from backend.core.db import get_conn
        with get_conn() as conn:
            with pytest.raises(psycopg.errors.CheckViolation):
                with conn.transaction():
                    conn.execute("""UPDATE game_player SET data_status='CANONICAL'
                                    WHERE source_id='kaggle_fc27_player_ratings'
                                      AND id = (SELECT id FROM game_player
                                                WHERE source_id='kaggle_fc27_player_ratings' LIMIT 1)""")

    def test_provenance_never_crosses_versions(self):
        from backend.core.db import query_one
        row = query_one("""
            SELECT count(*)::int AS n FROM field_provenance fp
            JOIN game_player gp ON gp.id = fp.canonical_entity_id
            JOIN source_observation so ON so.id = fp.source_observation_id
            WHERE so.game_version_id <> gp.game_version_id""")
        assert row["n"] == 0

    def test_playstyle_definitions_are_version_scoped(self):
        from backend.core.db import query
        rows = query("""SELECT gv.code, pd.data_status, count(*)::int n FROM playstyle_definition pd
                        JOIN game_version gv ON gv.id=pd.game_version_id GROUP BY 1,2""")
        by = {(r["code"], r["data_status"]): r["n"] for r in rows}
        assert by.get(("FC27", "CANONICAL"), 0) == 0 and by.get(("FC27", "RESEARCH_ONLY"), 0) > 0


# ---------------------------------------------------------------------- DB: v3 API
def _post(client, path, body):
    return client.post(path, json=body)


@requires_db
class TestV3ApiContract:
    @pytest.mark.parametrize("position", ["CM", "ST", "CB", "LB", "RW", "GK"])
    def test_valid_positions(self, client, position):
        r = _post(client, "/api/v3/recommendations",
                  {"game_version": "FC26", "position": position, "limit": 5})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ranked"] and all(x["player"]["data_status"] == "CANONICAL" for x in d["ranked"])
        assert (d["dataset"]["game_version"], d["dataset"]["data_status"],
                d["dataset"]["research_only"]) == ("FC26", "CANONICAL", False)

    @pytest.mark.parametrize("profile", ["POSSESSION", "COUNTER_ATTACK", "HIGH_PRESS",
                                         "LOW_BLOCK", "BALANCED"])
    def test_tactical_profiles(self, client, profile):
        r = _post(client, "/api/v3/recommendations",
                  {"game_version": "FC26", "position": "CM", "tactical_profile": profile, "limit": 3})
        assert r.status_code == 200, r.text

    @pytest.mark.parametrize("body", [
        {"game_version": "FC26", "position": "NOTAPOS"},
        {"game_version": "FC26", "position": "CM", "tactical_profile": "TIKITAKA_9000"},
        {"game_version": "FC25", "position": "CM"},
        {"game_version": "FC26"},
        {"game_version": "FC26", "position": "CM", "limit": 500},
        {"game_version": "FC26", "position": "CM", "entity_scope": "ut_card"},
        {"game_version": "FC26", "position": "CM", "unexpected": 1},
    ])
    def test_invalid_requests_rejected(self, client, body):
        assert _post(client, "/api/v3/recommendations", body).status_code == 422

    def test_fc27_without_opt_in_refused_not_fc26_fallback(self, client):
        r = _post(client, "/api/v3/recommendations", {"game_version": "FC27", "position": "CM"})
        assert r.status_code == 503
        assert "RESEARCH_ONLY" in r.json()["detail"]["detail"]

    def test_fc27_with_opt_in_serves_only_fc27_research_data(self, client):
        r = _post(client, "/api/v3/recommendations", {
            "game_version": "FC27", "position": "CM", "limit": 10, "include_research_data": True})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["dataset"]["research_only"] is True and d["dataset"]["data_status"] == "RESEARCH_ONLY"
        assert d["reference_distribution_version"] == FC27_REF
        assert {x["player"]["data_status"] for x in d["ranked"]} == {"RESEARCH_ONLY"}

    def test_research_data_refused_by_production_service(self):
        from backend.api.schemas_v3 import RecommendationRequestV3
        from backend.services.recommendation_service_v3 import RecommendationServiceV3
        svc = RecommendationServiceV3(environment=Environment.PRODUCTION)
        out = svc.recommend(RecommendationRequestV3(game_version="FC27", position="CM",
                                                    include_research_data=True))
        assert out["error"] == "RESEARCH_DATA_REFUSED_IN_PRODUCTION"

    def test_division_filter(self, client):
        r = _post(client, "/api/v3/recommendations", {
            "game_version": "FC27", "position": "ST", "limit": 10,
            "include_research_data": True, "division": "Women's Football"})
        assert r.status_code == 200
        assert {x["player"]["division"] for x in r.json()["ranked"]} == {"Women's Football"}

    def test_determinism_same_request_same_response(self, client):
        body = {"game_version": "FC26", "position": "ST", "tactical_profile": "HIGH_PRESS", "limit": 10}
        a = _post(client, "/api/v3/recommendations", body).json()
        b = _post(client, "/api/v3/recommendations", body).json()
        for d in (a, b):
            d.pop("request_id")
            d.pop("latency_ms")
        assert a == b

    def test_explanations_reconstruct_the_score(self, client):
        d = _post(client, "/api/v3/recommendations",
                  {"game_version": "FC26", "position": "CB", "limit": 10}).json()
        assert all(x["explanation"]["reconstructed_score_matches_ranking"] for x in d["ranked"])
        assert all(x["score_interval"]["low"] <= x["score_interval"]["high"] for x in d["ranked"])

    def test_compare_matches_recommendation_scores(self, client):
        req = {"game_version": "FC26", "position": "CM", "tactical_profile": "POSSESSION", "limit": 3}
        rec = _post(client, "/api/v3/recommendations", req).json()["ranked"]
        cmp_ = _post(client, "/api/v3/compare",
                     {"request": req, "entity_ids": [x["entity_id"] for x in rec]})
        assert cmp_.status_code == 200, cmp_.text
        by = {p["entity_id"]: p["score"] for p in cmp_.json()["players"]}
        assert all(by[x["entity_id"]] == x["score"] for x in rec)   # pool independence
        assert cmp_.json()["pairwise"][0]["why"]

    def test_compare_unknown_id_reported_not_invented(self, client):
        req = {"game_version": "FC26", "position": "CM", "limit": 2}
        rec = _post(client, "/api/v3/recommendations", req).json()["ranked"]
        ghost = str(uuid.uuid4())
        d = _post(client, "/api/v3/compare",
                  {"request": req, "entity_ids": [rec[0]["entity_id"], ghost]}).json()
        assert d["not_found"] == [ghost]

    def test_what_if_recomputes(self, client):
        r = _post(client, "/api/v3/what-if", {
            "base": {"game_version": "FC26", "position": "CM", "tactical_profile": "POSSESSION"},
            "variants": [{"label": "press", "tactical_profile": "HIGH_PRESS"}]})
        assert r.status_code == 200, r.text
        v = r.json()["variants"][0]
        assert v["demand_shift"] and v["top"]

    def test_what_if_rejects_noop_variant(self, client):
        r = _post(client, "/api/v3/what-if", {
            "base": {"game_version": "FC26", "position": "CM"}, "variants": [{"label": "none"}]})
        assert r.status_code == 422
