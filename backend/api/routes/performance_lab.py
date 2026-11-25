"""Local-only FC27 cohort, voluntary evidence intake, review, and model comparison."""
from collections import Counter
from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from backend.api.deps import admin_required, current_user_required, rate_limit_default
from backend.api.routes.recommendations import _raise_v3_error, _validate_v3
from backend.api.routes.research_cards import LocalRequest, research_service
from backend.core import db
from backend.core.config import get_settings
from backend.services.fc27_card_research import ResearchCards, SNAPSHOT
from backend.services.formations import FORMATION_SLOTS
from backend.services.performance_cohort import COHORT_VERSION, load_cohort
from backend.services.performance_evidence import (
    Context, EvidenceIn, Metric, Note, compare_observed, official_rating_checks, opinion_summary, patch_status,
    reported_matches, sources,
)

router = APIRouter(prefix="/api/research/fc27/performance", tags=["FC27 performance evidence"],
                   dependencies=[Depends(rate_limit_default)])
BASE = """
    SELECT e.*, r.disposition, r.reviewed_at, r.reason
    FROM fc27_staging.performance_evidence AS e
    LEFT JOIN fc27_staging.performance_evidence_review AS r ON r.evidence_id=e.id
    WHERE e.snapshot_id=%s AND e.cohort_version=%s
"""
SCOPE = SNAPSHOT, COHORT_VERSION


def cohort():
    try:
        return load_cohort(get_settings().database_url)
    except (ValueError, KeyError) as exc:
        raise HTTPException(503, "The pinned research cohort could not be reproduced.") from exc


def selected_item(item_id):
    return selected_items([item_id])[0]


def selected_items(item_ids):
    _, items = cohort()
    by_id = {item["card_item_id"]: item for item in items}
    try:
        return [by_id[str(item_id)] for item_id in item_ids]
    except KeyError as exc:
        raise HTTPException(404, "This item is outside the selected FC27 research cohort.") from exc


def reviewed_rows(item_ids=None):
    condition = " AND r.disposition='ACCEPTED' AND e.share_for_research"
    params = SCOPE
    if item_ids is not None:
        condition += " AND e.card_item_id=ANY(%s::uuid[])"
        params += (item_ids,)
    return db.query(BASE + condition + " ORDER BY e.created_at,e.id", params)


def view(row, target_patch=None, private=False):
    payload = row["payload"]
    result = {
        "id": row["id"], "schema_version": row["schema_version"], "card_item_id": row["card_item_id"],
        "observation_type": row["evidence_kind"], "source_key": row["source_key"],
        "source_url": payload["source_url"], "source_author": payload["source_author"],
        "source_date": payload["source_date"], "context": payload["context"],
        "topic": payload["topic"], "stance": payload["stance"], "note": payload["note"],
        "review_status": row["disposition"] or "PENDING", "submitted_on": row["created_at"],
        "provenance_status": ("REVIEWED_SUBMISSION" if row["disposition"] == "ACCEPTED"
                              else "SUBMITTER_ATTESTED"),
        "reviewed_on": row["reviewed_at"],
        "patch_compatibility": patch_status(payload["context"]["game_patch"], target_patch),
    }
    match = payload["match"]
    result["match"] = {key: match[key] for key in ("match_date", "minutes", "metrics")} if match else None
    if match:
        result["data_completeness"] = {"minutes_reported": match["minutes"] is not None,
                                       "metrics_reported": sorted(key for key, value in match["metrics"].items() if value is not None)}
    if private:
        result.update(payload=payload, review_reason=row["reason"])
    return result


@router.get("")
def index(include_research_data: Literal["true"], service=Depends(research_service)):
    manifest, items = cohort()
    rows = reviewed_rows()
    observations, conflicts = reported_matches(rows)
    evidence_counts = Counter(str(row["card_item_id"]) for row in rows if row["payload"]["match"] is None)
    match_counts = Counter(str(row["card_item_id"]) for row in observations)
    dispute_counts = Counter(row["card_item_id"] for row in conflicts)
    return {"research_only": True, "manifest": manifest,
            "cards": [{key: item[key] for key in ("cohort", "rank", "name", "card_item_id", "source_item_id",
                                                  "overall", "primary_position", "positions", "identity_status")}
                      | {"reviewed_match_count": match_counts[item["card_item_id"]],
                         "reviewed_note_count": evidence_counts[item["card_item_id"]],
                         "disputed_matches": dispute_counts[item["card_item_id"]]} for item in items],
            "sources": list(sources().values()), "formations": {
                name: [{"slot": slot.slot, "position": slot.position} for slot in slots]
                for name, slots in FORMATION_SLOTS.items()}}


