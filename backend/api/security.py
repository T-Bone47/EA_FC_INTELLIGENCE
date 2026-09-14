"""Authentication primitives: bcrypt password hashing + JWT sessions.

  * Passwords: bcrypt with per-user salt; plaintext is never stored or logged.
  * Tokens: short-lived JWT access tokens carrying a `jti` that maps to a
    server-side session row -> logout/revocation is real, not cosmetic.
  * Constant-time comparison for login (bcrypt handles it) and generic error
    messages (no user enumeration).
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt

from backend.core.config import get_settings


def hash_password(plain: str) -> str:
    if len(plain.encode()) > 72:
        # bcrypt truncates at 72 bytes; pre-hash longer passphrases deterministically
        plain = hashlib.sha256(plain.encode()).hexdigest()
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        if len(plain.encode()) > 72:
            plain = hashlib.sha256(plain.encode()).hexdigest()
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: uuid.UUID | str, email: str,
                        role: str = "user") -> tuple[str, str, datetime]:
    """Returns (token, jti, expires_at)."""
    settings = get_settings()
    jti = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=settings.access_token_ttl_minutes)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "iss": "ea-fc-player-intelligence",
    }
    token = jwt.encode(payload, settings.effective_jwt_secret(),
                       algorithm=settings.jwt_algorithm)
    return token, jti, expires


def decode_access_token(token: str) -> Optional[dict]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.effective_jwt_secret(),
                          algorithms=[settings.jwt_algorithm],
                          issuer="ea-fc-player-intelligence",
                          options={"require": ["exp", "sub", "jti"]})
    except jwt.PyJWTError:
        return None


def hash_ip(ip: Optional[str]) -> Optional[str]:
    """Store only a salted hash of client IPs (privacy-safe logging)."""
    if not ip:
        return None
    secret = get_settings().effective_jwt_secret()[:16]
    return hashlib.sha256(f"{secret}:{ip}".encode()).hexdigest()[:32]
