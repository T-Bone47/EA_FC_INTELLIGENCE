"""Authentication routes: signup / login / logout / me / profile.

Security properties:
  * bcrypt password hashing (never plaintext, never logged)
  * generic credentials error (no user enumeration)
  * strict rate limiting on auth endpoints
  * server-revocable sessions (jti -> user_session row)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from backend.api.deps import CurrentUser, current_user_required, rate_limit_auth
from backend.api.schemas import LoginRequest, ProfileUpdate, SignupRequest, TokenResponse
from backend.api.security import (
    create_access_token, hash_ip, hash_password, verify_password,
)
from backend.core.config import get_settings
from backend.repositories.user_repository import UserRepository

router = APIRouter(prefix="/api/auth", tags=["auth"],
                   dependencies=[Depends(rate_limit_auth)])
users = UserRepository()

GENERIC_CREDS_ERROR = "Invalid email or password."


@router.post("/signup", status_code=201)
def signup(body: SignupRequest, request: Request) -> TokenResponse:
    if users.email_exists(body.email):
        # same generic error as login to avoid user enumeration
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Unable to create account with these details.")
    user = users.create_user(body.email, hash_password(body.password),
                             body.display_name)
    token, jti, expires = create_access_token(user["id"], user["email"])
    users.create_session(user["id"], jti, expires,
                         request.headers.get("user-agent", "")[:300],
                         hash_ip(request.client.host if request.client else None))
    return TokenResponse(
        access_token=token,
        expires_in_minutes=get_settings().access_token_ttl_minutes,
        user={"id": str(user["id"]), "email": user["email"],
              "display_name": user["display_name"], "role": user["role"]})


@router.post("/login")
def login(body: LoginRequest, request: Request) -> TokenResponse:
    row = users.get_by_email(body.email)
    if row is None or not row["is_active"] or not verify_password(body.password,
                                                                  row["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail=GENERIC_CREDS_ERROR)
    users.touch_login(row["id"])
    token, jti, expires = create_access_token(row["id"], row["email"], row["role"])
    users.create_session(row["id"], jti, expires,
                         request.headers.get("user-agent", "")[:300],
                         hash_ip(request.client.host if request.client else None))
    return TokenResponse(
        access_token=token,
        expires_in_minutes=get_settings().access_token_ttl_minutes,
        user={"id": str(row["id"]), "email": row["email"],
              "display_name": row["display_name"], "role": row["role"]})


@router.post("/logout", status_code=204)
def logout(user: CurrentUser = Depends(current_user_required)) -> None:
    users.revoke_session(user.jti)


@router.post("/logout-all", status_code=204)
def logout_all(user: CurrentUser = Depends(current_user_required)) -> None:
    users.revoke_all_for_user(user.id)


@router.get("/me")
def me(user: CurrentUser = Depends(current_user_required)) -> dict:
    row = users.get_by_id(user.id)
    if row is None:
        raise HTTPException(404, "User not found.")
    return {"id": str(row["id"]), "email": row["email"],
            "display_name": row["display_name"], "role": row["role"],
            "preferred_game_version": row["preferred_game_version"],
            "preferences": row["preferences"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "last_login_at": row["last_login_at"].isoformat() if row["last_login_at"] else None}


@router.patch("/me")
def update_me(body: ProfileUpdate,
              user: CurrentUser = Depends(current_user_required)) -> dict:
    if body.preferred_game_version:
        from backend.api.deps import validate_game_version
        validate_game_version(body.preferred_game_version)
    users.update_profile(user.id, body.display_name,
                         body.preferred_game_version.upper()
                         if body.preferred_game_version else None,
                         body.preferences)
    return me(user)
