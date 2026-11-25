"""Explicit local access to the hash-pinned owner-supplied item release."""
import uuid
from typing import Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, field_validator

from backend.api.deps import current_user_optional, local_card_research_allowed, rate_limit_default
from backend.api.security import create_feedback_receipt
from backend.services.fc27_card_research import RELEASE, digest, validate_cached_membership
from backend.api.routes.recommendations import _raise_v3_error, _validate_v3
from backend.api.schemas_v3 import CardRecommendationRequest
from backend.core.config import get_settings
from backend.services.fc27_card_research import ResearchCards, card_facts, local_release, SNAPSHOT
from backend.services.v3_response_blocks import division_block
from backend.services.reference_distribution import ReferenceDistributionMismatch, ReferenceDistributionUnavailable
from backend.ingestion.fc27_source_evidence import name_key


class LocalRequest(CardRecommendationRequest):
    game_version: Literal["FC27"]
    include_research_data: Literal[True]


class LocalComparison(BaseModel):
    request: LocalRequest
    card_ids: list[uuid.UUID] = Field(min_length=2, max_length=5)

    @field_validator("card_ids")
    @classmethod
    def distinct(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Choose distinct item versions")
        return value


def research_service(request: Request, response: Response):
    settings = get_settings()
    if not local_card_research_allowed(request, settings):
        raise HTTPException(403, "Local FC27 card research is disabled here.")
    response.headers["Cache-Control"] = "private, no-store"
    try:
        validate_cached_membership()
        ref, pool = local_release(settings.database_url)
    except (OSError, ValueError, KeyError, ReferenceDistributionMismatch, ReferenceDistributionUnavailable, psycopg.Error) as exc:
        raise HTTPException(503, "The pinned FC27 item release is unavailable. Verify local staging and reference.") from exc
    return ResearchCards(ref, pool)


router = APIRouter(prefix="/api/research/fc27/cards", tags=["local card research"],
                   dependencies=[Depends(rate_limit_default)])


@router.get("")
def search(include_research_data: Literal["true"], q: str = Query("", max_length=80),
           offset: int = Query(0, ge=0), position: str | None = Query(None, max_length=3),
           rarity: str | None = Query(None, max_length=80),
           ovr_min: int | None = Query(None, ge=1, le=99),
           playstyle: str | None = Query(None, max_length=60), service=Depends(research_service)):
    key = name_key(q)
    style = name_key(playstyle or "")
    matches = [
        card for card in service.candidates
        if (key in name_key(card.name) or q.strip() == card.extra["source_item_id"])
        and (not position or position in (card.position_primary, *card.secondary_positions))
        and (not rarity or name_key(rarity) == name_key(card.rarity))
        and (ovr_min is None or (card.overall_rating is not None and card.overall_rating >= ovr_min))
        and (not style or card.playstyle_data_published and any(
            name_key(value) == style for value in (*card.playstyles_base, *card.playstyles_plus)
        ))
    ]
    return {"dataset": service.reference.version, "snapshot": SNAPSHOT, "research_only": True,
            "total": len(matches), "items": [card_facts(c) for c in matches[offset:offset+25]]}


@router.get("/items/{item_id}")
def detail(item_id: uuid.UUID, include_research_data: Literal["true"], service=Depends(research_service)):
    card = next((candidate for candidate in service.candidates if str(candidate.entity_id) == str(item_id)), None)
    if card is None:
        raise HTTPException(404, "An item is outside this research release.")
    return dict(card_facts(card), attributes=card.attributes.known())


@router.post("/recommendations")
def recommend(body: LocalRequest, service=Depends(research_service), user=Depends(current_user_optional)):
    _validate_v3(body)
    result = service.recommend(body)
    _raise_v3_error(result)
    # The explorer displays counts. Per-item exclusions belong on the explicit comparison.
    result.pop("excluded", None)
    result.pop("not_evaluable", None)
    result["division"] = division_block(None, (), applicable=False)
    if user:
        result["card_release_id"] = RELEASE
        result["tactical_context_hash"] = digest(body.model_dump(mode="json"))
        result["feedback_receipt"] = create_feedback_receipt(user.id, "FC27", result)
    return result


@router.post("/what-if")
def what_if(body: LocalRequest, tactical_profile: str = Query(max_length=30), service=Depends(research_service)):
    _validate_v3(body)
    variant = body.model_copy(update={"tactical_profile": tactical_profile.strip().upper(),
                                      "secondary_tactical_profile": None})
    _validate_v3(variant)
    result = service.what_if(body, [(variant.tactical_profile, {"tactical_profile": variant.tactical_profile,
                              "secondary_tactical_profile": None})], track_top=min(10, body.limit))
    _raise_v3_error(result)
    cards = {str(c.entity_id): c for c in service.candidates}
    for scenario in result["variants"]:
        for row in scenario.get("tracked_from_base", []):
            card = cards[row["entity_id"]]
            row["item_label"] = f"{card.name} · {card.rarity} · {card.extra['source_item_id']}"
    return result


@router.post("/compare")
def compare(body: LocalComparison, service=Depends(research_service)):
    _validate_v3(body.request)
    wanted = {str(i) for i in body.card_ids}
    items = {str(c.entity_id): c for c in service.candidates if str(c.entity_id) in wanted}
    if items.keys() != wanted:
        raise HTTPException(404, "An item is outside this research release.")
    result = service.compare(body.request, list(map(str, body.card_ids)))
    _raise_v3_error(result)
    result["cards"] = [dict(card_facts(items[str(i)]), attributes=items[str(i)].attributes.known())
                       for i in body.card_ids]
    result["outside_observed_position"] = result.pop("not_found")
    return result
