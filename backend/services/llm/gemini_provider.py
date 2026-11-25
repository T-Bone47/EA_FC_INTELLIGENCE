"""Google Gemini Free API Provider Adapter built on the official `google-genai` SDK.

Supports:
- Secure backend-only API key auth (`GEMINI_API_KEY`)
- Structured function declarations & multi-turn tool calling
- Native structured JSON Schema outputs (`response_schema` + `response_mime_type`)
- Incremental SSE streaming via `generate_content_stream`
- Bounded retry on transient 5xx, strict error classification & cancellation checks
- Full credential redaction on any raised exceptions
"""
from __future__ import annotations

import base64
import json
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from backend.core.config import Settings, get_settings
from backend.services.llm.contracts import (
    FootballLLMProvider,
    LLMMessage,
    LLMResponse,
    LLMToolCall,
    LLMToolSpec,
    ProviderError,
    ProviderErrorKind,
)
from backend.services.llm.free_guard import GEMINI_FREE_TIER_MODELS
from backend.services.llm.security import redact_secrets


def _json_schema_to_gemini_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitizes JSON Schema constructs unsupported by Gemini FunctionDeclaration."""
    if not isinstance(schema, dict):
        return {}
    cleaned: Dict[str, Any] = {}
    for k, v in schema.items():
        if k in ("$schema", "additionalProperties", "default", "title"):
            continue
        if k == "anyOf" and isinstance(v, list):
            # Collapse simple Optional[T] = anyOf[T, null] cleanly
            non_null = [item for item in v if isinstance(item, dict) and item.get("type") != "null"]
            if non_null:
                merged = _json_schema_to_gemini_schema(non_null[0])
                cleaned.update(merged)
            continue
        if k == "properties" and isinstance(v, dict):
            cleaned[k] = {pk: _json_schema_to_gemini_schema(pv) for pk, pv in v.items()}
        elif k == "items" and isinstance(v, dict):
            cleaned[k] = _json_schema_to_gemini_schema(v)
        else:
            cleaned[k] = v
    if cleaned.get("type") == "object" and not cleaned.get("properties"):
        cleaned["properties"] = {}
    return cleaned


class GeminiProvider(FootballLLMProvider):
    """Gemini API adapter enforcing official `google-genai` SDK & strict free safety."""

    provider_name = "gemini"

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    def _client(self, timeout_seconds: float) -> genai.Client:
        key = (self.settings.gemini_api_key or "").strip()
        if not key:
            raise ProviderError(
                ProviderErrorKind.AUTH_ERROR,
                "GEMINI_API_KEY is not configured.",
                provider="gemini",
                failover_allowed=True,
            )
        timeout_ms = max(2000, int(timeout_seconds * 1000))
        return genai.Client(
            api_key=key,
            http_options=types.HttpOptions(timeout=timeout_ms),
        )

    def _build_contents_and_system(
        self, messages: List[LLMMessage]
    ) -> tuple[Optional[str], List[types.Content]]:
        sys_parts: List[str] = []
        contents: List[types.Content] = []
        for msg in messages:
            if msg.role == "system":
                if msg.content:
                    sys_parts.append(msg.content)
                continue
            if msg.provider_parts:
                role = "model" if msg.role == "assistant" else "user"
                contents.append(types.Content(role=role, parts=msg.provider_parts))
                continue
            if msg.role == "assistant":
                parts: List[types.Part] = []
                if msg.content:
                    parts.append(types.Part.from_text(text=msg.content))
                for tc in msg.tool_calls:
                    parts.append(types.Part.from_function_call(name=tc.name, args=tc.arguments))
                if parts:
                    contents.append(types.Content(role="model", parts=parts))
                continue
            if msg.role == "tool":
                try:
                    resp_obj = json.loads(msg.content) if msg.content else {}
                    if not isinstance(resp_obj, dict):
                        resp_obj = {"result": resp_obj}
                except Exception:
                    resp_obj = {"result": msg.content}
                part = types.Part.from_function_response(
                    name=msg.tool_name or "tool_result",
                    response=resp_obj,
                )
                if contents and contents[-1].role == "user" and any(p.function_response is not None for p in (contents[-1].parts or [])):
                    contents[-1].parts.append(part)
                else:
                    contents.append(types.Content(role="user", parts=[part]))
                continue
            # user message
            user_parts: List[types.Part] = []
            if msg.content:
                user_parts.append(types.Part.from_text(text=msg.content))
            if msg.image_b64 and msg.image_mime:
                raw_bytes = base64.b64decode(msg.image_b64)
                user_parts.append(types.Part.from_bytes(data=raw_bytes, mime_type=msg.image_mime))
            if user_parts:
                contents.append(types.Content(role="user", parts=user_parts))

        system_instruction = "\n\n".join(sys_parts) if sys_parts else None
        return system_instruction, contents

    def _build_config(
        self,
        *,
        system_instruction: Optional[str],
        tools: Optional[List[LLMToolSpec]],
        response_schema: Optional[Dict[str, Any]],
        temperature: float,
        max_output_tokens: int,
    ) -> types.GenerateContentConfig:
        gemini_tools = None
        if tools:
            decls = [
                types.FunctionDeclaration(
                    name=t.name,
                    description=t.description[:512],
                    parameters_json_schema=_json_schema_to_gemini_schema(t.parameters_json_schema),
                )
                for t in tools
            ]
            gemini_tools = [types.Tool(function_declarations=decls)]

        kwargs: Dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
            "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True),
        }
        if system_instruction:
            kwargs["system_instruction"] = system_instruction
        if gemini_tools and not response_schema:
            kwargs["tools"] = gemini_tools
        if response_schema and not gemini_tools:
            kwargs["response_mime_type"] = "application/json"
            kwargs["response_json_schema"] = _json_schema_to_gemini_schema(response_schema)
        elif gemini_tools and response_schema:
            # Tools take precedence during ReAct rounds; final structured response runs after tool phase
            kwargs["tools"] = gemini_tools
        return types.GenerateContentConfig(**kwargs)

    def _classify_exception(self, exc: Exception, model: str) -> ProviderError:
        key = self.settings.gemini_api_key or ""
        msg = redact_secrets(str(exc), [key])
        if isinstance(exc, ProviderError):
            return exc
        code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        lower = msg.lower()
        if code in (401, 403) or "api key" in lower or "permission_denied" in lower or "unauthenticated" in lower:
            return ProviderError(
                ProviderErrorKind.AUTH_ERROR,
                f"Gemini authentication/permission error: {msg[:180]}",
                provider="gemini",
                model=model,
                status_code=code,
                failover_allowed=False,
            )
        if code == 429 or "resource_exhausted" in lower or "quota" in lower or "rate limit" in lower:
            kind = ProviderErrorKind.QUOTA_EXHAUSTED if "quota" in lower else ProviderErrorKind.RATE_LIMITED
            return ProviderError(
                kind,
                f"Gemini free quota/rate limit reached ({model}): {msg[:180]}",
                provider="gemini",
                model=model,
                status_code=429,
                retry_after_seconds=60.0,
                retryable_same_provider=False,
                failover_allowed=True,
            )
        if code == 404 or "not found" in lower or "unsupported model" in lower:
            return ProviderError(
                ProviderErrorKind.UNSUPPORTED_MODEL,
                f"Gemini model unavailable ({model}): {msg[:180]}",
                provider="gemini",
                model=model,
                status_code=code,
                failover_allowed=True,
            )
        if "timeout" in lower or "timed out" in lower or "deadline" in lower:
            return ProviderError(
                ProviderErrorKind.TIMEOUT,
                f"Gemini request timed out ({model}).",
                provider="gemini",
                model=model,
                status_code=code,
                retryable_same_provider=False,
                failover_allowed=True,
            )
        if code and int(code) >= 500:
            return ProviderError(
                ProviderErrorKind.TRANSIENT_SERVER_ERROR,
                f"Gemini transient server error HTTP {code}: {msg[:160]}",
                provider="gemini",
                model=model,
                status_code=int(code),
                retryable_same_provider=False,
                failover_allowed=True,
            )
        if "safety" in lower or "blocked" in lower:
            return ProviderError(
                ProviderErrorKind.SAFETY_BLOCKED,
                f"Gemini response blocked by safety policy: {msg[:160]}",
                provider="gemini",
                model=model,
                status_code=code,
                failover_allowed=False,
            )
        return ProviderError(
            ProviderErrorKind.UNAVAILABLE,
            f"Gemini call failed ({type(exc).__name__}): {msg[:180]}",
            provider="gemini",
            model=model,
            status_code=code,
            failover_allowed=True,
        )

    def _extract_response(self, resp: Any, model: str, elapsed_ms: float) -> LLMResponse:
        usage = getattr(resp, "usage_metadata", None)
        in_tok = int(getattr(usage, "prompt_token_count", 0) or 0)
        out_tok = int(getattr(usage, "candidates_token_count", 0) or 0)
        tot_tok = int(getattr(usage, "total_token_count", in_tok + out_tok) or (in_tok + out_tok))

        text_chunks: List[str] = []
        tool_calls: List[LLMToolCall] = []
        raw_parts: List[Any] = []
        finish_reason = None

        candidates = getattr(resp, "candidates", None) or []
        if candidates:
            c0 = candidates[0]
            finish_reason = str(getattr(c0, "finish_reason", "") or "")
            if finish_reason and "SAFETY" in finish_reason.upper():
                raise ProviderError(
                    ProviderErrorKind.SAFETY_BLOCKED,
                    f"Gemini stopped generation with finish_reason={finish_reason}",
                    provider="gemini",
                    model=model,
                    failover_allowed=False,
                )
            content = getattr(c0, "content", None)
            parts = getattr(content, "parts", None) or []
            raw_parts = list(parts)
            for idx, p in enumerate(parts):
                if getattr(p, "thought", False):
                    continue
                if getattr(p, "text", None):
                    text_chunks.append(str(p.text))
                fc = getattr(p, "function_call", None)
                if fc is not None and getattr(fc, "name", None):
                    args = dict(getattr(fc, "args", None) or {})
                    call_id = str(getattr(fc, "id", None) or f"gem-call-{idx}")
                    tool_calls.append(LLMToolCall(call_id=call_id, name=str(fc.name), arguments=args))
        elif getattr(resp, "text", None):
            text_chunks.append(str(resp.text))

        full_text = "".join(text_chunks).strip()
        structured = None
        if full_text.startswith("{") or full_text.startswith("```json"):
            cleaned = full_text.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.strip("`").lstrip("json").strip()
            try:
                parsed = json.loads(cleaned)
                if isinstance(parsed, dict):
                    structured = parsed
            except Exception:
                structured = None

        return LLMResponse(
            provider="gemini",
            model=model,
            text=full_text,
            tool_calls=tool_calls,
            structured_json=structured,
            prompt_tokens=in_tok,
            completion_tokens=out_tok,
            total_tokens=tot_tok,
            reported_cost_usd=0.0,
            latency_ms=round(elapsed_ms, 2),
            finish_reason=finish_reason,
            raw_provider_parts=raw_parts,
        )

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
        if cancel_event and cancel_event.is_set():
            raise ProviderError(ProviderErrorKind.CANCELLED, "Request cancelled.", provider="gemini", model=model, failover_allowed=False)

        client = self._client(timeout_seconds)
        system_instruction, contents = self._build_contents_and_system(messages)
        cfg = self._build_config(
            system_instruction=system_instruction,
            tools=tools,
            response_schema=response_schema,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

        last_err: Optional[ProviderError] = None
        for attempt in range(2):
            if cancel_event and cancel_event.is_set():
                raise ProviderError(ProviderErrorKind.CANCELLED, "Request cancelled.", provider="gemini", model=model, failover_allowed=False)
            t0 = time.perf_counter()
            try:
                resp = client.models.generate_content(model=model, contents=contents, config=cfg)
                return self._extract_response(resp, model, (time.perf_counter() - t0) * 1000.0)
            except Exception as exc:
                perr = self._classify_exception(exc, model)
                last_err = perr
                if perr.retryable_same_provider and attempt == 0:
                    time.sleep(0.4)
                    continue
                raise perr from exc
        raise last_err or ProviderError(ProviderErrorKind.UNAVAILABLE, "Gemini call failed.", provider="gemini", model=model)

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
        client = self._client(timeout_seconds)
        system_instruction, contents = self._build_contents_and_system(messages)
        cfg = self._build_config(
            system_instruction=system_instruction,
            tools=tools,
            response_schema=response_schema,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        t0 = time.perf_counter()
        first_token_ms = 0.0
        text_parts: List[str] = []
        tool_calls: List[LLMToolCall] = []
        raw_parts: List[Any] = []
        in_tok = 0
        out_tok = 0
        tot_tok = 0
        finish_reason = None
        try:
            stream = client.models.generate_content_stream(model=model, contents=contents, config=cfg)
            for chunk in stream:
                if cancel_event and cancel_event.is_set():
                    raise ProviderError(ProviderErrorKind.CANCELLED, "Request cancelled during stream.", provider="gemini", model=model, failover_allowed=False)
                usage = getattr(chunk, "usage_metadata", None)
                if usage:
                    in_tok = int(getattr(usage, "prompt_token_count", in_tok) or in_tok)
                    out_tok = int(getattr(usage, "candidates_token_count", out_tok) or out_tok)
                    tot_tok = int(getattr(usage, "total_token_count", in_tok + out_tok) or (in_tok + out_tok))
                cands = getattr(chunk, "candidates", None) or []
                if cands:
                    c0 = cands[0]
                    finish_reason = str(getattr(c0, "finish_reason", finish_reason or "") or finish_reason or "")
                    content = getattr(c0, "content", None)
                    for idx, p in enumerate(getattr(content, "parts", None) or []):
                        raw_parts.append(p)
                        if getattr(p, "thought", False):
                            continue
                        ptxt = getattr(p, "text", None)
                        if ptxt:
                            if first_token_ms <= 0.0:
                                first_token_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                            s = str(ptxt)
                            text_parts.append(s)
                            if on_chunk:
                                on_chunk(s)
                        fc = getattr(p, "function_call", None)
                        if fc is not None and getattr(fc, "name", None):
                            if first_token_ms <= 0.0:
                                first_token_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                            tool_calls.append(
                                LLMToolCall(
                                    call_id=str(getattr(fc, "id", None) or f"gem-call-{len(tool_calls)}-{idx}"),
                                    name=str(fc.name),
                                    arguments=dict(getattr(fc, "args", None) or {}),
                                )
                            )
            full_text = "".join(text_parts).strip()
            structured = None
            if full_text.startswith("{") or full_text.startswith("```json"):
                cleaned = full_text.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.strip("`").lstrip("json").strip()
                try:
                    parsed = json.loads(cleaned)
                    if isinstance(parsed, dict):
                        structured = parsed
                except Exception:
                    structured = None
            total_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            return LLMResponse(
                provider="gemini",
                model=model,
                text=full_text,
                tool_calls=tool_calls,
                structured_json=structured,
                prompt_tokens=in_tok,
                completion_tokens=out_tok,
                total_tokens=tot_tok or (in_tok + out_tok),
                reported_cost_usd=0.0,
                latency_ms=total_ms,
                ttft_ms=first_token_ms or total_ms,
                finish_reason=finish_reason,
                raw_provider_parts=raw_parts,
            )
        except Exception as exc:
            raise self._classify_exception(exc, model) from exc

    def health_check(self) -> Dict[str, Any]:
        return {
            "provider": "gemini",
            "sdk": "google-genai",
            "key_configured": self.settings.has_gemini_key(),
            "configured_model": self.settings.gemini_model,
            "free_allowlist_size": len(GEMINI_FREE_TIER_MODELS),
        }
