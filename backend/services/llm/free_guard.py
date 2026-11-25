"""Strict Free-Only Enforcement Guard & Quota/Budget Manager.

Guarantees:
- Paid OpenRouter endpoints or nonzero pricing models are blocked BEFORE inference.
- Paid Gemini models (Pro/Argon/Carbon/Image/TTS) are blocked when free_only=True.
- Daily, per-minute, per-user, token, concurrency, and per-turn request quotas
  track individual provider requests (including tool rounds and retries).
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from backend.core.config import Settings, get_settings
from backend.services.llm.contracts import ModelCapabilities, ProviderError, ProviderErrorKind


# Explicit free-tier Gemini models confirmed on /v1beta/models (2026-11-25)
GEMINI_FREE_TIER_MODELS = {
    "gemini-4-hydrogen",
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.1-flash-lite-preview",
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemma-4-26b-a4b-it",
    "gemma-4-31b-it",
}

# Models known to require billing or specialized paid image/audio quotas
GEMINI_PAID_OR_BLOCKED_PREFIXES = (
    "gemini-4-argon",
    "gemini-4-carbon",
    "gemini-4-neon",
    "gemini-2.5-pro",
    "gemini-3.1-pro",
    "gemini-3-pro",
    "gemini-pro-latest",
    "lyria",
    "nano-banana",
    "veo",
    "imagen",
    "gemini-decision",
)


class PaidModelBlockedError(ProviderError):
    """Raised whenever a paid or unverified model/capability is attempted in free-only mode."""

    def __init__(self, provider: str, model: str, reason: str) -> None:
        super().__init__(
            ProviderErrorKind.PAID_MODEL_BLOCKED,
            f"Blocked by AI_COACH_FREE_ONLY policy ({provider}:{model}): {reason}",
            provider=provider,
            model=model,
            retryable_same_provider=False,
            failover_allowed=False,
        )


class FreeUsageGuard:
    """Pre-flight validator preventing any billable LLM calls."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    @property
    def free_only_enforced(self) -> bool:
        return bool(self.settings.ai_coach_free_only or not self.settings.ai_coach_allow_paid_usage)

    def assert_provider_allowed(self, provider: str) -> None:
        p = provider.lower().strip()
        if p not in ("gemini", "openrouter", "deterministic"):
            raise ProviderError(
                ProviderErrorKind.INVALID_REQUEST,
                f"Provider {provider!r} is disabled. Only Gemini, OpenRouter free models, and DeterministicCoach are permitted.",
                provider=p,
                failover_allowed=False,
            )

    def validate_model(
        self,
        provider: str,
        model_id: str,
        capabilities: Optional[ModelCapabilities] = None,
        *,
        requires_tools: bool = False,
        requires_images: bool = False,
        requires_video: bool = False,
    ) -> None:
        self.assert_provider_allowed(provider)
        p = provider.lower().strip()
        mid = (model_id or "").strip()
        if p == "deterministic":
            return
        if not mid:
            raise PaidModelBlockedError(p, mid, "Empty model identifier.")

        if requires_video and not self.settings.effective_allow_external_video():
            raise ProviderError(
                ProviderErrorKind.MEDIA_POLICY_BLOCKED,
                "External video transmission to LLM is disabled by policy.",
                provider=p,
                model=mid,
                failover_allowed=False,
            )
        if requires_images and not self.settings.effective_allow_external_images():
            raise ProviderError(
                ProviderErrorKind.MEDIA_POLICY_BLOCKED,
                "External image transmission to LLM is disabled by policy.",
                provider=p,
                model=mid,
                failover_allowed=False,
            )

        if not self.free_only_enforced:
            return

        if p == "gemini":
            if any(mid.startswith(pref) for pref in GEMINI_PAID_OR_BLOCKED_PREFIXES) or "-tts" in mid or "-image" in mid or "-live" in mid:
                raise PaidModelBlockedError("gemini", mid, "Paid/pro/media-generation Gemini model blocked under free-only policy.")
            if mid not in GEMINI_FREE_TIER_MODELS:
                raise PaidModelBlockedError("gemini", mid, "Model is not in verified Gemini API Free Tier allowlist.")
        elif p == "openrouter":
            is_named_free = mid == "openrouter/free" or mid.endswith(":free")
            if not is_named_free:
                raise PaidModelBlockedError("openrouter", mid, "OpenRouter model must be 'openrouter/free' or end with ':free'.")
            if capabilities is not None:
                if not capabilities.available:
                    raise ProviderError(
                        ProviderErrorKind.UNSUPPORTED_MODEL,
                        f"OpenRouter model {mid!r} is currently unavailable in live catalog.",
                        provider="openrouter",
                        model=mid,
                        failover_allowed=True,
                    )
                if (capabilities.input_price_usd_per_token or 0.0) > 0.0 or (capabilities.output_price_usd_per_token or 0.0) > 0.0 or capabilities.additional_fees_present:
                    raise PaidModelBlockedError("openrouter", mid, "Non-zero token or request pricing detected in live catalog.")
                if not capabilities.free_tier_eligible:
                    raise PaidModelBlockedError("openrouter", mid, "Model not flagged free_tier_eligible in registry.")

        if capabilities is not None:
            if requires_tools and not capabilities.supports_tools:
                raise ProviderError(
                    ProviderErrorKind.UNSUPPORTED_TOOLS,
                    f"Model {mid!r} does not advertise function/tool calling support.",
                    provider=p,
                    model=mid,
                    failover_allowed=True,
                )
            if requires_images and "image" not in capabilities.input_modalities:
                raise ProviderError(
                    ProviderErrorKind.MEDIA_POLICY_BLOCKED,
                    f"Model {mid!r} does not support image inputs.",
                    provider=p,
                    model=mid,
                    failover_allowed=True,
                )


