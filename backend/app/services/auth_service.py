"""Authentication business logic: registration, login, token refresh.

Separates all auth state-machine logic from the HTTP layer so that the
service functions can be exercised in unit tests without needing a live
FastAPI application.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse


async def register_user(db: AsyncSession, data: RegisterRequest) -> User:
    """Create and persist a new user account.

    Args:
        db: Active async database session.
        data: Validated registration payload.

    Returns:
        The newly created and committed ``User`` ORM instance.

    Raises:
        HTTPException: 409 if the email address is already registered.
        HTTPException: 422 if the requested role is invalid (caught from
            ``User.create``).
    """
    # Check for duplicate email first to give a clean 409 rather than a
    # database integrity error that might leak implementation details.
    existing_result = await db.execute(
        select(User).where(User.email == data.email)
    )
    if existing_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email '{data.email}' is already registered.",
        )

    try:
        user = User.create(
            email=data.email,
            role=data.role,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            company=data.company,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email '{data.email}' is already registered.",
        ) from exc

    await db.refresh(user)
    return user


async def login_user(db: AsyncSession, data: LoginRequest) -> TokenResponse:
    """Authenticate a user by email and password, returning a token pair.

    Args:
        db: Active async database session.
        data: Validated login payload.

    Returns:
        A ``TokenResponse`` containing an access token and a refresh token.

    Raises:
        HTTPException: 401 if the email is not registered or the password is
            incorrect.
        HTTPException: 403 if the account is inactive.
    """
    result = await db.execute(select(User).where(User.email == data.email))
    user: User | None = result.scalar_one_or_none()

    if user is None or user.hashed_password is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Contact your administrator.",
        )

    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id),
    )


async def refresh_access_token(
    db: AsyncSession, refresh_token: str
) -> TokenResponse:
    """Issue a new access token from a valid refresh token.

    Args:
        db: Active async database session.
        refresh_token: A signed refresh JWT previously issued at login.

    Returns:
        A ``TokenResponse`` with a new access token.  The refresh token
        itself is **not** rotated in this implementation.

    Raises:
        HTTPException: 401 if the refresh token is invalid, expired, or
            does not have ``type=refresh``.
        HTTPException: 401 if the referenced user no longer exists.
        HTTPException: 403 if the account is inactive.
    """
    payload = decode_token(refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Provided token is not a refresh token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is missing the subject claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = UUID(user_id_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid subject claim in refresh token.",
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

    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        refresh_token=refresh_token,  # return the same refresh token
    )


async def upsert_google_user(
    db: AsyncSession,
    google_id: str,
    email: str,
    full_name: str | None,
) -> User:
    """Find or create a user from Google OAuth2 user-info data.

    Lookup order: google_id → email → create new client account.

    Args:
        db: Active async database session.
        google_id: Google ``sub`` claim (unique subject identifier).
        email: Email address from Google user-info endpoint.
        full_name: Display name from Google, or ``None``.

    Returns:
        The upserted and committed ``User`` ORM instance.
    """
    result = await db.execute(select(User).where(User.google_id == google_id))
    user: User | None = result.scalar_one_or_none()

    if user is None:
        result2 = await db.execute(select(User).where(User.email == email))
        user = result2.scalar_one_or_none()

    if user is None:
        user = User.create(
            email=email,
            role="client",
            full_name=full_name,
            google_id=google_id,
        )
        db.add(user)
    else:
        user.google_id = google_id
        if full_name and not user.full_name:
            user.full_name = full_name

    await db.commit()
    await db.refresh(user)
    return user


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User:
    """Fetch a single user by primary key.

    Args:
        db: Active async database session.
        user_id: UUID of the user to retrieve.

    Returns:
        The ``User`` ORM instance.

    Raises:
        HTTPException: 404 if no user with ``user_id`` exists.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{user_id}' not found.",
        )

    return user
