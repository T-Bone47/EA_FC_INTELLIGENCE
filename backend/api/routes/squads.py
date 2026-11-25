"""Squad builder endpoints (§33): squads, slots, evaluation, replacements.

Ownership: every operation is scoped to the authenticated user. Chemistry is
never fabricated — squad evaluation surfaces verified link facts and returns
team_fit=INSUFFICIENT_EVIDENCE until version rules are verified (§22).
"""
from __future__ import annotations

import uuid
import hashlib
import json
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, ValidationError
from psycopg.errors import UniqueViolation

from backend.api.deps import (
    CurrentUser, can_read_catalogue, current_user_required, fc27_research_requested, rate_limit_default,
    require_catalogue_release, require_legacy_research_environment,
)
from backend.api.routes.meta import FORMATIONS
from backend.api.routes.recommendations import _raise_v3_error, _validate_v3, get_service, get_service_v3
from backend.api.schemas_v3 import RecommendationRequestV3
from backend.services.formations import slots_for
from backend.services.formation_optimizer import optimal_assignments
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
def get_squad(squad_id: uuid.UUID, user: CurrentUser = Depends(current_user_required),
              include_research_data: bool = False):
    squad = squads.get_squad(uuid.UUID(user.id), squad_id)
    if squad is None:
        raise HTTPException(404, "Squad not found (or not owned by you).")
    version = squad["game_version_code"]
    player_visible = can_read_catalogue(version, "game_player")
    card_visible = can_read_catalogue(version, "ut_card")
    research = fc27_research_requested(version, include_research_data)
    rows = squads.slots(squad_id, uuid.UUID(user.id), research=research) if player_visible or card_visible else []
    slots = [row for row in rows if (row["ut_card_id"] is None or card_visible)
             and (row["game_player_id"] is None or player_visible)]
    return _json_safe({**squad, "slots": slots})


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


@router.delete("/{squad_id}", status_code=204, response_model=None)
def delete_squad(squad_id: uuid.UUID, user: CurrentUser = Depends(current_user_required)):
    if squads.delete_squad(uuid.UUID(user.id), squad_id) == 0:
        raise HTTPException(404, "Squad not found (or not owned by you).")


@router.put("/{squad_id}/slots/{slot_index}")
def assign_slot(squad_id: uuid.UUID, slot_index: int, body: SlotAssign,
                user: CurrentUser = Depends(current_user_required), include_research_data: bool = False):
    squad = squads.get_squad(uuid.UUID(user.id), squad_id)
    if squad is None:
        raise HTTPException(404, "Squad not found (or not owned by you).")
    if body.slot_index != slot_index:
        raise HTTPException(422, "slot_index mismatch")
    layout = FORMATIONS.get(squad["formation"], [])
    if not 0 <= slot_index < len(layout):
        raise HTTPException(422, f"formation {squad['formation']} has {len(layout)} slots")
    if body.slot_position != layout[slot_index]:
        raise HTTPException(422, f"slot {slot_index} of {squad['formation']} is "
                                 f"{layout[slot_index]}, not {body.slot_position}")
    research = fc27_research_requested(squad["game_version_code"], include_research_data)
    if body.game_player_id and body.ut_card_id:
        raise HTTPException(422, "Choose a player or a card for this slot.")
    if body.game_player_id:
        require_catalogue_release(squad["game_version_code"], "game_player")
        page = players.player_page(squad["game_version_id"], body.game_player_id, research=research,
                                   include_cards=False, include_other_versions=False)
        if page is None:
            raise HTTPException(404, "Player not found in this squad's game version "
                                     "(versions are never mixed).")
    if body.ut_card_id:
        if research:
            raise HTTPException(422, "FC27 research squads accept players only.")
        require_catalogue_release(squad["game_version_code"], "ut_card")
        if players.card_page(squad["game_version_id"], body.ut_card_id, include_player=False) is None:
            raise HTTPException(404, "Card not found in this squad's game version.")
    squads.assign_slot(squad_id, uuid.UUID(user.id), slot_index, body.slot_position,
                       body.game_player_id, body.ut_card_id)
    return get_squad(squad_id, user, include_research_data)


