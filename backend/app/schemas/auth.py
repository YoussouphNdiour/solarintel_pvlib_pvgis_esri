"""Pydantic v2 schemas for auth endpoints.

Defines request bodies and response models for:
- User registration
- Email/password login
- JWT token responses
- Token refresh
- Authenticated user profile
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class RegisterRequest(BaseModel):
    """Request body for POST /api/v2/auth/register.

    Attributes:
        email: Valid email address; used as the unique login identifier.
        password: Plain-text password; must be at least 8 characters.
        full_name: Optional display name.
        company: Optional organisation name.
        role: Access role; defaults to ``"technicien"``.
    """

    email: EmailStr
    password: str
    full_name: str | None = None
    company: str | None = None
    role: str = "technicien"

    @field_validator("password")
    @classmethod
    def password_min_length(cls, value: str) -> str:
        """Enforce minimum password length of 8 characters.

        Args:
            value: The raw password string provided by the client.

        Returns:
            The validated password string, unchanged.

        Raises:
            ValueError: If the password is shorter than 8 characters.
        """
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        return value

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, value: str) -> str:
        """Ensure the supplied role is one of the allowed values.

        Args:
            value: The raw role string.

        Returns:
            The validated role string.

        Raises:
            ValueError: If the role is not in the allowed set.
        """
        allowed = ("admin", "commercial", "technicien", "client")
        if value not in allowed:
            raise ValueError(f"role must be one of {allowed}")
        return value


class LoginRequest(BaseModel):
    """Request body for POST /api/v2/auth/login.

    Attributes:
        email: Registered email address.
        password: Plain-text password to verify against the stored hash.
    """

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Response body containing the issued JWT pair.

    Attributes:
        access_token: Short-lived JWT for API requests.
        refresh_token: Long-lived JWT used to obtain a new access_token.
        token_type: Always ``"bearer"``.
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Request body for POST /api/v2/auth/refresh.

    Attributes:
        refresh_token: A valid, unexpired refresh JWT.
    """

    refresh_token: str


class UserResponse(BaseModel):
    """Serialised user profile returned to clients.

    Attributes:
        id: UUID primary key of the user.
        email: Unique login email.
        full_name: Optional display name.
        role: Access-control role string.
        company: Optional organisation name.
        is_active: Whether the account is active.
        created_at: UTC timestamp when the account was created.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str | None
    role: str
    company: str | None
    is_active: bool
    created_at: datetime
