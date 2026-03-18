"""
Authentication Router
~~~~~~~~~~~~~~~~~~~~~
JWT-based authentication for the PCAP Analyzer API.

Endpoints
---------
POST /auth/login    – validate credentials → access + refresh tokens
POST /auth/refresh  – exchange refresh token → new access token
GET  /auth/me       – return current user profile from token

Token Strategy
--------------
- Access token:  24 h HS256 JWT  (claim: sub=username, type=access)
- Refresh token: 7 d  HS256 JWT  (claim: sub=username, type=refresh)
- Passwords hashed with bcrypt via passlib

The `get_current_user` dependency is importable by other routers that
need to protect their endpoints:

    from logics.api.routers.auth import get_current_user
    ...
    async def my_endpoint(current_user = Depends(get_current_user)):
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext

from logics.api.core.config import settings
from logics.api.models.schema import (
    AuthLoginRequest,
    AuthLoginResponse,
    TokenRefreshRequest,
    UserResponse,
)
from logics.data_layer.postgres.connection import db_pool
from logics.log import get_logger

logger = get_logger(__name__)

# ── Crypto helpers ─────────────────────────────────────────────────────────────

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def _verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def _create_token(data: dict[str, Any], expire_minutes: int) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(username: str) -> str:
    return _create_token(
        {"sub": username, "type": "access"},
        settings.access_token_expire_minutes,
    )


def create_refresh_token(username: str) -> str:
    return _create_token(
        {"sub": username, "type": "refresh"},
        settings.refresh_token_expire_minutes,
    )


# ── DB helpers ─────────────────────────────────────────────────────────────────

async def _get_user_by_username(username: str) -> dict | None:
    """Fetch user row dict from PostgreSQL, or None if not found."""
    pool = db_pool.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, username, email, password FROM users WHERE username = $1",
            username,
        )
    return dict(row) if row else None


# ── Dependency: current user ───────────────────────────────────────────────────

async def get_current_user(token: str = Depends(_oauth2_scheme)) -> dict:
    """
    FastAPI dependency — validates the Bearer JWT and returns the user dict.
    Raises HTTP 401 if the token is invalid or expired.

    Usage::

        @router.get("/protected")
        async def protected(user = Depends(get_current_user)):
            return {"user": user["username"]}
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        username: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        if username is None or token_type != "access":
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    user = await _get_user_by_username(username)
    if user is None:
        raise credentials_exc
    return user


# ── Router ─────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=AuthLoginResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticate with username + password.
    Returns a short-lived access token and a long-lived refresh token.

    The access token should be sent as ``Authorization: Bearer <token>``
    on all protected requests.
    """
    user = await _get_user_by_username(form_data.username)
    if user is None or not _verify_password(form_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(form_data.username)
    logger.info("auth.login | user=%s", form_data.username)
    return AuthLoginResponse(access_token=access_token)


@router.post("/refresh", response_model=AuthLoginResponse)
async def refresh_token(body: TokenRefreshRequest):
    """
    Exchange a valid refresh token for a new access token.
    Useful for keeping long-lived sessions alive without re-entering credentials.
    """
    invalid_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            body.refresh_token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        username: str | None = payload.get("sub")
        if payload.get("type") != "refresh" or username is None:
            raise invalid_exc
    except JWTError:
        raise invalid_exc

    user = await _get_user_by_username(username)
    if user is None:
        raise invalid_exc

    access_token = create_access_token(username)
    logger.info("auth.refresh | user=%s", username)
    return AuthLoginResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return UserResponse(
        username=current_user["username"],
        email=current_user["email"],
    )