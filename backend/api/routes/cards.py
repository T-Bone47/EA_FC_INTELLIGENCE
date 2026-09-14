"""Card intelligence endpoints (Phase 3 §41 — additive only).

Conventions match the existing surface (players.py): /api prefix,
rate_limit_default dependency, validate_game_version, server-side filtering
with pagination (max 100/page). The card page itself already exists at
GET /api/cards/{card_id} in players.py — it is NOT duplicated here.

Card comparison goes through the existing POST /api/compare, which resolves
both players and canonical cards (§12) — no duplicate endpoint.
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.deps import (
    Pagination, pagination_params, rate_limit_default, validate_game_version,
)
from backend.repositories.player_repository import PlayerRepository
from backend.services import card_value_service

router = APIRouter(prefix="/api", tags=["cards"],
                   dependencies=[Depends(rate_limit_default)])
repo = PlayerRepository()


def _json_safe(obj):
    from datetime import date, datetime
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    return obj


def _gv_id(game_version: str) -> uuid.UUID:
    gvid = repo.game_version_id(game_version)
    if gvid is None:
        raise HTTPException(404, f"game version {game_version} not registered")
    return gvid


def _require_production_card(game_version: str, card_id: uuid.UUID) -> dict:
    page = repo.card_page(_gv_id(game_version), card_id)
    if page is None or (page.get("card") or {}).get("is_synthetic"):
        raise HTTPException(404, "Card not found in this game version's "
                                 "canonical data (synthetic test data is not "
                                 "exposed through production endpoints).")
    return page


@router.get("/cards")
def search_cards(
    game_version: str = Query("FC26"),
    q: Optional[str] = Query(default=None, max_length=80),
    position: Optional[str] = Query(default=None, max_length=5),
    rarity: Optional[str] = Query(default=None, max_length=40),
    card_type: Optional[str] = Query(default=None, max_length=40),
    playstyle: Optional[str] = Query(default=None, max_length=60),
    ovr_min: Optional[int] = Query(default=None, ge=1, le=99),
    ovr_max: Optional[int] = Query(default=None, ge=1, le=99),
    price_max: Optional[int] = Query(default=None, ge=0),
    sort: str = Query("overall_rating", max_length=20),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    pagination: Pagination = Depends(pagination_params),
) -> dict:
    gv = validate_game_version(game_version)
    result = repo.card_search(
        _gv_id(gv), q=q, position=position, rarity=rarity, card_type=card_type,
        playstyle=playstyle, ovr_min=ovr_min, ovr_max=ovr_max,
        price_max=price_max, sort=sort, sort_dir=sort_dir,
        page=pagination.page, page_size=pagination.page_size)
    return {"game_version": gv, **_json_safe(result)}


@router.get("/cards/{card_id}/versions")
def card_versions(card_id: uuid.UUID, game_version: str = Query("FC26")) -> dict:
    gv = validate_game_version(game_version)
    page = _require_production_card(gv, card_id)
    return {"game_version": gv, "card_id": str(card_id),
            "card_name": page["card"].get("card_name"),
            "versions": _json_safe(page.get("versions") or []),
            "note": ("version history reflects persisted card_version rows only "
                     "— upgrades are never inferred (§3/§8)")}


@router.get("/cards/{card_id}/prices")
def card_prices(card_id: uuid.UUID, game_version: str = Query("FC26"),
                limit: int = Query(100, ge=1, le=500)) -> dict:
    gv = validate_game_version(game_version)
    _require_production_card(gv, card_id)
    history = card_value_service.price_history(card_id, limit=limit)
    return {"game_version": gv, **_json_safe(history)}


@router.get("/cards/{card_id}/value")
def card_value(card_id: uuid.UUID, game_version: str = Query("FC26")) -> dict:
    """Price/budget facts for one card WITHOUT a user context.

    Value is contextual (§14): a real value score requires a recommendation
    request (POST /api/recommendations with entity_scope='ut_card'). This
    endpoint reports verified-price status and freshness only — it never
    invents a value number.
    """
    gv = validate_game_version(game_version)
    page = _require_production_card(gv, card_id)
    price = page.get("price")
    has_price = bool(price and price.get("price_coins") is not None)
    return {
        "game_version": gv,
        "card_id": str(card_id),
        "price_status": "VERIFIED_PRICE" if has_price else "PRICE_UNKNOWN",
        "latest_price": _json_safe(price) if has_price else None,
        "value_status": "REQUIRES_USER_CONTEXT",
        "note": ("value = marginal contextual utility per verified cost — "
                 "compute via POST /api/recommendations (entity_scope="
                 "'ut_card'); OVR/price is never used as value (§14)"),
    }


@router.get("/card-data-status")
def card_data_status(game_version: str = Query("FC26")) -> dict:
    """§44 data-quality surface: what card data exists — and what is NO_DATA."""
    gv = validate_game_version(game_version)
    return {"game_version": gv, **_json_safe(repo.card_data_status(_gv_id(gv)))}