@router.get("/items/{card_id}")
def item_evidence(card_id: UUID, include_research_data: Literal["true"], patch: str | None = None,
                  service=Depends(research_service)):
    item = selected_item(card_id)
    rows = reviewed_rows([card_id])
    compatible = [row for row in rows if not patch or row["payload"]["context"]["game_patch"] == patch]
    observed, disputed = reported_matches(rows)
    observed = [row for row in observed if not patch or row["payload"]["context"]["game_patch"] == patch]
    today = date.today()
    visible = []
    for row in rows:
        result = view(row, patch)
        dated = result["match"]["match_date"] if result["match"] else result["source_date"]
        result["age_days"] = (today - date.fromisoformat(dated)).days if dated else None
        visible.append(result)
    return {"card": item, "reviewed_evidence": visible, "opinion_groups": opinion_summary(compatible),
            "official_ratings_reference": official_rating_checks().get(item["source_item_id"]),
            "compatible_match_count": len(observed), "disputes": disputed,
            "discovery_queries": [f'FC27 "{item["name"]}" "{item["primary_position"]}" {term}'
                                  for term in ("gold base item", "role and PlayStyles", "match review and patch", "controlled card comparison")]}


class Intake(BaseModel):
    model_config = ConfigDict(extra="forbid")
    include_research_data: Literal[True]
    records: list[EvidenceIn] = Field(min_length=1, max_length=50)


@router.post("/submissions", status_code=201)
def submit(body: Intake, service=Depends(research_service), user=Depends(current_user_required)):
    items = selected_items([entry.card_item_id for entry in body.records])
    ids = []
    with db.get_conn() as conn:
        for item, entry in zip(items, body.records):
            if entry.observation_type in {"OFFICIAL_GAME_MECHANIC", "OFFICIAL_CARD_ATTRIBUTE", "OWNER_RECORDED_MATCH"} and user.role != "admin":
                raise HTTPException(403, "Only a research administrator can classify this source.")
            if entry.context.position and entry.context.position not in item["positions"]:
                raise HTTPException(422, "This position is outside the card's published positions.")
            if entry.context.position and (entry.context.position == "GK") != (item["primary_position"] == "GK"):
                raise HTTPException(422, "Goalkeeper and outfield card evidence must be recorded separately.")
            payload = entry.model_dump(mode="json")
            result = conn.execute("""
                INSERT INTO fc27_staging.performance_evidence
                    (owner_id,snapshot_id,source_item_id,cohort_version,card_item_id,schema_version,
                     fingerprint,evidence_kind,source_key,payload,share_for_research)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(owner_id,cohort_version,fingerprint) DO NOTHING RETURNING id
            """, (user.id, SNAPSHOT, item["source_item_id"], COHORT_VERSION, entry.card_item_id,
                  entry.schema_version, entry.fingerprint(), entry.observation_type, entry.source_key,
                  Jsonb(payload), entry.share_for_research)).fetchone()
            if result is None:
                result = conn.execute("""
                    SELECT id,payload FROM fc27_staging.performance_evidence
                    WHERE owner_id=%s AND cohort_version=%s AND fingerprint=%s
                """, (user.id, COHORT_VERSION, entry.fingerprint())).fetchone()
                if result["payload"] != payload:
                    raise HTTPException(409, "A conflicting or duplicate submission already uses this match key or claim.")
            ids.append(result["id"])
    return {"ids": ids, "review_status": "SUBMITTED"}


@router.get("/submissions")
def submissions(include_research_data: Literal["true"], service=Depends(research_service), user=Depends(current_user_required)):
    rows = db.query(BASE + " AND e.owner_id=%s ORDER BY e.created_at DESC,e.id LIMIT 100", (*SCOPE, user.id))
    return {"items": [view(row, private=True) for row in rows]}


@router.get("/review")
def review_queue(include_research_data: Literal["true"], service=Depends(research_service), user=Depends(admin_required)):
    rows = db.query(BASE + " AND e.share_for_research AND r.disposition IS NULL ORDER BY e.created_at,e.id LIMIT 100", SCOPE)
    return {"items": [view(row, private=True) for row in rows]}


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    include_research_data: Literal[True]
    decision: Literal["ACCEPTED", "REJECTED", "WITHDRAWN"]
    reason: Note = Field(max_length=500)


