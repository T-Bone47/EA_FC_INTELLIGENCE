"""Player search, player pages, card pages — production read surface.

Never loads the whole universe into the browser: server-side filtering,
pagination (max 100/page), trigram name search, indexed columns.
Synthetic data is excluded by the repository firewall.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.deps import (
    Pagination, can_read_catalogue, fc27_research_requested, is_production_like, pagination_params, rate_limit_default,
    require_catalogue_release,
    validate_game_version,
)
from backend.repositories.player_repository import PlayerRepository

router = APIRouter(prefix="/api", tags=["players"],
                   dependencies=[Depends(rate_limit_default)])
repo = PlayerRepository()


def _json_safe(obj):
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
        raise HTTPException(404, f"game_version {game_version} not registered")
    return gvid


@router.get("/players")
def search_players(
    game_version: str = Query("FC26"),
    include_research_data: bool = Query(False),
    q: Optional[str] = Query(default=None, max_length=80),
    position: Optional[str] = Query(default=None, max_length=5),
    club: Optional[str] = Query(default=None, max_length=80),
    nation: Optional[str] = Query(default=None, max_length=80),
    league: Optional[str] = Query(default=None, max_length=80),
    playstyle: Optional[str] = Query(default=None, max_length=60),
    ovr_min: Optional[int] = Query(default=None, ge=1, le=99),
    ovr_max: Optional[int] = Query(default=None, ge=1, le=99),
    sort: str = Query("overall_rating", max_length=20),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    pagination: Pagination = Depends(pagination_params),
) -> dict:
    gv = validate_game_version(game_version)
    require_catalogue_release(gv, "game_player")
    research = fc27_research_requested(gv, include_research_data)
    result = repo.search(
        _gv_id(gv), q=q, position=position.upper() if position else None,
        club=club, nation=nation, league=league,
        ovr_min=ovr_min, ovr_max=ovr_max, playstyle=playstyle,
        sort=sort, sort_dir=sort_dir,
        page=pagination.page, page_size=pagination.page_size, research=research)
    return {"game_version": gv, "research_only": research, **_json_safe(result)}


@router.get("/players/facets")
def facets(game_version: str = Query("FC26"), include_research_data: bool = Query(False)) -> dict:
    gv = validate_game_version(game_version)
    require_catalogue_release(gv, "game_player")
    research = fc27_research_requested(gv, include_research_data)
    return {"game_version": gv, **_json_safe(repo.facets(_gv_id(gv), research=research))}


@router.get("/players/{player_id}")
def player_page(player_id: uuid.UUID, game_version: str = Query("FC26"),
                include_research_data: bool = Query(False)) -> dict:
    gv = validate_game_version(game_version)
    require_catalogue_release(gv, "game_player")
    research = fc27_research_requested(gv, include_research_data)
    page = repo.player_page(_gv_id(gv), player_id, research=research,
                            include_cards=not research and can_read_catalogue(gv, "ut_card"),
                            include_other_versions=not research and not is_production_like())
    if page is None:
        raise HTTPException(404, "Player not found in this game version's "
                                 "canonical data (or excluded by the synthetic "
                                 "data firewall).")
    return _json_safe(page)


@router.get("/cards/{card_id}")
def card_page(card_id: uuid.UUID, game_version: str = Query("FC26")) -> dict:
    gv = validate_game_version(game_version)
    require_catalogue_release(gv, "ut_card")
    page = repo.card_page(_gv_id(gv), card_id, include_player=can_read_catalogue(gv, "game_player"))
    if page is None:
        raise HTTPException(404, "Card not found in this game version.")
    return _json_safe(page)
