"""Phase 43 Comprehensive Backend Verification Suite:
- 43A: Search Co-Pilot active-filter hydration, strict provider vs consent separation, deadline failover
- 43B: Immutable versioned TacticalConfigurationSnapshot, unknown preservation, edition isolation
- 43C: 4-phase TacticalFingerprint separation (nominal vs observed shape), nulls preserved
- 43D/E: 8 experiment workflows, synthetic & edition firewall, SciPy/Bootstrap/Bayesian/LOO/confounder inference
- 43F/G/H: Advisory formation recommendations, behavior-first replacement triage, counterfactual diffs
- 43I/J: YOLO/CVAT dataset exporter, detector ECE/Brier calibration, non-existent ONNX guard, Personal Meta patch isolation
- 43K: All 10 verified Phase 43 Co-Pilot tools & API IDOR ownership isolation
"""
from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.core.config import Settings
from backend.cv_training import (
    BoundingBoxLabel,
    DatasetManifest,
    FrameGroundTruth,
    FramePrediction,
    LabeledFrameRecord,
    compute_detector_ece_and_brier,
    export_manifest_to_yolo_dataset,
    parse_yolo_label_lines,
    register_cv_checkpoint_record,
)
from backend.cv_training.evaluator import BoxItem
from backend.domain.phase40_models import CoachContextEnvelope, CoachQuestionRequest, MatchRecordCreate
from backend.domain.phase43_models import (
    EvidenceGrade,
    ExperimentArm,
    ExperimentMatchLinkCreate,
    ExperimentType,
    StatisticalVerdict,
    TacticalExperimentCreate,
    TacticalSlotConfig,
    TacticalSnapshotCreate,
)
from backend.repositories.phase40_repository import Phase40Repository
from backend.repositories.phase43_repository import Phase43Repository
from backend.services.coach_tools import CoachToolRegistry
from backend.services.experiment_analysis_service import ExperimentAnalysisService
from backend.services.llm.contracts import FootballLLMProvider, LLMResponse, ProviderError, ProviderErrorKind
from backend.services.llm.free_guard import FreeUsageGuard, QuotaManager
from backend.services.llm.registry import ModelCapabilityRegistry, ProviderHealthMonitor
from backend.services.llm.router import FootballModelRouter, TaskIntent
from backend.services.personal_coach_orchestrator import PersonalCoachOrchestrator
from backend.services.personal_formation_engine import PersonalFormationEngine
from backend.services.personal_meta_service import PersonalMetaService
from backend.services.replacement_experiment_service import ReplacementExperimentService
from backend.services.tactical_counterfactual_service import TacticalCounterfactualService
from backend.services.tactical_experiment_engine import TacticalExperimentEngine
from backend.services.tactical_fingerprint_engine import TacticalFingerprintEngine
from backend.services.tactical_snapshot_service import TacticalSnapshotService


class _SlowOrFailingProvider(FootballLLMProvider):
    def __init__(self, name: str, fn):
        self.provider_name = name
        self.fn = fn

    def generate(self, **kwargs) -> LLMResponse:
        return self.fn(**kwargs)

    def health_check(self):
        return {"provider": self.provider_name}


def _auth_client_for(email: str) -> TestClient:
    app = create_app()
    client = TestClient(app)
    r = client.post("/api/auth/signup", json={"email": email, "password": "Password43!", "display_name": email.split("@")[0]})
    if r.status_code == 409:
        r = client.post("/api/auth/login", json={"email": email, "password": "Password43!"})
    assert r.status_code in (200, 201), r.text
    client.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return client


