"""User + session persistence (authentication layer)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.core.db import execute, get_conn, query, query_one


class UserRepository:
    # ------------------------------------------------------------------ users
    def create_user(self, email: str, password_hash: str,
                    display_name: Optional[str] = None) -> dict:
        row = query_one(
            """INSERT INTO user_profile (email, password_hash, display_name)
               VALUES (lower(%s), %s, %s)
               RETURNING id, email, display_name, role, created_at""",
            (email.strip(), password_hash, display_name))
        return dict(row)  # type: ignore[arg-type]

    def get_by_email(self, email: str) -> Optional[dict]:
        row = query_one(
            """SELECT id, email, password_hash, display_name, role, is_active,
                      preferred_game_version, preferences, created_at, last_login_at
               FROM user_profile WHERE lower(email) = lower(%s)""", (email.strip(),))
        return dict(row) if row else None

    def get_by_id(self, user_id: uuid.UUID | str) -> Optional[dict]:
        row = query_one(
            """SELECT id, email, display_name, role, is_active,
                      preferred_game_version, preferences, created_at, last_login_at
               FROM user_profile WHERE id = %s""", (str(user_id),))
        return dict(row) if row else None

    def email_exists(self, email: str) -> bool:
        return query_one("SELECT 1 FROM user_profile WHERE lower(email)=lower(%s)",
                         (email.strip(),)) is not None

    def touch_login(self, user_id: uuid.UUID | str) -> None:
        execute("UPDATE user_profile SET last_login_at = now() WHERE id=%s", (str(user_id),))

    def update_profile(self, user_id: uuid.UUID | str,
                       display_name: Optional[str] = None,
                       preferred_game_version: Optional[str] = None,
                       preferences: Optional[dict] = None) -> None:
        import json
        execute("""UPDATE user_profile SET
                     display_name = COALESCE(%s, display_name),
                     preferred_game_version = COALESCE(%s, preferred_game_version),
                     preferences = COALESCE(%s::jsonb, preferences),
                     updated_at = now()
                   WHERE id = %s""",
                (display_name, preferred_game_version,
                 json.dumps(preferences) if preferences is not None else None,
                 str(user_id)))

    def update_password(self, user_id: uuid.UUID | str, password_hash: str) -> None:
        execute("UPDATE user_profile SET password_hash=%s, updated_at=now() WHERE id=%s",
                (password_hash, str(user_id)))

    # ------------------------------------------------------------------ sessions
    def create_session(self, user_id: uuid.UUID | str, jti: str,
                       expires_at: datetime, user_agent: Optional[str],
                       ip_hash: Optional[str]) -> None:
        execute("""INSERT INTO user_session (jti, user_profile_id, expires_at,
                                             user_agent, ip_hash)
                   VALUES (%s,%s,%s,%s,%s)""",
                (jti, str(user_id), expires_at, user_agent, ip_hash))

    def session_active(self, jti: str) -> Optional[dict]:
        row = query_one(
            """SELECT s.user_profile_id, s.expires_at, u.is_active
               FROM user_session s JOIN user_profile u ON u.id = s.user_profile_id
               WHERE s.jti=%s AND s.revoked_at IS NULL""", (jti,))
        if not row:
            return None
        if row["expires_at"].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            return None
        if not row["is_active"]:
            return None
        return dict(row)

    def revoke_session(self, jti: str) -> None:
        execute("UPDATE user_session SET revoked_at = now() "
                "WHERE jti=%s AND revoked_at IS NULL", (jti,))

    def revoke_all_for_user(self, user_id: uuid.UUID | str) -> int:
        return execute("UPDATE user_session SET revoked_at = now() "
                       "WHERE user_profile_id=%s AND revoked_at IS NULL", (str(user_id),))