@dataclass
class TurnBudgetTracker:
    max_provider_requests: int
    max_tokens: int
    requests_used: int = 0
    tokens_used: int = 0

    def reserve_request(self, provider: str) -> None:
        if self.requests_used >= self.max_provider_requests:
            raise ProviderError(
                ProviderErrorKind.QUOTA_EXHAUSTED,
                f"Per-turn provider request cap ({self.max_provider_requests}) reached.",
                provider=provider,
                failover_allowed=False,
            )
        if self.tokens_used >= self.max_tokens:
            raise ProviderError(
                ProviderErrorKind.QUOTA_EXHAUSTED,
                f"Per-turn token budget ({self.max_tokens}) reached.",
                provider=provider,
                failover_allowed=False,
            )
        self.requests_used += 1

    def record_tokens(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.tokens_used += max(0, int(prompt_tokens)) + max(0, int(completion_tokens))


@dataclass
class QuotaState:
    day_key: str = ""
    daily_requests_by_provider: Dict[str, int] = field(default_factory=dict)
    rpm_window: Dict[str, deque[float]] = field(default_factory=dict)
    user_rpm_window: Dict[str, deque[float]] = field(default_factory=dict)
    cooldown_until: Dict[str, float] = field(default_factory=dict)
    tokens_today_by_provider: Dict[str, int] = field(default_factory=dict)
    reported_cost_today_usd: float = 0.0


class RedisQuotaBackend:
    """Optional shared multi-worker rate/cooldown store activated ONLY when REDIS_URL is configured."""

    def __init__(self, redis_url: str) -> None:
        self._client = None
        try:
            import redis
            client = redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=1.0)
            client.ping()
            self._client = client
        except Exception:
            self._client = None

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def get_cooldown_remaining(self, cd_key: str) -> float:
        if not self._client:
            return 0.0
        try:
            ttl = self._client.ttl(f"eafc:coach:cd:{cd_key}")
            return float(ttl) if ttl and ttl > 0 else 0.0
        except Exception:
            return 0.0

    def set_cooldown(self, cd_key: str, seconds: int) -> None:
        if not self._client:
            return
        try:
            self._client.setex(f"eafc:coach:cd:{cd_key}", max(5, int(seconds)), "1")
        except Exception:
            pass

    def incr_window(self, key: str, ttl_seconds: int) -> int:
        if not self._client:
            return -1
        try:
            pipe = self._client.pipeline()
            pipe.incr(key)
            pipe.expire(key, ttl_seconds, nx=True)
            res = pipe.execute()
            return int(res[0])
        except Exception:
            return -1