def test_phase43a_consent_separation_deadline_failover_and_search_copilot():
    repo = Phase40Repository(force_memory=True)
    gemini_called = {"count": 0}

    def fail_if_called(**kwargs):
        gemini_called["count"] += 1
        return LLMResponse(provider="gemini", model="gemini-4-hydrogen", text='{"answer":"ok"}')

    s = Settings(
        gemini_api_key="AIzaSyMockTest43000000000000000000",
        openrouter_api_key="sk-or-v1-mock43000000000000000000",
        ai_coach_gemini_timeout_seconds=8.0,
        ai_coach_openrouter_timeout_seconds=8.0,
        ai_coach_total_deadline_seconds=18.0,
    )
    reg = ModelCapabilityRegistry(s)
    reg._last_refresh_mono["gemini"] = 1e12
    reg._last_refresh_mono["openrouter"] = 1e12

    router = FootballModelRouter(
        settings=s,
        registry=reg,
        guard=FreeUsageGuard(s),
        quota=QuotaManager(s),
        health=ProviderHealthMonitor(),
        providers={
            "gemini": _SlowOrFailingProvider("gemini", fail_if_called),
            "openrouter": _SlowOrFailingProvider("openrouter", fail_if_called),
        },
    )
    orch = PersonalCoachOrchestrator(repo, settings=s, router=router)

    # 1. Provider selection NEVER overrides external-LLM data sharing consent
    no_consent = orch.ask(
        "u-consent-43a",
        CoachQuestionRequest(
            question="Which CM fits my tactics?",
            game_version="FC26",
            preferred_provider="GEMINI",
            consent_external_llm=False,
        ),
    )
    assert gemini_called["count"] == 0
    assert no_consent.response_mode == "DETERMINISTIC_COACH"
    assert "CONSENT_REQUIRED_FOR_EXTERNAL_LLM" in no_consent.security_notices

    # 2. Search Co-Pilot active filter + card selection deterministic fallback
    r_search = orch.ask(
        "u-search-43a",
        CoachQuestionRequest(
            question="Which one is better for my style?",
            game_version="FC26",
            preferred_provider="DETERMINISTIC",
            context_envelope=CoachContextEnvelope(
                route_name="PLAYER_DISCOVERY",
                game_version="FC26",
                active_filters={"position": "RW", "ovr_min": 84},
                selected_player_names=["Mohamed Salah", "Lamine Yamal"],
            ),
        ),
    )
    assert r_search.intent == "PLAYER_COMPARISON"
    assert len(r_search.player_cards) >= 2
    assert "Your Gamer DNA" not in r_search.answer[:40]

    # 3. TurnBudgetTracker enforces total turn deadline when budget expired
    qm = QuotaManager(s)
    tb = qm.new_turn_budget()
    tb.started_mono -= 100.0
    assert tb.is_deadline_exceeded() is True
    resp, notes = router.invoke(
        user_id="u-deadline",
        intent=TaskIntent.GENERAL_FOOTBALL,
        messages=[],
        turn_budget=tb,
    )
    assert resp is None
    assert any("deadline" in n.lower() for n in notes)


