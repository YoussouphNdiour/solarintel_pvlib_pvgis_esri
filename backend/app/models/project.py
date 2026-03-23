"""Project ORM model for SolarIntel v2.

A Project represents a physical solar installation site linked to a User.
It holds geospatial data (lat/lon + optional polygon) and is the root
aggregate for Simulation, Equipment, and Monitoring records.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Float

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.equipment import Equipment
    from app.models.monitoring import Monitoring
    from app.models.simulation import Simulation
    from app.models.user import User


class Project(Base):
    """A solar installation site.

    Attributes:
        user_id: FK to the owning User; CASCADE-deleted with the user.
        name: Human-readable project label.
        description: Optional long-form description.
        latitude: WGS-84 decimal latitude of the installation site.
        longitude: WGS-84 decimal longitude of the installation site.
        polygon_geojson: Optional GeoJSON polygon of the roof / array area.
        address: Human-readable site address.
        updated_at: Last-modified timestamp.
        user: Back-reference to the owning User.
        simulations: All simulation runs for this project.
        equipment: The single equipment record (one-to-one).
        monitoring_entries: Time-series production telemetry.
    """

    __tablename__ = "projects"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    polygon_geojson: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="GeoJSON polygon of the installation area",
    )
    address: Mapped[str | None] = mapped_column(String(400), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship(
        "User",
        back_populates="projects",
        lazy="selectin",
    )
    simulations: Mapped[list["Simulation"]] = relationship(
        "Simulation",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    equipment: Mapped["Equipment | None"] = relationship(
        "Equipment",
        back_populates="project",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="noload",
    )
    monitoring_entries: Mapped[list["Monitoring"]] = relationship(
        "Monitoring",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    @classmethod
    def create(
        cls,
        *,
        user_id: uuid.UUID,
        name: str,
        latitude: float,
        longitude: float,
        description: str | None = None,
        polygon_geojson: dict | None = None,
        address: str | None = None,
    ) -> "Project":
        """Create a new Project instance (not yet persisted).

        Args:
            user_id: UUID of the owning user.
            name: Project display name.
            latitude: Site latitude in decimal degrees.
            longitude: Site longitude in decimal degrees.
            description: Optional project description.
            polygon_geojson: Optional GeoJSON polygon dict.
            address: Optional human-readable address string.

        Returns:
            A new Project instance ready to be added to a session.
        """
        return cls(
            id=uuid.uuid4(),
            user_id=user_id,
            name=name,
            latitude=latitude,
            longitude=longitude,
            description=description,
            polygon_geojson=polygon_geojson,
            address=address,
        )