@router.delete("/{squad_id}/slots/{slot_index}")
def clear_slot(squad_id: uuid.UUID, slot_index: int,
               user: CurrentUser = Depends(current_user_required)):
    if squads.get_squad(uuid.UUID(user.id), squad_id) is None:
        raise HTTPException(404, "Squad not found (or not owned by you).")
    squads.clear_slot(squad_id, uuid.UUID(user.id), slot_index)
    return get_squad(squad_id, user)


def _tactical_request(squad, assignment, research: bool) -> RecommendationRequestV3:
    tactics = squad.get("tactics") or {}
    try:
        request = RecommendationRequestV3(
            game_version=squad["game_version_code"], position=assignment.position,
            formation=squad["formation"], slot=assignment.slot,
            tactical_profile=tactics.get("tactical_profile") or "BALANCED",
            secondary_tactical_profile=tactics.get("secondary_tactical_profile"),
            include_research_data=research, division=tactics.get("division"),
            limit=25, explain_top_n=2,
        )
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_context=False, include_input=False)) from exc
    _validate_v3(request)
    return request


@router.get("/{squad_id}/tactical-analysis")
def tactical_analysis(squad_id: uuid.UUID, include_research_data: bool = False,
                      user: CurrentUser = Depends(current_user_required)) -> dict:
    squad = get_squad(squad_id, user, include_research_data)
    require_catalogue_release(squad["game_version_code"], "game_player")
    service = get_service_v3()
    assigned = {row["slot_index"]: row for row in squad["slots"]}
    evaluated = []
    dataset = None
    for index, assignment in enumerate(slots_for(squad["formation"])):
        row = assigned.get(index, {})
        slot = {"slot_index": index, "slot": assignment.slot, "position": assignment.position,
                "status": "EMPTY", "player": row.get("player_name"), "entity_id": row.get("game_player_id"),
                "score": None, "coverage": None}
        if player_id := row.get("game_player_id"):
            result = service.compare(_tactical_request(squad, assignment, include_research_data), [player_id])
            _raise_v3_error(result)
            dataset = result["dataset"]
            if result["players"]:
                player = result["players"][0]
                slot.update(status="ASSESSED", score=player["score"], coverage=player["coverage"],
                            explanation=player["explanation"])
            else:
                slot["status"] = "INELIGIBLE_OR_UNAVAILABLE"
        elif row.get("ut_card_id"):
            slot["status"] = "CARD_REFERENCE_UNAVAILABLE"
        evaluated.append(slot)
    strengths = sorted((row for row in evaluated if row["score"] is not None),
                       key=lambda row: (-row["score"], row["slot_index"]))
    weak = [row["slot"] for row in evaluated if row["status"] == "INELIGIBLE_OR_UNAVAILABLE"]
    weak.extend(row["slot"] for row in strengths[-2:] if len(strengths) > 2)
    return {"game_version": squad["game_version_code"], "formation": squad["formation"], "dataset": dataset,
            "slots": evaluated, "weak_slots": weak, "strong_slots": [row["slot"] for row in strengths[:2]],
            "chemistry": {"status": "UNAVAILABLE", "reason": "Verified chemistry inputs are unavailable."},
            "budget": {"status": "UNAVAILABLE", "reason": "Verified market observations are required."}}