def test_phase43b_to_e_snapshots_fingerprints_and_experiment_statistics():
    p40 = Phase40Repository(force_memory=True)
    p43 = Phase43Repository(force_memory=True)
    uid = "u-exp-43"

    snap_svc = TacticalSnapshotService(p43, p40)
    snap_a = snap_svc.create_snapshot(
        uid,
        TacticalSnapshotCreate(
            label="Base 4-3-3 High",
            game_version="FC27",
            game_patch="PATCH_1.04",
            formation="4-3-3",
            tactical_profile="HIGH_PRESS",
            line_height=75,
            slots=[
                TacticalSlotConfig(slot_index=0, slot_position="GK", player_name="Alisson", overall_rating=89),
                TacticalSlotConfig(slot_index=5, slot_position="CDM", player_name="Tchouameni", overall_rating=85, assigned_role="Holding", role_familiarity="ROLE_PLUS"),
            ],
        ),
    )
    assert snap_a.is_immutable is True
    assert "build_up_style" in snap_a.unknown_fields
    assert "defensive_approach" in snap_a.unknown_fields

    snap_b = snap_svc.create_snapshot(
        uid,
        TacticalSnapshotCreate(
            label="Variant 4-2-3-1 Control",
            game_version="FC27",
            game_patch="PATCH_1.04",
            formation="4-2-3-1",
            tactical_profile="POSSESSION",
            parent_snapshot_id=snap_a.snapshot_id,
            line_height=52,
            width_setting=48,
        ),
    )
    assert snap_b.version_number == 2

    # Edition wall prevents FC26 fork from FC27 parent
    with pytest.raises(ValueError, match="edition"):
        snap_svc.create_snapshot(
            uid,
            TacticalSnapshotCreate(
                label="Cross Edition",
                game_version="FC26",
                formation="4-4-2",
                parent_snapshot_id=snap_a.snapshot_id,
            ),
        )

    # Seed 3 Arm A matches (high transition exposure ~0.42) + 3 Arm B matches (~0.14) + 1 synthetic match
    exp_eng = TacticalExperimentEngine(p43, p40)
    exp = exp_eng.create_experiment(
        uid,
        TacticalExperimentCreate(
            title="4-3-3 vs 4-2-3-1 Transition Defense",
            hypothesis="Double pivot lowers transition exposure rate.",
            experiment_type=ExperimentType.FORMATION_COMPARISON,
            game_version="FC27",
            baseline_patch="PATCH_1.04",
            baseline_snapshot_id=snap_a.snapshot_id,
            variant_snapshot_id=snap_b.snapshot_id,
            primary_metric="conceded_transition_rate",
            target_min_matches_per_arm=3,
        ),
    )

    fp_eng = TacticalFingerprintEngine(p43)
    for i in range(3):
        m_a = p40.save_match(
            uid,
            MatchRecordCreate(
                video_id=f"VA-{i}",
                game_version="FC27",
                game_patch="PATCH_1.04",
                formation="4-3-3",
                provenance="REAL_VIDEO_DECODED",
                tracking_coverage_pct=88.0,
                feature_metrics={"transition_opportunities": 10, "exposed_transitions": 4 + (i % 2), "pressing_intensity": 0.72, "defensive_compactness": 0.48, "possession_share": 0.49},
                match_result={"goals_for": 1, "goals_against": 2, "outcome": "LOSS"},
            ),
        )
        m_b = p40.save_match(
            uid,
            MatchRecordCreate(
                video_id=f"VB-{i}",
                game_version="FC27",
                game_patch="PATCH_1.04",
                formation="4-2-3-1",
                provenance="REAL_VIDEO_DECODED",
                tracking_coverage_pct=91.0,
                feature_metrics={"transition_opportunities": 10, "exposed_transitions": 1 + (i % 2), "pressing_intensity": 0.54, "defensive_compactness": 0.72, "possession_share": 0.58},
                match_result={"goals_for": 2, "goals_against": 1, "outcome": "WIN"},
            ),
        )
        fp = fp_eng.build_fingerprint(uid, m_b, snapshot=snap_b)
        assert len(fp.phases) == 4
        assert fp.observed_out_of_possession_shape == "COMPACT_MID_LOW_BLOCK"
        assert "conceded_transition_rate" in fp.phases[3].metrics
        exp_eng.link_match(uid, exp.experiment_id, ExperimentMatchLinkCreate(match_id=m_a.match_id, arm=ExperimentArm.BASELINE_A, match_order=i * 2))
        exp_eng.link_match(uid, exp.experiment_id, ExperimentMatchLinkCreate(match_id=m_b.match_id, arm=ExperimentArm.VARIANT_B, match_order=i * 2 + 1))

    # Add synthetic match that MUST be excluded cleanly by analysis engine
    m_synth = p40.save_match(
        uid,
        MatchRecordCreate(
            video_id="VS-SYNTH",
            game_version="FC27",
            game_patch="PATCH_1.04",
            formation="4-2-3-1",
            provenance="SYNTHETIC_FIXTURE",
            feature_metrics={"transition_opportunities": 10, "exposed_transitions": 0},
        ),
    )
    lnk_s = exp_eng.link_match(uid, exp.experiment_id, ExperimentMatchLinkCreate(match_id=m_synth.match_id, arm=ExperimentArm.VARIANT_B, match_order=99))
    assert lnk_s["excluded_reason"] == "SYNTHETIC_FIXTURE_EXCLUDED"

    analysis = ExperimentAnalysisService(p43, p40).analyze(uid, exp.experiment_id)
    assert analysis.unit_of_analysis == "MATCH_CLUSTER_AGGREGATE"
    assert analysis.arm_a.eligible_match_count == 3
    assert analysis.arm_b.eligible_match_count == 3
    assert analysis.confounders.synthetic_excluded_count == 1
    assert analysis.verdict == StatisticalVerdict.SUPPORTED_IMPROVEMENT
    assert analysis.evidence_grade == EvidenceGrade.CONTROLLED_EXPERIMENT_EVIDENCE
    assert analysis.bayesian_posterior_prob_b_better is not None and analysis.bayesian_posterior_prob_b_better > 0.85
    assert analysis.bootstrap_ci_95 is not None

    # Personal Meta remains strictly isolated by game_patch and reports V3.2.1 unaltered
    meta_104 = PersonalMetaService(p40, p43).build_profile(uid, game_version="FC27", game_patch="PATCH_1.04")
    meta_103 = PersonalMetaService(p40, p43).build_profile(uid, game_version="FC27", game_patch="PATCH_1.03")
    assert meta_104.eligible_match_count == 6
    assert meta_104.strongest_system == "4-2-3-1"
    assert meta_103.eligible_match_count == 0
    assert meta_104.frozen_v321_weights_altered is False

    # Formations & Replacement triage & Counterfactual comparison
    f_rec = PersonalFormationEngine(p40, p43).recommend_formations(uid, game_version="FC27", game_patch="PATCH_1.04")
    assert f_rec.frozen_v321_preserved is True
    assert f_rec.ranked_formations[0].formation == "4-2-3-1"

    cf = TacticalCounterfactualService(p43).compare_snapshots(uid, snap_a.snapshot_id, snap_b.snapshot_id)
    assert cf.evidence_grade == EvidenceGrade.THEORETICAL_SUITABILITY
    assert cf.rest_defense_risk_delta < 0

    triage = ReplacementExperimentService(p40).evaluate_replacement(uid, target_slot="CDM", game_version="FC27")
    assert triage.market_price_status == "MARKET_PRICE_UNAVAILABLE"
    assert triage.frozen_v321_untouched is True


