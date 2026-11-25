"""Private saved card scenarios, signed item feedback and exact shortlist evaluations."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.api.deps import current_user_required, rate_limit_default
from backend.api.routes.research_cards import research_service, LocalComparison, compare
from backend.api.security import read_feedback_receipt
from backend.core import db
from backend.services.card_squad_lab import Profile, SquadPlan, evaluate, transform_formation
from backend.services.fc27_card_research import RELEASE, SNAPSHOT, ResearchCards, card_facts
from backend.services.recommendation_engine_v3 import ENGINE_VERSION
from backend.services.v3_config import DEFAULT_V3_CONFIG

router = APIRouter(prefix="/api/research/fc27/cards", tags=["local card research"],
                   dependencies=[Depends(rate_limit_default)])


@router.post("/squad/preview")
def preview(body: SquadPlan, service=Depends(research_service)):
    try:
        return evaluate(service, body)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


class Transformation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan: SquadPlan
    target: str = Field(max_length=12)
    use_shortlist: bool = False


@router.post("/squad/transform")
def transform(body: Transformation, service=Depends(research_service)):
    try:
        return transform_formation(service, body.plan, body.target, body.use_shortlist)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


class Save(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan: SquadPlan
    receipt: str = Field(pattern=r"^[0-9a-f]{64}$")
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def strip_name(cls, name):
        if not name.strip():
            raise ValueError("Name your squad.")
        return name.strip()


@router.post("/squad/saved", status_code=201)
def save(body: Save, service=Depends(research_service), user=Depends(current_user_required)):
    result = preview(body.plan, service)
    if result["receipt"] != body.receipt:
        raise HTTPException(409, "Squad settings or evidence changed. Preview the squad again.")
    return db.query_one("""INSERT INTO fc27_staging.card_squad(owner_id,snapshot_id,release_id,name,receipt,plan)
                           VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT(owner_id,release_id,receipt,name)
                           DO UPDATE SET name=EXCLUDED.name RETURNING id,name""",
                        (user.id, SNAPSHOT, RELEASE, body.name, body.receipt, Jsonb(body.plan.model_dump(mode="json"))))


@router.get("/squad/saved")
def saved(include_research_data: Literal["true"], service=Depends(research_service), user=Depends(current_user_required)):
    return {"items": db.query("""SELECT id,name FROM fc27_staging.card_squad WHERE owner_id=%s
                         AND snapshot_id=%s AND release_id=%s ORDER BY created_at DESC,id""", (user.id,SNAPSHOT,RELEASE))}


@router.get("/squad/saved/{squad_id}")
def reopen(squad_id: UUID, include_research_data: Literal["true"], service=Depends(research_service),
           user=Depends(current_user_required)):
    row = db.query_one("""SELECT id,name,plan FROM fc27_staging.card_squad WHERE id=%s AND owner_id=%s
                          AND snapshot_id=%s AND release_id=%s""", (squad_id,user.id,SNAPSHOT,RELEASE))
    if not row:
        raise HTTPException(404, "Saved research squad unavailable.")
    plan = SquadPlan.model_validate(row["plan"])
    row["preview"] = preview(plan, service)
    ids = set(plan.candidate_ids)
    row["items"] = [card_facts(c) for c in service.candidates if c.entity_id in ids]
    return row


class CardFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")
    include_research_data: Literal[True]
    receipt: str = Field(max_length=16000)
    recommendation_id: UUID
    card_item_id: UUID
    action: Literal["SELECTED","REJECTED","ALTERNATIVE_SELECTED","SAVED"]


@router.post("/feedback")
def feedback(body: CardFeedback, service=Depends(research_service), user=Depends(current_user_required)):
    signed = read_feedback_receipt(body.receipt, user.id)
    context = signed["context"] if signed else {}
    if (context.get("card_release_id") != RELEASE or context.get("reference_distribution_version") != service.reference.version
            or context.get("engine_version") != ENGINE_VERSION or context.get("config_version") != DEFAULT_V3_CONFIG.config_version
            or not context.get("tactical_context_hash") or signed.get("game_version") != "FC27"
            or signed.get("recommendation_id") != str(body.recommendation_id) or str(body.card_item_id) not in signed["entity_ids"]):
        raise HTTPException(422, "An active card receipt for this user, item and release is required.")
    card = next((c for c in service.candidates if c.entity_id == body.card_item_id), None)
    if not card:
        raise HTTPException(404, "Card unavailable.")
    row = db.query_one("""INSERT INTO fc27_staging.card_feedback
              (user_id,recommendation_id,item_id,snapshot_id,source_item_id,context,action) VALUES (%s,%s,%s,%s,%s,%s,%s)
              ON CONFLICT(user_id,recommendation_id,item_id) DO UPDATE SET action=EXCLUDED.action
              WHERE card_feedback.action=EXCLUDED.action RETURNING action""",
              (user.id,body.recommendation_id,body.card_item_id,SNAPSHOT,card.extra["source_item_id"],Jsonb(context),body.action))
    if not row:
        raise HTTPException(409, "A different response was already recorded for this item.")
    return {"status":"recorded", **row}


class MultiComparison(LocalComparison):
    profiles: list[Profile] = Field(min_length=1, max_length=6)


@router.post("/compare-tactics")
def compare_tactics(body: MultiComparison, service=Depends(research_service)):
    selected = set(body.card_ids)
    service = ResearchCards(service.reference, [c for c in service.candidates if c.entity_id in selected])
    if len(service.candidates) != len(selected):
        raise HTTPException(404, "An item is outside this research release.")
    outcomes = []
    for profile in dict.fromkeys(body.profiles):
        req = body.request.model_copy(update={"tactical_profile": profile})
        comparison = compare(LocalComparison(request=req, card_ids=body.card_ids), service)
        rows = comparison["players"]
        complete = len(rows) == len(body.card_ids)
        uncertain = not complete or any(p["within_noise_threshold"] or p["intervals_overlap"]
                                        for p in comparison["pairwise"] if p["higher"] == rows[0]["entity_id"])
        outcomes.append({"profile":profile,"scores":{r["entity_id"]:r["score"] for r in rows},
                         "leader":rows[0]["entity_id"] if rows and not uncertain else None,
                         "pairwise":comparison["pairwise"],"all_evaluable":complete})
    # Compare observed positions under the base tactic, without an assigned formation slot.
    positions = {}
    for position in sorted({p for c in service.candidates for p in (c.position_primary,*c.secondary_positions)}):
        req = body.request.model_copy(update={"position":position,"formation":None,"slot":None})
        evaluated = service.compare(req, [str(i) for i in body.card_ids])
        positions[position] = {r["entity_id"]:{"score":r["score"],"coverage":r["coverage"]}
                               for r in evaluated.get("players",[])}
    return {"research_only":True,"release_id":RELEASE,"outcomes":outcomes,"position_fits":positions,
            "clear_leads":{str(i):sum(o["leader"] == str(i) for o in outcomes) for i in body.card_ids},
            "tested_profiles":len(outcomes)}
