"""FastAPI application factory — production API surface.

Canonical surface: /api/* (version-aware). The old demo V1 recommendation path
is intentionally removed (§24): the user-facing product must not depend on
demo fixtures, and V2 is no longer hardcoded to FC26.

Security (§26): CORS allowlist, request size limit, security headers, safe
error handling (no stack traces / internals leaked), rate limiting via route
dependencies, secrets only from environment.
"""
from __future__ import annotations

import logging
import uuid as uuid_lib
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.core.config import get_settings

log = logging.getLogger("eafc.api")


def create_app() -> FastAPI:
    settings = get_settings()
    # Fail fast on misconfiguration: effective_jwt_secret() raises in production
    # when JWT_SECRET is unset. Without this the app would boot and only fail on
    # the first token issue/verify (a runtime 500 instead of a startup error).
    settings.effective_jwt_secret()
    app = FastAPI(
        title="EA FC Player Intelligence API",
        version="2.0.0",
        description=("Player SUITABILITY intelligence for EA SPORTS FC Ultimate "
                     "Team. Deterministic, explainable, version-aware. "
                     "UNKNOWN data is never fabricated."),
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )

    # ------------------------------------------------------------ middleware
    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        # request size limit
        cl = request.headers.get("content-length")
        if cl and int(cl) > settings.max_request_bytes:
            return JSONResponse(status_code=413,
                                content={"detail": "Request body too large."})
        request.state.request_id = str(uuid_lib.uuid4())[:8]
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains")
        return response

    origins = settings.cors_origin_list()
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
            max_age=600,
        )

    # ------------------------------------------------------------ error handling
    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        rid = getattr(request.state, "request_id", "????????")
        # full detail server-side only; users get a safe message
        log.exception("unhandled error [request_id=%s] %s %s",
                      rid, request.method, request.url.path)
        return JSONResponse(status_code=500, content={
            "detail": "Internal server error.",
            "request_id": rid,
        })

    # ------------------------------------------------------------ routes
    from backend.api.routes import (
        auth, cards, compare, feedback, health, meta, players,
        recommendations, squads,
    )
    for module in (health, meta, auth, players, cards, recommendations,
                   compare, squads, feedback):
        app.include_router(module.router)

    @app.get("/api")
    def api_root() -> dict:
        return {
            "service": "EA FC Player Intelligence",
            "version": "2.0.0",
            "docs": "/api/docs",
            "canonical_endpoints": [
                "POST /api/recommendations",
                "POST /api/recommendations/parse-intent",
                "POST /api/compare",
                "GET  /api/players",
                "GET  /api/players/{id}",
                "GET  /api/cards/{id}",
                "GET  /api/meta/reference",
                "POST /api/auth/signup | /api/auth/login",
                "CRUD /api/squads",
                "POST /api/feedback",
            ],
            "data_policy": "UNKNOWN is never fabricated; synthetic test data is "
                           "firewalled from production endpoints.",
        }

    # ------------------------------------------------------------ frontend
    dist = settings.frontend_dist
    if dist and Path(dist).exists():
        app.mount("/assets", StaticFiles(directory=Path(dist) / "assets"),
                  name="assets")

        @app.get("/{full_path:path}")
        def spa(full_path: str):
            if full_path.startswith("api/"):
                return JSONResponse(status_code=404, content={"detail": "Not found."})
            candidate = Path(dist) / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(Path(dist) / "index.html")
    return app


app = create_app()
