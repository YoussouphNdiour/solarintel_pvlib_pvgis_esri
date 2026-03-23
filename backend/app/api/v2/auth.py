"""Auth endpoints: register, login, refresh, /me, Google OAuth.

All routes are mounted under the ``/api/v2/auth`` prefix via the v2 router.

Google OAuth2 flow:
1. Client hits GET /google → redirect to Google consent screen.
2. Google redirects to GET /google/callback?code=... → exchange code for
   user info, upsert User, return JWT pair.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import RedirectResponse
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    require_roles,
)
from app.db.session import get_async_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import (
    login_user,
    refresh_access_token,
    register_user,
    upsert_google_user,
)

router = APIRouter(tags=["auth"])


# ── Registration ──────────────────────────────────────────────────────────────


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_async_db),
) -> User:
    """Create a new user account.

    Args:
        data: Registration payload (email, password, optional role / name).
        db: Async database session.

    Returns:
        The newly created user profile (no password hash exposed).

    Raises:
        HTTPException: 409 if the email is already taken.
        HTTPException: 422 if validation fails.
    """
    return await register_user(db, data)


# ── Login ─────────────────────────────────────────────────────────────────────


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive a JWT pair",
)
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_async_db),
) -> TokenResponse:
    """Authenticate with email and password.

    Args:
        data: Login credentials.
        db: Async database session.

    Returns:
        Access token and refresh token.

    Raises:
        HTTPException: 401 for invalid credentials.
        HTTPException: 403 for inactive accounts.
    """
    return await login_user(db, data)


# ── Token Refresh ─────────────────────────────────────────────────────────────


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Exchange a refresh token for a new access token",
)
async def refresh(
    data: RefreshRequest,
    db: AsyncSession = Depends(get_async_db),
) -> TokenResponse:
    """Issue a new access token using a valid refresh token.

    Args:
        data: Payload containing the refresh token.
        db: Async database session.

    Returns:
        A fresh access token (refresh token unchanged).

    Raises:
        HTTPException: 401 if the refresh token is invalid or expired.
    """
    return await refresh_access_token(db, data.refresh_token)


# ── Current user ──────────────────────────────────────────────────────────────


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Return the authenticated user's profile",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> User:
    """Return the profile of the currently authenticated user.

    Args:
        current_user: User resolved by the ``get_current_user`` dependency.

    Returns:
        The authenticated user's profile.
    """
    return current_user


# ── Admin-only diagnostic endpoint (RBAC demonstration) ──────────────────────


@router.get(
    "/admin-only",
    summary="Admin/commercial-gated diagnostic endpoint",
    response_model=dict[str, str],
)
async def admin_only(
    current_user: User = Depends(require_roles("admin", "commercial")),
) -> dict[str, str]:
    """Return a diagnostic message visible only to admin and commercial users.

    Args:
        current_user: Resolved by ``require_roles``; 403 for other roles.

    Returns:
        A simple confirmation dict.
    """
    return {"detail": f"Welcome, {current_user.role} {current_user.email}"}


# ── Google OAuth2 ─────────────────────────────────────────────────────────────

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
_GOOGLE_SCOPES = "openid email profile"
_GOOGLE_REDIRECT_PATH = "/api/v2/auth/google/callback"


@router.get(
    "/google",
    summary="Redirect to Google OAuth2 consent screen",
    status_code=status.HTTP_302_FOUND,
)
async def google_auth_redirect() -> RedirectResponse:
    """Redirect the browser to Google's OAuth2 authorisation endpoint.

    Returns:
        302 redirect to the Google consent screen.

    Raises:
        HTTPException: 503 if Google OAuth2 is not configured.
    """
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth2 is not configured on this server.",
        )

    params = (
        f"client_id={settings.google_client_id}"
        f"&redirect_uri={_build_redirect_uri()}"
        f"&response_type=code"
        f"&scope={_GOOGLE_SCOPES.replace(' ', '%20')}"
        f"&access_type=offline"
        f"&prompt=consent"
    )
    return RedirectResponse(url=f"{_GOOGLE_AUTH_URL}?{params}")


@router.get(
    "/google/callback",
    response_model=TokenResponse,
    summary="Google OAuth2 callback — exchange code for JWT",
)
async def google_auth_callback(
    code: str,
    db: AsyncSession = Depends(get_async_db),
) -> TokenResponse:
    """Handle the Google OAuth2 redirect, exchange the code, and issue JWTs.

    Args:
        code: Authorisation code provided by Google in the redirect query.
        db: Async database session.

    Returns:
        JWT access + refresh token pair for the authenticated Google user.

    Raises:
        HTTPException: 400 if the code exchange fails.
        HTTPException: 503 if Google OAuth2 is not configured.
    """
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth2 is not configured on this server.",
        )

    async with AsyncClient() as http:
        # Exchange authorisation code for tokens.
        token_response = await http.post(
            _GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": _build_redirect_uri(),
                "grant_type": "authorization_code",
            },
        )
        if token_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange authorisation code with Google.",
            )
        google_tokens: dict[str, str] = token_response.json()

        # Fetch user info using the access token.
        userinfo_response = await http.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {google_tokens['access_token']}"},
        )
        if userinfo_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to retrieve user info from Google.",
            )
        userinfo: dict[str, str] = userinfo_response.json()

    user = await upsert_google_user(
        db,
        google_id=userinfo["sub"],
        email=userinfo["email"],
        full_name=userinfo.get("name"),
    )
    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id),
    )


# ── Bootstrap: promote first admin ───────────────────────────────────────────


@router.post(
    "/make-admin",
    response_model=dict[str, str],
    summary="Promote a user to admin role (requires SECRET_KEY header)",
)
async def make_admin(
    email: str,
    x_secret_key: str = Header(..., alias="X-Secret-Key"),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, str]:
    """Bootstrap endpoint: promote a user to admin.

    Protected by the server's SECRET_KEY — only the server operator
    can call this. Use once to create the first admin, then ignore.

    Headers:
        X-Secret-Key: must match the SECRET_KEY environment variable.

    Query params:
        email: The email address of the user to promote.
    """
    settings = get_settings()
    if x_secret_key != settings.secret_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")

    result = await db.execute(select(User).where(User.email == email))
    user: User | None = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail=f"User '{email}' not found.")

    await db.execute(
        update(User).where(User.email == email).values(role="admin")
    )
    await db.commit()
    return {"detail": f"{email} is now admin."}


# ── Internal helpers ──────────────────────────────────────────────────────────


def _build_redirect_uri() -> str:
    """Construct the absolute Google OAuth2 redirect URI.

    Returns:
        The callback URL Google will redirect to after the user consents.
    """
    settings = get_settings()
    # In development the first allowed origin is used; in production the
    # PVGIS base URL host is a reasonable proxy for the public domain.
    origin = settings.allowed_origins[0].rstrip("/")
    return f"{origin}{_GOOGLE_REDIRECT_PATH}"
