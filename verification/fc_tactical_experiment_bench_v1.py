"""Phase 43 Comprehensive Evaluation Suite: FC_TACTICAL_EXPERIMENT_BENCH_V1.

Evaluates 7 strictly separated categories without mixing synthetic calibration tests
with personal empirical gameplay evidence:
1. Tactical Fingerprint extraction & <14 player visibility abstention
2. Match-clustered Statistical Inference (positive effect, exact null, patch-drift confounder)
3. Formation Suitability across all 12 formations + head-to-head comparison
4. Player Replacement Triage (behavior/tactical first, MARKET_PRICE_UNAVAILABLE)
5. Multi-Objective Squad Optimization (hard constraints + exact combinatorial parity check)
6. Co-Pilot 12 Tactical Tools + TACTICAL_LAB compare-formation intent routing
7. CV Runtime Status & Calibrated ECE/Brier probe (synthetic proxy isolated from real clips)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.config import get_settings
from backend.cv_training.benchmark_cv import build_synthetic_calibrated_broadcast_sequence
from backend.cv_training.dataset_tools import compute_detector_ece_and_brier, get_cv_pipeline_status
from backend.cv_training.evaluator import BoxItem, FramePrediction
from backend.domain.phase40_models import CoachContextEnvelope, CoachQuestionRequest, MatchRecordCreate
from backend.domain.phase43_models import (
    ExperimentArm,
    ExperimentMatchLinkCreate,
    ExperimentType,
    SquadOptimizationRequest,
    StatisticalVerdict,
    TacticalExperimentCreate,
    TacticalSnapshotCreate,
)
from backend.repositories.phase40_repository import Phase40Repository
from backend.repositories.phase43_repository import Phase43Repository
from backend.services.coach_tools import CoachToolRegistry
from backend.services.experiment_analysis_service import ExperimentAnalysisService
from backend.services.llm.router import FootballModelRouter, QuotaManager
from backend.services.multi_channel_perception import PixelPerceptionExtractor
from backend.services.multi_objective_squad_optimizer import MultiObjectiveSquadOptimizer
from backend.services.personal_coach_orchestrator import PersonalCoachOrchestrator
from backend.services.personal_formation_engine import PersonalFormationEngine
from backend.services.replacement_experiment_service import ReplacementExperimentService
from backend.services.tactical_experiment_engine import TacticalExperimentEngine
from backend.services.tactical_fingerprint_engine import TacticalFingerprintEngine
from backend.services.tactical_snapshot_service import TacticalSnapshotService


def _cat_a_fingerprint_and_abstention() -> Dict[str, Any]:
    p40 = Phase40Repository(force_memory=True)
    p43 = Phase43Repository(force_memory=True)
    uid = "bench-u-fp"
    fp_eng = TacticalFingerprintEngine(p43)

    m_full = p40.save_match(
        uid,
        MatchRecordCreate(
            video_id="B-FULL",
            game_version="FC27",
            game_patch="PATCH_1.04",
            formation="4-2-3-1",
            provenance="REAL_VIDEO_DECODED",
            tracking_coverage_pct=89.0,
            telemetry_summary={"calibration_state": "GOOD", "visible_outfield_players": 18, "frames_analyzed": 240},
            feature_metrics={"possession_share": 0.56, "central_progression": 0.61, "wing_utilization": 0.48, "defensive_compactness": 0.74, "pressing_intensity": 0.55, "transition_opportunities": 10, "exposed_transitions": 2},
        ),
    )
    m_partial = p40.save_match(
        uid,
        MatchRecordCreate(
            video_id="B-PARTIAL",
            game_version="FC27",
            game_patch="PATCH_1.04",
            formation="4-3-3",
            provenance="REAL_VIDEO_DECODED",
            tracking_coverage_pct=55.0,
            telemetry_summary={"calibration_state": "COARSE", "visible_outfield_players": 10, "frames_analyzed": 120},
            feature_metrics={"possession_share": 0.51, "defensive_compactness": 0.60, "pressing_intensity": 0.65},
        ),
    )
    fp_full = fp_eng.build_fingerprint(uid, m_full, save=False)
    fp_partial = fp_eng.build_fingerprint(uid, m_partial, save=False)

    compactness_full = next(p.metrics["defensive_compactness"] for p in fp_full.phases if p.phase == "OUT_OF_POSSESSION")
    compactness_partial = next(p.metrics["defensive_compactness"] for p in fp_partial.phases if p.phase == "OUT_OF_POSSESSION")

    passed = (
        compactness_full is not None
        and fp_full.team_compactness_abstained is False
        and fp_partial.team_compactness_abstained is True
        and compactness_partial is None
        and "conceded_transition_rate" in fp_full.metric_details
    )
    return {
        "category": "A_TACTICAL_FINGERPRINT_AND_ABSTENTION",
        "passed": passed,
        "full_compactness": compactness_full,
        "partial_abstained": fp_partial.team_compactness_abstained,
        "partial_abstain_reason": fp_partial.abstention_reason,
    }


def _cat_b_statistical_inference() -> Dict[str, Any]:
    p40 = Phase40Repository(force_memory=True)
    p43 = Phase43Repository(force_memory=True)
    uid = "bench-u-stats"
    sn = TacticalSnapshotService(p43, p40)
    eng = TacticalExperimentEngine(p43, p40)
    ana = ExperimentAnalysisService(p43, p40)

    s_a = sn.create_snapshot(uid, TacticalSnapshotCreate(label="Bench Base 4-3-3", game_version="FC27", game_patch="PATCH_1.04", formation="4-3-3"))
    s_b = sn.create_snapshot(uid, TacticalSnapshotCreate(label="Bench Control 4-2-3-1", game_version="FC27", game_patch="PATCH_1.04", formation="4-2-3-1", parent_snapshot_id=s_a.snapshot_id))

    # 1. Clear improvement
    e_pos = eng.create_experiment(uid, TacticalExperimentCreate(title="Positive Signal Test", hypothesis="Lower conceded rate", experiment_type=ExperimentType.FORMATION_COMPARISON, game_version="FC27", baseline_patch="PATCH_1.04", baseline_snapshot_id=s_a.snapshot_id, variant_snapshot_id=s_b.snapshot_id))
    for i in range(4):
        ma = p40.save_match(uid, MatchRecordCreate(video_id=f"POS-A-{i}", game_version="FC27", game_patch="PATCH_1.04", formation="4-3-3", provenance="REAL_VIDEO_DECODED", tracking_coverage_pct=85.0, feature_metrics={"transition_opportunities": 10, "exposed_transitions": 4 + (i % 2)}))
        mb = p40.save_match(uid, MatchRecordCreate(video_id=f"POS-B-{i}", game_version="FC27", game_patch="PATCH_1.04", formation="4-2-3-1", provenance="REAL_VIDEO_DECODED", tracking_coverage_pct=88.0, feature_metrics={"transition_opportunities": 10, "exposed_transitions": 1}))
        eng.link_match(uid, e_pos.experiment_id, ExperimentMatchLinkCreate(match_id=ma.match_id, arm=ExperimentArm.BASELINE_A, match_order=i * 2))
        eng.link_match(uid, e_pos.experiment_id, ExperimentMatchLinkCreate(match_id=mb.match_id, arm=ExperimentArm.VARIANT_B, match_order=i * 2 + 1))
    res_pos = ana.analyze(uid, e_pos.experiment_id, persist=False)

    # 2. Exact null effect (identical means + safe zero baseline handling)
    e_null = eng.create_experiment(uid, TacticalExperimentCreate(title="Exact Null Test", hypothesis="Zero difference stays neutral", experiment_type=ExperimentType.FORMATION_COMPARISON, game_version="FC27", baseline_patch="PATCH_1.04", baseline_snapshot_id=s_a.snapshot_id, variant_snapshot_id=s_b.snapshot_id))
    for i in range(3):
        ma = p40.save_match(uid, MatchRecordCreate(video_id=f"NULL-A-{i}", game_version="FC27", game_patch="PATCH_1.04", formation="4-3-3", provenance="REAL_VIDEO_DECODED", tracking_coverage_pct=85.0, feature_metrics={"transition_opportunities": 10, "exposed_transitions": 0}))
        mb = p40.save_match(uid, MatchRecordCreate(video_id=f"NULL-B-{i}", game_version="FC27", game_patch="PATCH_1.04", formation="4-2-3-1", provenance="REAL_VIDEO_DECODED", tracking_coverage_pct=85.0, feature_metrics={"transition_opportunities": 10, "exposed_transitions": 0}))
        eng.link_match(uid, e_null.experiment_id, ExperimentMatchLinkCreate(match_id=ma.match_id, arm=ExperimentArm.BASELINE_A, match_order=i * 2))
        eng.link_match(uid, e_null.experiment_id, ExperimentMatchLinkCreate(match_id=mb.match_id, arm=ExperimentArm.VARIANT_B, match_order=i * 2 + 1))
    res_null = ana.analyze(uid, e_null.experiment_id, persist=False)

    # 3. Confounded patch drift MUST downgrade to INCONCLUSIVE
    e_conf = eng.create_experiment(uid, TacticalExperimentCreate(title="Patch Drift Confound Test", hypothesis="Detects patch confounding", experiment_type=ExperimentType.FORMATION_COMPARISON, game_version="FC27", baseline_patch="PATCH_1.04", baseline_snapshot_id=s_a.snapshot_id, variant_snapshot_id=s_b.snapshot_id))
    for i in range(3):
        ma = p40.save_match(uid, MatchRecordCreate(video_id=f"CNF-A-{i}", game_version="FC27", game_patch="PATCH_1.03", formation="4-3-3", provenance="REAL_VIDEO_DECODED", tracking_coverage_pct=85.0, feature_metrics={"transition_opportunities": 10, "exposed_transitions": 5}))
        mb = p40.save_match(uid, MatchRecordCreate(video_id=f"CNF-B-{i}", game_version="FC27", game_patch="PATCH_1.04", formation="4-2-3-1", provenance="REAL_VIDEO_DECODED", tracking_coverage_pct=85.0, feature_metrics={"transition_opportunities": 10, "exposed_transitions": 1}))
        eng.link_match(uid, e_conf.experiment_id, ExperimentMatchLinkCreate(match_id=ma.match_id, arm=ExperimentArm.BASELINE_A, match_order=i * 2))
        eng.link_match(uid, e_conf.experiment_id, ExperimentMatchLinkCreate(match_id=mb.match_id, arm=ExperimentArm.VARIANT_B, match_order=i * 2 + 1))
    res_conf = ana.analyze(uid, e_conf.experiment_id, persist=False)

    passed = (
        res_pos.verdict == StatisticalVerdict.SUPPORTED_IMPROVEMENT
        and res_pos.relative_improvement is not None
        and res_null.verdict != StatisticalVerdict.SUPPORTED_IMPROVEMENT
        and res_null.relative_improvement is None
        and res_conf.confounders.patch_drift_detected is True
        and res_conf.verdict == StatisticalVerdict.INCONCLUSIVE
    )
    return {
        "category": "B_STATISTICAL_INFERENCE",
        "passed": passed,
        "pos_verdict": res_pos.verdict.value,
        "pos_prob_meaningful": res_pos.posterior_prob_meaningful,
        "null_verdict": res_null.verdict.value,
        "confound_verdict": res_conf.verdict.value,
    }


def _cat_c_formations() -> Dict[str, Any]:
    p40 = Phase40Repository(force_memory=True)
    p43 = Phase43Repository(force_memory=True)
    eng = PersonalFormationEngine(p40, p43)
    rec = eng.recommend_formations("bench-form-u", game_version="FC27", game_patch="PATCH_1.04", top_k=12)
    cmp_rep = eng.compare_formations("bench-form-u", "4-3-3", "4-2-3-1", game_version="FC27")
    passed = (
        len(rec.ranked_formations) == 12
        and rec.frozen_v321_preserved is True
        and cmp_rep.preferred_formation in ("4-3-3", "4-2-3-1")
        and len(cmp_rep.structural_differences) >= 3
    )
    return {
        "category": "C_FORMATION_RECOMMENDATION_12_SHAPES",
        "passed": passed,
        "formation_count": len(rec.ranked_formations),
        "top_formation": rec.ranked_formations[0].formation,
        "compare_winner": cmp_rep.preferred_formation,
    }


def _cat_d_replacement_triage() -> Dict[str, Any]:
    p40 = Phase40Repository(force_memory=True)
    uid = "bench-repl-u"
    for i in range(2):
        p40.save_match(uid, MatchRecordCreate(video_id=f"R-{i}", game_version="FC27", game_patch="PATCH_1.04", formation="4-3-3", provenance="REAL_VIDEO_DECODED", tracking_coverage_pct=85.0, feature_metrics={"transition_opportunities": 10, "exposed_transitions": 4, "pressing_intensity": 0.78}))
    rep = ReplacementExperimentService(p40).evaluate_replacement(uid, target_slot="CDM", current_player_name="Test Pivot", game_version="FC27")
    passed = (
        rep.frozen_v321_untouched is True
        and rep.market_price_status == "MARKET_PRICE_UNAVAILABLE"
        and len(rep.candidate_comparisons) >= 2
        and any(c["option"] == "NO_COIN_TACTICAL_ADJUSTMENT" for c in rep.candidate_comparisons)
    )
    return {
        "category": "D_REPLACEMENT_TRIAGE",
        "passed": passed,
        "recommendation": rep.primary_recommendation,
        "comparisons": len(rep.candidate_comparisons),
    }


def _cat_e_squad_optimizer_exact_parity() -> Dict[str, Any]:
    pool: List[Dict[str, Any]] = [
        {"entity_id": "GK-1", "name": "Alisson", "position_primary": "GK", "overall_rating": 89, "coin_cost": 45000},
        {"entity_id": "GK-2", "name": "Raya", "position_primary": "GK", "overall_rating": 83, "coin_cost": 8000},
        {"entity_id": "RB-1", "name": "Walker", "position_primary": "RB", "overall_rating": 84, "coin_cost": 25000},
        {"entity_id": "CB-1", "name": "Saliba", "position_primary": "CB", "overall_rating": 87, "coin_cost": 70000},
        {"entity_id": "CB-2", "name": "Van Dijk", "position_primary": "CB", "overall_rating": 89, "coin_cost": 95000},
        {"entity_id": "LB-1", "name": "Theo Hernandez", "position_primary": "LB", "overall_rating": 87, "coin_cost": 85000},
        {"entity_id": "CDM-1", "name": "Tchouameni", "position_primary": "CDM", "overall_rating": 85, "coin_cost": 20000, "playstyles": ["Intercept"]},
        {"entity_id": "CM-1", "name": "Valverde", "position_primary": "CM", "overall_rating": 88, "coin_cost": 90000},
        {"entity_id": "CM-2", "name": "Pedri", "position_primary": "CM", "overall_rating": 87, "coin_cost": 40000},
        {"entity_id": "RW-1", "name": "Saka", "position_primary": "RW", "overall_rating": 87, "coin_cost": 55000},
        {"entity_id": "LW-1", "name": "Vinicius Jr", "position_primary": "LW", "overall_rating": 90, "coin_cost": 150000},
        {"entity_id": "ST-1", "name": "Isak", "position_primary": "ST", "overall_rating": 86, "coin_cost": 35000},
        {"entity_id": "ST-2", "name": "Griezmann", "position_primary": "ST", "overall_rating": 88, "coin_cost": 60000},
    ]
    opt = MultiObjectiveSquadOptimizer(Phase40Repository(force_memory=True))
    res = opt.optimize_squad(
        "bench-opt-u",
        SquadOptimizationRequest(
            game_version="FC27",
            formation="4-3-3",
            objective="PERSONALIZED",
            candidate_pool=pool,
            max_alternatives=3,
        ),
    )
    checks = res.hard_constraints_verified
    passed = (
        checks["exact_11_players"]
        and checks["single_gk"]
        and checks["all_players_unique"]
        and checks["position_slots_valid"]
        and res.exact_parity_checked is True
        and res.exact_optimal_gap is not None
        and res.exact_optimal_gap <= 0.02
        and res.frozen_v321_weights_altered is False
        and len(res.alternatives) >= 2
    )
    return {
        "category": "E_MULTI_OBJECTIVE_SQUAD_OPTIMIZER",
        "passed": passed,
        "solver": res.solver_method,
        "exact_parity_checked": res.exact_parity_checked,
        "exact_optimal_gap": res.exact_optimal_gap,
        "utility": res.primary_xi.get("utility"),
    }


def _cat_f_copilot_tools_and_routing() -> Dict[str, Any]:
    reg = CoachToolRegistry()
    names_ok = len(CoachToolRegistry.PHASE43_TOOLS) == 12 and all(t in reg._handlers for t in CoachToolRegistry.PHASE43_TOOLS)

    s = get_settings().model_copy(update={"gemini_api_key": None, "openrouter_api_key": None})
    orch = PersonalCoachOrchestrator(Phase40Repository(force_memory=True), settings=s)
    ans = orch.ask(
        "bench-u-cp",
        CoachQuestionRequest(
            question="Compare 4-3-3 and 4-2-3-1 for my playstyle",
            game_version="FC27",
            preferred_provider="DETERMINISTIC",
            context_envelope=CoachContextEnvelope(route_name="TACTICAL_LAB", game_version="FC27"),
        ),
    )
    called = [t.get("tool") if isinstance(t, dict) else getattr(t, "tool_name", "") for t in (ans.tool_trace or [])]
    return {
        "category": "F_COPILOT_TOOLS_AND_ROUTING",
        "passed": bool(names_ok and ans.intent == "TACTICAL_RECOMMENDATION" and "compare_formations" in called),
        "phase43_tools_count": len(CoachToolRegistry.PHASE43_TOOLS),
        "routed_intent": ans.intent,
        "tools_called": called,
    }


def _cat_g_cv_calibration_probe() -> Dict[str, Any]:
    status = get_cv_pipeline_status()
    frames, gt = build_synthetic_calibrated_broadcast_sequence(num_frames=6)
    ext = PixelPerceptionExtractor()
    preds: List[FramePrediction] = []
    for fi, rgb in enumerate(frames):
        pl, ball = ext.detect_broadcast_players_and_ball(rgb, fi, fi * 0.2)
        bxs = [BoxItem(class_name="player", xyxy_norm=(p.bbox_xywh[0], p.bbox_xywh[1], p.bbox_xywh[0] + p.bbox_xywh[2], p.bbox_xywh[1] + p.bbox_xywh[3]), confidence=p.confidence) for p in pl]
        if ball is not None:
            bxs.append(BoxItem(class_name="ball", xyxy_norm=(ball.bbox_xywh[0], ball.bbox_xywh[1], ball.bbox_xywh[0] + ball.bbox_xywh[2], ball.bbox_xywh[1] + ball.bbox_xywh[3]), confidence=ball.confidence))
        preds.append(FramePrediction(frame_index=fi, boxes=bxs))
    cal = compute_detector_ece_and_brier(gt, preds, evaluation_scope="SYNTHETIC_CALIBRATED_GEOMETRY_PROXY")
    passed = (
        status["onnx_detector"]["status"] == "NO_TRAINED_WEIGHTS_PRESENT"
        and "broadcast" in status["model_streams"]
        and "minimap_roi" in status["model_streams"]
        and cal["evaluation_scope"] == "SYNTHETIC_CALIBRATED_GEOMETRY_PROXY"
    )
    return {
        "category": "G_CV_RUNTIME_AND_CALIBRATION",
        "passed": passed,
        "onnx_status": status["onnx_detector"]["status"],
        "ece": cal["ece"],
        "brier": cal["brier_score"],
    }


def run_bench() -> Dict[str, Any]:
    results = [
        _cat_a_fingerprint_and_abstention(),
        _cat_b_statistical_inference(),
        _cat_c_formations(),
        _cat_d_replacement_triage(),
        _cat_e_squad_optimizer_exact_parity(),
        _cat_f_copilot_tools_and_routing(),
        _cat_g_cv_calibration_probe(),
    ]
    overall = all(r["passed"] for r in results)
    return {
        "benchmark": "FC_TACTICAL_EXPERIMENT_BENCH_V1",
        "categories_total": len(results),
        "categories_passed": sum(1 for r in results if r["passed"]),
        "overall_passed": overall,
        "results": results,
    }


if __name__ == "__main__":
    out = run_bench()
    print(json.dumps(out, indent=2))
    sys.exit(0 if out["overall_passed"] else 1)
