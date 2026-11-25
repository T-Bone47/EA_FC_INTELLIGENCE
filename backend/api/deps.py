"""FastAPI dependencies: auth, rate limiting, pagination, version validation.

Rate limiting: in-process sliding window per (route-class, client). Good for a
single-instance deployment; the api_rate_bucket table exists for a future
shared-store limiter. Limits are conservative defaults, configurable by env.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from fastapi import Depends, Header, HTTPException, Request, status

from backend.api.security import decode_access_token
from backend.core.config import Settings, get_settings
from backend.repositories.user_repository import UserRepository
from backend.services.data_license_gate import (
    Environment, catalogue_releases, environment_from_settings,
)

_users = UserRepository()


# ------------------------------------------------------------------ rate limit
@dataclass
class _Window:
    hits: list[float] = field(default_factory=list)


class RateLimiter:
    def __init__(self):
        self._buckets: dict[str, _Window] = {}
        self._lock = threading.Lock()

    def check(self, key: str, limit_per_minute: int) -> None:
        now = time.monotonic()
        with self._lock:
            w = self._buckets.setdefault(key, _Window())
            w.hits = [t for t in w.hits if now - t < 60.0]
            if len(w.hits) >= limit_per_minute:
                retry = int(60 - (now - w.hits[0])) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Try again later.",
                    headers={"Retry-After": str(retry)})
            w.hits.append(now)
            # opportunistic cleanup to bound memory
            if len(self._buckets) > 50_000:
                for k in list(self._buckets):
                    if not self._buckets[k].hits or now - self._buckets[k].hits[-1] > 120:
                        del self._buckets[k]


rate_limiter = RateLimiter()


def client_ip(request: Request) -> str:
    if request.client:
        return request.client.host
    return "unknown"


def rate_limit_default(request: Request) -> None:
    s = get_settings()
    rate_limiter.check(f"default:{client_ip(request)}",
                       s.rate_limit_requests_per_minute)


def rate_limit_auth(request: Request) -> None:
    s = get_settings()
    rate_limiter.check(f"auth:{client_ip(request)}", s.rate_limit_auth_per_minute)


# ------------------------------------------------------------------ auth
@dataclass
class CurrentUser:
    id: str
    email: str
    role: str
    jti: str


def _extract_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def current_user_optional(request: Request,
                          authorization: Optional[str] = Header(default=None)
                          ) -> Optional[CurrentUser]:
    token = _extract_token(authorization)
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    session = _users.session_active(payload["jti"])
    if session is None:      # revoked / expired / deactivated
        return None
    rate_limiter.check(f"user:{payload['sub']}",
                       get_settings().rate_limit_requests_per_minute * 2)
    return CurrentUser(id=payload["sub"], email=payload.get("email", ""),
                       role=payload.get("role", "user"), jti=payload["jti"])


def current_user_required(user: Optional[CurrentUser] =
                          Depends(current_user_optional)) -> CurrentUser:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"})
    return user


def admin_required(user: CurrentUser = Depends(current_user_required)) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Admin privileges required.")
    return user


# ------------------------------------------------------------------ pagination
@dataclass
class Pagination:
    page: int
    page_size: int


def pagination_params(page: int = 1, page_size: int = 25) -> Pagination:
    if page < 1:
        raise HTTPException(422, "page must be >= 1")
    if not 1 <= page_size <= 100:
        raise HTTPException(422, "page_size must be between 1 and 100")
    return Pagination(page=page, page_size=page_size)


# ------------------------------------------------------------------ versioning
def validate_game_version(code: str) -> str:
    s = get_settings()
    up = str(code or "").strip().upper()
    if up not in s.supported_versions():
        raise HTTPException(
            status_code=422,
            detail=(f"Unsupported game_version {code!r}. Supported: "
                    f"{s.supported_versions()}. Versions are never mixed or "
                    "silently defaulted."))
    return up

def catalogue_environment() -> Environment:
    return environment_from_settings(get_settings().environment)


def is_production_like() -> bool:
    return catalogue_environment() == Environment.PRODUCTION


def can_read_catalogue(game_version: str, entity_scope: str) -> bool:
    environment = catalogue_environment()
    return environment == Environment.LOCAL or entity_scope in catalogue_releases(environment).get(game_version, {})


def require_catalogue_release(game_version: str, entity_scope: str) -> None:
    if not can_read_catalogue(game_version, entity_scope):
        raise HTTPException(403, detail={
            "error": "DATA_LICENSE_GATE_FAILED",
            "detail": f"No verified {entity_scope} dataset is available for {game_version}.",
        })


def local_card_research_allowed(request: Request, settings: Settings) -> bool:
    loopback = {"127.0.0.1", "::1", "localhost", "testclient"}
    return (
        settings.fc27_card_research_enabled
        and environment_from_settings(settings.environment) == Environment.LOCAL
        and urlparse(settings.database_url).hostname in loopback
        and request.url.hostname in loopback
        and request.client is not None and request.client.host in loopback
        and not any(header == "forwarded" or header.startswith("x-forwarded-") for header in request.headers)
    )


def fc27_research_requested(game_version: str, opt_in: bool) -> bool:
    if not opt_in:
        return False
    if game_version != "FC27":
        raise HTTPException(422, "The research opt-in is available for FC27 players only.")
    if catalogue_environment() != Environment.LOCAL:
        raise HTTPException(403, detail={"error": "DATA_LICENSE_GATE_FAILED",
                                         "detail": "FC27 research browsing requires an isolated local deployment."})
    return True


def require_legacy_research_environment() -> None:
    """The frozen V2 services are restricted to isolated local and test deployments."""
    if catalogue_environment() != Environment.LOCAL:
        raise HTTPException(410, "Legacy intelligence is disabled here. Use the V3 player intelligence endpoints.")
