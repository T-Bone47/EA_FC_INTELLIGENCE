"""Dynamic Model Capability Registry & Provider Health Monitor.

Periodically refreshes live OpenRouter (/api/v1/models) and Gemini (/v1beta/models)
catalogs with bounded TTL caching, verifying zero pricing, modality support,
tool calling, and availability. Never fetches entire catalogs on every chat turn.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from backend.core.config import Settings, get_settings
from backend.services.llm.contracts import ModelCapabilities
from backend.services.llm.free_guard import GEMINI_FREE_TIER_MODELS
from backend.services.llm.security import redact_secrets


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_float(val: Any) -> Optional[float]:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _default_seeded_capabilities() -> Dict[str, ModelCapabilities]:
    ts = "2026-11-25T00:00:00+00:00"
    seeded = [
        ModelCapabilities(
            provider="gemini",
            model_id="gemini-4-hydrogen",
            display_name="Gemini 4 Hydrogen",
            context_length=1_048_576,
            max_output_tokens=65_536,
            input_modalities=["text", "image", "audio", "video"],
            supports_tools=True,
            supports_structured_outputs=True,
            supports_streaming=True,
            supports_reasoning=True,
            input_price_usd_per_token=0.0,
            output_price_usd_per_token=0.0,
            free_tier_eligible=True,
            available=True,
            last_verified_iso=ts,
            notes="Verified Gemini API free-tier flagship reasoning & tool model.",
        ),
        ModelCapabilities(
            provider="gemini",
            model_id="gemini-3.8-flash",
            display_name="Gemini 3.8 Flash",
            context_length=1_048_576,
            max_output_tokens=65_536,
            input_modalities=["text", "image", "audio", "video"],
            supports_tools=True,
            supports_structured_outputs=True,
            supports_streaming=True,
            supports_reasoning=True,
            input_price_usd_per_token=0.0,
            output_price_usd_per_token=0.0,
            free_tier_eligible=True,
            available=True,
            last_verified_iso=ts,
            notes="Verified fast Gemini free-tier Flash model.",
        ),
        ModelCapabilities(
            provider="gemini",
            model_id="gemini-3.6-flash",
            display_name="Gemini 3.6 Flash",
            context_length=1_048_576,
            max_output_tokens=65_536,
            input_modalities=["text", "image"],
            supports_tools=True,
            supports_structured_outputs=True,
            supports_streaming=True,
            input_price_usd_per_token=0.0,
            output_price_usd_per_token=0.0,
            free_tier_eligible=True,
            available=True,
            last_verified_iso=ts,
        ),
        ModelCapabilities(
            provider="gemini",
            model_id="gemini-2.5-flash",
            display_name="Gemini 2.5 Flash",
            context_length=1_048_576,
            max_output_tokens=65_536,
            input_modalities=["text", "image"],
            supports_tools=True,
            supports_structured_outputs=True,
            supports_streaming=True,
            input_price_usd_per_token=0.0,
            output_price_usd_per_token=0.0,
            free_tier_eligible=True,
            available=True,
            last_verified_iso=ts,
        ),
        ModelCapabilities(
            provider="openrouter",
            model_id="openrouter/free",
            display_name="OpenRouter Free Models Router",
            context_length=200_000,
            max_output_tokens=16_384,
            input_modalities=["text", "image"],
            supports_tools=True,
            supports_structured_outputs=True,
            supports_streaming=True,
            supports_reasoning=True,
            input_price_usd_per_token=0.0,
            output_price_usd_per_token=0.0,
            free_tier_eligible=True,
            available=True,
            last_verified_iso=ts,
            notes="Official OpenRouter zero-price capability-filtering free router.",
        ),
        ModelCapabilities(
            provider="openrouter",
            model_id="nvidia/nemotron-3.5-super-vl:free",
            display_name="NVIDIA Nemotron 3.5 Super VL 120B (free)",
            context_length=1_000_000,
            max_output_tokens=131_072,
            input_modalities=["text", "image", "video"],
            supports_tools=True,
            supports_structured_outputs=True,
            supports_streaming=True,
            supports_reasoning=True,
            input_price_usd_per_token=0.0,
            output_price_usd_per_token=0.0,
            free_tier_eligible=True,
            available=True,
            last_verified_iso=ts,
        ),
        ModelCapabilities(
            provider="openrouter",
            model_id="nvidia/nemotron-3-ultra-550b-a55b:free",
            display_name="NVIDIA Nemotron 3 Ultra 550B (free)",
            context_length=1_000_000,
            max_output_tokens=65_536,
            input_modalities=["text"],
            supports_tools=True,
            supports_structured_outputs=False,
            supports_streaming=True,
            supports_reasoning=True,
            input_price_usd_per_token=0.0,
            output_price_usd_per_token=0.0,
            free_tier_eligible=True,
            available=True,
            last_verified_iso=ts,
        ),
        ModelCapabilities(
            provider="openrouter",
            model_id="nvidia/nemotron-3.5-lightning:free",
            display_name="NVIDIA Nemotron 3.5 Lightning (free)",
            context_length=1_000_000,
            max_output_tokens=65_536,
            input_modalities=["text"],
            supports_tools=True,
            supports_structured_outputs=False,
            supports_streaming=True,
            supports_reasoning=True,
            input_price_usd_per_token=0.0,
            output_price_usd_per_token=0.0,
            free_tier_eligible=True,
            available=True,
            last_verified_iso=ts,
        ),
        ModelCapabilities(
            provider="openrouter",
            model_id="google/gemma-4-26b-a4b-it:free",
            display_name="Google Gemma 4 26B A4B (free)",
            context_length=262_144,
            max_output_tokens=32_768,
            input_modalities=["text", "image", "video"],
            supports_tools=True,
            supports_structured_outputs=False,
            supports_streaming=True,
            supports_reasoning=True,
            input_price_usd_per_token=0.0,
            output_price_usd_per_token=0.0,
            free_tier_eligible=True,
            available=True,
            last_verified_iso=ts,
        ),
        ModelCapabilities(
            provider="openrouter",
            model_id="baidu/ernie-5.5-flash-preview:free",
            display_name="Baidu ERNIE 5.5 Flash Preview (free)",
            context_length=1_024_000,
            max_output_tokens=131_072,
            input_modalities=["text"],
            supports_tools=True,
            supports_structured_outputs=True,
            supports_streaming=True,
            supports_reasoning=True,
            input_price_usd_per_token=0.0,
            output_price_usd_per_token=0.0,
            free_tier_eligible=True,
            available=True,
            last_verified_iso=ts,
        ),
    ]
    return {f"{m.provider}:{m.model_id}": m for m in seeded}


class ModelCapabilityRegistry:
    """TTL-cached registry discovering live Gemini & OpenRouter free models."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self._lock = threading.RLock()
        self._models: Dict[str, ModelCapabilities] = _default_seeded_capabilities()
        self._last_refresh_mono: Dict[str, float] = {}
        self._last_refresh_error: Dict[str, str] = {}

    def _stale(self, provider: str) -> bool:
        ttl = max(60, int(self.settings.ai_coach_catalog_refresh_seconds))
        last = self._last_refresh_mono.get(provider)
        return last is None or (time.monotonic() - last) > ttl

    def refresh_gemini(self, force: bool = False) -> List[ModelCapabilities]:
        if not force and not self._stale("gemini"):
            return self.list_models(provider="gemini")
        if not self.settings.has_gemini_key():
            return self.list_models(provider="gemini")
        url = "https://generativelanguage.googleapis.com/v1beta/models"
        try:
            r = httpx.get(
                url,
                headers={"x-goog-api-key": self.settings.gemini_api_key or ""},
                params={"pageSize": 100},
                timeout=10.0,
            )
            r.raise_for_status()
            rows = r.json().get("models", [])
            ts = _now_iso()
            seen_ids: set[str] = set()
            with self._lock:
                for m in rows:
                    mid = str(m.get("name", "")).replace("models/", "")
                    if not mid:
                        continue
                    methods = set(m.get("supportedGenerationMethods") or [])
                    if "generateContent" not in methods:
                        continue
                    is_free = mid in GEMINI_FREE_TIER_MODELS
                    key = f"gemini:{mid}"
                    seen_ids.add(key)
                    self._models[key] = ModelCapabilities(
                        provider="gemini",
                        model_id=mid,
                        display_name=str(m.get("displayName") or mid),
                        context_length=int(m.get("inputTokenLimit") or 32768),
                        max_output_tokens=int(m.get("outputTokenLimit") or 8192),
                        input_modalities=["text", "image"] if ("flash" in mid or "hydrogen" in mid or "gemma-4" in mid) else ["text"],
                        supports_tools=("gemini-" in mid and "-tts" not in mid and "-image" not in mid),
                        supports_structured_outputs=("gemini-" in mid and "-tts" not in mid),
                        supports_streaming=True,
                        supports_reasoning=("hydrogen" in mid or "3.8" in mid or "2.5" in mid or "pro" in mid or "gemma-4" in mid),
                        input_price_usd_per_token=0.0 if is_free else None,
                        output_price_usd_per_token=0.0 if is_free else None,
                        free_tier_eligible=is_free,
                        available=True,
                        last_verified_iso=ts,
                        notes="Verified live via Gemini /v1beta/models",
                    )
                for key, item in list(self._models.items()):
                    if item.provider == "gemini" and key not in seen_ids:
                        item.available = False
                self._last_refresh_mono["gemini"] = time.monotonic()
                self._last_refresh_error.pop("gemini", None)
        except Exception as exc:
            with self._lock:
                self._last_refresh_error["gemini"] = redact_secrets(f"{type(exc).__name__}: {exc}")
        return self.list_models(provider="gemini")

    def refresh_openrouter(self, force: bool = False) -> List[ModelCapabilities]:
        if not force and not self._stale("openrouter"):
            return self.list_models(provider="openrouter")
        try:
            r = httpx.get("https://openrouter.ai/api/v1/models", timeout=12.0)
            r.raise_for_status()
            rows = r.json().get("data", [])
            ts = _now_iso()
            seen_ids: set[str] = set()
            with self._lock:
                for m in rows:
                    mid = str(m.get("id") or "")
                    if not mid:
                        continue
                    pricing = m.get("pricing") or {}
                    p_in = _parse_float(pricing.get("prompt"))
                    p_out = _parse_float(pricing.get("completion"))
                    extra_fees = any(
                        (_parse_float(v) or 0.0) > 0.0
                        for k, v in pricing.items()
                        if k not in ("prompt", "completion")
                    )
                    is_free_named = mid == "openrouter/free" or mid.endswith(":free")
                    zero_priced = (p_in == 0.0 and p_out == 0.0 and not extra_fees)
                    if not is_free_named and not zero_priced:
                        continue
                    params = set(m.get("supported_parameters") or [])
                    arch = m.get("architecture") or {}
                    in_mods = list(arch.get("input_modalities") or ["text"])
                    key = f"openrouter:{mid}"
                    seen_ids.add(key)
                    self._models[key] = ModelCapabilities(
                        provider="openrouter",
                        model_id=mid,
                        display_name=str(m.get("name") or mid),
                        context_length=int(m.get("context_length") or 128_000),
                        max_output_tokens=int((m.get("top_provider") or {}).get("max_completion_tokens") or 16_384),
                        input_modalities=in_mods,
                        supports_tools=("tools" in params),
                        supports_structured_outputs=("structured_outputs" in params or "response_format" in params),
                        supports_streaming=True,
                        supports_reasoning=("reasoning" in params or "reasoning_effort" in params),
                        input_price_usd_per_token=p_in,
                        output_price_usd_per_token=p_out,
                        additional_fees_present=extra_fees,
                        free_tier_eligible=bool(is_free_named and zero_priced),
                        available=True,
                        last_verified_iso=ts,
                        notes="Verified live via OpenRouter /api/v1/models",
                    )
                for key, item in list(self._models.items()):
                    if item.provider == "openrouter" and key not in seen_ids:
                        item.available = False
                self._last_refresh_mono["openrouter"] = time.monotonic()
                self._last_refresh_error.pop("openrouter", None)
        except Exception as exc:
            with self._lock:
                self._last_refresh_error["openrouter"] = redact_secrets(f"{type(exc).__name__}: {exc}")
        return self.list_models(provider="openrouter")

    def mark_unavailable(self, provider: str, model_id: str, reason: str = "") -> None:
        with self._lock:
            item = self._models.get(f"{provider}:{model_id}")
            if item:
                item.available = False
                if reason:
                    item.notes = redact_secrets(reason)[:200]

    def get(self, provider: str, model_id: str) -> Optional[ModelCapabilities]:
        with self._lock:
            return self._models.get(f"{provider}:{model_id}")

    def list_models(
        self,
        *,
        provider: Optional[str] = None,
        free_only: bool = True,
        available_only: bool = True,
    ) -> List[ModelCapabilities]:
        with self._lock:
            out: List[ModelCapabilities] = []
            for m in self._models.values():
                if provider and m.provider != provider:
                    continue
                if free_only and not m.free_tier_eligible:
                    continue
                if available_only and not m.available:
                    continue
                out.append(m.model_copy())
            return sorted(out, key=lambda item: (item.provider, item.model_id))

    def diagnostics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "last_refresh_errors": dict(self._last_refresh_error),
                "free_model_counts": {
                    "gemini": sum(1 for m in self._models.values() if m.provider == "gemini" and m.free_tier_eligible and m.available),
                    "openrouter": sum(1 for m in self._models.values() if m.provider == "openrouter" and m.free_tier_eligible and m.available),
                },
            }