@router.post("/review/{record_id}")
def review(record_id: UUID, body: Decision, service=Depends(research_service), user=Depends(current_user_required)):
    withdrawing = body.decision == "WITHDRAWN"
    if not withdrawing and user.role != "admin":
        raise HTTPException(403, "Only a research administrator can review evidence.")
    with db.get_conn() as conn:
        row = conn.execute("""
            SELECT owner_id,share_for_research,evidence_kind FROM fc27_staging.performance_evidence
            WHERE id=%s AND snapshot_id=%s AND cohort_version=%s FOR UPDATE
        """, (record_id, *SCOPE)).fetchone()
        if not row or (withdrawing and str(row["owner_id"]) != user.id) or (not withdrawing and not row["share_for_research"]):
            raise HTTPException(404, "Evidence is unavailable for this action.")
        if (body.decision == "ACCEPTED" and row["evidence_kind"] == "CONTROLLED_EXPERIMENT"
                and str(row["owner_id"]) == user.id):
            raise HTTPException(403, "Controlled evidence must be accepted by another reviewer.")
        decided = conn.execute("""
            INSERT INTO fc27_staging.performance_evidence_review AS r(evidence_id,reviewer_id,disposition,reason)
            VALUES (%s,%s,%s,%s)
            ON CONFLICT(evidence_id) DO UPDATE SET reviewer_id=EXCLUDED.reviewer_id,
                disposition=EXCLUDED.disposition,reason=EXCLUDED.reason,reviewed_at=now()
            WHERE EXCLUDED.disposition='WITHDRAWN' AND r.disposition!='WITHDRAWN'
            RETURNING disposition
        """, (record_id, user.id, body.decision, body.reason)).fetchone()
        if not decided:
            raise HTTPException(409, "This evidence already has a decision.")
    return {"review_status": decided["disposition"]}


class Comparison(BaseModel):
    model_config = ConfigDict(extra="forbid")
    game_version: Literal["FC27"]
    include_research_data: Literal[True]
    card_ids: tuple[UUID, UUID]
    context: Context
    metric: Metric


@router.post("/compare")
def comparison(body: Comparison, service=Depends(research_service)):
    if body.card_ids[0] == body.card_ids[1]:
        raise HTTPException(422, "Choose two distinct card items.")
    selected_items(body.card_ids)
    context = body.context
    request = LocalRequest(game_version="FC27", include_research_data=True, position=context.position or "",
                           formation=context.formation if context.slot else None, slot=context.slot,
                           tactical_profile=context.tactical_profile or "BALANCED", explain_top_n=2) if context.position else None
    if request is None:
        raise HTTPException(422, "Select a position for the model comparison.")
    _validate_v3(request)
    subset = ResearchCards(service.reference, [card for card in service.candidates if card.entity_id in body.card_ids])
    items = [str(item) for item in body.card_ids]
    prediction = subset.compare(request, items)
    _raise_v3_error(prediction)
    predicted = {str(row["entity_id"]): {"score": row["score"], "coverage": row["coverage"],
                                        "interval": row["score_interval"], "strengths": row["key_strengths"]}
                 for row in prediction["players"]}
    observed = compare_observed(reviewed_rows(list(body.card_ids)), items, body.metric, context.model_dump())
    agreement = None
    # V3.2 interval overlap and tie threshold determine whether the prediction distinguishes the cards.
    pair = prediction["pairwise"][0] if len(prediction["pairwise"]) == 1 else None
    delta = observed["paired_difference_per_90"]
    if pair and not pair["within_noise_threshold"] and not pair["intervals_overlap"] and delta not in (None, 0):
        agreement = "DIRECTION_AGREES" if (delta > 0) == (pair["higher"] == items[0]) else "DIRECTION_DIFFERS"
    return {"predictions": predicted, "model_scope": "POSITION_SLOT_AND_TACTIC",
            "model_dataset": prediction["dataset"], "model_request": prediction["request"],
            "model_pairwise": prediction["pairwise"], "observed": observed,
            "direction_agreement": agreement, "holdout_status": "UNEVALUATED_NO_FROZEN_HOLDOUT",
            "research_only": True}
