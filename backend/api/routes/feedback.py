"""Feedback capture (§34) + saved players.

Feedback rows are the future training data for a learning-to-rank stage —
which is deliberately NOT built yet (deterministic engine first).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response

from backend.api.deps import (
    CurrentUser, admin_required, can_read_catalogue, current_user_required, fc27_research_requested, rate_limit_default,
    require_catalogue_release,
    validate_game_version,
)
from backend.api.schemas import FeedbackIn, SavePlayerIn
from backend.api.security import read_feedback_receipt
from backend.core.config import get_settings
from backend.repositories.feedback_repository import FeedbackRepository
from backend.repositories.player_repository import PlayerRepository
from backend.repositories.squad_repository import SquadRepository

router = APIRouter(prefix="/api", tags=["feedback"],
                   dependencies=[Depends(rate_limit_default)])
feedback = FeedbackRepository()
squads = SquadRepository()
players = PlayerRepository()


@router.post("/feedback", status_code=201)
def record_feedback(body: FeedbackIn,
                    user: CurrentUser = Depends(current_user_required)) -> dict:
    gv = validate_game_version(body.game_version)
    context = {**body.request_context, "served_recommendation_verified": False}
    research = False
    if body.receipt is not None:
        signed = read_feedback_receipt(body.receipt, user.id)
        if (not signed or "card_release_id" in signed["context"] or signed["recommendation_id"] != body.recommendation_id or
                signed["game_version"] != gv or body.entity_type != "game_player" or
                str(body.entity_id) not in signed["entity_ids"]):
            raise HTTPException(422, "Feedback must match a recommendation served to this profile.")
        context = {**signed["context"], "served_recommendation_verified": True}
        research = fc27_research_requested(gv, context["research_only"])
    gvid = players.game_version_id(gv)
    if body.entity_id is not None:
        require_catalogue_release(gv, body.entity_type)
        if body.entity_type == "game_player":
            entity = players.player_page(gvid, body.entity_id, include_cards=False, include_other_versions=False, research=research)
        else:
            entity = players.card_page(gvid, body.entity_id, include_player=False)
        if entity is None:
            raise HTTPException(404, "Feedback entity is unavailable in this game version.")
    fid = feedback.record(
        user_id=uuid.UUID(user.id), game_version_id=gvid,
        action=body.action, entity_type=body.entity_type,
        entity_id=body.entity_id, request_context=context,
        recommendation_id=body.recommendation_id, reason=body.reason)
    return {"id": str(fid), "status": "recorded"}


@router.get("/feedback/stats")
def feedback_stats(_: CurrentUser = Depends(admin_required)) -> dict:
    return feedback.label_stats()


# ------------------------------------------------------------------ saved players
@router.get("/saved-players")
def list_saved(game_version: str | None = None,
               user: CurrentUser = Depends(current_user_required)) -> dict:
    gv = validate_game_version(game_version) if game_version else None
    from datetime import date, datetime
    versions = [gv] if gv else get_settings().supported_versions()
    scopes = {(code, scope) for code in versions for scope in ("game_player", "ut_card")
              if can_read_catalogue(code, scope)}
    if not scopes:
        return {"items": [], "total": 0}
    items = [it for it in squads.saved_players(uuid.UUID(user.id), gv)
             if (it["game_version"], it["entity_type"]) in scopes]
    for it in items:
        it["entity_id"] = str(it["entity_id"])
        it["id"] = str(it["id"])
        if isinstance(it.get("created_at"), (datetime, date)):
            it["created_at"] = it["created_at"].isoformat()
    return {"items": items, "total": len(items)}


@router.post("/saved-players", status_code=201)
def save_player(body: SavePlayerIn,
                user: CurrentUser = Depends(current_user_required)) -> dict:
    gv = validate_game_version(body.game_version)
    require_catalogue_release(gv, body.entity_type)
    gvid = players.game_version_id(gv)
    if body.entity_type == "game_player":
        page = players.player_page(gvid, body.entity_id, include_cards=False, include_other_versions=False)
        if page is None:
            raise HTTPException(404, "Player not found in this game version.")
    else:
        page = players.card_page(gvid, body.entity_id, include_player=False)
        if page is None:
            raise HTTPException(404, "Card not found in canonical production data.")
    squads.save_player(uuid.UUID(user.id), gvid, body.entity_type,
                       body.entity_id, body.note)
    return {"status": "saved", "entity_id": str(body.entity_id)}


@router.delete("/saved-players/{entity_id}", status_code=204, response_model=None)
def unsave_player(entity_id: uuid.UUID, entity_type: str = "game_player",
                  user: CurrentUser = Depends(current_user_required)) -> None:
    if squads.unsave_player(uuid.UUID(user.id), entity_type, entity_id) == 0:
        raise HTTPException(404, "Saved entry not found.")
