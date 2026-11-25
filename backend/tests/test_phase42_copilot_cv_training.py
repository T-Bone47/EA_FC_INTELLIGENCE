"""Phase 42 Comprehensive Backend Verification Suite:
- 42C: Circuit breaker state machine, provider timeouts, minimal tool subsets, shared BM25 cache, Research Registry
- 42D: User coaching preferences persistence, rolling summary + live DB freshness, optional Redis quota backend
- 42E: CoachContextEnvelope validation & cross-user IDOR anti-spoofing
- 42F: CV dataset manifest validation, leakage-free match splitting, OSS license gate, Hungarian evaluator, benchmark
- 42G: Multimodal screenshot redaction & consent enforcement vs provider choice
- 42H/I: 8-category adaptive drills linked to Phase 41 Decision Windows, calibrated BKT, closed-loop progression
"""
from __future__ import annotations

from uuid import uuid4

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.core.config import get_settings
from backend.cv_training import (
    BoundingBoxLabel,
    DatasetManifest,
    FrameGroundTruth,
    FramePrediction,
    LabeledFrameRecord,
    build_training_recipe,
    evaluate_detection_and_tracking,
    probe_local_cv_environment,
    split_by_match_group,
    validate_manifest,
)
from backend.cv_training.benchmark_cv import build_synthetic_calibrated_broadcast_sequence
from backend.cv_training.evaluator import BoxItem
from backend.cv_training.export_onnx import inspect_onnx_detector_compatibility
from backend.domain.phase40_models import (
    ArchetypeAssessment,
    ExperimentalBKTState,
    GamerDNAProfile,
    MatchIntelligenceRecord,
    RecurringMistakePattern,
)
from backend.services.coach_tools import CoachToolRegistry
from backend.services.llm.router import TaskIntent
from backend.services.football_knowledge_service import RESEARCH_SOURCE_REGISTRY, get_shared_knowledge_service
from backend.services.llm.free_guard import QuotaManager, RedisQuotaBackend
from backend.services.llm.registry import ProviderHealthMonitor
from backend.services.multi_channel_perception import PixelPerceptionExtractor
from backend.services.performance_progression_service import PerformanceProgressionService
from backend.services.training_plan_service import (
    TRAINING_CATEGORIES,
    TrainingPlanService,
    bkt_update,
    evaluate_bkt_calibration,
)


def _auth_client_for(email: str) -> TestClient:
    app = create_app()
    client = TestClient(app)
    resp = client.post("/api/auth/signup", json={"email": email, "password": "Password123!", "display_name": email.split("@")[0]})
    if resp.status_code == 409:
        resp = client.post("/api/auth/login", json={"email": email, "password": "Password123!"})
    assert resp.status_code in (200, 201), resp.text
    tok = resp.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {tok}"})
    return client


def test_phase42_circuit_breaker_timeout_tools_and_research_registry():
    settings = get_settings()
    assert settings.effective_provider_timeout("gemini") <= 16.0
    assert settings.effective_provider_timeout("openrouter") <= 18.0

    # Minimal intent tool routing <= 7 schemas per intent
    reg_tools = CoachToolRegistry()
    gp_tools = reg_tools.select_tool_specs_for_intent(TaskIntent.GAMEPLAY_ANALYSIS)
    squad_tools = reg_tools.select_tool_specs_for_intent(TaskIntent.SQUAD_OPTIMIZATION)
    assert 3 <= len(gp_tools) <= 7
    assert 3 <= len(squad_tools) <= 7

    # Shared cached knowledge singleton & 20+ Section 3 research sources
    kb1 = get_shared_knowledge_service()
    kb2 = get_shared_knowledge_service()
    assert kb1 is kb2
    assert len(RESEARCH_SOURCE_REGISTRY) >= 20

    # Circuit breaker CLOSED -> OPEN state machine
    mon = ProviderHealthMonitor(failure_threshold=2, open_seconds=60.0)
    is_open, _ = mon.is_circuit_open("gemini", "gemini-test")
    assert not is_open
    mon.record_failure("gemini", "503", model_id="gemini-test", transient=True)
    is_open, _ = mon.is_circuit_open("gemini", "gemini-test")
    assert not is_open
    mon.record_failure("gemini", "503", model_id="gemini-test", transient=True)
    is_open, rem = mon.is_circuit_open("gemini", "gemini-test")
    assert is_open and rem > 0


