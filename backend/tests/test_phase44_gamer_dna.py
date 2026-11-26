"""Phase 44 Comprehensive Verification Suite: Professional Gamer DNA V2, Governed Similarity & Style Sandbox."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.api.deps import CurrentUser, current_user_required
from backend.api.main import create_app
from backend.domain.phase40_models import ColdStartPreferences, MatchIntelligenceRecord
from backend.domain.phase43_models import DesignType, ExperimentType, TacticalExperimentCreate, TacticalSnapshotCreate
from backend.domain.phase44_models import (
    FeatureSourceType,
    ProStyleProfileVersion,
    ProfessionalGamerReference,
    ReferenceMatchRecord,
    ReferenceRightsRecord,
    RightsStatus,
    StyleRecommendationFeedbackCreate,
    StyleSandboxRequest,
    UsagePurpose,
)
from backend.repositories.phase40_repository import Phase40Repository
from backend.repositories.phase43_repository import Phase43Repository
from backend.repositories.phase44_repository import Phase44Repository
from backend.services.coach_tools import CoachToolRegistry
from backend.services.coach_tools_extended import INTENT_TO_TOOLS
from backend.services.elite_skill_gap_engine import EliteSkillGapEngine
from backend.services.gamer_dna_v2_engine import (
    ARCHETYPES_V2,
    FEATURE_CATALOG_V2,
    PROFICIENCY_FEATURE_IDS,
    STYLE_FEATURE_IDS,
    GamerDNAV2Engine,
    StyleArchetypeEngine,
)
from backend.services.llm.router import TaskIntent
from backend.services.personal_coach_orchestrator import PersonalCoachOrchestrator
from backend.services.professional_similarity_engine import ProfessionalGamerSimilarityEngine
from backend.services.reference_governance_service import (
    ProfessionalReferenceRepository,
    ReferenceRightsValidator,
)
from backend.services.style_evolution_engine import StyleEvolutionEngine
from backend.services.style_squad_training_bridge import (
    EliteTrainingPathwayService,
    PlayingStyleSandbox,
    StyleAwareRecommendationService,
)
from backend.services.tactical_experiment_engine import TacticalExperimentEngine
from backend.services.tactical_snapshot_service import TacticalSnapshotService


def _match(uid: str, mid: str, *, gv: str = "FC27", patch: str = "PATCH_1.04", prov: str = "USER_SUBMITTED_RECORD", days_ago: int = 1, fm: dict | None = None, form: str = "4-2-3-1") -> MatchIntelligenceRecord:
    base = {
        "possession_share": 0.64,
        "pass_accuracy": 0.88,
        "pressing_intensity": 0.50,
        "defensive_compactness": 0.76,
        "defensive_transition_management": 0.72,
        "central_progression": 0.68,
        "short_pass_preference": 0.80,
        "direct_progression": 0.36,
        "wide_attacking_preference": 0.38,
        "central_attacking_preference": 0.72,
        "risk_taking_preference": 0.32,
        "safer_alternative_preference": 0.78,
        "passing_network_density": 0.78,
        "shot_selection_preference": 0.44,
    }
    if fm:
        base.update(fm)
    return MatchIntelligenceRecord(
        match_id=mid,
        user_id=uid,
        provenance=prov,
        game_version=gv,  # type: ignore[arg-type]
        game_patch=patch,
        formation=form,
        tracking_coverage_pct=84.0,
        observation_quality="HIGH",
        feature_metrics=base,
        opponent_context={"pressing_intensity": 0.62, "defensive_compactness": 0.58},
        created_at=(datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(),
    )


def test_phase44_feature_architecture_separation_and_synthetic_exclusion():
    assert len(FEATURE_CATALOG_V2) == 60
    assert len(STYLE_FEATURE_IDS) == 53
    assert len(PROFICIENCY_FEATURE_IDS) == 7
    assert len(ARCHETYPES_V2) == 10

    eng = GamerDNAV2Engine()
    real_m = _match("u44-1", "M-REAL-1", fm={"possession_share": 0.66})
    synth_m = _match("u44-1", "M-SYNTH-1", prov="SYNTHETIC_FIXTURE", fm={"pressing_intensity": 0.99, "crossing_preference": 0.99})
    prof = eng.build_profile("u44-1", [real_m, synth_m], game_version="FC27")

    assert prof.eligible_match_count == 1
    assert prof.synthetic_excluded_count == 1
    assert prof.profile_maturity == "PRELIMINARY"
    # Absent metrics MUST stay None, never 0.0, and never inherit synthetic fixture metrics
    assert prof.style_features["crossing_preference"].raw_value is None
    assert prof.style_features["pressing_tendency"].raw_value != 0.99
    # Group G proficiency features flagged cleanly
    for fid in PROFICIENCY_FEATURE_IDS:
        assert prof.proficiency_features[fid].is_proficiency_only is True
        assert fid not in prof.style_features


def test_phase44_cold_start_hints_vs_empty_matches():
    eng = GamerDNAV2Engine()
    cold = ColdStartPreferences(preferred_tempo="SLOW_POSSESSION", preferred_formation="4-3-3", pressing_comfort="HIGH_PRESS")
    p = eng.build_profile("u-cold", [], game_version="FC27", cold_start=cold)
    assert p.eligible_match_count == 0
    assert p.profile_maturity == "COLD_START"
    assert p.archetype.status == "COLD_START_HINT"
    assert p.archetype.primary_archetype == "Possession Architect"


def test_phase44_reference_governance_fail_closed_and_revocation():
    repo = Phase44Repository(force_memory=True)
    ref_repo = ProfessionalReferenceRepository(repo)
    cands = ref_repo.list_candidates()
    assert len(cands) == 8
    for c in cands:
        assert c.rights_status == RightsStatus.METADATA_ONLY
        ok, reason = ReferenceRightsValidator.is_permitted(c.rights, UsagePurpose.FEATURE_EXTRACTION)
        assert ok is False
        assert "BLOCKED" in reason

    # Attempting to ingest match payload for unverified candidate drops features cleanly
    sanitized = ref_repo.match_repo.ingest_match(
        ReferenceMatchRecord(
            reference_id=cands[0].reference_id,
            coverage_pct=90.0,
            feature_payload={"style_features": {"pressing_intensity": 0.9}},
        )
    )
    assert sanitized.feature_payload == {}
    assert sanitized.coverage_pct == 0.0

    # Grant research rights on one test candidate, verify eligibility, then revoke and verify cascade invalidation
    rid = cands[0].reference_id
    ref_repo.repo.upsert_reference(
        cands[0].model_copy(update={"dataset_version": "test.v1", "reference_match_count": 2, "profile_coverage": 0.8}),
        ReferenceRightsRecord(
            reference_id=rid,
            rights_status=RightsStatus.RESEARCH_ONLY,
            allow_local_research=True,
            allow_feature_extraction=True,
            verified_by="UNIT_TEST",
        ),
    )
    ref_repo.match_repo.ingest_match(
        ReferenceMatchRecord(
            reference_id=rid,
            game_version="FC27",
            coverage_pct=85.0,
            feature_payload={"style_features": {"pressing_intensity": 0.85, "short_pass_preference": 0.72}},
        )
    )
    pro_p = ref_repo.profile_builder.build_profile(rid, game_version="FC27")
    assert pro_p is not None
    assert len(ref_repo.list_eligible_pro_profiles(game_version="FC27")) == 1

    revoked = ref_repo.revoke_rights(rid, reason="Player withdrew research consent")
    assert revoked is not None and revoked.rights_status == RightsStatus.REVOKED
    assert len(ref_repo.list_eligible_pro_profiles(game_version="FC27")) == 0


def test_phase44_similarity_abstain_when_unverified_and_compute_uncertainty_when_authorized():
    repo = Phase44Repository(force_memory=True)
    ref_repo = ProfessionalReferenceRepository(repo)
    sim_eng = ProfessionalGamerSimilarityEngine(ref_repo)
    dna_eng = GamerDNAV2Engine()

    matches = [_match("u-sim", f"MS-{i}", days_ago=i) for i in range(4)]
    user_p = dna_eng.build_profile("u-sim", matches, game_version="FC27")

    # Zero authorized pro profiles -> MUST abstain cleanly
    abstained = sim_eng.compare(user_p, user_matches=matches)
    assert abstained.abstained is True
    assert "Zero rights-verified" in (abstained.abstention_reason or "")
    assert abstained.fallback_archetype_summary

    # Pass two authorized research-only synthetic test profiles cleanly
    p_close = ProStyleProfileVersion(
        reference_id="TEST-PRO-CLOSE",
        public_alias="Authorized Close Style",
        rights_status=RightsStatus.RESEARCH_ONLY,
        game_version="FC27",
        eligible_ref_matches=5,
        coverage=0.80,
        style_values={
            "possession_retention_preference": 0.65,
            "short_pass_preference": 0.81,
            "direct_progression": 0.35,
            "central_attacking_preference": 0.70,
            "pressing_tendency": 0.50,
            "risk_taking_preference": 0.31,
            "safer_alternative_preference": 0.79,
            "passing_network_density": 0.77,
        },
        distributions={"pass_direction_distribution": {"short_central": 0.48, "wide_flank": 0.22, "long_direct": 0.14, "backward_recycle": 0.16}},
    )
    p_far = ProStyleProfileVersion(
        reference_id="TEST-PRO-FAR",
        public_alias="Authorized Direct Counter",
        rights_status=RightsStatus.RESEARCH_ONLY,
        game_version="FC27",
        eligible_ref_matches=5,
        coverage=0.80,
        style_values={
            "possession_retention_preference": 0.34,
            "short_pass_preference": 0.40,
            "direct_progression": 0.88,
            "central_attacking_preference": 0.45,
            "pressing_tendency": 0.32,
            "risk_taking_preference": 0.80,
            "safer_alternative_preference": 0.32,
            "passing_network_density": 0.42,
        },
        distributions={"pass_direction_distribution": {"short_central": 0.18, "wide_flank": 0.22, "long_direct": 0.48, "backward_recycle": 0.12}},
    )
    rep = sim_eng.compare(user_p, user_matches=matches, candidate_profiles=[p_far, p_close])
    assert rep.abstained is False
    assert rep.matches[0].reference_id == "TEST-PRO-CLOSE"
    assert rep.matches[0].interpretable_similarity_index > rep.matches[1].interpretable_similarity_index
    assert len(rep.matches[0].confidence_band) == 2
    assert rep.uncertainty_summary["bootstrap_resamples"] == 24
    assert "jensen_shannon_distance" in rep.matches[0].distributional_distances


def test_phase44_skill_gap_and_style_evolution_with_experiment_attribution():
    dna_eng = GamerDNAV2Engine()
    p43_repo = Phase43Repository(force_memory=True)
    p40_repo = Phase40Repository(force_memory=True)

    ms = [
        _match("u-evo", "ME-1", days_ago=8, form="4-3-3", fm={"pressing_intensity": 0.40, "direct_progression": 0.30, "pass_accuracy": 0.71, "defensive_transition_management": 0.50}),
        _match("u-evo", "ME-2", days_ago=6, form="4-3-3", fm={"pressing_intensity": 0.42, "direct_progression": 0.32, "pass_accuracy": 0.72, "defensive_transition_management": 0.52}),
        _match("u-evo", "ME-3", days_ago=3, form="4-2-3-1", fm={"pressing_intensity": 0.78, "direct_progression": 0.74, "pass_accuracy": 0.73, "defensive_transition_management": 0.55}),
        _match("u-evo", "ME-4", days_ago=1, form="4-2-3-1", fm={"pressing_intensity": 0.82, "direct_progression": 0.76, "pass_accuracy": 0.74, "defensive_transition_management": 0.54}),
    ]
    prof = dna_eng.build_profile("u-evo", ms, game_version="FC27")

    gap_rep = EliteSkillGapEngine().analyze(prof)
    assert gap_rep.reference_population_verified is False
    assert any(g.dimension in ("pass_success_rate", "defensive_recovery_success") for g in gap_rep.gaps)

    # Create Phase 43 experiment linking 4-3-3 vs 4-2-3-1
    snap_svc = TacticalSnapshotService(p43_repo, p40_repo)
    s_a = snap_svc.create_snapshot("u-evo", TacticalSnapshotCreate(label="A", formation="4-3-3"))
    s_b = snap_svc.create_snapshot("u-evo", TacticalSnapshotCreate(label="B", formation="4-2-3-1"))
    exp = TacticalExperimentEngine(p43_repo, p40_repo).create_experiment(
        "u-evo",
        TacticalExperimentCreate(
            title="Evo Test", hypothesis="4-2-3-1 changes pressing & transitions cleanly",
            experiment_type=ExperimentType.FORMATION_COMPARISON,
            baseline_snapshot_id=s_a.snapshot_id, variant_snapshot_id=s_b.snapshot_id,
        ),
    )

    evo_rep = StyleEvolutionEngine(dna_eng).analyze("u-evo", ms, game_version="FC27", experiments=[exp], window_size=2)
    assert evo_rep.total_matches_evaluated == 4
    assert evo_rep.shift_detected is True
    assert any(w.experiment_linked_id == exp.experiment_id for w in evo_rep.windows)


def test_phase44_bridge_tools_and_copilot_intent_ceiling():
    # Crucial Phase 42 free-tier invariant check: <= 7 tools per intent + ALL_TOOLS preserved at 34
    assert len(CoachToolRegistry.ALL_TOOLS) == 34
    assert len(CoachToolRegistry.PHASE44_TOOLS) == 13
    for intent, names in INTENT_TO_TOOLS.items():
        assert 3 <= len(names) <= 7, f"{intent} exceeded 7 tools: {len(names)}"

    reg = CoachToolRegistry()
    for tname in CoachToolRegistry.PHASE44_TOOLS:
        out, rec = reg.execute(tname, "u-tools-44", game_version="FC27")
        assert rec.status == "OK", f"Tool {tname} failed: {out}"

    orch = PersonalCoachOrchestrator()
    intent = orch.classify_intent("Which pro player plays like my style and what is my skill gap?", False, {"source_route": "/gamer-dna"})
    assert intent == TaskIntent.GAMER_DNA

    # Sandbox dry-run + experiment creation check
    sb = PlayingStyleSandbox(Phase40Repository(force_memory=True), Phase43Repository(force_memory=True))
    res = sb.preview("u-sb", StyleSandboxRequest(game_version="FC27", sandbox_mode="SHIFT_COUNTER_ATTACK", convert_to_experiment=True))
    assert res["frozen_v321_weights_altered"] is False
    assert res["created_experiment"] is not None
    assert all(res["hard_constraints_verified"].values())

    # Recommendation bridge & training pathway check
    rec_res = StyleAwareRecommendationService().recommend_players("u-sb", game_version="FC27", position="CM", limit=3)
    assert rec_res["frozen_v321_weights_altered"] is False
    assert rec_res["market_price_status"] == "MARKET_PRICE_UNAVAILABLE"

    path = EliteTrainingPathwayService().build_pathway("u-sb", game_version="FC27")
    assert path["practice_only"] is True


def test_phase44_api_routes_and_idor_scoping():
    app = create_app()
    uid_a = f"p44-a-{uuid4().hex[:6]}"
    uid_b = f"p44-b-{uuid4().hex[:6]}"
    active = {"id": uid_a}

    def _override_user() -> CurrentUser:
        return CurrentUser(id=active["id"], email="dna@test.local", role="user", jti="jti-p44-test")

    app.dependency_overrides[current_user_required] = _override_user
    client = TestClient(app)

    h = client.get("/api/phase44/health")
    assert h.status_code == 200
    assert h.json()["feature_count"] == 60
    assert h.json()["pro_comparison_enabled"] is False

    prof = client.get("/api/phase44/profile?game_version=FC27&persist=true")
    assert prof.status_code == 200
    assert prof.json()["user_id"] == uid_a

    # IDOR check: user B sees zero persisted profiles belonging to user A
    active["id"] = uid_b
    hist_b = client.get("/api/phase44/profiles/history")
    assert hist_b.status_code == 200
    assert hist_b.json()["count"] == 0

    active["id"] = uid_a
    for path in (
        "/api/phase44/archetypes?game_version=FC27",
        "/api/phase44/references",
        "/api/phase44/similarity?game_version=FC27",
        "/api/phase44/skill-gap?game_version=FC27",
        "/api/phase44/evolution?game_version=FC27",
        "/api/phase44/recommendations/players?game_version=FC27&position=CM",
        "/api/phase44/recommendations/formations?game_version=FC27",
        "/api/phase44/training-pathway?game_version=FC27",
    ):
        r = client.get(path)
        assert r.status_code == 200, f"GET {path} failed: {r.text}"

    sim = client.get("/api/phase44/similarity?game_version=FC27").json()
    assert sim["abstained"] is True

    sb = client.post("/api/phase44/sandbox/preview", json={"game_version": "FC27", "sandbox_mode": "SUPPORT_NATURAL_POSSESSION"})
    assert sb.status_code == 200
    assert sb.json()["frozen_v321_weights_altered"] is False

    fb = client.post(
        "/api/phase44/feedback",
        json={
            "recommendation_id": "REC-P44-1",
            "recommendation_type": "STYLE_FORMATION",
            "game_version": "FC27",
            "user_action": "ACCEPTED",
        },
    )
    assert fb.status_code == 201
    rst = client.post("/api/phase44/reset")
    assert rst.status_code == 200
    assert rst.json()["reset"] is True
    app.dependency_overrides.clear()
