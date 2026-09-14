"""Application configuration via environment (pydantic-settings).

Secrets are never hardcoded. In development an ephemeral JWT secret is generated
and loudly flagged; in production a missing secret is a fatal error.
"""
from __future__ import annotations

import secrets
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"          # development | staging | production
    database_url: str = "postgresql://eafc:eafc_dev_only@localhost:5432/eafc_intelligence"

    jwt_secret: str | None = None
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60 * 12

    cors_origins: str = ""                    # comma-separated; empty = same-origin only
    rate_limit_requests_per_minute: int = 240
    rate_limit_auth_per_minute: int = 10      # stricter for login/signup
    max_request_bytes: int = 1_000_000

    default_game_version: str = "FC26"
    supported_game_versions: str = "FC26,FC27"

    frontend_dist: str = ""                   # path to built frontend (served by API)

    def supported_versions(self) -> list[str]:
        return [v.strip() for v in self.supported_game_versions.split(",") if v.strip()]

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def effective_jwt_secret(self) -> str:
        if self.jwt_secret:
            return self.jwt_secret
        if self.environment == "production":
            raise RuntimeError(
                "JWT_SECRET must be set in production. Refusing to start with a "
                "generated secret.")
        # development-only ephemeral secret (tokens invalidate on restart)
        return _DEV_SECRET


_DEV_SECRET = secrets.token_urlsafe(48)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if not s.jwt_secret and s.environment != "production":
        import warnings
        warnings.warn(
            "JWT_SECRET not set — using an ephemeral development secret. "
            "Set JWT_SECRET in any deployed environment.", stacklevel=2)
    return s
