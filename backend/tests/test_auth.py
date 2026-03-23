"""AUTH-001: Tests for authentication service and endpoints.

Covers:
- Password hashing and verification (unit)
- JWT creation and decoding (unit)
- Register, login, refresh, /me endpoints (integration)
- Role-based access control (integration)

All tests use asyncio_mode="auto" (configured in pyproject.toml).
The in-memory SQLite session from conftest is overridden via dependency injection
into a TestClient so that no real database or network calls are made.
"""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_async_db
from app.main import create_application
from app.models.user import User
from app.services.auth_service import register_user
from app.schemas.auth import RegisterRequest

settings = get_settings()

# ── Helpers ───────────────────────────────────────────────────────────────────

_PLAIN_PW = "S3cur3P@ssw0rd!"
_ADMIN_EMAIL = "admin@solarintel.sn"
_CLIENT_EMAIL = "client@solarintel.sn"
_USER_EMAIL = "user@solarintel.sn"


# ── App fixture with DB override ──────────────────────────────────────────────


@pytest_asyncio.fixture()
async def test_app(async_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """FastAPI TestClient whose get_async_db is overridden with the test session.

    Args:
        async_session: In-memory SQLite session from conftest.

    Yields:
        An httpx.AsyncClient wired to the FastAPI app under test.
    """

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield async_session

    application: FastAPI = create_application()
    application.dependency_overrides[get_async_db] = _override_db

    transport = ASGITransport(app=application)  # type: ignore[arg-type]
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        yield client


# ── User fixtures ─────────────────────────────────────────────────────────────


@pytest_asyncio.fixture()
async def registered_user(async_session: AsyncSession) -> User:
    """A standard active technicien user persisted to the test DB."""
    data = RegisterRequest(
        email=_USER_EMAIL,
        password=_PLAIN_PW,
        full_name="Test User",
        role="technicien",
    )
    user = await register_user(async_session, data)
    return user


@pytest_asyncio.fixture()
async def admin_user(async_session: AsyncSession) -> User:
    """An admin user persisted to the test DB."""
    data = RegisterRequest(
        email=_ADMIN_EMAIL,
        password=_PLAIN_PW,
        full_name="Admin User",
        role="admin",
    )
    user = await register_user(async_session, data)
    return user


@pytest_asyncio.fixture()
async def client_user(async_session: AsyncSession) -> User:
    """A client-role user persisted to the test DB."""
    data = RegisterRequest(
        email=_CLIENT_EMAIL,
        password=_PLAIN_PW,
        full_name="Client User",
        role="client",
    )
    user = await register_user(async_session, data)
    return user


def auth_headers(user: User) -> dict[str, str]:
    """Return a Bearer Authorization header for the given user.

    Args:
        user: The authenticated user whose JWT should be issued.

    Returns:
        Dict containing the ``Authorization`` header value.
    """
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


# ═════════════════════════════════════════════════════════════════════════════
# ── UNIT TESTS: password hashing ─────────────────────────────────────────────
# ═════════════════════════════════════════════════════════════════════════════


def test_hash_password() -> None:
    """Hashed password differs from plaintext and verifies correctly."""
    hashed = hash_password(_PLAIN_PW)
    assert hashed != _PLAIN_PW
    assert verify_password(_PLAIN_PW, hashed) is True


def test_verify_password_wrong() -> None:
    """Wrong password returns False from verify_password."""
    hashed = hash_password(_PLAIN_PW)
    assert verify_password("WrongP@ssw0rd!", hashed) is False


# ═════════════════════════════════════════════════════════════════════════════
# ── UNIT TESTS: JWT creation and decoding ────────────────────────────────────
# ═════════════════════════════════════════════════════════════════════════════


def test_create_access_token() -> None:
    """Access token contains sub, role, type=access; exp ≈ 30 min from now."""
    user_id = uuid4()
    token = create_access_token(user_id, "technicien")
    payload = decode_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["role"] == "technicien"
    assert payload["type"] == "access"

    now = int(time.time())
    expected_exp = now + settings.access_token_expire_minutes * 60
    # Allow ±10 s clock drift
    assert abs(payload["exp"] - expected_exp) < 10


def test_create_refresh_token() -> None:
    """Refresh token contains type=refresh; exp ≈ 7 days from now."""
    user_id = uuid4()
    token = create_refresh_token(user_id)
    payload = decode_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["type"] == "refresh"

    now = int(time.time())
    expected_exp = now + settings.refresh_token_expire_days * 86400
    assert abs(payload["exp"] - expected_exp) < 10


def test_decode_valid_token() -> None:
    """decode_token returns the correct payload for a valid access token."""
    user_id = uuid4()
    token = create_access_token(user_id, "admin")
    payload = decode_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["role"] == "admin"


def test_decode_expired_token() -> None:
    """decode_token raises HTTPException 401 for an expired token."""
    from fastapi import HTTPException
    from jose import jwt

    expired_payload = {
        "sub": str(uuid4()),
        "role": "technicien",
        "type": "access",
        "exp": int(time.time()) - 3600,  # expired 1 hour ago
    }
    token = jwt.encode(
        expired_payload, settings.secret_key, algorithm=settings.algorithm
    )

    with pytest.raises(HTTPException) as exc_info:
        decode_token(token)

    assert exc_info.value.status_code == 401


def test_decode_tampered_token() -> None:
    """decode_token raises HTTPException 401 for a tampered token."""
    from fastapi import HTTPException

    user_id = uuid4()
    token = create_access_token(user_id, "admin")
    tampered = token[:-4] + "XXXX"

    with pytest.raises(HTTPException) as exc_info:
        decode_token(tampered)

    assert exc_info.value.status_code == 401


# ═════════════════════════════════════════════════════════════════════════════
# ── INTEGRATION TESTS: /api/v2/auth/* endpoints ───────────────────────────────
# ═════════════════════════════════════════════════════════════════════════════


async def test_register_success(test_app: AsyncClient) -> None:
    """POST /register returns 201 with email and role."""
    response = await test_app.post(
        "/api/v2/auth/register",
        json={
            "email": "new@solarintel.sn",
            "password": "StrongP@ss1!",
            "full_name": "New User",
            "role": "technicien",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new@solarintel.sn"
    assert body["role"] == "technicien"
    assert "id" in body
    assert "hashed_password" not in body


async def test_register_duplicate_email(test_app: AsyncClient) -> None:
    """POST /register with a duplicate email returns 409."""
    payload = {
        "email": "dup@solarintel.sn",
        "password": "StrongP@ss1!",
    }
    r1 = await test_app.post("/api/v2/auth/register", json=payload)
    assert r1.status_code == 201

    r2 = await test_app.post("/api/v2/auth/register", json=payload)
    assert r2.status_code == 409


async def test_register_invalid_email(test_app: AsyncClient) -> None:
    """POST /register with a malformed email returns 422."""
    response = await test_app.post(
        "/api/v2/auth/register",
        json={"email": "not-an-email", "password": "StrongP@ss1!"},
    )
    assert response.status_code == 422


async def test_login_success(
    test_app: AsyncClient, registered_user: User
) -> None:
    """POST /login returns 200 with access_token, refresh_token, token_type."""
    response = await test_app.post(
        "/api/v2/auth/login",
        json={"email": _USER_EMAIL, "password": _PLAIN_PW},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


async def test_login_wrong_password(
    test_app: AsyncClient, registered_user: User
) -> None:
    """POST /login with wrong password returns 401."""
    response = await test_app.post(
        "/api/v2/auth/login",
        json={"email": _USER_EMAIL, "password": "WrongP@ssw0rd!"},
    )
    assert response.status_code == 401


async def test_login_inactive_user(
    test_app: AsyncClient, async_session: AsyncSession, registered_user: User
) -> None:
    """POST /login for an inactive account returns 403."""
    registered_user.is_active = False
    async_session.add(registered_user)
    await async_session.commit()

    response = await test_app.post(
        "/api/v2/auth/login",
        json={"email": _USER_EMAIL, "password": _PLAIN_PW},
    )
    assert response.status_code == 403


async def test_refresh_token(
    test_app: AsyncClient, registered_user: User
) -> None:
    """POST /refresh returns 200 with a new access_token."""
    refresh_tok = create_refresh_token(registered_user.id)
    response = await test_app.post(
        "/api/v2/auth/refresh",
        json={"refresh_token": refresh_tok},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body


async def test_refresh_invalid_token(test_app: AsyncClient) -> None:
    """POST /refresh with a garbage token returns 401."""
    response = await test_app.post(
        "/api/v2/auth/refresh",
        json={"refresh_token": "not.a.valid.token"},
    )
    assert response.status_code == 401


async def test_get_me_authenticated(
    test_app: AsyncClient, registered_user: User
) -> None:
    """GET /me with a valid Bearer token returns 200 with user data."""
    headers = auth_headers(registered_user)
    response = await test_app.get("/api/v2/auth/me", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == _USER_EMAIL
    assert body["role"] == "technicien"


async def test_get_me_unauthenticated(test_app: AsyncClient) -> None:
    """GET /me without a token returns 403 (HTTPBearer rejects missing creds)."""
    response = await test_app.get("/api/v2/auth/me")
    # HTTPBearer returns 403 when the Authorization header is absent
    assert response.status_code == 403


# ═════════════════════════════════════════════════════════════════════════════
# ── INTEGRATION TESTS: role-based access control ─────────────────────────────
# ═════════════════════════════════════════════════════════════════════════════


async def test_role_admin_access(
    test_app: AsyncClient, admin_user: User
) -> None:
    """Admin user can reach the admin-gated /me endpoint as a proxy for RBAC.

    The /api/v2/auth/me endpoint itself is accessible by any authenticated user.
    We test that an admin token is accepted without a 401/403.
    """
    headers = auth_headers(admin_user)
    response = await test_app.get("/api/v2/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


async def test_role_client_forbidden(
    test_app: AsyncClient, client_user: User
) -> None:
    """Client-role user is blocked from the admin-only diagnostic endpoint."""
    headers = auth_headers(client_user)
    # /api/v2/auth/admin-only is gated to admin + commercial only
    response = await test_app.get(
        "/api/v2/auth/admin-only", headers=headers
    )
    assert response.status_code == 403
