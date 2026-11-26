"""Application configuration via environment (pydantic-settings).

Secrets are never hardcoded or exposed in logs/API responses. In development an
ephemeral JWT secret is generated and loudly flagged; in production a missing
secret is a fatal error.
"""
from __future__ import annotations

import secrets
from functools import lru_cache
from typing import Any

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
    fc27_card_research_enabled: bool = False
    supported_game_versions: str = "FC26,FC27"

    frontend_dist: str = ""                   # path to built frontend (served by API)

    # ---------------------------------------------------------------- Phase 41.5 AI Coach
    ai_coach_enabled: bool = True
    ai_coach_provider: str = "gemini"
    ai_coach_fallback_provider: str = "openrouter"

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-4-hydrogen"

    openrouter_api_key: str | None = None
    openrouter_model: str = "openrouter/free"

    ai_coach_free_only: bool = True
    ai_coach_allow_paid_usage: bool = False
    ai_coach_deterministic_fallback: bool = True

    ai_coach_allow_external_video: bool = False
    ai_coach_video_upload_to_llm: bool = False
    ai_coach_allow_external_images: bool = False

    ai_coach_max_tool_rounds: int = 3
    ai_coach_max_provider_requests_per_turn: int = 4
    ai_coach_daily_provider_budget: int = 200
    ai_coach_requests_per_minute: int = 15
    ai_coach_per_user_requests_per_minute: int = 8
    ai_coach_token_budget_per_turn: int = 16000
    ai_coach_cooldown_seconds: int = 60
    ai_coach_concurrent_request_limit: int = 3
    ai_coach_provider_timeout_seconds: float = 12.0
    ai_coach_gemini_timeout_seconds: float = 10.0
    ai_coach_openrouter_timeout_seconds: float = 12.0
    ai_coach_total_deadline_seconds: float = 24.0
    ai_coach_catalog_refresh_seconds: int = 1800
    ai_coach_circuit_breaker_failures: int = 2
    ai_coach_circuit_breaker_cooldown_seconds: float = 120.0
    redis_url: str | None = None

    def effective_provider_timeout(self, provider: str) -> float:
        p = provider.lower().strip()
        if p == "gemini":
            return max(4.0, float(self.ai_coach_gemini_timeout_seconds))
        if p == "openrouter":
            return max(4.0, float(self.ai_coach_openrouter_timeout_seconds))
        return max(4.0, float(self.ai_coach_provider_timeout_seconds))

    def supported_versions(self) -> list[str]:
        return [v.strip() for v in self.supported_game_versions.split(",") if v.strip()]

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def effective_allow_external_video(self) -> bool:
        """Honors both alias flags; defaults strictly to False."""
        return bool(self.ai_coach_allow_external_video or self.ai_coach_video_upload_to_llm)

    def effective_allow_external_images(self) -> bool:
        return bool(self.ai_coach_allow_external_images)

    def has_gemini_key(self) -> bool:
        return bool(self.gemini_api_key and self.gemini_api_key.strip())

    def has_openrouter_key(self) -> bool:
        return bool(self.openrouter_api_key and self.openrouter_api_key.strip())

    def safe_ai_public_summary(self) -> dict[str, Any]:
        """Non-secret configuration summary safe for API health/UI diagnostics."""
        return {
            "enabled": bool(self.ai_coach_enabled),
            "primary_provider": self.ai_coach_provider,
            "fallback_provider": self.ai_coach_fallback_provider,
            "gemini_configured": self.has_gemini_key(),
            "gemini_model": self.gemini_model,
            "openrouter_configured": self.has_openrouter_key(),
            "openrouter_model": self.openrouter_model,
            "free_only": bool(self.ai_coach_free_only),
            "allow_paid_usage": bool(self.ai_coach_allow_paid_usage),
            "deterministic_fallback": bool(self.ai_coach_deterministic_fallback),
            "allow_external_video": self.effective_allow_external_video(),
            "allow_external_images": self.effective_allow_external_images(),
            "max_tool_rounds": int(self.ai_coach_max_tool_rounds),
            "max_provider_requests_per_turn": int(self.ai_coach_max_provider_requests_per_turn),
            "gemini_timeout_seconds": float(self.ai_coach_gemini_timeout_seconds),
            "openrouter_timeout_seconds": float(self.ai_coach_openrouter_timeout_seconds),
            "total_deadline_seconds": float(self.ai_coach_total_deadline_seconds),
            "shared_quota_backend": "redis" if bool(self.redis_url and self.redis_url.strip()) else "in_process_single_worker",
        }

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