@router.get("/{squad_id}/tactical-replacements/{slot_index}")
def tactical_replacements(squad_id: uuid.UUID, slot_index: int, include_research_data: bool = False,
                          user: CurrentUser = Depends(current_user_required)) -> dict:
    squad = get_squad(squad_id, user, include_research_data)
    require_catalogue_release(squad["game_version_code"], "game_player")
    slots = slots_for(squad["formation"])
    if not 0 <= slot_index < len(slots):
        raise HTTPException(422, "Choose a slot from this squad's formation.")
    request = _tactical_request(squad, slots[slot_index], include_research_data)
    service = get_service_v3()
    result = service.recommend(request)
    _raise_v3_error(result)
    occupied = {row["game_player_id"] for row in squad["slots"] if row["game_player_id"]}
    incumbent = next((row["game_player_id"] for row in squad["slots"] if row["slot_index"] == slot_index), None)
    baseline = None
    if incumbent:
        compared = service.compare(request, [incumbent])
        _raise_v3_error(compared)
        if compared["players"]:
            baseline = compared["players"][0]["score"]
    suggestions = [{**entry, "score_change": round(entry["score"] - baseline, 6) if baseline is not None else None}
                   for entry in result["ranked"] if entry["entity_id"] not in occupied
                   and (baseline is None or entry["score"] > baseline)]
    return {"request": result["request"], "dataset": result["dataset"], "ranked": suggestions[:8],
            "incumbent_score": baseline}


@router.get("/{squad_id}/optimal-lineup")
def optimal_lineup(squad_id: uuid.UUID, pool: Literal["squad", "catalogue"] = "squad",
                   include_research_data: bool = False, user: CurrentUser = Depends(current_user_required)):
    squad = get_squad(squad_id, user, include_research_data)
    require_catalogue_release(squad["game_version_code"], "game_player")
    assignments = slots_for(squad["formation"])
    roster = sorted({row["game_player_id"] for row in squad["slots"] if row.get("game_player_id")})
    service = get_service_v3()
    options = []
    dataset = None
    for slot in assignments:
        request = _tactical_request(squad, slot, include_research_data)
        if pool == "catalogue":
            result = service.recommend(request.model_copy(update={"limit": len(assignments)}))
            _raise_v3_error(result)
            entries = result["ranked"]
        elif roster:
            result = service.compare(request, roster)
            _raise_v3_error(result)
            entries = result["players"]
        else:
            options.append([])
            continue
        dataset = result["dataset"]
        options.append([{k: row[k] for k in ("entity_id", "name", "score", "coverage", "explanation")} for row in entries])
    selected = optimal_assignments(options)
    rows = [{"slot_index": i, "slot": slot.slot, "position": slot.position, "player": entry}
            for i, (slot, entry) in enumerate(zip(assignments, selected))]
    plan = {"squad_id": str(squad_id), "game_version": squad["game_version_code"], "formation": squad["formation"],
            "tactics": squad.get("tactics") or {}, "pool": pool, "slots": rows, "dataset": dataset,
            "filled": sum(e is not None for e in selected),
            "total_fit": round(sum(e["score"] for e in selected if e), 10),
            "price_status": "UNAVAILABLE", "chemistry_status": "UNAVAILABLE"}
    # Only stable decision inputs belong in the receipt (explanation text can vary in tie order).
    signature = [plan["squad_id"], plan["formation"], plan["tactics"], pool, dataset, include_research_data,
                 [(e["entity_id"], e["score"]) if e else None for e in selected]]
    plan["receipt"] = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()
    return plan


class SaveLineup(BaseModel):
    name: str = Field(min_length=1, max_length=80, pattern=r"\S")
    pool: Literal["squad", "catalogue"]
    receipt: str = Field(pattern="^[0-9a-f]{64}$")


@router.post("/{squad_id}/optimal-lineup", status_code=201)
def save_optimal_lineup(squad_id: uuid.UUID, body: SaveLineup, include_research_data: bool = False,
                        user: CurrentUser = Depends(current_user_required)):
    plan = optimal_lineup(squad_id, body.pool, include_research_data, user)
    if plan["receipt"] != body.receipt or not plan["filled"]:
        raise HTTPException(409, "Refresh the lineup preview before saving.")
    try:
        new_id = squads.create_lineup_copy(user.id, body.name.strip(), _gv_id_or_404(plan["game_version"]), plan)
    except UniqueViolation as exc:
        raise HTTPException(409, "Choose another squad name.") from exc
    return {"id": str(new_id)}


@router.get("/{squad_id}/evaluation", dependencies=[Depends(require_legacy_research_environment)])
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


@router.post("/{squad_id}/recommend-replacement", dependencies=[Depends(require_legacy_research_environment)])
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
