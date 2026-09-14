"""Squad builder endpoints (§33): squads, slots, evaluation, replacements.

Ownership: every operation is scoped to the authenticated user. Chemistry is
never fabricated — squad evaluation surfaces verified link facts and returns
team_fit=INSUFFICIENT_EVIDENCE until version rules are verified (§22).
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import CurrentUser, current_user_required, rate_limit_default
from backend.api.routes.meta import FORMATIONS
from backend.api.routes.recommendations import get_service
from backend.api.schemas import (
    RecommendationRequest, SlotAssign, SquadCreate, SquadReplaceRequest, SquadUpdate,
)
from backend.repositories.player_repository import PlayerRepository
from backend.repositories.squad_repository import SquadRepository
from backend.services.team_context import TeamContextService

router = APIRouter(prefix="/api/squads", tags=["squads"],
                   dependencies=[Depends(rate_limit_default)])
squads = SquadRepository()
players = PlayerRepository()


def _json_safe(o):
    from datetime import date, datetime
    if isinstance(o, dict):
        return {k: _json_safe(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_json_safe(v) for v in o]
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, uuid.UUID):
        return str(o)
    return o


def _gv_id_or_404(code: str) -> uuid.UUID:
    gvid = players.game_version_id(code.upper())
    if gvid is None:
        raise HTTPException(404, f"game_version {code} not registered")
    return gvid


@router.post("", status_code=201)
def create_squad(body: SquadCreate, user: CurrentUser = Depends(current_user_required)):
    from backend.api.deps import validate_game_version
    gv = validate_game_version(body.game_version)
    if body.formation.upper() not in FORMATIONS:
        raise HTTPException(422, f"Unknown formation {body.formation!r}. "
                                 f"Known: {sorted(FORMATIONS)}")
    try:
        squad = squads.create_squad(uuid.UUID(user.id), body.name,
                                    body.formation, _gv_id_or_404(gv), body.tactics)
    except Exception as e:
        if "duplicate key" in str(e):
            raise HTTPException(409, "You already have a squad with that name.")
        raise
    return _json_safe(squad)


@router.get("")
def list_squads(user: CurrentUser = Depends(current_user_required)):
    return _json_safe(squads.list_squads(uuid.UUID(user.id)))


@router.get("/{squad_id}")
def get_squad(squad_id: uuid.UUID, user: CurrentUser = Depends(current_user_required)):
    squad = squads.get_squad(uuid.UUID(user.id), squad_id)
    if squad is None:
        raise HTTPException(404, "Squad not found (or not owned by you).")
    return _json_safe({**squad, "slots": squads.slots(squad_id, uuid.UUID(user.id))})


@router.patch("/{squad_id}")
def update_squad(squad_id: uuid.UUID, body: SquadUpdate,
                 user: CurrentUser = Depends(current_user_required)):
    if squads.get_squad(uuid.UUID(user.id), squad_id) is None:
        raise HTTPException(404, "Squad not found (or not owned by you).")
    if body.formation and body.formation.upper() not in FORMATIONS:
        raise HTTPException(422, f"Unknown formation {body.formation!r}")
    squads.rename_squad(uuid.UUID(user.id), squad_id, body.name, body.formation,
                        body.tactics)
    return get_squad(squad_id, user)


@router.delete("/{squad_id}", status_code=204)
def delete_squad(squad_id: uuid.UUID, user: CurrentUser = Depends(current_user_required)):
    if squads.delete_squad(uuid.UUID(user.id), squad_id) == 0:
        raise HTTPException(404, "Squad not found (or not owned by you).")


@router.put("/{squad_id}/slots/{slot_index}")
def assign_slot(squad_id: uuid.UUID, slot_index: int, body: SlotAssign,
                user: CurrentUser = Depends(current_user_required)):
    squad = squads.get_squad(uuid.UUID(user.id), squad_id)
    if squad is None:
        raise HTTPException(404, "Squad not found (or not owned by you).")
    if body.slot_index != slot_index:
        raise HTTPException(422, "slot_index mismatch")
    layout = FORMATIONS.get(squad["formation"], [])
    if slot_index >= len(layout):
        raise HTTPException(422, f"formation {squad['formation']} has {len(layout)} slots")
    if body.slot_position != layout[slot_index]:
        raise HTTPException(422, f"slot {slot_index} of {squad['formation']} is "
                                 f"{layout[slot_index]}, not {body.slot_position}")
    if body.game_player_id:
        page = players.player_page(squad["game_version_id"], body.game_player_id)
        if page is None:
            raise HTTPException(404, "Player not found in this squad's game version "
                                     "(versions are never mixed).")
    if body.ut_card_id:
        from backend.repositories.player_repository import PlayerRepository
        if PlayerRepository().card_page(squad["game_version_id"], body.ut_card_id) is None:
            raise HTTPException(404, "Card not found in this squad's game version.")
    squads.assign_slot(squad_id, uuid.UUID(user.id), slot_index, body.slot_position,
                       body.game_player_id, body.ut_card_id)
    return get_squad(squad_id, user)


@router.delete("/{squad_id}/slots/{slot_index}")
def clear_slot(squad_id: uuid.UUID, slot_index: int,
               user: CurrentUser = Depends(current_user_required)):
    if squads.get_squad(uuid.UUID(user.id), squad_id) is None:
        raise HTTPException(404, "Squad not found (or not owned by you).")
    squads.clear_slot(squad_id, uuid.UUID(user.id), slot_index)
    return get_squad(squad_id, user)


@router.get("/{squad_id}/evaluation")
def evaluate_squad(squad_id: uuid.UUID,
                   user: CurrentUser = Depends(current_user_required)):
    """Squad summary with VERIFIED link facts. Chemistry itself stays
    INSUFFICIENT_EVIDENCE until version rules are verified — never faked."""
    ctx = squads.squad_context(uuid.UUID(user.id), squad_id)
    if ctx is None:
        raise HTTPException(404, "Squad not found (or not owned by you).")
    link = TeamContextService.link_summary(ctx)
    filled = ctx.filled_slots()
    position_matches = []
    layout = FORMATIONS.get(ctx.formation, [])
    slot_rows = squads.slots(squad_id, uuid.UUID(user.id))
    for s in slot_rows:
        expected = layout[s["slot_index"]] if s["slot_index"] < len(layout) else None
        position_matches.append({
            "slot_index": s["slot_index"],
            "expected_position": expected,
            "player": s.get("player_name"),
            "player_position": s.get("position_primary"),
            "out_of_position": bool(expected and s.get("position_primary")
                                    and s["position_primary"] != expected),
        })
    return {
        "squad_id": str(squad_id),
        "formation": ctx.formation,
        "game_version": ctx.game_version,
        "links": link,
        "slots": _json_safe(slot_rows),
        "position_checks": position_matches,
        "chemistry": {
            "status": "INSUFFICIENT_EVIDENCE",
            "reason": (f"{ctx.game_version} chemistry rules are not verified in this "
                       "system; link facts above are real, but a chemistry SCORE "
                       "would be fabricated (§22)."),
        },
    }


@router.post("/{squad_id}/recommend-replacement")
def recommend_replacement(squad_id: uuid.UUID, body: SquadReplaceRequest,
                          user: CurrentUser = Depends(current_user_required)):
    """Recommendation for one slot, using the rest of the squad as context."""
    squad = squads.get_squad(uuid.UUID(user.id), squad_id)
    if squad is None:
        raise HTTPException(404, "Squad not found (or not owned by you).")
    layout = FORMATIONS.get(squad["formation"], [])
    if body.slot_index >= len(layout):
        raise HTTPException(422, f"formation {squad['formation']} has {len(layout)} slots")
    position = layout[body.slot_index]

    if body.recommendation:
        req_in = body.recommendation
        if req_in.game_version.upper() != squad["game_version_code"]:
            raise HTTPException(422, "recommendation.game_version must match the "
                                     "squad's version — never mixed")
    else:
        req_in = RecommendationRequest(game_version=squad["game_version_code"])
    req = req_in.to_requirements()
    req.position = position
    req.squad_id = squad_id

    ctx = squads.squad_context(uuid.UUID(user.id), squad_id)
    result = get_service().recommend(req, squad_ctx=ctx)
    result["slot"] = {"slot_index": body.slot_index, "slot_position": position}
    return result