def test_phase43i_cv_yolo_exporter_and_ece_calibration(tmp_path: Path):
    frames = [
        LabeledFrameRecord(
            frame_id=f"FR-{i}",
            match_id=f"MATCH-{i // 2}",
            video_id=f"VID-{i // 2}",
            frame_index=i,
            timestamp_sec=float(i),
            width=1280,
            height=720,
            is_synthetic_calibration_test=False,
            labels=[BoundingBoxLabel(class_id=0, class_name="player", xywh_norm=(0.5, 0.5, 0.04, 0.09))],
        )
        for i in range(6)
    ]
    manifest = DatasetManifest(dataset_name="eafc_human_sample", frames=frames)
    exp_out = export_manifest_to_yolo_dataset(manifest, tmp_path / "yolo_ds")
    assert exp_out["leakage_free_verified"] is True
    assert (tmp_path / "yolo_ds" / "data.yaml").exists()
    assert (tmp_path / "yolo_ds" / "cvat_labels.json").exists()

    parsed = parse_yolo_label_lines(["0 0.500000 0.500000 0.040000 0.090000 7"])
    assert len(parsed) == 1 and parsed[0].track_id == 7

    gt = [FrameGroundTruth(frame_index=0, boxes=[BoxItem(class_name="player", xyxy_norm=(0.4, 0.4, 0.5, 0.6), confidence=1.0)])]
    pred = [FramePrediction(frame_index=0, boxes=[BoxItem(class_name="player", xyxy_norm=(0.41, 0.41, 0.5, 0.6), confidence=0.85)])]
    cal = compute_detector_ece_and_brier(gt, pred, evaluation_scope="LABELED_VALIDATION_SET")
    assert cal["ece"] == pytest.approx(0.15, abs=1e-3)
    assert cal["brier_score"] == pytest.approx(0.0225, abs=1e-3)

    with pytest.raises(FileNotFoundError):
        register_cv_checkpoint_record(
            checkpoint_id="CKPT-BAD",
            architecture="YOLOX_APACHE2",
            dataset_manifest="test",
            evaluation_scope="LABELED_VALIDATION_SET",
            onnx_path=str(tmp_path / "missing_fc_detector.onnx"),
        )


