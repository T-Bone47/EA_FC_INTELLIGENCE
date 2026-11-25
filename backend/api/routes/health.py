"""Health & readiness endpoints."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.api.deps import is_production_like

router = APIRouter(tags=["health"])


@router.get("/api/health")
@router.get("/api/v1/health")     # compatibility alias with the old surface
def health() -> dict:
    return {"status": "ok", "service": "ea-fc-player-intelligence"}


@router.get("/api/health/ready")
def ready() -> dict:
    """Check the required schema in production and report row counts in local QA."""
    from backend.core.db import query, query_one
    try:
        if is_production_like():
            row = query_one("SELECT to_regclass('catalogue_serving.game_player') IS NOT NULL AS ready FROM candidate_cache_generation")
            if row is None or not row["ready"]:
                return JSONResponse(status_code=503, content={"status": "not_ready", "database": "up"})
            return {"status": "ready", "database": "up"}
        row = query_one("""
            SELECT (SELECT count(*) FROM game_player
                     WHERE data_status = 'CANONICAL') AS game_players,
                   (SELECT count(*) FROM game_player_playstyle gpp
                     JOIN game_player gp ON gp.id = gpp.game_player_id
                     WHERE gp.data_status = 'CANONICAL') AS playstyles,
                   (SELECT count(*) FROM ut_card
                     WHERE is_synthetic = FALSE) AS ut_cards,
                   (SELECT count(*) FROM game_version) AS game_versions""")
        version_rows = query("""
                SELECT gv.code,
                       count(gp.id) FILTER (WHERE gp.data_status = 'CANONICAL')::int AS n,
                       count(gp.id) FILTER (WHERE gp.data_status = 'RESEARCH_ONLY')::int AS r
                FROM game_version gv
                LEFT JOIN game_player gp ON gp.game_version_id = gv.id
                GROUP BY gv.code ORDER BY gv.code""")
        per_version = {r["code"]: r["n"] for r in version_rows}
        research = {r["code"]: r["r"] for r in version_rows}
        return {"status": "ready", "database": "up", **row,
                "game_players_by_version": per_version,
                "research_only_game_players_by_version_not_served": research}
    except Exception:
        return JSONResponse(status_code=503,
                            content={"status": "not_ready", "database": "down"})
