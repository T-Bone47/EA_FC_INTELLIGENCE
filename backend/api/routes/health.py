"""Health & readiness endpoints."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/api/health")
@router.get("/api/v1/health")     # compatibility alias with the old surface
def health() -> dict:
    return {"status": "ok", "service": "ea-fc-player-intelligence"}


@router.get("/api/health/ready")
def ready() -> dict:
    """Readiness probe. Counts are REAL and scoped to production data only:
    synthetic rows are excluded, and per-version counts make an empty version
    (e.g. FC27 = 0) visible instead of implied by an aggregate."""
    from backend.core.db import query, query_one
    try:
        row = query_one("""
            SELECT (SELECT count(*) FROM game_player
                     WHERE data_status <> 'SYNTHETIC_TEST') AS game_players,
                   (SELECT count(*) FROM game_player_playstyle) AS playstyles,
                   (SELECT count(*) FROM ut_card
                     WHERE is_synthetic = FALSE) AS ut_cards,
                   (SELECT count(*) FROM game_version) AS game_versions""")
        per_version = {
            r["code"]: r["n"] for r in query("""
                SELECT gv.code, count(gp.id) FILTER (
                         WHERE gp.data_status <> 'SYNTHETIC_TEST')::int AS n
                FROM game_version gv
                LEFT JOIN game_player gp ON gp.game_version_id = gv.id
                GROUP BY gv.code ORDER BY gv.code""")
        }
        return {"status": "ready", "database": "up", **row,
                "game_players_by_version": per_version}
    except Exception:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503,
                            content={"status": "not_ready", "database": "down"})
