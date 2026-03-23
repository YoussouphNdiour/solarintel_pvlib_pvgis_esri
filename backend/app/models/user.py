"""User ORM model for SolarIntel v2.

Represents platform users: admins, commercial staff, technicians, and clients.
Supports both password-based and Google OAuth2 authentication.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.project import Project

# Exhaustive set of valid roles — validated at the DB enum level.
USER_ROLES = ("admin", "commercial", "technicien", "client")


class User(Base):
    """Platform user account.

    Attributes:
        email: Unique login identifier; indexed for fast lookup.
        hashed_password: bcrypt hash; ``None`` for OAuth-only accounts.
        role: Access-control role — one of ``USER_ROLES``.
        company: Optional organisation name.
        full_name: Display name shown in the UI.
        is_active: Soft-delete / account suspension flag.
        google_id: Google OAuth2 subject identifier; unique when set.
        updated_at: Last-modified timestamp; auto-updated on every write.
        projects: Back-populated list of projects owned by this user.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(254),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    role: Mapped[str] = mapped_column(
        Enum(*USER_ROLES, name="user_role"),
        nullable=False,
        default="technicien",
        server_default="technicien",
    )
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    google_id: Mapped[str | None] = mapped_column(
        String(128),
        unique=True,
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    projects: Mapped[list["Project"]] = relationship(
        "Project",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    def validate_role(self) -> None:
        """Raise ValueError when the role is not in USER_ROLES.

        Raises:
            ValueError: If ``self.role`` is not one of the allowed role strings.
        """
        if self.role not in USER_ROLES:
            raise ValueError(
                f"Invalid role '{self.role}'. Must be one of: {USER_ROLES}"
            )

    @classmethod
    def create(
        cls,
        *,
        email: str,
        role: str = "technicien",
        hashed_password: str | None = None,
        full_name: str | None = None,
        company: str | None = None,
        google_id: str | None = None,
    ) -> "User":
        """Construct a User with role validation.

        Args:
            email: The user's unique email address.
            role: Access role; must be in USER_ROLES.
            hashed_password: Pre-hashed password string, or None for OAuth.
            full_name: Optional display name.
            company: Optional organisation name.
            google_id: Google OAuth2 subject ID, or None.

        Returns:
            A new User instance (not yet persisted to the database).

        Raises:
            ValueError: If ``role`` is not a valid role string.
        """
        if role not in USER_ROLES:
            raise ValueError(
                f"Invalid role '{role}'. Must be one of: {USER_ROLES}"
            )
        return cls(
            id=uuid.uuid4(),
            email=email,
            role=role,
            hashed_password=hashed_password,
            full_name=full_name,
            company=company,
            google_id=google_id,
        )