class QuotaManager:
    """Thread-safe RPM, daily, per-user, token, concurrency, and cooldown controller."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self._lock = threading.RLock()
        self._state = QuotaState(day_key=self._today())
        self._semaphore = threading.BoundedSemaphore(max(1, int(self.settings.ai_coach_concurrent_request_limit)))
        r_url = (getattr(self.settings, "redis_url", None) or "").strip()
        self._redis: Optional[RedisQuotaBackend] = RedisQuotaBackend(r_url) if r_url else None

    @staticmethod
    def _today() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _roll_day_if_needed(self) -> None:
        today = self._today()
        if self._state.day_key != today:
            self._state = QuotaState(day_key=today)

    def acquire_concurrency_slot(self, timeout: float = 2.0) -> bool:
        return self._semaphore.acquire(timeout=timeout)

    def release_concurrency_slot(self) -> None:
        try:
            self._semaphore.release()
        except ValueError:
            pass

    def check_and_consume(self, provider: str, user_id: str, model_id: Optional[str] = None) -> None:
        now = time.monotonic()
        with self._lock:
            self._roll_day_if_needed()
            model_key = f"{provider}:{model_id}" if model_id else provider
            for cd_key in (provider, model_key):
                if self._redis and self._redis.enabled:
                    r_cd = self._redis.get_cooldown_remaining(cd_key)
                    if r_cd > 0:
                        raise ProviderError(
                            ProviderErrorKind.RATE_LIMITED,
                            f"{cd_key} is in shared cooldown for {round(r_cd, 1)}s after rate limiting.",
                            provider=provider,
                            model=model_id,
                            retry_after_seconds=round(r_cd, 1),
                            failover_allowed=True,
                        )
                cd = self._state.cooldown_until.get(cd_key, 0.0)
                if now < cd:
                    rem = round(cd - now, 1)
                    raise ProviderError(
                        ProviderErrorKind.RATE_LIMITED,
                        f"{cd_key} is in cooldown for {rem}s after rate limiting.",
                        provider=provider,
                        model=model_id,
                        retry_after_seconds=rem,
                        failover_allowed=True,
                    )

            daily_count = self._state.daily_requests_by_provider.get(provider, 0)
            if daily_count >= int(self.settings.ai_coach_daily_provider_budget):
                raise ProviderError(
                    ProviderErrorKind.QUOTA_EXHAUSTED,
                    f"Daily provider request budget ({self.settings.ai_coach_daily_provider_budget}) exhausted for {provider}.",
                    provider=provider,
                    failover_allowed=True,
                )

            p_win = self._state.rpm_window.setdefault(provider, deque())
            while p_win and now - p_win[0] > 60.0:
                p_win.popleft()
            if len(p_win) >= int(self.settings.ai_coach_requests_per_minute):
                raise ProviderError(
                    ProviderErrorKind.RATE_LIMITED,
                    f"Provider RPM limit ({self.settings.ai_coach_requests_per_minute}/min) reached for {provider}.",
                    provider=provider,
                    retry_after_seconds=round(60.0 - (now - p_win[0]), 1),
                    failover_allowed=True,
                )

            u_win = self._state.user_rpm_window.setdefault(str(user_id), deque())
            while u_win and now - u_win[0] > 60.0:
                u_win.popleft()
            if len(u_win) >= int(self.settings.ai_coach_per_user_requests_per_minute):
                raise ProviderError(
                    ProviderErrorKind.RATE_LIMITED,
                    f"Per-user coach RPM limit ({self.settings.ai_coach_per_user_requests_per_minute}/min) reached.",
                    provider=provider,
                    retry_after_seconds=round(60.0 - (now - u_win[0]), 1),
                    failover_allowed=False,
                )

            p_win.append(now)
            u_win.append(now)
            self._state.daily_requests_by_provider[provider] = daily_count + 1

    def trigger_cooldown(
        self,
        provider: str,
        retry_after_seconds: Optional[float] = None,
        model_id: Optional[str] = None,
    ) -> None:
        cd = retry_after_seconds if (retry_after_seconds and retry_after_seconds > 0) else float(self.settings.ai_coach_cooldown_seconds)
        cd = min(max(cd, 5.0), 600.0)
        key = f"{provider}:{model_id}" if model_id else provider
        with self._lock:
            self._state.cooldown_until[key] = time.monotonic() + cd
            if self._redis and self._redis.enabled:
                self._redis.set_cooldown(key, int(round(cd)))

    def record_usage(self, provider: str, prompt_tokens: int, completion_tokens: int, cost_usd: float = 0.0) -> None:
        with self._lock:
            self._roll_day_if_needed()
            self._state.tokens_today_by_provider[provider] = (
                self._state.tokens_today_by_provider.get(provider, 0) + max(0, prompt_tokens) + max(0, completion_tokens)
            )
            self._state.reported_cost_today_usd += max(0.0, float(cost_usd))

    def new_turn_budget(self) -> TurnBudgetTracker:
        return TurnBudgetTracker(
            max_provider_requests=max(1, int(self.settings.ai_coach_max_provider_requests_per_turn)),
            max_tokens=max(1024, int(self.settings.ai_coach_token_budget_per_turn)),
        )

    def snapshot(self) -> Dict[str, Any]:
        now = time.monotonic()
        with self._lock:
            self._roll_day_if_needed()
            return {
                "day_utc": self._state.day_key,
                "daily_budget_per_provider": int(self.settings.ai_coach_daily_provider_budget),
                "rpm_limit": int(self.settings.ai_coach_requests_per_minute),
                "per_user_rpm_limit": int(self.settings.ai_coach_per_user_requests_per_minute),
                "daily_requests": dict(self._state.daily_requests_by_provider),
                "tokens_today": dict(self._state.tokens_today_by_provider),
                "reported_cost_usd_today": round(self._state.reported_cost_today_usd, 6),
                "shared_backend": "redis" if (self._redis and self._redis.enabled) else "in_process",
                "active_cooldowns_sec": {
                    p: round(exp - now, 1)
                    for p, exp in self._state.cooldown_until.items()
                    if exp > now
                },
            }
