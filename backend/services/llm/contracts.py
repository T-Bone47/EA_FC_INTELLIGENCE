"""Provider-independent contracts for Phase 41.5 Football LLM integration."""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable, Dict, Iterator, List, Literal, Optional
import threading

from pydantic import BaseModel, Field


class ProviderErrorKind(str, Enum):
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    RATE_LIMITED = "RATE_LIMITED"
    AUTH_ERROR = "AUTH_ERROR"
    UNSUPPORTED_MODEL = "UNSUPPORTED_MODEL"
    UNSUPPORTED_TOOLS = "UNSUPPORTED_TOOLS"
    SCHEMA_ERROR = "SCHEMA_ERROR"
    PAID_MODEL_BLOCKED = "PAID_MODEL_BLOCKED"
    TIMEOUT = "TIMEOUT"
    TRANSIENT_SERVER_ERROR = "TRANSIENT_SERVER_ERROR"
    SAFETY_BLOCKED = "SAFETY_BLOCKED"
    MEDIA_POLICY_BLOCKED = "MEDIA_POLICY_BLOCKED"
    CANCELLED = "CANCELLED"
    INVALID_REQUEST = "INVALID_REQUEST"
    UNAVAILABLE = "UNAVAILABLE"


class ProviderError(RuntimeError):
    """Classified provider error safe to propagate without credential leakage."""

    def __init__(
        self,
        kind: ProviderErrorKind,
        message: str,
        *,
        provider: str,
        model: Optional[str] = None,
        status_code: Optional[int] = None,
        retry_after_seconds: Optional[float] = None,
        retryable_same_provider: bool = False,
        failover_allowed: bool = True,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.provider = provider
        self.model = model
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        self.retryable_same_provider = retryable_same_provider
        self.failover_allowed = failover_allowed


class LLMToolSpec(BaseModel):
    name: str
    description: str
    parameters_json_schema: Dict[str, Any]


class LLMToolCall(BaseModel):
    call_id: str
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    raw_arguments: Optional[str] = None
    provider_meta: Dict[str, Any] = Field(default_factory=dict)


class LLMMessage(BaseModel):
    """Provider-agnostic normalized message supporting multi-turn tool calling."""
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    tool_calls: List[LLMToolCall] = Field(default_factory=list)
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    image_b64: Optional[str] = None
    image_mime: Optional[str] = None
    provider_parts: Optional[List[Any]] = Field(default=None, exclude=True)


class LLMResponse(BaseModel):
    provider: str
    model: str
    text: str = ""
    tool_calls: List[LLMToolCall] = Field(default_factory=list)
    structured_json: Optional[Dict[str, Any]] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    reported_cost_usd: float = 0.0
    latency_ms: float = 0.0
    ttft_ms: float = 0.0
    finish_reason: Optional[str] = None
    raw_provider_parts: Optional[List[Any]] = Field(default=None, exclude=True)
    generation_id: Optional[str] = None


class LLMStreamChunk(BaseModel):
    delta_text: str = ""
    done: bool = False
    response: Optional[LLMResponse] = None


class ModelCapabilities(BaseModel):
    provider: Literal["gemini", "openrouter"]
    model_id: str
    display_name: str = ""
    context_length: int = 0
    max_output_tokens: int = 4096
    input_modalities: List[str] = Field(default_factory=lambda: ["text"])
    supports_tools: bool = False
    supports_structured_outputs: bool = False
    supports_streaming: bool = True
    supports_reasoning: bool = False
    input_price_usd_per_token: Optional[float] = None
    output_price_usd_per_token: Optional[float] = None
    additional_fees_present: bool = False
    free_tier_eligible: bool = False
    available: bool = True
    last_verified_iso: str = ""
    notes: str = ""


class FootballLLMProvider(ABC):
    """Provider-independent interface for Gemini & OpenRouter free backends."""

    provider_name: str

    @abstractmethod
    def generate(
        self,
        *,
        model: str,
        messages: List[LLMMessage],
        tools: Optional[List[LLMToolSpec]] = None,
        response_schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.2,
        max_output_tokens: int = 1600,
        timeout_seconds: float = 20.0,
        cancel_event: Optional[threading.Event] = None,
        privacy_strict: bool = False,
    ) -> LLMResponse:
        raise NotImplementedError

    def generate_stream(
        self,
        *,
        model: str,
        messages: List[LLMMessage],
        tools: Optional[List[LLMToolSpec]] = None,
        response_schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.2,
        max_output_tokens: int = 1600,
        timeout_seconds: float = 20.0,
        cancel_event: Optional[threading.Event] = None,
        privacy_strict: bool = False,
        on_chunk: Optional[Callable[[str], None]] = None,
    ) -> LLMResponse:
        resp = self.generate(
            model=model,
            messages=messages,
            tools=tools,
            response_schema=response_schema,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            timeout_seconds=timeout_seconds,
            cancel_event=cancel_event,
            privacy_strict=privacy_strict,
        )
        if on_chunk and resp.text:
            on_chunk(resp.text)
        return resp

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        raise NotImplementedError
