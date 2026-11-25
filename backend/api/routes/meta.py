"""Reference metadata: versions, positions, playstyles, tactics, formations.

Formations are a product/UI reference (slot layouts), not EA-published data —
clearly separated from provenance-backed game data. Everything game-specific
is read from version-aware reference tables.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from backend.api.availability import availability

from backend.api.deps import can_read_catalogue, fc27_research_requested, is_production_like, rate_limit_default, require_catalogue_release, validate_game_version
from backend.core.config import get_settings
from backend.core.db import catalogue_query as query, get_catalogue_conn
from backend.services.data_license_gate import Environment, environment_from_settings
from backend.services.archetypes import ARCHETYPE_DEFINITIONS
from backend.services.engine_config import ENGINE_VERSION, QUALITY_BANDS
from backend.services.formations import FORMATION_SLOTS, TACTICAL_DIMENSIONS
from backend.services.scoring_config import TACTICAL_ATTRIBUTE_WEIGHTS

router = APIRouter(prefix="/api/meta", tags=["meta"],
                   dependencies=[Depends(rate_limit_default)])

# Product-level formation reference (slot positions per formation).
FORMATIONS: dict[str, list[str]] = {
    "4-2-3-1": ["GK", "LB", "CB", "CB", "RB", "CDM", "CDM", "LM", "CAM", "RM", "ST"],
    "4-3-3": ["GK", "LB", "CB", "CB", "RB", "CM", "CM", "CM", "LW", "ST", "RW"],
    "4-4-2": ["GK", "LB", "CB", "CB", "RB", "LM", "CM", "CM", "RM", "ST", "ST"],
    "4-3-2-1": ["GK", "LB", "CB", "CB", "RB", "CM", "CM", "CM", "CAM", "CAM", "ST"],
    "4-5-1": ["GK", "LB", "CB", "CB", "RB", "LM", "CM", "CM", "CM", "RM", "ST"],
    "4-1-2-1-2": ["GK", "LB", "CB", "CB", "RB", "CDM", "CM", "CM", "CAM", "ST", "ST"],
    "3-5-2": ["GK", "CB", "CB", "CB", "LM", "CM", "CDM", "CM", "RM", "ST", "ST"],
    "3-4-2-1": ["GK", "CB", "CB", "CB", "LM", "CM", "CM", "RM", "CAM", "CAM", "ST"],
    "3-4-3": ["GK", "CB", "CB", "CB", "LM", "CM", "CM", "RM", "LW", "ST", "RW"],
    "5-3-2": ["GK", "LB", "CB", "CB", "CB", "RB", "CM", "CM", "CM", "ST", "ST"],
    "5-2-1-2": ["GK", "LB", "CB", "CB", "CB", "RB", "CDM", "CDM", "CAM", "ST", "ST"],
    "4-2-2-2": ["GK", "LB", "CB", "CB", "RB", "CDM", "CDM", "CAM", "CAM", "ST", "ST"],
}


@router.get("/game-versions")
def game_versions() -> list[dict]:
    if is_production_like():
        return [{"code": code, "display_name": code,
                 "status": "ACTIVE" if can_read_catalogue(code, "game_player") else "NO_DATA",
                 "released_on": None, "config": {}}
                for code in get_settings().supported_versions()]
    rows = query("""SELECT code, display_name, status, released_on, config
                    FROM game_version ORDER BY code""")
    for r in rows:
        r["released_on"] = r["released_on"].isoformat() if r["released_on"] else None
    return rows


@router.get("/availability")
def data_availability(request: Request, response: Response) -> dict:
    response.headers["Cache-Control"] = "private, no-store"
    return availability(request)


@router.get("/reference")
def reference(game_version: str = Query("FC26"), include_research_data: bool = Query(False)) -> dict:
    gv = validate_game_version(game_version)
    require_catalogue_release(gv, "game_player")
    research = fc27_research_requested(gv, include_research_data)
    rows = query("SELECT id, code, config, status FROM game_version WHERE code=%s", (gv,))
    if not rows:
        raise HTTPException(404, f"game_version {gv} not registered")
    cfg = rows[0]["config"] or {}
    data_status = "RESEARCH_ONLY" if research else "CANONICAL"
    with get_catalogue_conn(local_fc27_research=research) as conn:
        positions = cfg.get("positions", [])
        if research:
            positions = [row["position_primary"] for row in conn.execute(
                "SELECT DISTINCT position_primary FROM game_player WHERE game_version_id=%s "
                "AND data_status=%s AND position_primary IS NOT NULL ORDER BY position_primary",
                (rows[0]["id"], data_status)).fetchall()]
        playstyles = conn.execute(
            """SELECT pd.playstyle_name,
                      count(gp.id) FILTER (WHERE gpp.tier='plus')::int AS plus_holders,
                      count(gp.id)::int AS total_holders
               FROM playstyle_definition pd
               LEFT JOIN game_player_playstyle gpp ON gpp.playstyle_definition_id = pd.id
               LEFT JOIN game_player gp ON gp.id = gpp.game_player_id
                 AND gp.game_version_id = pd.game_version_id AND gp.data_status = pd.data_status
               WHERE pd.game_version_id = %s AND pd.data_status = %s
               GROUP BY pd.playstyle_name HAVING %s OR count(gp.id) > 0 ORDER BY pd.playstyle_name""",
            (rows[0]["id"], data_status, not research and not is_production_like()
             and environment_from_settings(get_settings().environment) == Environment.LOCAL)).fetchall()
    return {
        "game_version": gv,
        "status": ("ACTIVE" if positions else "DATA_NOT_INGESTED") if research else rows[0]["status"],
        "research_only": research,
        "positions": positions,
        "position_types": cfg.get("position_types", {}),
        "tactical_profiles": sorted(TACTICAL_ATTRIBUTE_WEIGHTS),
        "tactical_dimensions": list(TACTICAL_DIMENSIONS),
        "formations": FORMATIONS,
        "formation_slots": {
            f: [{"slot": sl.slot, "position": sl.position, "side": sl.side,
                 "duty": sl.duty} for sl in slots]
            for f, slots in FORMATION_SLOTS.items()
        },
        "archetypes": {
            name: {"positions": list(d["positions"]), "description": d["description"]}
            for name, d in ARCHETYPE_DEFINITIONS.items()
        },
        "quality_bands": dict(QUALITY_BANDS),
        "engine_version": ENGINE_VERSION,
        "playstyles": playstyles,
        "capabilities": {
            "roles_available": bool(cfg.get("roles_available")),
            "market_data_available": bool(cfg.get("market_data_available")),
            "chemistry_rules_verified": bool(cfg.get("chemistry_rules_verified")),
            "women_universe_included": cfg.get("women_universe_included"),
        },
        "notes": None if research else cfg.get("note"),
    }
