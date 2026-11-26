"""Phase 43 Unified API Routes: Personal Tactical Experimentation Lab & Empirical Intelligence.

All personal endpoints enforce `current_user_required` and strict user_id ownership.
Supports:
- Immutable versioned TacticalConfigurationSnapshots
- Phase-separated TacticalFingerprints (nominal vs observed shape)
- Match-clustered A/B/ABBA Tactical Experiments + SciPy/Bayesian Analysis
- Personal Formation Recommendations (preserving frozen V3.2.1)
- Behavior-first Replacement Triage & Counterfactual Configuration Comparisons
- Edition- & patch-isolated Personal Meta Profiles
- Real-footage CV pipeline status & calibrated ECE/Brier check
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.api.deps import CurrentUser, current_user_required, rate_limit_default
from backend.cv_training.benchmark_cv import build_synthetic_calibrated_broadcast_sequence, run_benchmark
from backend.cv_training.dataset_tools import compute_detector_ece_and_brier, get_cv_pipeline_status, register_cv_checkpoint_record
from backend.cv_training.evaluator import BoxItem, FramePrediction
from backend.domain.phase43_models import (
    ExperimentMatchLinkCreate,
    ExperimentStatusUpdate,
    RecommendationFeedbackCreate,
    SquadOptimizationRequest,
    TacticalExperimentCreate,
    TacticalSnapshotCreate,
)
from backend.repositories.phase40_repository import MatchNotFoundError, get_phase40_repository
from backend.repositories.phase43_repository import (
    ExperimentNotFoundError,
    SnapshotNotFoundError,
    get_phase43_repository,
)
from backend.services.experiment_analysis_service import ExperimentAnalysisService
from backend.services.multi_channel_perception import PixelPerceptionExtractor
from backend.services.multi_objective_squad_optimizer import MultiObjectiveSquadOptimizer
from backend.services.personal_formation_engine import PersonalFormationEngine
from backend.services.personal_meta_service import PersonalMetaService
from backend.services.replacement_experiment_service import ReplacementExperimentService
from backend.services.tactical_counterfactual_service import TacticalCounterfactualService
from backend.services.tactical_experiment_engine import TacticalExperimentEngine
from backend.services.tactical_fingerprint_engine import TacticalFingerprintEngine
from backend.services.tactical_snapshot_service import TacticalSnapshotService


router = APIRouter(
    prefix="/api/phase43",
    tags=["phase43-tactical-lab"],
    dependencies=[Depends(rate_limit_default)],
)


class FingerprintBuildRequest(BaseModel):
    match_id: str = Field(min_length=2, max_length=80)
    snapshot_id: Optional[str] = Field(default=None, max_length=64)


class ReplacementTriageRequest(BaseModel):
    target_slot: str = Field(min_length=1, max_length=12)
    current_player_name: Optional[str] = Field(default=None, max_length=80)
    game_version: Literal["FC26", "FC27"] = "FC27"
    budget_coins: Optional[int] = Field(default=None, ge=0)


class CounterfactualCompareRequest(BaseModel):
    baseline_snapshot_id: str = Field(min_length=3, max_length=64)
    variant_snapshot_id: str = Field(min_length=3, max_length=64)


@router.get("/health")
def phase43_health() -> Dict[str, Any]:
    return {
        "status": "OK",
        "phase": "43",
        "frozen_v321_preserved": True,
        "experiment_types_supported": 8,
        "unit_of_analysis": "MATCH_CLUSTER_AGGREGATE",
    }


@router.post("/snapshots", status_code=201)
def create_tactical_snapshot(
    body: TacticalSnapshotCreate,
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    svc = TacticalSnapshotService()
    try:
        return svc.create_snapshot(user.id, body).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/snapshots")
def list_tactical_snapshots(
    game_version: Optional[str] = Query(None, max_length=10),
    game_patch: Optional[str] = Query(None, max_length=32),
    limit: int = Query(50, ge=1, le=100),
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    items = get_phase43_repository().list_snapshots(user.id, game_version=game_version, game_patch=game_patch, limit=limit)
    return {"count": len(items), "items": [s.model_dump(mode="json") for s in items]}


@router.get("/snapshots/{snapshot_id}")
def get_tactical_snapshot(
    snapshot_id: str,
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    try:
        return get_phase43_repository().get_snapshot(user.id, snapshot_id).model_dump(mode="json")
    except SnapshotNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/fingerprints/build", status_code=201)
def build_tactical_fingerprint(
    body: FingerprintBuildRequest,
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    p40 = get_phase40_repository()
    p43 = get_phase43_repository()
    try:
        match = p40.get_match(user.id, body.match_id)
    except MatchNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    snap = None
    if body.snapshot_id:
        try:
            snap = p43.get_snapshot(user.id, body.snapshot_id)
        except SnapshotNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    fp = TacticalFingerprintEngine(p43).build_fingerprint(user.id, match, snapshot=snap)
    return fp.model_dump(mode="json")


@router.get("/fingerprints")
def list_tactical_fingerprints(
    match_id: Optional[str] = Query(None, max_length=80),
    limit: int = Query(50, ge=1, le=100),
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    fps = get_phase43_repository().list_fingerprints(user.id, match_id=match_id, limit=limit)
    return {"count": len(fps), "items": [f.model_dump(mode="json") for f in fps]}


@router.post("/experiments", status_code=201)
def create_experiment(
    body: TacticalExperimentCreate,
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    eng = TacticalExperimentEngine()
    try:
        exp = eng.create_experiment(user.id, body)
        return {
            **exp.model_dump(mode="json"),
            "recommended_schedule": eng.get_recommended_schedule(exp.experiment_id),
        }
    except SnapshotNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/experiments")
def list_experiments(
    game_version: Optional[str] = Query(None, max_length=10),
    limit: int = Query(30, ge=1, le=100),
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    items = get_phase43_repository().list_experiments(user.id, game_version=game_version, limit=limit)
    return {"count": len(items), "items": [e.model_dump(mode="json") for e in items]}


@router.get("/experiments/suggest")
def suggest_tactical_experiment(
    game_version: Literal["FC26", "FC27"] = Query("FC27"),
    game_patch: str = Query("PATCH_1.04", max_length=32),
    focus_weakness: Optional[str] = Query(None, max_length=64),
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    return TacticalExperimentEngine().suggest_tactical_experiment(
        user.id, game_version=game_version, game_patch=game_patch, focus_weakness=focus_weakness
    )


@router.post("/experiments/preview")
def preview_tactical_experiment(
    body: TacticalExperimentCreate,
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    try:
        return TacticalExperimentEngine().preview_tactical_experiment(user.id, body)
    except SnapshotNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/experiments/sample-size")
def estimate_experiment_sample_size(
    expected_delta: float = Query(0.08, gt=0.0, le=1.0),
    pooled_sd: float = Query(0.14, gt=0.0, le=1.0),
    power: float = Query(0.80, ge=0.5, le=0.99),
) -> Dict[str, Any]:
    return ExperimentAnalysisService().estimate_required_sample_size(
        expected_delta=expected_delta, pooled_sd=pooled_sd, power=power
    )


@router.get("/experiments/{experiment_id}")
def get_experiment(
    experiment_id: str,
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    try:
        return get_phase43_repository().get_experiment(user.id, experiment_id).model_dump(mode="json")
    except ExperimentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/experiments/{experiment_id}/matches")
def link_experiment_match(
    experiment_id: str,
    body: ExperimentMatchLinkCreate,
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    eng = TacticalExperimentEngine()
    try:
        return eng.link_match(user.id, experiment_id, body)
    except (ExperimentNotFoundError, MatchNotFoundError, SnapshotNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/experiments/{experiment_id}/analyze")
def analyze_experiment(
    experiment_id: str,
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    try:
        return ExperimentAnalysisService().analyze(user.id, experiment_id).model_dump(mode="json")
    except (ExperimentNotFoundError, SnapshotNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/recommendations/formations")
def recommend_personal_formations(
    game_version: Literal["FC26", "FC27"] = Query("FC27"),
    game_patch: str = Query("PATCH_1.04", max_length=32),
    top_k: int = Query(6, ge=1, le=12),
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    return PersonalFormationEngine().recommend_formations(
        user.id, game_version=game_version, game_patch=game_patch, top_k=top_k
    ).model_dump(mode="json")


@router.post("/recommendations/replacement-triage")
def evaluate_replacement_triage(
    body: ReplacementTriageRequest,
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    return ReplacementExperimentService().evaluate_replacement(
        user.id,
        target_slot=body.target_slot,
        current_player_name=body.current_player_name,
        game_version=body.game_version,
        budget_coins=body.budget_coins,
    ).model_dump(mode="json")


@router.post("/counterfactuals/compare")
def compare_tactical_counterfactuals(
    body: CounterfactualCompareRequest,
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    try:
        return TacticalCounterfactualService().compare_snapshots(
            user.id, body.baseline_snapshot_id, body.variant_snapshot_id
        ).model_dump(mode="json")
    except SnapshotNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/snapshots/diff")
def diff_tactical_snapshots(
    body: CounterfactualCompareRequest,
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    try:
        return TacticalSnapshotService().diff_snapshots(user.id, body.baseline_snapshot_id, body.variant_snapshot_id)
    except SnapshotNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/formations/compare")
def compare_personal_formations(
    formation_a: str = Query("4-3-3", max_length=16),
    formation_b: str = Query("4-2-3-1", max_length=16),
    game_version: Literal["FC26", "FC27"] = Query("FC27"),
    game_patch: str = Query("PATCH_1.04", max_length=32),
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    try:
        return PersonalFormationEngine().compare_formations(
            user.id, formation_a, formation_b, game_version=game_version, game_patch=game_patch
        ).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/experiments/{experiment_id}/status")
def update_experiment_status(
    experiment_id: str,
    body: ExperimentStatusUpdate,
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    try:
        return TacticalExperimentEngine().update_status(
            user.id, experiment_id, body.status, reason=body.reason
        ).model_dump(mode="json")
    except ExperimentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/experiments/{experiment_id}/assignments")
def list_experiment_assignments(
    experiment_id: str,
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    try:
        p43 = get_phase43_repository()
        _ = p43.get_experiment(user.id, experiment_id)
        assigns = p43.list_experiment_assignments(user.id, experiment_id)
        return {"experiment_id": experiment_id, "count": len(assigns), "assignments": assigns}
    except ExperimentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/experiments/{experiment_id}/uncertainty")
def explain_experiment_uncertainty(
    experiment_id: str,
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    try:
        return ExperimentAnalysisService().explain_uncertainty(user.id, experiment_id)
    except (ExperimentNotFoundError, SnapshotNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/squads/optimize")
def optimize_personal_squad(
    body: SquadOptimizationRequest,
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    return MultiObjectiveSquadOptimizer().optimize_squad(user.id, body).model_dump(mode="json")


@router.post("/feedback", status_code=201)
def record_recommendation_feedback(
    body: RecommendationFeedbackCreate,
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    return PersonalMetaService().record_feedback(user.id, body).model_dump(mode="json")


@router.get("/feedback")
def list_recommendation_feedback(
    game_version: Optional[str] = Query(None, max_length=10),
    limit: int = Query(50, ge=1, le=100),
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    items = PersonalMetaService().list_feedback(user.id, game_version=game_version, limit=limit)
    return {"count": len(items), "items": [f.model_dump(mode="json") for f in items]}


@router.get("/personal-meta")
def get_personal_meta(
    game_version: Literal["FC26", "FC27"] = Query("FC27"),
    game_patch: str = Query("PATCH_1.04", max_length=32),
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    return PersonalMetaService().build_profile(
        user.id, game_version=game_version, game_patch=game_patch
    ).model_dump(mode="json")


@router.get("/cv/status")
def cv_status() -> Dict[str, Any]:
    return get_cv_pipeline_status()


@router.post("/cv/benchmark-calibration")
def run_cv_calibration_probe(
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    frames, gt_frames = build_synthetic_calibrated_broadcast_sequence(num_frames=8)
    ext = PixelPerceptionExtractor()
    preds: List[FramePrediction] = []
    for fi, rgb in enumerate(frames):
        pl, ball = ext.detect_broadcast_players_and_ball(rgb, fi, fi * 0.2)
        bxs = [BoxItem(class_name="player", xyxy_norm=(p.bbox_xywh[0], p.bbox_xywh[1], p.bbox_xywh[0] + p.bbox_xywh[2], p.bbox_xywh[1] + p.bbox_xywh[3]), confidence=p.confidence) for p in pl]
        if ball is not None:
            bxs.append(BoxItem(class_name="ball", xyxy_norm=(ball.bbox_xywh[0], ball.bbox_xywh[1], ball.bbox_xywh[0] + ball.bbox_xywh[2], ball.bbox_xywh[1] + ball.bbox_xywh[3]), confidence=ball.confidence))
        preds.append(FramePrediction(frame_index=fi, boxes=bxs))
    cal = compute_detector_ece_and_brier(gt_frames, preds, evaluation_scope="SYNTHETIC_CALIBRATED_GEOMETRY_PROXY")
    from pathlib import Path
    bench = run_benchmark(Path(__file__).resolve().parents[3])
    m = bench["synthetic_calibrated_geometry_proxy"]["metrics"]
    ckpt = register_cv_checkpoint_record(
        checkpoint_id="CKPT-CLASSICAL-HSV-PROXY-P43",
        architecture="CV_CLASSICAL_HSV_BYTETRACK",
        dataset_manifest="SYNTHETIC_CALIBRATED_GEOMETRY_PROXY",
        evaluation_scope="SYNTHETIC_CALIBRATED_GEOMETRY_PROXY",
        map_50=m.get("map50"),
        precision_score=m.get("macro_precision"),
        recall_score=m.get("macro_recall"),
        idf1=m.get("idf1"),
        hota_proxy=m.get("hota"),
        fps_rtx3050=bench["synthetic_calibrated_geometry_proxy"].get("fps"),
        onnx_path=None,
        license_name="BSD-3-Clause / MIT (OpenCV + SciPy)",
    )
    return {
        "calibration": cal,
        "synthetic_proxy_metrics": m,
        "checkpoint_registered": ckpt,
        "real_uploaded_clips": bench["real_uploaded_clips"],
    }
