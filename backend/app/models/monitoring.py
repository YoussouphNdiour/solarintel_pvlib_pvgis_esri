"""Monitoring ORM model for SolarIntel v2.

Records time-series production telemetry for a Project.
Data can arrive via webhook callbacks (inverter monitoring APIs) or be
back-filled from Open-Meteo climate reanalysis data.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Float

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.project import Project


class Monitoring(Base):
    """A single telemetry reading for a Project.

    Attributes:
        project_id: FK to the parent Project; CASCADE-deleted with it.
        timestamp: UTC timestamp of the measurement; indexed.
        production_kwh: Energy produced during the measurement interval in kWh.
        irradiance_wm2: In-plane irradiance in W/m² (optional).
        temperature_c: Ambient temperature in °C (optional).
        source: Data origin — ``"webhook"`` or ``"open_meteo"``.
        project: Back-reference to the owning Project.
    """

    __tablename__ = "monitoring"

    # Composite index for typical time-range queries scoped to a project
    __table_args__ = (
        Index("ix_monitoring_project_timestamp", "project_id", "timestamp"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    production_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    irradiance_wm2: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="webhook",
        server_default="webhook",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="monitoring_entries",
        lazy="selectin",
    )

    @classmethod
    def create(
        cls,
        *,
        project_id: uuid.UUID,
        timestamp: datetime,
        production_kwh: float,
        irradiance_wm2: float | None = None,
        temperature_c: float | None = None,
        source: str = "webhook",
    ) -> "Monitoring":
        """Construct a Monitoring entry (not yet persisted).

        Args:
            project_id: UUID of the owning project.
            timestamp: Measurement timestamp (timezone-aware UTC recommended).
            production_kwh: Energy produced in the interval, in kWh.
            irradiance_wm2: Optional in-plane irradiance in W/m².
            temperature_c: Optional ambient temperature in °C.
            source: Data source identifier (``"webhook"`` or ``"open_meteo"``).

        Returns:
            A new Monitoring instance ready for session.add().
        """
        return cls(
            id=uuid.uuid4(),
            project_id=project_id,
            timestamp=timestamp,
            production_kwh=production_kwh,
            irradiance_wm2=irradiance_wm2,
            temperature_c=temperature_c,
            source=source,
        )
