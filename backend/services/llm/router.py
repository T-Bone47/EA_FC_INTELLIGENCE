"""Capability-Aware Football Model Router (Gemini Free -> OpenRouter Free -> Deterministic).

Handles task-aware model selection, pre-flight free-only verification,
bounded cross-provider failover with normalized conversation rebuilding,
and cooldown/health tracking without infinite fallback loops.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from backend.core.config import Settings, get_settings
from backend.services.llm.contracts import (
    FootballLLMProvider,
    LLMMessage,
    LLMResponse,
    LLMToolSpec,
    ProviderError,
    ProviderErrorKind,
)
from backend.services.llm.free_guard import (
    FreeUsageGuard,
    QuotaManager,
    TurnBudgetTracker,
)
from backend.services.llm.gemini_provider import GeminiProvider
from backend.services.llm.openrouter_provider import OpenRouterProvider
from backend.services.llm.registry import ModelCapabilityRegistry, ProviderHealthMonitor


class TaskIntent(str, Enum):
    PLAYER_DISCOVERY = "PLAYER_DISCOVERY"
    PLAYER_COMPARISON = "PLAYER_COMPARISON"
    TEAM_BUILDING = "TEAM_BUILDING"
    SQUAD_OPTIMIZATION = "SQUAD_OPTIMIZATION"
    TACTICAL_RECOMMENDATION = "TACTICAL_RECOMMENDATION"
    GAMEPLAY_ANALYSIS = "GAMEPLAY_ANALYSIS"
    DECISION_ANALYSIS = "DECISION_ANALYSIS"
    GAMER_PERFORMANCE = "GAMER_PERFORMANCE"
    TRAINING = "TRAINING"
    GAME_MECHANICS = "GAME_MECHANICS"
    GENERAL_FOOTBALL = "GENERAL_FOOTBALL"
    IMAGE_SCREENSHOT = "IMAGE_SCREENSHOT"


@dataclass
class RoutingDecision:
    candidates: List[Tuple[str, str]]
    requires_tools: bool
    requires_images: bool
    reason: str
    warnings: List[str] = field(default_factory=list)


def normalize_messages_for_cross_provider(messages: List[LLMMessage]) -> List[LLMMessage]:
    """Rebuilds provider-agnostic history cleanly without leaking Gemini/OR opaque parts."""
    normalized: List[LLMMessage] = []
    for m in messages:
        normalized.append(
            LLMMessage(
                role=m.role,
                content=m.content,
                tool_calls=list(m.tool_calls),
                tool_call_id=m.tool_call_id,
                tool_name=m.tool_name,
                image_b64=m.image_b64,
                image_mime=m.image_mime,
                provider_parts=None,
            )
        )
    return normalized


class FootballModelRouter:
    """Routes each turn across verified free Gemini & OpenRouter backends safely."""

    def __init__(
        self,
        *,
        settings: Optional[Settings] = None,
        registry: Optional[ModelCapabilityRegistry] = None,
        guard: Optional[FreeUsageGuard] = None,
        quota: Optional[QuotaManager] = None,
        health: Optional[ProviderHealthMonitor] = None,
        providers: Optional[Dict[str, FootballLLMProvider]] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.registry = registry or ModelCapabilityRegistry(self.settings)
        self.guard = guard or FreeUsageGuard(self.settings)
        self.quota = quota or QuotaManager(self.settings)
        self.health = health or ProviderHealthMonitor()
        self.providers: Dict[str, FootballLLMProvider] = providers or {
            "gemini": GeminiProvider(self.settings),
            "openrouter": OpenRouterProvider(self.settings),
        }

    def select_candidates(
        self,
        *,
        intent: TaskIntent,
        preferred_provider: str = "AUTO",
        model_override: Optional[str] = None,
        requires_tools: bool = True,
        requires_images: bool = False,
    ) -> RoutingDecision:
        pref = (preferred_provider or "AUTO").upper().strip()
        if pref in ("DETERMINISTIC", "DETERMINISTIC_COACH"):
            return RoutingDecision([], requires_tools, requires_images, "Deterministic mode explicitly requested.")
        if not self.settings.ai_coach_enabled:
            return RoutingDecision([], requires_tools, requires_images, "AI_COACH_ENABLED=false; using deterministic intelligence.")

        warnings: List[str] = []
        # Refresh catalogs gracefully using TTL cache (no per-question full fetches)
        if self.settings.has_gemini_key():
            self.registry.refresh_gemini(force=False)
        if self.settings.has_openrouter_key():
            self.registry.refresh_openrouter(force=False)

        gem_default = self.settings.gemini_model or "gemini-4-hydrogen"
        if intent in (TaskIntent.GAME_MECHANICS, TaskIntent.PLAYER_DISCOVERY, TaskIntent.PLAYER_COMPARISON, TaskIntent.GENERAL_FOOTBALL):
            # Prefer fast verified Gemini 3.6 Flash when primary reasoning model is under load
            gem_candidates = [gem_default, "gemini-3.6-flash", "gemini-3.8-flash"]
        else:
            gem_candidates = [gem_default, "gemini-3.8-flash", "gemini-3.6-flash"]
        gem_candidates = list(dict.fromkeys(gem_candidates))
        if pref == "AUTO":
            # Include fast fallback alongside default so open circuit never leaves 0 Gemini options
            gem_candidates = gem_candidates[:2] + (["gemini-3.6-flash"] if "gemini-3.6-flash" not in gem_candidates[:2] else [])

        or_default = self.settings.openrouter_model or "openrouter/free"
        if requires_images:
            or_candidates = [
                or_default,
                "nvidia/nemotron-3.5-super-vl:free",
                "google/gemma-4-26b-a4b-it:free",
            ]
        elif intent in (TaskIntent.TACTICAL_RECOMMENDATION, TaskIntent.DECISION_ANALYSIS, TaskIntent.SQUAD_OPTIMIZATION):
            or_candidates = [
                or_default,
                "nvidia/nemotron-3.5-super-vl:free",
                "nvidia/nemotron-3-ultra-550b-a55b:free",
                "baidu/ernie-5.5-flash-preview:free",
            ]
        else:
            or_candidates = [
                or_default,
                "nvidia/nemotron-3.5-lightning:free",
                "google/gemma-4-26b-a4b-it:free",
                "baidu/ernie-5.5-flash-preview:free",
            ]
        # Deduplicate while preserving order
        gem_candidates = list(dict.fromkeys(gem_candidates))
        or_candidates = list(dict.fromkeys(or_candidates))

        pairs: List[Tuple[str, str]] = []
        if model_override and ":" in model_override:
            ov_p, ov_m = model_override.split(":", 1)
            ov_p = ov_p.lower().strip()
            self.guard.assert_provider_allowed(ov_p)
            cap = self.registry.get(ov_p, ov_m.strip())
            self.guard.validate_model(
                ov_p,
                ov_m.strip(),
                cap,
                requires_tools=requires_tools,
                requires_images=requires_images,
            )
            pairs.append((ov_p, ov_m.strip()))

        add_gemini = pref in ("AUTO", "GEMINI") and self.settings.has_gemini_key()
        add_openrouter = pref in ("AUTO", "OPENROUTER", "OPENROUTER_FREE") and self.settings.has_openrouter_key()

        if pref == "GEMINI" and not self.settings.has_gemini_key():
            warnings.append("GEMINI_API_KEY unavailable; cannot invoke Gemini primary.")
        if pref in ("OPENROUTER", "OPENROUTER_FREE") and not self.settings.has_openrouter_key():
            warnings.append("OPENROUTER_API_KEY unavailable; cannot invoke OpenRouter.")

        primary_env = (self.settings.ai_coach_provider or "gemini").lower()
        fallback_env = (self.settings.ai_coach_fallback_provider or "openrouter").lower()
        order = [primary_env, fallback_env] if pref == "AUTO" else (["gemini"] if pref == "GEMINI" else ["openrouter"])
        order = list(dict.fromkeys(p for p in order if p in ("gemini", "openrouter")))

        for prov in order:
            if prov == "gemini" and add_gemini:
                for mid in gem_candidates:
                    cap = self.registry.get("gemini", mid)
                    try:
                        self.guard.validate_model(
                            "gemini", mid, cap, requires_tools=requires_tools, requires_images=requires_images
                        )
                        if ("gemini", mid) not in pairs:
                            pairs.append(("gemini", mid))
                    except ProviderError:
                        continue
            elif prov == "openrouter" and add_openrouter:
                for mid in or_candidates:
                    cap = self.registry.get("openrouter", mid)
                    try:
                        self.guard.validate_model(
                            "openrouter", mid, cap, requires_tools=requires_tools, requires_images=requires_images
                        )
                        if ("openrouter", mid) not in pairs:
                            pairs.append(("openrouter", mid))
                    except ProviderError:
                        continue

        return RoutingDecision(
            candidates=pairs,
            requires_tools=requires_tools,
            requires_images=requires_images,
            reason=f"Routed for intent={intent.value} pref={pref} free_only={self.guard.free_only_enforced}",
            warnings=warnings,
        )

    def invoke(
        self,
        *,
        user_id: str,
        intent: TaskIntent,
        messages: List[LLMMessage],
        tools: Optional[List[LLMToolSpec]] = None,
        response_schema: Optional[Dict[str, Any]] = None,
        preferred_provider: str = "AUTO",
        model_override: Optional[str] = None,
        turn_budget: Optional[TurnBudgetTracker] = None,
        requires_images: bool = False,
        stream: bool = False,
        on_chunk: Optional[Callable[[str], None]] = None,
        cancel_event: Optional[threading.Event] = None,
        privacy_strict: bool = False,
    ) -> Tuple[Optional[LLMResponse], List[str]]:
        """Attempts routed free models once each in priority order with fail-closed safety."""
        decision = self.select_candidates(
            intent=intent,
            preferred_provider=preferred_provider,
            model_override=model_override,
            requires_tools=bool(tools),
            requires_images=requires_images,
        )
        notes = list(decision.warnings)
        if not decision.candidates:
            return None, notes + [decision.reason]

        budget = turn_budget or self.quota.new_turn_budget()
        attempted: set[Tuple[str, str]] = set()
        last_provider: Optional[str] = None

        if not self.quota.acquire_concurrency_slot(timeout=2.5):
            notes.append("Concurrent AI Coach request slot busy; fell back to deterministic coaching.")
            return None, notes

        try:
            for provider_name, model_id in decision.candidates:
                if (provider_name, model_id) in attempted:
                    continue
                attempted.add((provider_name, model_id))

                if cancel_event and cancel_event.is_set():
                    raise ProviderError(ProviderErrorKind.CANCELLED, "Cancelled by caller.", provider=provider_name, model=model_id, failover_allowed=False)

                adapter = self.providers.get(provider_name)
                if not adapter:
                    continue

                cap = self.registry.get(provider_name, model_id)
                self.guard.validate_model(
                    provider_name,
                    model_id,
                    cap,
                    requires_tools=bool(tools),
                    requires_images=requires_images,
                )

                is_open, rem_sec = self.health.is_circuit_open(provider_name, model_id)
                if is_open:
                    notes.append(f"{provider_name}/{model_id}: circuit open ({rem_sec}s remaining); skipped without wasting budget.")
                    continue

                try:
                    self.quota.check_and_consume(provider_name, user_id, model_id=model_id)
                    budget.reserve_request(provider_name)
                except ProviderError as qerr:
                    notes.append(str(qerr))
                    if not qerr.failover_allowed:
                        break
                    continue

                call_msgs = (
                    normalize_messages_for_cross_provider(messages)
                    if (last_provider and last_provider != provider_name)
                    else messages
                )
                last_provider = provider_name
                per_timeout = self.settings.effective_provider_timeout(provider_name)

                try:
                    if stream:
                        resp = adapter.generate_stream(
                            model=model_id,
                            messages=call_msgs,
                            tools=tools,
                            response_schema=response_schema,
                            timeout_seconds=per_timeout,
                            cancel_event=cancel_event,
                            privacy_strict=privacy_strict,
                            on_chunk=on_chunk,
                        )
                    else:
                        resp = adapter.generate(
                            model=model_id,
                            messages=call_msgs,
                            tools=tools,
                            response_schema=response_schema,
                            timeout_seconds=per_timeout,
                            cancel_event=cancel_event,
                            privacy_strict=privacy_strict,
                        )
                    budget.record_tokens(resp.prompt_tokens, resp.completion_tokens)
                    self.quota.record_usage(provider_name, resp.prompt_tokens, resp.completion_tokens, resp.reported_cost_usd)
                    self.health.record_success(
                        provider_name,
                        resp.latency_ms,
                        resp.total_tokens,
                        model_id=model_id,
                        ttft_ms=resp.ttft_ms,
                    )
                    return resp, notes
                except ProviderError as perr:
                    transient = perr.kind in (
                        ProviderErrorKind.RATE_LIMITED,
                        ProviderErrorKind.QUOTA_EXHAUSTED,
                        ProviderErrorKind.TIMEOUT,
                        ProviderErrorKind.TRANSIENT_SERVER_ERROR,
                        ProviderErrorKind.UNAVAILABLE,
                    )
                    self.health.record_failure(provider_name, str(perr), model_id=model_id, transient=transient)
                    notes.append(f"{provider_name}/{model_id}: {perr}")
                    if perr.kind in (ProviderErrorKind.RATE_LIMITED, ProviderErrorKind.QUOTA_EXHAUSTED):
                        self.quota.trigger_cooldown(provider_name, perr.retry_after_seconds, model_id=model_id)
                    if perr.kind in (ProviderErrorKind.UNSUPPORTED_MODEL, ProviderErrorKind.UNSUPPORTED_TOOLS):
                        self.registry.mark_unavailable(provider_name, model_id, str(perr))
                    if not perr.failover_allowed:
                        if perr.kind in (ProviderErrorKind.PAID_MODEL_BLOCKED, ProviderErrorKind.MEDIA_POLICY_BLOCKED, ProviderErrorKind.CANCELLED):
                            raise
                        break
                    continue
        finally:
            self.quota.release_concurrency_slot()

        return None, notes