def test_phase43k_all_12_copilot_tools_and_api_idor_isolation():
    reg = CoachToolRegistry()
    assert len(CoachToolRegistry.PHASE43_TOOLS) == 12
    for tool_name in CoachToolRegistry.PHASE43_TOOLS:
        assert tool_name in reg._handlers

    # Non-mutating confirmation gate on create_tactical_experiment when confirm=False
    prev, rec_prev = reg.execute("create_tactical_experiment", "u-gate-p43", title="Gate Check Trial")
    assert rec_prev.status == "OK"
    assert prev["preview_only"] is True
    assert prev["mutates_saved_config"] is False

    c1 = _auth_client_for(f"p43_owner_{uuid.uuid4().hex[:6]}@example.com")
    c2 = _auth_client_for(f"p43_other_{uuid.uuid4().hex[:6]}@example.com")

    s1 = c1.post("/api/phase43/snapshots", json={"label": "Own Setup", "game_version": "FC27", "formation": "4-2-3-1"})
    assert s1.status_code == 201
    sid1 = s1.json()["snapshot_id"]

    # Cross-user IDOR denied cleanly
    assert c2.get(f"/api/phase43/snapshots/{sid1}").status_code == 404
    assert c1.get("/api/phase43/health").json()["phase"] == "43"
    assert c1.get("/api/phase43/cv/status").status_code == 200
    assert c1.get("/api/phase40/health").json()["phase43_tools_registered"] == 12


