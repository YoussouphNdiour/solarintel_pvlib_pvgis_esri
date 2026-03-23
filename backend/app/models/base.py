"""Declarative base for all SQLAlchemy 2.0 ORM models.

Provides:
- UUID primary key (auto-generated via uuid4)
- ``created_at`` timestamp (set once at INSERT, never updated)
All domain models must inherit from ``Base``.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Abstract declarative base shared by all ORM models.

    Every model that inherits from this class receives:
    - ``id``: UUID primary key, generated client-side by ``uuid.uuid4``.
    - ``created_at``: timezone-aware UTC timestamp, set automatically on INSERT
      via the database ``now()`` function.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        sort_order=-2,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        sort_order=-1,
    )

    def __repr__(self) -> str:
        """Return a concise developer-friendly representation."""
        return f"<{self.__class__.__name__} id={self.id}>"

    @staticmethod
    def _utcnow() -> datetime:
        """Return the current UTC datetime (timezone-aware).

        Returns:
            Current UTC datetime with tzinfo set to ``timezone.utc``.
        """
        return datetime.now(tz=timezone.utc)