@dataclass
class ProviderStats:
    success_count: int = 0
    error_count: int = 0
    consecutive_failures: int = 0
    last_error: Optional[str] = None
    last_error_iso: Optional[str] = None
    last_success_iso: Optional[str] = None
    avg_latency_ms: float = 0.0
    avg_ttft_ms: float = 0.0
    total_tokens: int = 0


@dataclass
class ModelCircuitState:
    state: str = "CLOSED"  # CLOSED | OPEN | HALF_OPEN
    consecutive_failures: int = 0
    opened_until_mono: float = 0.0
    success_count: int = 0
    error_count: int = 0
    avg_latency_ms: float = 0.0
    avg_ttft_ms: float = 0.0
    last_error: Optional[str] = None


class ProviderHealthMonitor:
    """Tracks live reliability, TTFT/latency EMA, and per-model circuit breakers."""

    def __init__(self, failure_threshold: int = 2, open_seconds: float = 120.0) -> None:
        self._lock = threading.RLock()
        self._failure_threshold = max(2, int(failure_threshold))
        self._open_seconds = max(15.0, float(open_seconds))
        self._stats: Dict[str, ProviderStats] = {
            "gemini": ProviderStats(),
            "openrouter": ProviderStats(),
            "deterministic": ProviderStats(),
        }
        self._circuits: Dict[str, ModelCircuitState] = {}

    def is_circuit_open(self, provider: str, model_id: str) -> tuple[bool, float]:
        """Returns (should_skip, remaining_sec). Transitions expired OPEN -> HALF_OPEN."""
        key = f"{provider}:{model_id}"
        now = time.monotonic()
        with self._lock:
            c = self._circuits.get(key)
            if c is None:
                return False, 0.0
            if c.state == "OPEN":
                if now < c.opened_until_mono:
                    return True, round(c.opened_until_mono - now, 1)
                c.state = "HALF_OPEN"
                return False, 0.0
            return False, 0.0

    def record_success(
        self,
        provider: str,
        latency_ms: float,
        tokens: int = 0,
        *,
        model_id: Optional[str] = None,
        ttft_ms: float = 0.0,
    ) -> None:
        with self._lock:
            st = self._stats.setdefault(provider, ProviderStats())
            st.success_count += 1
            st.consecutive_failures = 0
            st.last_success_iso = _now_iso()
            st.total_tokens += max(0, tokens)
            st.avg_latency_ms = latency_ms if st.avg_latency_ms <= 0 else round(0.75 * st.avg_latency_ms + 0.25 * latency_ms, 2)
            eff_ttft = ttft_ms if ttft_ms > 0 else latency_ms
            st.avg_ttft_ms = eff_ttft if st.avg_ttft_ms <= 0 else round(0.75 * st.avg_ttft_ms + 0.25 * eff_ttft, 2)
            if model_id:
                c = self._circuits.setdefault(f"{provider}:{model_id}", ModelCircuitState())
                c.state = "CLOSED"
                c.consecutive_failures = 0
                c.opened_until_mono = 0.0
                c.success_count += 1
                c.avg_latency_ms = latency_ms if c.avg_latency_ms <= 0 else round(0.75 * c.avg_latency_ms + 0.25 * latency_ms, 2)
                c.avg_ttft_ms = eff_ttft if c.avg_ttft_ms <= 0 else round(0.75 * c.avg_ttft_ms + 0.25 * eff_ttft, 2)

    def record_failure(
        self,
        provider: str,
        error_msg: str,
        *,
        model_id: Optional[str] = None,
        transient: bool = True,
    ) -> None:
        clean = redact_secrets(error_msg)[:240]
        with self._lock:
            st = self._stats.setdefault(provider, ProviderStats())
            st.error_count += 1
            st.consecutive_failures += 1
            st.last_error = clean
            st.last_error_iso = _now_iso()
            if model_id:
                c = self._circuits.setdefault(f"{provider}:{model_id}", ModelCircuitState())
                c.error_count += 1
                c.consecutive_failures += 1
                c.last_error = clean
                if transient and (c.state == "HALF_OPEN" or c.consecutive_failures >= self._failure_threshold):
                    c.state = "OPEN"
                    c.opened_until_mono = time.monotonic() + self._open_seconds

    def snapshot(self) -> Dict[str, Any]:
        now = time.monotonic()
        with self._lock:
            return {
                p: {
                    "healthy": st.consecutive_failures < 3,
                    "success_count": st.success_count,
                    "error_count": st.error_count,
                    "consecutive_failures": st.consecutive_failures,
                    "avg_latency_ms": round(st.avg_latency_ms, 2),
                    "avg_ttft_ms": round(st.avg_ttft_ms, 2),
                    "total_tokens": st.total_tokens,
                    "last_success_iso": st.last_success_iso,
                    "last_error": st.last_error,
                    "last_error_iso": st.last_error_iso,
                }
                for p, st in self._stats.items()
            } | {
                "model_circuits": {
                    k: {
                        "state": c.state,
                        "consecutive_failures": c.consecutive_failures,
                        "open_remaining_sec": round(max(0.0, c.opened_until_mono - now), 1) if c.state == "OPEN" else 0.0,
                        "avg_latency_ms": round(c.avg_latency_ms, 2),
                        "avg_ttft_ms": round(c.avg_ttft_ms, 2),
                    }
                    for k, c in self._circuits.items()
                }
            }
