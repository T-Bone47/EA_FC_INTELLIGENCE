"""Phase 41.5 Hybrid Agentic LLM Package (Gemini Free API & OpenRouter Free Tiers)."""
from backend.services.llm.contracts import (
    FootballLLMProvider,
    LLMMessage,
    LLMResponse,
    LLMStreamChunk,
    LLMToolCall,
    LLMToolSpec,
    ModelCapabilities,
    ProviderError,
    ProviderErrorKind,
)
from backend.services.llm.free_guard import (
    GEMINI_FREE_TIER_MODELS,
    FreeUsageGuard,
    PaidModelBlockedError,
    QuotaManager,
    TurnBudgetTracker,
)
from backend.services.llm.gemini_provider import GeminiProvider
from backend.services.llm.openrouter_provider import OpenRouterProvider
from backend.services.llm.registry import ModelCapabilityRegistry, ProviderHealthMonitor
from backend.services.llm.router import FootballModelRouter, RoutingDecision, TaskIntent
from backend.services.llm.security import redact_dict, redact_secrets, sanitize_untrusted_text

__all__ = [
    "FootballLLMProvider",
    "FootballModelRouter",
    "FreeUsageGuard",
    "GEMINI_FREE_TIER_MODELS",
    "GeminiProvider",
    "LLMMessage",
    "LLMResponse",
    "LLMStreamChunk",
    "LLMToolCall",
    "LLMToolSpec",
    "ModelCapabilities",
    "ModelCapabilityRegistry",
    "OpenRouterProvider",
    "PaidModelBlockedError",
    "ProviderError",
    "ProviderErrorKind",
    "ProviderHealthMonitor",
    "QuotaManager",
    "RoutingDecision",
    "TaskIntent",
    "TurnBudgetTracker",
    "redact_dict",
    "redact_secrets",
    "sanitize_untrusted_text",
]
