"""Phase 44 Unified API Routes: Professional Gamer DNA V2, Governed Similarity & Style Sandbox.

All personal endpoints enforce `current_user_required` and strict user_id ownership.
Public pro reference registry exposes candidate metadata and fail-closed rights status only.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.deps import CurrentUser, current_user_required, rate_limit_default
from backend.core.config import get_settings
from backend.domain.phase44_models import (
    StyleRecommendationFeedbackCreate,
    StyleRecommendationFeedbackRecord,
    StyleSandboxRequest,
)
from backend.repositories.phase40_repository import get_phase40_repository
from backend.repositories.phase41_repository import get_phase41_repository
from backend.repositories.phase43_repository import get_phase43_repository
from backend.repositories.phase44_repository import get_phase44_repository
from backend.services.elite_skill_gap_engine import EliteSkillGapEngine
from backend.services.gamer_dna_v2_engine import ARCHETYPES_V2, FEATURE_CATALOG_V2, GamerDNAV2Engine
from backend.services.professional_similarity_engine import ProfessionalGamerSimilarityEngine
from backend.services.reference_governance_service import ProfessionalReferenceRepository
from backend.services.style_evolution_engine import StyleEvolutionEngine
from backend.services.style_squad_training_bridge import (
    EliteTrainingPathwayService,
    PlayingStyleSandbox,
    StyleAwareRecommendationService,
)


router = APIRouter(
    prefix="/api/phase44",
    tags=["phase44-gamer-dna"],
    dependencies=[Depends(rate_limit_default)],
)


def _gv(v: Optional[str]) -> str:
    return "FC26" if str(v or "FC27").upper() == "FC26" else "FC27"


@router.get("/health")
def phase44_health() -> Dict[str, Any]:
    ref_repo = ProfessionalReferenceRepository(get_phase44_repository())
    manifest = ref_repo.get_manifest()
    return {
        "status": "OK",
        "phase": "44",
        "feature_count": len(FEATURE_CATALOG_V2),
        "style_feature_count": sum(1 for v in FEATURE_CATALOG_V2.values() if not v["is_proficiency_only"]),
        "proficiency_feature_count": sum(1 for v in FEATURE_CATALOG_V2.values() if v["is_proficiency_only"]),
        "archetype_count": len(ARCHETYPES_V2),
        "pro_comparison_enabled": manifest["authorized_profile_count"] > 0,
        "reference_manifest": manifest,
        "frozen_v321_preserved": True,
    }


@router.get("/profile")
def get_gamer_dna_v2_profile(
    game_version: str = Query("FC27", max_length=10),
    game_patch: str = Query("ALL", max_length=32),
    gameplay_mode: str = Query("ALL", max_length=40),
    persist: bool = Query(True),
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    gv = _gv(game_version)
    p40 = get_phase40_repository()
    p41 = get_phase41_repository()
    p43 = get_phase43_repository()
    p44 = get_phase44_repository()
    matches = p40.list_matches(user.id, game_version=gv, exclude_synthetic=True, limit=60)
    fps = p43.list_fingerprints(user.id, limit=30)
    wins = p41.list_decision_windows(user.id, exclude_synthetic=True, limit=80)
    cold = p40.get_cold_start_preferences(user.id)

    prof = GamerDNAV2Engine().build_profile(
        user.id,
        matches,
        game_version=gv,
        game_patch=game_patch,
        gameplay_mode=gameplay_mode,
        fingerprints=fps,
        decision_windows=wins,
        cold_start=cold,
    )
    if persist:
        p44.save_gamer_profile(prof)
    return prof.model_dump(mode="json")


@router.get("/profiles/history")
def list_gamer_dna_history(
    game_version: Optional[str] = Query(None, max_length=10),
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    p44 = get_phase44_repository()
    gv = _gv(game_version) if game_version else None
    items = p44.list_gamer_profiles(user.id, game_version=gv, limit=15)
    return {"count": len(items), "profiles": [x.model_dump(mode="json") for x in items]}


@router.get("/archetypes")
def get_style_archetypes(
    game_version: str = Query("FC27", max_length=10),
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    gv = _gv(game_version)
    p40 = get_phase40_repository()
    matches = p40.list_matches(user.id, game_version=gv, exclude_synthetic=True, limit=50)
    cold = p40.get_cold_start_preferences(user.id)
    prof = GamerDNAV2Engine().build_profile(user.id, matches, game_version=gv, cold_start=cold)
    return {
        "game_version": gv,
        "eligible_match_count": prof.eligible_match_count,
        "archetype": prof.archetype.model_dump(mode="json"),
        "taxonomy": [{"name": k, "summary": v[1], "anchor_features": list(v[0].keys())} for k, v in ARCHETYPES_V2.items()],
    }


@router.get("/references")
def list_pro_references(user: CurrentUser = Depends(current_user_required)) -> Dict[str, Any]:
    _ = user
    ref_repo = ProfessionalReferenceRepository(get_phase44_repository())
    cands = ref_repo.list_candidates()
    return {
        "manifest": ref_repo.get_manifest(),
        "candidates": [c.model_dump(mode="json") for c in cands],
    }


@router.post("/references/{reference_id}/revoke")
def revoke_pro_reference_rights(
    reference_id: str,
    reason: str = Query("Rights revoked", max_length=200),
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    settings = get_settings()
    if settings.environment not in ("local", "test", "development") and user.role != "admin":
        raise HTTPException(status_code=403, detail="Reference rights administration requires local/admin authorization.")
    ref_repo = ProfessionalReferenceRepository(get_phase44_repository())
    updated = ref_repo.revoke_rights(reference_id, reason=reason)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Reference {reference_id!r} not found.")
    return {"revoked": True, "reference": updated.model_dump(mode="json")}


@router.get("/similarity")
def get_pro_style_similarity(
    game_version: str = Query("FC27", max_length=10),
    game_patch: str = Query("ALL", max_length=32),
    top_n: int = Query(5, ge=1, le=10),
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    gv = _gv(game_version)
    p40 = get_phase40_repository()
    p44 = get_phase44_repository()
    matches = p40.list_matches(user.id, game_version=gv, exclude_synthetic=True, limit=60)
    cold = p40.get_cold_start_preferences(user.id)
    prof = GamerDNAV2Engine().build_profile(user.id, matches, game_version=gv, game_patch=game_patch, cold_start=cold)
    p44.save_gamer_profile(prof)
    rep = ProfessionalGamerSimilarityEngine(ProfessionalReferenceRepository(p44)).compare(
        prof, user_matches=matches, top_n=top_n
    )
    p44.save_similarity_run(rep)
    return rep.model_dump(mode="json")


@router.get("/skill-gap")
def get_elite_skill_gap(
    game_version: str = Query("FC27", max_length=10),
    game_patch: str = Query("ALL", max_length=32),
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    gv = _gv(game_version)
    p40 = get_phase40_repository()
    p41 = get_phase41_repository()
    matches = p40.list_matches(user.id, game_version=gv, exclude_synthetic=True, limit=60)
    wins = p41.list_decision_windows(user.id, exclude_synthetic=True, limit=80)
    cold = p40.get_cold_start_preferences(user.id)
    prof = GamerDNAV2Engine().build_profile(
        user.id, matches, game_version=gv, game_patch=game_patch, decision_windows=wins, cold_start=cold
    )
    return EliteSkillGapEngine().analyze(prof).model_dump(mode="json")


@router.get("/evolution")
def get_style_evolution(
    game_version: str = Query("FC27", max_length=10),
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    gv = _gv(game_version)
    p40 = get_phase40_repository()
    p43 = get_phase43_repository()
    matches = p40.list_matches(user.id, game_version=gv, exclude_synthetic=True, limit=80)
    exps = p43.list_experiments(user.id, game_version=gv, limit=20)
    return StyleEvolutionEngine().analyze(user.id, matches, game_version=gv, experiments=exps).model_dump(mode="json")


@router.get("/recommendations/players")
def recommend_style_players(
    game_version: str = Query("FC27", max_length=10),
    position: str = Query("CM", max_length=8),
    mode: str = Query("SUPPORT_NATURAL_STYLE", max_length=40),
    limit: int = Query(6, ge=1, le=10),
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    return StyleAwareRecommendationService().recommend_players(
        user.id, game_version=_gv(game_version), position=position, mode=mode, limit=limit
    )


@router.get("/recommendations/formations")
def recommend_style_formations(
    game_version: str = Query("FC27", max_length=10),
    game_patch: str = Query("PATCH_1.04", max_length=32),
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    return StyleAwareRecommendationService().recommend_formations(
        user.id, game_version=_gv(game_version), game_patch=game_patch
    )


@router.post("/sandbox/preview")
def preview_style_sandbox(
    body: StyleSandboxRequest,
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    return PlayingStyleSandbox().preview(user.id, body)


@router.get("/training-pathway")
def get_elite_training_pathway(
    game_version: str = Query("FC27", max_length=10),
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    return EliteTrainingPathwayService().build_pathway(user.id, game_version=_gv(game_version))


@router.post("/feedback", status_code=201)
def record_style_feedback(
    body: StyleRecommendationFeedbackCreate,
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    rec = StyleRecommendationFeedbackRecord(user_id=user.id, **body.model_dump())
    saved = get_phase44_repository().save_feedback(rec)
    return saved.model_dump(mode="json")


@router.get("/feedback")
def list_style_feedback(
    game_version: Optional[str] = Query(None, max_length=10),
    user: CurrentUser = Depends(current_user_required),
) -> Dict[str, Any]:
    gv = _gv(game_version) if game_version else None
    items = get_phase44_repository().list_feedback(user.id, game_version=gv, limit=40)
    return {"count": len(items), "items": [x.model_dump(mode="json") for x in items]}


@router.post("/reset")
def reset_gamer_phase44_data(user: CurrentUser = Depends(current_user_required)) -> Dict[str, Any]:
    counts = get_phase44_repository().reset_user_phase44_data(user.id)
    return {"reset": True, **counts}
