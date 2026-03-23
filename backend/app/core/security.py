"""JWT token creation, verification, and FastAPI auth dependencies.

Provides:
- ``hash_password`` / ``verify_password``: bcrypt helpers.
- ``create_access_token`` / ``create_refresh_token``: JWT issuance.
- ``decode_token``: Validates and decodes a JWT string.
- ``get_current_user``: FastAPI dependency for authenticated routes.
- ``require_roles``: Role-gating dependency factory.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_async_db
from app.models.user import User

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_security_scheme = HTTPBearer()


# ── Password helpers ──────────────────────────────────────────────────────────


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of the given plain-text password.

    Args:
        plain: The plain-text password to hash.

    Returns:
        A bcrypt-hashed password string suitable for database storage.
    """
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Compare a plain-text password against a stored bcrypt hash.

    Args:
        plain: The plain-text password supplied by the user.
        hashed: The bcrypt hash retrieved from the database.

    Returns:
        ``True`` if the password matches; ``False`` otherwise.
    """
    return bool(_pwd_context.verify(plain, hashed))


# ── Token creation ────────────────────────────────────────────────────────────


def create_access_token(user_id: UUID, role: str) -> str:
    """Issue a short-lived JWT access token.

    Args:
        user_id: The UUID of the authenticated user.
        role: The user's access-control role string.

    Returns:
        A signed JWT string carrying ``sub``, ``role``, ``type=access``,
        and ``exp`` claims.
    """
    settings = get_settings()
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": now,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(user_id: UUID) -> str:
    """Issue a long-lived JWT refresh token.

    Args:
        user_id: The UUID of the authenticated user.

    Returns:
        A signed JWT string carrying ``sub``, ``type=refresh``, and ``exp``
        claims.  The token does not embed a role; it is only used to obtain
        a new access token.
    """
    settings = get_settings()
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(days=settings.refresh_token_expire_days)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expire,
        "iat": now,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


# ── Token decoding ────────────────────────────────────────────────────────────


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token string.

    Args:
        token: The raw JWT string to decode and verify.

    Returns:
        The decoded claims dictionary if the token is valid.

    Raises:
        HTTPException: 401 if the token is expired, tampered, or otherwise
            invalid.
    """
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ── FastAPI dependencies ──────────────────────────────────────────────────────


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_security_scheme),
    db: AsyncSession = Depends(get_async_db),
) -> User:
    """FastAPI dependency: resolve and return the authenticated User.

    Decodes the Bearer token from the ``Authorization`` header, validates it,
    and fetches the corresponding User from the database.

    Args:
        credentials: Bearer credentials extracted by ``HTTPBearer``.
        db: Async database session injected by ``get_async_db``.

    Returns:
        The active User record that owns the token.

    Raises:
        HTTPException: 401 if the token is invalid or the user does not exist.
        HTTPException: 403 if the user account is inactive.
    """
    payload = decode_token(credentials.credentials)
    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = UUID(user_id_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid subject claim format.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive.",
        )

    return user


def require_roles(*roles: str) -> Callable[..., Any]:
    """Return a FastAPI dependency that enforces role-based access control.

    Args:
        *roles: One or more role strings that are permitted to call the
            endpoint (e.g. ``"admin"``, ``"commercial"``).

    Returns:
        A FastAPI dependency callable that resolves to the current user if
        authorised, or raises ``HTTPException 403`` otherwise.

    Example::

        @router.get("/admin-only")
        async def admin_only(
            user: User = Depends(require_roles("admin", "commercial"))
        ): ...
    """

    async def _dependency(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Access denied. Required roles: {list(roles)}. "
                    f"Your role: {current_user.role}."
                ),
            )
        return current_user

    return _dependency