def test_phase42_redis_quota_fallback_and_preferences_api():
    rq = RedisQuotaBackend("redis://127.0.0.1:6399/0")
    assert rq.enabled is False  # gracefully falls back without local Redis daemon
    qm = QuotaManager(get_settings())
    assert qm.snapshot()["shared_backend"] == "in_process"

    c = _auth_client_for("phase42_prefs@example.com")
    get_r = c.get("/api/phase40/coach/preferences")
    assert get_r.status_code == 200
    put_r = c.put(
        "/api/phase40/coach/preferences",
        json={
            "preferred_provider": "OPENROUTER_FREE",
            "consent_external_llm": True,
            "favorite_formation": "4-3-3",
            "playstyle_focus": "HIGH_PRESS",
        },
    )
    assert put_r.status_code == 200
    assert put_r.json()["preferred_provider"] == "OPENROUTER_FREE"

    reg_r = c.get("/api/phase40/research-registry")
    assert reg_r.status_code == 200
    assert reg_r.json()["count"] >= 20


def test_phase42_context_envelope_idor_and_multimodal_consent_boundary():
    c1 = _auth_client_for("phase42_owner@example.com")
    c2 = _auth_client_for("phase42_other@example.com")

    # Owner creates a personal match and decision window
    m = c1.post(
        "/api/phase40/matches",
        json={
            "video_id": f"VID-OWN-42-{uuid4().hex[:6]}",
            "game_version": "FC27",
            "game_patch": "PATCH_1.04",
            "formation": "4-2-3-1",
            "provenance": "REAL_VIDEO_DECODED",
            "observation_quality": "HIGH",
            "tracking_coverage_pct": 91.0,
            "duration_seconds": 300.0,
            "feature_metrics": {"transition_opportunities": 6, "exposed_transitions": 2},
            "coaching_findings": [],
        },
    )
    assert m.status_code == 201
    own_match_id = m.json()["match_id"]

    # Attacker tries to spoof User A's match_id and send an unredacted screenshot
    res = c2.post(
        "/api/phase40/coach/ask",
        json={
            "question": "Analyze this match and screenshot",
            "game_version": "FC27",
            "preferred_provider": "DETERMINISTIC",
            "active_match_id": own_match_id,
            "context_envelope": {
                "route_name": "GAMEPLAY_STUDIO",
                "game_version": "FC27",
                "match_id": own_match_id,
                "squad_id": "foreign-squad-999",
            },
            "image_b64": "ZmFrZV9pbWFnZV9ieXRlcw==",
            "image_mime": "image/png",
            "user_consent_media": True,
            "redaction_confirmed": False,  # Must block media transmission
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    notices = " ".join(body.get("security_notices", []))
    assert "blocked" in notices.lower() or "redaction" in notices.lower()
    assert "unauthorized" in notices.lower()
    assert own_match_id not in body.get("relevant_match_ids", [])

    # Valid redacted media with explicit consent produces unverified candidate marker
    res_ok = c1.post(
        "/api/phase40/coach/ask",
        json={
            "question": "Review my redacted formation screenshot",
            "game_version": "FC27",
            "preferred_provider": "DETERMINISTIC",
            "context_envelope": {"route_name": "SQUAD_LAB", "game_version": "FC27"},
            "screenshot_use_case": "FORMATION_SCREENSHOT",
            "image_b64": "ZmFrZV9yZWRhY3RlZF9wbmc=",
            "image_mime": "image/png",
            "user_consent_media": True,
            "redaction_confirmed": True,
        },
    )
    assert res_ok.status_code == 200
    notes = " ".join(res_ok.json().get("multimodal_candidate_notes", []))
    assert "CANDIDATE_MULTIMODAL_OBSERVATION_UNVERIFIED" in notes


def test_phase42_cv_training_splitter_evaluator_and_detector():
    env = probe_local_cv_environment()
    assert env["opencv"] is not None

    onnx_check = inspect_onnx_detector_compatibility()
    assert onnx_check["status"] in ("NO_TRAINED_WEIGHTS_PRESENT", "VERIFIED_OPENCV_DNN")

    # OSS license safety check
    recipe = build_training_recipe(framework="YOLOX_APACHE2")
    assert recipe.commercial_safe is True
    assert recipe.batch_size_4gb_vram == 4
    with pytest.raises(PermissionError):
        build_training_recipe(framework="ULTRALYTICS_AGPL3_OPT_IN", accept_agpl_copyleft=False)

    # Synthetic calibrated geometry check + match-level zero leakage split
    frames, gt_frames = build_synthetic_calibrated_broadcast_sequence(num_frames=6)
    extractor = PixelPerceptionExtractor()
    preds: list[FramePrediction] = []
    manifest_records: list[LabeledFrameRecord] = []

    for fi, rgb in enumerate(frames):
        players, ball = extractor.detect_broadcast_players_and_ball(rgb, fi, fi * 0.2)
        pboxes = [
            BoxItem(
                class_name="player",
                xyxy_norm=(p.bbox_xywh[0], p.bbox_xywh[1], p.bbox_xywh[0] + p.bbox_xywh[2], p.bbox_xywh[1] + p.bbox_xywh[3]),
                confidence=p.confidence,
                track_id=f"T-{idx}",
            )
            for idx, p in enumerate(players)
        ]
        if ball is not None:
            pboxes.append(
                BoxItem(
                    class_name="ball",
                    xyxy_norm=(ball.bbox_xywh[0], ball.bbox_xywh[1], ball.bbox_xywh[0] + ball.bbox_xywh[2], ball.bbox_xywh[1] + ball.bbox_xywh[3]),
                    confidence=ball.confidence,
                )
            )
        preds.append(FramePrediction(frame_index=fi, boxes=pboxes))
        manifest_records.append(
            LabeledFrameRecord(
                frame_id=f"F-{fi}",
                match_id=f"M-{fi // 2}",
                video_id=f"V-{fi // 2}",
                frame_index=fi,
                timestamp_sec=fi * 0.2,
                width=1280,
                height=720,
                is_synthetic_calibration_test=True,
                labels=[BoundingBoxLabel(class_id=0, class_name="player", xywh_norm=(0.5, 0.5, 0.03, 0.08))],
            )
        )

    assert validate_manifest(DatasetManifest(dataset_name="strict", frames=manifest_records), allow_synthetic=False)["valid"] is False
    assert validate_manifest(DatasetManifest(dataset_name="proxy", frames=manifest_records), allow_synthetic=True)["valid"] is True

    split = split_by_match_group(manifest_records)
    assert split.leakage_free_verified is True
    assert set(split.train_matches).isdisjoint(split.val_matches)
    assert set(split.train_matches).isdisjoint(split.test_matches)

    metrics = evaluate_detection_and_tracking(gt_frames, preds, evaluation_scope="SYNTHETIC_CALIBRATED_GEOMETRY_PROXY")
    assert metrics.player_ap50 >= 0.70
    assert metrics.ball_recall >= 0.50


def test_phase42_adaptive_training_decision_linkage_and_closed_loop_progression():
    assert len(TRAINING_CATEGORIES) == 8
    dna = GamerDNAProfile(
        user_id="u-42",
        archetype=ArchetypeAssessment(
            status="SINGLE_DOMINANT",
            primary_archetype="Balanced Builder",
            summary="Test profile",
        ),
    )
    win = {
        "window_id": "WIN-TEST-01",
        "match_id": "M-1",
        "video_id": "VID-1",
        "decision_type": "PASS_SELECTION",
        "provenance": "REAL_VIDEO_DECODED",
        "action_timestamp_sec": 34.5,
        "regret_estimate": 0.19,
        "counterfactual_comparison": {
            "best_alternative_id": "OPT-SAFE",
            "best_alternative_label": "Switch to weak-side FB",
            "best_alternative_utility": 0.78,
        },
        "candidate_actions": [
            {"action_id": "OPT-SAFE", "action_family": "SWITCH_PLAY", "label": "Switch to weak-side FB", "is_observed_choice": False, "value_breakdown": {"risk_adjusted_utility": 0.78}},
            {"action_id": "OPT-RISK", "action_family": "THROUGH_BALL", "label": "Force central lane", "is_observed_choice": True, "value_breakdown": {"risk_adjusted_utility": 0.59}},
        ],
    }
    plan = TrainingPlanService().generate_plan(
        "u-42",
        mistakes=[
            RecurringMistakePattern(
                mistake_id="MK-TEST-01",
                diagnostic_code="RISKY_PASSING_DECISION",
                title="Risky Central Progression Passes",
                formal_definition="Attempting vertical pass through <2.5m lane clearance.",
                required_evidence="3+ observed central corridor interceptions.",
                total_occurrences=3,
                total_opportunities=10,
                normalized_rate=0.3,
                severity_estimate="HIGH",
                confidence_level="MODERATE",
                narrative="Repeated risky central passes.",
                supporting_clips=[],
            )
        ],
        dna=dna,
        decision_windows=[win],
    )
    assert plan.decision_windows_linked == 1
    assert len(plan.categories_covered) >= 3
    assert plan.exercises[0].linked_window_id == "WIN-TEST-01"
    assert plan.exercises[0].hide_outcome_by_default is True

    # Bounded BKT updates + calibration
    s0 = ExperimentalBKTState(skill_code="progression_selection", p_slip=0.99, p_guess=0.01)
    s1 = bkt_update(s0, True)
    assert s1.practice_only is True
    assert s1.p_slip <= 0.25 and s1.p_guess >= 0.05
    cal = evaluate_bkt_calibration([
        {"prior_p": 0.25, "is_optimal_or_defensible": True},
        {"prior_p": 0.45, "is_optimal_or_defensible": True},
    ])
    assert cal["brier_score"] is not None

    # Closed-loop progression tracking across comparable matches
    prog = PerformanceProgressionService().evaluate(
        "u-42",
        matches=[
            MatchIntelligenceRecord(
                match_id=f"M-{i}",
                user_id="u-42",
                game_version="FC27",
                game_patch="PATCH_1.04",
                formation="4-2-3-1",
                provenance="REAL_VIDEO_DECODED",
                observation_quality="HIGH",
                tracking_coverage_pct=90.0,
                duration_seconds=300.0,
                feature_metrics={"transition_opportunities": 10, "exposed_transitions": 4 - i, "opponent_quality_proxy": "HIGH"},
                coaching_findings=(
                    [{"diagnostic_code": "RISKY_PASSING_DECISION", "summary": "Central turnover risk"}] * (3 if i < 2 else 0)
                ),
            )
            for i in range(4)
        ],
        training_attempts=[{"skill_code": "progression_selection", "is_optimal_or_defensible": True, "posterior_p": 0.62}],
    )
    assert len(prog.weakness_loop_tracking) >= 1
    assert prog.weakness_loop_tracking[0]["verdict"] == "PROVISIONAL_IMPROVEMENT"
    assert "causal" in prog.causal_disclaimer.lower()
