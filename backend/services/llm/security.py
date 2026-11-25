"""Security utilities: secret redaction, untrusted input framing & media consent gate."""
from __future__ import annotations

import os
import re
from typing import Any, Dict, Iterable, Optional

_SECRET_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
    re.compile(r"sk-or-v1-[0-9a-fA-F]{20,}"),
    re.compile(r"sk-[A-Za-z0-9\-_]{20,}"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9\._\-]{16,}"),
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[=:]\s*['\"]?([^\s'\",;]{8,})['\"]?"),
]

ALLOWED_IMAGE_MIMES = {"image/png", "image/jpeg", "image/webp"}
MAX_IMAGE_BYTES = 4 * 1024 * 1024  # 4 MB hard limit


def _active_env_secrets() -> list[str]:
    vals: list[str] = []
    for k in ("GEMINI_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY", "JWT_SECRET"):
        v = (os.environ.get(k) or "").strip()
        if len(v) >= 8:
            vals.append(v)
    return vals


def redact_secrets(text: str, extra_secrets: Iterable[str] = ()) -> str:
    """Scrubs known API keys, tokens, and credential patterns from any text/log."""
    if not text:
        return ""
    out = str(text)
    for secret in [*_active_env_secrets(), *[s for s in extra_secrets if s and len(s) >= 8]]:
        if secret in out:
            out = out.replace(secret, "[REDACTED_SECRET]")
    out = _SECRET_PATTERNS[0].sub("[REDACTED_GEMINI_KEY]", out)
    out = _SECRET_PATTERNS[1].sub("[REDACTED_OPENROUTER_KEY]", out)
    out = _SECRET_PATTERNS[2].sub("[REDACTED_API_KEY]", out)
    out = _SECRET_PATTERNS[3].sub(r"\1[REDACTED_TOKEN]", out)
    out = _SECRET_PATTERNS[4].sub(r"\1=[REDACTED]", out)
    return out


_SAFE_TOKEN_COUNT_KEYS = {"token_usage", "max_output_tokens", "prompt_tokens", "completion_tokens", "total_tokens"}


def redact_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively redacts sensitive keys/values inside dictionaries before logging."""
    cleaned: Dict[str, Any] = {}
    for k, v in data.items():
        kl = str(k).lower()
        is_secret_key = kl not in _SAFE_TOKEN_COUNT_KEYS and any(
            tok in kl for tok in ("api_key", "secret", "password", "authorization", "token")
        )
        if is_secret_key:
            cleaned[k] = "[REDACTED]"
        elif isinstance(v, dict):
            cleaned[k] = redact_dict(v)
        elif isinstance(v, str):
            cleaned[k] = redact_secrets(v)
        else:
            cleaned[k] = v
    return cleaned


def sanitize_untrusted_text(text: str, max_len: int = 2000) -> str:
    """Normalizes untrusted prompt/document content and strips control chars."""
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", str(text or "")).strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len] + "…"
    return redact_secrets(cleaned)


def check_media_transmission_allowed(
    *,
    media_type: str,
    allow_external_images: bool,
    allow_external_video: bool,
    user_consent_media: bool,
    mime_type: Optional[str] = None,
    byte_length: int = 0,
) -> tuple[bool, Optional[str]]:
    """Enforces default-disabled external media transmission & validation gates."""
    mtype = media_type.lower()
    if mtype == "video":
        if not allow_external_video or not user_consent_media:
            return False, "External LLM video upload is disabled by default privacy & policy guard (AI_COACH_ALLOW_EXTERNAL_VIDEO=false)."
        return False, "External raw video transmission remains restricted in Phase 41.5; use local Gameplay Studio CV decoding instead."
    if mtype == "image":
        if not allow_external_images:
            return False, "External LLM image upload is disabled by server configuration (AI_COACH_ALLOW_EXTERNAL_IMAGES=false)."
        if not user_consent_media:
            return False, "Explicit per-request image upload consent is required before sending screenshots externally."
        if mime_type not in ALLOWED_IMAGE_MIMES:
            return False, f"Unsupported screenshot MIME type {mime_type!r}; allowed: {sorted(ALLOWED_IMAGE_MIMES)}."
        if byte_length <= 0 or byte_length > MAX_IMAGE_BYTES:
            return False, f"Screenshot size {byte_length}B violates 1B..{MAX_IMAGE_BYTES}B safety limit."
        return True, None
    return False, f"Unsupported external media type {media_type!r}."
