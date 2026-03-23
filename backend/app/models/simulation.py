"""Simulation ORM model for SolarIntel v2.

Stores PV yield simulation results computed from PVGIS irradiance data.
Each simulation belongs to one Project and may produce one Report.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Float, Integer

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.report import Report

SIMULATION_STATUSES = ("pending", "running", "completed", "failed")


class Simulation(Base):
    """PV yield simulation record.

    Attributes:
        project_id: FK to the owning Project; CASCADE-deleted with it.
        panel_count: Number of PV panels installed.
        peak_kwc: System peak power in kWp (kilowatt-peak).
        annual_kwh: Total estimated annual energy production in kWh.
        specific_yield: Energy yield per kWp (kWh/kWp/year).
        performance_ratio: System performance ratio (0–1 scale).
        monthly_data: JSON array with one entry per month (12 items).
        params: Full simulation parameter snapshot (panel specs, orientation, …).
        senelec_savings_xof: Estimated annual electricity bill savings in XOF.
        payback_years: Simple payback period in years.
        roi_percent: Return on investment percentage over project lifetime.
        status: Lifecycle status of the simulation run.
        report: Associated PDF/HTML report (one-to-one, optional).
        project: Back-reference to the owning Project.
    """

    __tablename__ = "simulations"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    panel_count: Mapped[int] = mapped_column(Integer, nullable=False)
    peak_kwc: Mapped[float] = mapped_column(Float, nullable=False)
    annual_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    specific_yield: Mapped[float | None] = mapped_column(Float, nullable=True)
    performance_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    monthly_data: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="12-element array of monthly production records",
    )
    params: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Full simulation input parameters snapshot",
    )
    senelec_savings_xof: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    payback_years: Mapped[float | None] = mapped_column(Float, nullable=True)
    roi_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(*SIMULATION_STATUSES, name="simulation_status"),
        nullable=False,
        default="completed",
        server_default="completed",
    )
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="simulations",
        lazy="selectin",
    )
    report: Mapped["Report | None"] = relationship(
        "Report",
        back_populates="simulation",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )

    @classmethod
    def create(
        cls,
        *,
        project_id: uuid.UUID,
        panel_count: int,
        peak_kwc: float,
        annual_kwh: float,
        specific_yield: float | None = None,
        performance_ratio: float | None = None,
        monthly_data: list | None = None,
        params: dict | None = None,
        senelec_savings_xof: float | None = None,
        payback_years: float | None = None,
        roi_percent: float | None = None,
        status: str = "completed",
    ) -> "Simulation":
        """Construct a Simulation instance (not yet persisted).

        Args:
            project_id: UUID of the owning project.
            panel_count: Number of solar panels.
            peak_kwc: System peak power in kWp.
            annual_kwh: Annual energy production estimate in kWh.
            specific_yield: Optional kWh/kWp specific yield figure.
            performance_ratio: Optional system PR (0–1).
            monthly_data: Optional 12-month breakdown list.
            params: Optional full parameter snapshot dict.
            senelec_savings_xof: Optional annual savings in XOF.
            payback_years: Optional simple payback period.
            roi_percent: Optional ROI percentage.
            status: Initial lifecycle status string.

        Returns:
            A new Simulation instance ready for session.add().

        Raises:
            ValueError: If ``status`` is not a valid simulation status.
        """
        if status not in SIMULATION_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. Must be one of: {SIMULATION_STATUSES}"
            )
        return cls(
            id=uuid.uuid4(),
            project_id=project_id,
            panel_count=panel_count,
            peak_kwc=peak_kwc,
            annual_kwh=annual_kwh,
            specific_yield=specific_yield,
            performance_ratio=performance_ratio,
            monthly_data=monthly_data,
            params=params,
            senelec_savings_xof=senelec_savings_xof,
            payback_years=payback_years,
            roi_percent=roi_percent,
            status=status,
        )
