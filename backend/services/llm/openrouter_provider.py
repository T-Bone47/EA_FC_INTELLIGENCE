"""OpenRouter Free-Model Provider Adapter (https://openrouter.ai/api/v1).

Enforces:
- Strict zero-price provider routing (`allow_fallbacks: false`, `max_price: {"prompt": 0, "completion": 0}`)
- No paid plugins or web-search addons
- OpenAI-compatible function calling + multi-turn tool call loops
- SSE streaming with incremental tool_call argument assembly
- Retry-After cooldown handling & secret redaction
"""
from __future__ import annotations

import json
import threading
import time
from typing import Any, Callable, Dict, List, Optional

import httpx

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
from backend.services.llm.security import redact_secrets


class OpenRouterProvider(FootballLLMProvider):
    """OpenRouter Chat Completions adapter over httpx with free-only guardrails."""

    provider_name = "openrouter"
    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    def _headers(self) -> Dict[str, str]:
        key = (self.settings.openrouter_api_key or "").strip()
        if not key:
            raise ProviderError(
                ProviderErrorKind.AUTH_ERROR,
                "OPENROUTER_API_KEY is not configured.",
                provider="openrouter",
                failover_allowed=False,
            )
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5173",
            "X-Title": "EA FC Intelligence Coach",
        }

    def _serialize_messages(self, messages: List[LLMMessage]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for msg in messages:
            if msg.role == "assistant":
                entry: Dict[str, Any] = {"role": "assistant", "content": msg.content or None}
                if msg.tool_calls:
                    entry["tool_calls"] = [
                        {
                            "id": tc.call_id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in msg.tool_calls
                    ]
                out.append(entry)
            elif msg.role == "tool":
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id or "call_0",
                        "name": msg.tool_name or "tool_result",
                        "content": msg.content,
                    }
                )
            elif msg.role == "user" and msg.image_b64 and msg.image_mime:
                out.append(
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": msg.content or ""},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{msg.image_mime};base64,{msg.image_b64}"},
                            },
                        ],
                    }
                )
            else:
                out.append({"role": msg.role, "content": msg.content})
        return out

    def _build_payload(
        self,
        *,
        model: str,
        messages: List[LLMMessage],
        tools: Optional[List[LLMToolSpec]],
        response_schema: Optional[Dict[str, Any]],
        temperature: float,
        max_output_tokens: int,
        stream: bool,
        privacy_strict: bool,
    ) -> Dict[str, Any]:
        provider_prefs: Dict[str, Any] = {
            "allow_fallbacks": False,
            "require_parameters": True,
            "max_price": {"prompt": 0, "completion": 0},
        }
        if privacy_strict:
            provider_prefs["data_collection"] = "deny"

        payload: Dict[str, Any] = {
            "model": model,
            "messages": self._serialize_messages(messages),
            "temperature": temperature,
            "max_tokens": max_output_tokens,
            "stream": stream,
            "provider": provider_prefs,
        }
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description[:512],
                        "parameters": t.parameters_json_schema,
                    },
                }
                for t in tools
            ]
            payload["tool_choice"] = "auto"
        elif response_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "coach_structured_response",
                    "strict": False,
                    "schema": response_schema,
                },
            }
        return payload

    def _classify_http_error(self, status_code: int, body_text: str, headers: Any, model: str) -> ProviderError:
        msg = redact_secrets(body_text, [self.settings.openrouter_api_key or ""])
        retry_after = None
        try:
            if headers and headers.get("retry-after"):
                retry_after = float(headers["retry-after"])
        except Exception:
            retry_after = None

        if status_code in (401, 403):
            return ProviderError(
                ProviderErrorKind.AUTH_ERROR,
                f"OpenRouter authentication error ({status_code}): {msg[:160]}",
                provider="openrouter",
                model=model,
                status_code=status_code,
                failover_allowed=False,
            )
        if status_code == 402:
            return ProviderError(
                ProviderErrorKind.PAID_MODEL_BLOCKED,
                f"OpenRouter blocked billable request (HTTP 402): {msg[:160]}",
                provider="openrouter",
                model=model,
                status_code=402,
                failover_allowed=False,
            )
        if status_code == 429:
            return ProviderError(
                ProviderErrorKind.RATE_LIMITED,
                f"OpenRouter rate limit (429) on {model}: {msg[:160]}",
                provider="openrouter",
                model=model,
                status_code=429,
                retry_after_seconds=retry_after or 60.0,
                failover_allowed=True,
            )
        if status_code == 404 or "no endpoints found" in msg.lower():
            kind = ProviderErrorKind.UNSUPPORTED_TOOLS if "parameter" in msg.lower() or "tool" in msg.lower() else ProviderErrorKind.UNSUPPORTED_MODEL
            return ProviderError(
                kind,
                f"OpenRouter model/route unavailable ({model}): {msg[:160]}",
                provider="openrouter",
                model=model,
                status_code=status_code,
                failover_allowed=True,
            )
        if status_code >= 500:
            return ProviderError(
                ProviderErrorKind.TRANSIENT_SERVER_ERROR,
                f"OpenRouter server error HTTP {status_code}: {msg[:160]}",
                provider="openrouter",
                model=model,
                status_code=status_code,
                retryable_same_provider=False,
                failover_allowed=True,
            )
        return ProviderError(
            ProviderErrorKind.UNAVAILABLE,
            f"OpenRouter error HTTP {status_code}: {msg[:160]}",
            provider="openrouter",
            model=model,
            status_code=status_code,
            failover_allowed=True,
        )

    def _parse_json_maybe(self, text: str) -> Optional[Dict[str, Any]]:
        cleaned = (text or "").strip()
        if not cleaned:
            return None
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").lstrip("json").strip()
        try:
            parsed = json.loads(cleaned)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start >= 0 and end > start:
                try:
                    parsed = json.loads(cleaned[start : end + 1])
                    return parsed if isinstance(parsed, dict) else None
                except Exception:
                    return None
            return None

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
            raise ProviderError(ProviderErrorKind.CANCELLED, "Request cancelled.", provider="openrouter", model=model, failover_allowed=False)

        payload = self._build_payload(
            model=model,
            messages=messages,
            tools=tools,
            response_schema=response_schema,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            stream=False,
            privacy_strict=privacy_strict,
        )
        headers = self._headers()

        last_err: Optional[ProviderError] = None
        for attempt in range(2):
            if cancel_event and cancel_event.is_set():
                raise ProviderError(ProviderErrorKind.CANCELLED, "Request cancelled.", provider="openrouter", model=model, failover_allowed=False)
            t0 = time.perf_counter()
            try:
                res = httpx.post(f"{self.BASE_URL}/chat/completions", headers=headers, json=payload, timeout=timeout_seconds)
                if res.status_code >= 400:
                    err = self._classify_http_error(res.status_code, res.text, res.headers, model)
                    if err.retryable_same_provider and attempt == 0:
                        last_err = err
                        time.sleep(0.4)
                        continue
                    raise err

                data = res.json()
                actual_model = str(data.get("model") or model)
                choices = data.get("choices") or []
                msg = (choices[0].get("message") or {}) if choices else {}
                finish_reason = str(choices[0].get("finish_reason") or "") if choices else None
                content = str(msg.get("content") or "").strip()

                tcalls: List[LLMToolCall] = []
                for idx, raw_tc in enumerate(msg.get("tool_calls") or []):
                    fn = raw_tc.get("function") or {}
                    raw_args = fn.get("arguments") or "{}"
                    try:
                        parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
                        if not isinstance(parsed_args, dict):
                            parsed_args = {}
                    except Exception:
                        parsed_args = {}
                    tcalls.append(
                        LLMToolCall(
                            call_id=str(raw_tc.get("id") or f"or-call-{idx}"),
                            name=str(fn.get("name") or ""),
                            arguments=parsed_args,
                            raw_arguments=str(raw_args),
                        )
                    )

                usage = data.get("usage") or {}
                in_tok = int(usage.get("prompt_tokens") or 0)
                out_tok = int(usage.get("completion_tokens") or 0)
                tot_tok = int(usage.get("total_tokens") or (in_tok + out_tok))
                cost = float(usage.get("cost") or 0.0)
                if cost > 0.0 and self.settings.ai_coach_free_only:
                    raise ProviderError(
                        ProviderErrorKind.PAID_MODEL_BLOCKED,
                        f"OpenRouter returned non-zero reported cost (${cost}) in free-only mode.",
                        provider="openrouter",
                        model=actual_model,
                        failover_allowed=False,
                    )

                return LLMResponse(
                    provider="openrouter",
                    model=actual_model,
                    text=content,
                    tool_calls=tcalls,
                    structured_json=self._parse_json_maybe(content),
                    prompt_tokens=in_tok,
                    completion_tokens=out_tok,
                    total_tokens=tot_tok,
                    reported_cost_usd=cost,
                    latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                    finish_reason=finish_reason,
                    generation_id=data.get("id"),
                )
            except ProviderError:
                raise
            except httpx.TimeoutException as exc:
                raise ProviderError(ProviderErrorKind.TIMEOUT, f"OpenRouter request timed out ({model}).", provider="openrouter", model=model, failover_allowed=True) from exc
            except Exception as exc:
                raise ProviderError(
                    ProviderErrorKind.UNAVAILABLE,
                    redact_secrets(f"OpenRouter transport error ({type(exc).__name__}): {exc}", [self.settings.openrouter_api_key or ""]),
                    provider="openrouter",
                    model=model,
                    failover_allowed=True,
                ) from exc
        raise last_err or ProviderError(ProviderErrorKind.UNAVAILABLE, "OpenRouter request failed.", provider="openrouter", model=model)

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
        if cancel_event and cancel_event.is_set():
            raise ProviderError(ProviderErrorKind.CANCELLED, "Request cancelled.", provider="openrouter", model=model, failover_allowed=False)

        payload = self._build_payload(
            model=model,
            messages=messages,
            tools=tools,
            response_schema=response_schema,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            stream=True,
            privacy_strict=privacy_strict,
        )
        headers = self._headers()
        t0 = time.perf_counter()
        first_token_ms = 0.0
        text_parts: List[str] = []
        tc_acc: Dict[int, Dict[str, Any]] = {}
        actual_model = model
        finish_reason = None
        in_tok = 0
        out_tok = 0
        cost = 0.0

        try:
            with httpx.stream("POST", f"{self.BASE_URL}/chat/completions", headers=headers, json=payload, timeout=timeout_seconds) as res:
                if res.status_code >= 400:
                    body = res.read().decode("utf-8", errors="replace")
                    raise self._classify_http_error(res.status_code, body, res.headers, model)
                for line in res.iter_lines():
                    if cancel_event and cancel_event.is_set():
                        raise ProviderError(ProviderErrorKind.CANCELLED, "Request cancelled during stream.", provider="openrouter", model=model, failover_allowed=False)
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                    except Exception:
                        continue
                    if chunk.get("model"):
                        actual_model = str(chunk["model"])
                    if chunk.get("usage"):
                        u = chunk["usage"]
                        in_tok = int(u.get("prompt_tokens") or in_tok)
                        out_tok = int(u.get("completion_tokens") or out_tok)
                        cost = float(u.get("cost") or cost)
                    for ch in chunk.get("choices") or []:
                        if ch.get("finish_reason"):
                            finish_reason = str(ch["finish_reason"])
                        delta = ch.get("delta") or {}
                        txt = delta.get("content")
                        if txt:
                            if first_token_ms <= 0.0:
                                first_token_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                            s = str(txt)
                            text_parts.append(s)
                            if on_chunk:
                                on_chunk(s)
                        for dtc in delta.get("tool_calls") or []:
                            if first_token_ms <= 0.0:
                                first_token_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                            idx = int(dtc.get("index") or 0)
                            bucket = tc_acc.setdefault(idx, {"id": f"or-call-{idx}", "name": "", "args": ""})
                            if dtc.get("id"):
                                bucket["id"] = str(dtc["id"])
                            fn = dtc.get("function") or {}
                            if fn.get("name"):
                                bucket["name"] += str(fn["name"])
                            if fn.get("arguments"):
                                bucket["args"] += str(fn["arguments"])
        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderError(ProviderErrorKind.TIMEOUT, f"OpenRouter stream timed out ({model}).", provider="openrouter", model=model, failover_allowed=True) from exc
        except Exception as exc:
            raise ProviderError(
                ProviderErrorKind.UNAVAILABLE,
                redact_secrets(f"OpenRouter stream error ({type(exc).__name__}): {exc}", [self.settings.openrouter_api_key or ""]),
                provider="openrouter",
                model=model,
                failover_allowed=True,
            ) from exc

        tcalls: List[LLMToolCall] = []
        for idx in sorted(tc_acc):
            b = tc_acc[idx]
            try:
                parsed_args = json.loads(b["args"]) if b["args"] else {}
                if not isinstance(parsed_args, dict):
                    parsed_args = {}
            except Exception:
                parsed_args = {}
            tcalls.append(LLMToolCall(call_id=b["id"], name=b["name"], arguments=parsed_args, raw_arguments=b["args"]))

        full_text = "".join(text_parts).strip()
        total_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return LLMResponse(
            provider="openrouter",
            model=actual_model,
            text=full_text,
            tool_calls=tcalls,
            structured_json=self._parse_json_maybe(full_text),
            prompt_tokens=in_tok,
            completion_tokens=out_tok,
            total_tokens=in_tok + out_tok,
            reported_cost_usd=cost,
            latency_ms=total_ms,
            ttft_ms=first_token_ms or total_ms,
            finish_reason=finish_reason,
        )

    def health_check(self) -> Dict[str, Any]:
        return {
            "provider": "openrouter",
            "base_url": self.BASE_URL,
            "key_configured": self.settings.has_openrouter_key(),
            "configured_model": self.settings.openrouter_model,
        }
