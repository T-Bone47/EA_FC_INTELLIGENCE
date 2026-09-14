"""Feedback capture (§34) + saved players.

Feedback rows are the future training data for a learning-to-rank stage —
which is deliberately NOT built yet (deterministic engine first).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import (
    CurrentUser, admin_required, current_user_required, rate_limit_default,
    validate_game_version,
)
from backend.api.schemas import FeedbackIn, SavePlayerIn
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
    gvid = players.game_version_id(gv)
    fid = feedback.record(
        user_id=uuid.UUID(user.id), game_version_id=gvid,
        action=body.action, entity_type=body.entity_type,
        entity_id=body.entity_id, request_context=body.request_context,
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
    items = squads.saved_players(uuid.UUID(user.id), gv)
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
    gvid = players.game_version_id(gv)
    if body.entity_type == "game_player":
        page = players.player_page(gvid, body.entity_id)
        if page is None:
            raise HTTPException(404, "Player not found in this game version.")
    else:
        page = players.card_page(gvid, body.entity_id)
        if page is None or page["card"].get("is_synthetic"):
            raise HTTPException(404, "Card not found in canonical production data.")
    squads.save_player(uuid.UUID(user.id), gvid, body.entity_type,
                       body.entity_id, body.note)
    return {"status": "saved", "entity_id": str(body.entity_id)}


@router.delete("/saved-players/{entity_id}", status_code=204)
def unsave_player(entity_id: uuid.UUID, entity_type: str = "game_player",
                  user: CurrentUser = Depends(current_user_required)) -> None:
    if squads.unsave_player(uuid.UUID(user.id), entity_type, entity_id) == 0:
        raise HTTPException(404, "Saved entry not found.")