def test_phase43_complete_coverage_abstention_optimizer_lifecycle_feedback():
    from backend.domain.phase43_models import DesignType, ExperimentStatus, SquadOptimizationRequest
    from backend.services.multi_objective_squad_optimizer import MultiObjectiveSquadOptimizer
    from backend.services.personal_formation_engine import PersonalFormationEngine
    from backend.services.tactical_counterfactual_service import TacticalCounterfactualService

    p40 = Phase40Repository(force_memory=True)
    p43 = Phase43Repository(force_memory=True)
    uid = "u-p43-complete"

    # 1. Explicit abstention when visible_outfield_players < 14
    m_low_vis = p40.save_match(
        uid,
        MatchRecordCreate(
            video_id="LOW-VIS-14",
            game_version="FC27",
            game_patch="PATCH_1.04",
            formation="4-3-3",
            provenance="REAL_VIDEO_DECODED",
            tracking_coverage_pct=65.0,
            telemetry_summary={"calibration_state": "MODERATE", "visible_outfield_players": 11, "frames_analyzed": 100},
            feature_metrics={"possession_share": 0.52, "defensive_compactness": 0.68, "pressing_intensity": 0.60, "transition_opportunities": 5, "exposed_transitions": 0},
        ),
    )
    fp_low = TacticalFingerprintEngine(p43).build_fingerprint(uid, m_low_vis, save=False)
    assert fp_low.team_compactness_abstained is True
    assert fp_low.abstention_reason and "14" in fp_low.abstention_reason
    out_block = next(p for p in fp_low.phases if p.phase == "OUT_OF_POSSESSION")
    assert out_block.metrics["defensive_compactness"] is None
    assert fp_low.metric_details["defensive_compactness"].abstained_reason is not None

    # 2. All 12 formations + compare_formations
    f_eng = PersonalFormationEngine(p40, p43)
    rec_12 = f_eng.recommend_formations(uid, game_version="FC27", game_patch="PATCH_1.04", top_k=12)
    assert len(rec_12.ranked_formations) == 12
    assert rec_12.ranked_formations[0].theoretical_fit > 0
    cmp_rep = f_eng.compare_formations(uid, "4-3-3", "4-2-3-1", game_version="FC27")
    assert len(cmp_rep.structural_differences) >= 3

    # 3. Lifecycle transitions, seeded schedule, adherence & safe zero baseline relative_improvement
    sn_svc = TacticalSnapshotService(p43, p40)
    s_a = sn_svc.create_snapshot(uid, TacticalSnapshotCreate(label="A 4-3-3", game_version="FC27", formation="4-3-3", line_height=70, width_setting=60))
    s_b = sn_svc.create_snapshot(uid, TacticalSnapshotCreate(label="B 4-2-3-1", game_version="FC27", formation="4-2-3-1", line_height=50, width_setting=48, parent_snapshot_id=s_a.snapshot_id))
    diff = sn_svc.diff_snapshots(uid, s_a.snapshot_id, s_b.snapshot_id)
    assert any(d["field"] == "formation" for d in diff["field_changes"])

    exp_eng = TacticalExperimentEngine(p43, p40)
    exp = exp_eng.create_experiment(
        uid,
        TacticalExperimentCreate(
            title="Zero Denominator & Adherence Check",
            hypothesis="Verify lifecycle and relative_improvement zero guard.",
            experiment_type=ExperimentType.FORMATION_COMPARISON,
            game_version="FC27",
            baseline_snapshot_id=s_a.snapshot_id,
            variant_snapshot_id=s_b.snapshot_id,
            design_type=DesignType.CROSSOVER_ABBA,
            target_min_matches_per_arm=2,
        ),
    )
    assert exp.status == ExperimentStatus.READY
    assert len(exp.assignments) >= 4
    exp_paused = exp_eng.update_status(uid, exp.experiment_id, ExperimentStatus.PAUSED, reason="Break check")
    assert exp_paused.status == ExperimentStatus.PAUSED
    exp_active = exp_eng.update_status(uid, exp.experiment_id, ExperimentStatus.ACTIVE, reason="Resume trial")
    assert exp_active.status == ExperimentStatus.ACTIVE

    for idx in range(2):
        ma = p40.save_match(uid, MatchRecordCreate(video_id=f"Z-A-{idx}", game_version="FC27", game_patch="PATCH_1.04", formation="4-3-3", provenance="REAL_VIDEO_DECODED", tracking_coverage_pct=80.0, feature_metrics={"transition_opportunities": 8, "exposed_transitions": 0}))
        mb = p40.save_match(uid, MatchRecordCreate(video_id=f"Z-B-{idx}", game_version="FC27", game_patch="PATCH_1.04", formation="4-2-3-1", provenance="REAL_VIDEO_DECODED", tracking_coverage_pct=80.0, feature_metrics={"transition_opportunities": 8, "exposed_transitions": 0}))
        exp_eng.link_match(uid, exp.experiment_id, ExperimentMatchLinkCreate(match_id=ma.match_id, arm=ExperimentArm.BASELINE_A, match_order=idx * 2))
        exp_eng.link_match(uid, exp.experiment_id, ExperimentMatchLinkCreate(match_id=mb.match_id, arm=ExperimentArm.VARIANT_B, match_order=idx * 2 + 1))

    ana_svc = ExperimentAnalysisService(p43, p40)
    res_zero = ana_svc.analyze(uid, exp.experiment_id, persist=False)
    assert res_zero.relative_improvement is None
    assert res_zero.posterior_prob_meaningful is not None
    ss_plan = ana_svc.estimate_required_sample_size(expected_delta=0.08, pooled_sd=0.14)
    assert ss_plan["recommended_matches_per_arm"] >= 3

    # 4. Counterfactual spatial zone & sensitivity sweep
    cf = TacticalCounterfactualService(p43).compare_snapshots(uid, s_a.snapshot_id, s_b.snapshot_id)
    assert "zone14_overloads_delta" in cf.zone_geometry_deltas
    assert len(cf.sensitivity_sweep) == 9
    assert cf.epistemic_classification["future_match_win_rate_and_stamina"] == "UNSUPPORTED_ASSUMPTION"

    # 5. Multi-Objective Squad Optimizer constraints & exact parity check
    pool = [
        {"entity_id": "GK-1", "name": "GK One", "position_primary": "GK", "overall_rating": 88, "coin_cost": 40000},
        {"entity_id": "GK-2", "name": "GK Two", "position_primary": "GK", "overall_rating": 82, "coin_cost": 9000},
        {"entity_id": "RB-1", "name": "RB One", "position_primary": "RB", "overall_rating": 85, "coin_cost": 25000},
        {"entity_id": "CB-1", "name": "CB One", "position_primary": "CB", "overall_rating": 87, "coin_cost": 65000},
        {"entity_id": "CB-2", "name": "CB Two", "position_primary": "CB", "overall_rating": 86, "coin_cost": 55000},
        {"entity_id": "LB-1", "name": "LB One", "position_primary": "LB", "overall_rating": 85, "coin_cost": 30000},
        {"entity_id": "CDM-1", "name": "CDM One", "position_primary": "CDM", "overall_rating": 86, "coin_cost": 22000, "playstyles": ["Intercept"]},
        {"entity_id": "CM-1", "name": "CM One", "position_primary": "CM", "overall_rating": 87, "coin_cost": 50000},
        {"entity_id": "CM-2", "name": "CM Two", "position_primary": "CM", "overall_rating": 84, "coin_cost": 18000},
        {"entity_id": "RW-1", "name": "RW One", "position_primary": "RW", "overall_rating": 87, "coin_cost": 45000},
        {"entity_id": "LW-1", "name": "LW One", "position_primary": "LW", "overall_rating": 88, "coin_cost": 75000},
        {"entity_id": "ST-1", "name": "ST One", "position_primary": "ST", "overall_rating": 88, "coin_cost": 80000},
    ]
    opt_res = MultiObjectiveSquadOptimizer(p40).optimize_squad(
        uid, SquadOptimizationRequest(game_version="FC27", formation="4-3-3", objective="PERSONALIZED", candidate_pool=pool)
    )
    assert all(opt_res.hard_constraints_verified.values())
    assert opt_res.exact_parity_checked is True
    assert opt_res.frozen_v321_weights_altered is False

    # 6. TACTICAL_LAB "Compare 4-3-3 and 4-2-3-1" orchestrator routing + Feedback Ledger API
    s = Settings(environment="test", gemini_api_key=None, openrouter_api_key=None)
    orch = PersonalCoachOrchestrator(p40, settings=s)
    ans = orch.ask(
        uid,
        CoachQuestionRequest(
            question="Compare 4-3-3 and 4-2-3-1 for my tactics",
            game_version="FC27",
            preferred_provider="DETERMINISTIC",
            context_envelope=CoachContextEnvelope(route_name="TACTICAL_LAB", game_version="FC27"),
        ),
    )
    assert ans.intent == "TACTICAL_RECOMMENDATION"
    called = [t.get("tool") if isinstance(t, dict) else getattr(t, "tool_name", "") for t in (ans.tool_trace or [])]
    assert "compare_formations" in called

    c1 = _auth_client_for(f"p43_fb_{uuid.uuid4().hex[:6]}@example.com")
    fb = c1.post(
        "/api/phase43/feedback",
        json={
            "recommendation_id": "REC-TEST-1",
            "recommendation_type": "FORMATION_CHANGE",
            "game_version": "FC27",
            "game_patch": "PATCH_1.04",
            "user_action": "ACCEPTED",
            "estimated_effect": 0.12,
            "notes": "Adopted 4-2-3-1 suggestion",
        },
    )
    assert fb.status_code == 201
    assert c1.get("/api/phase43/feedback").json()["count"] >= 1
    assert c1.get("/api/phase43/formations/compare?formation_a=4-3-3&formation_b=4-2-3-1").status_code == 200
    assert c1.get("/api/phase43/experiments/suggest").status_code == 200
    assert c1.get("/api/phase43/experiments/sample-size").status_code == 200
