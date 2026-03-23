"""Equipment ORM model for SolarIntel v2.

Stores the hardware bill-of-materials for a solar installation.
One Equipment record per Project (enforced by unique constraint on project_id).
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Float, Integer

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.project import Project


class Equipment(Base):
    """Solar installation hardware specification.

    Attributes:
        project_id: FK to the parent Project; unique (one-to-one relationship).
        panel_model: Full model name of the PV panel (e.g. ``JA Solar JAM72S30 545W``).
        panel_power_wc: Panel peak power in Watt-crête (Wp).
        inverter_model: Full inverter model name (e.g. ``GOODWE GW20KT-DT``).
        inverter_kva: Inverter rated apparent power in kVA.
        battery_model: Optional battery model name.
        battery_kwh: Optional battery usable energy capacity in kWh.
        details: JSONB blob with full technical specifications.
        project: Back-reference to the owning Project.
    """

    __tablename__ = "equipment"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # Enforces the one-to-one relationship
        index=True,
    )
    panel_model: Mapped[str] = mapped_column(String(200), nullable=False)
    panel_power_wc: Mapped[int] = mapped_column(Integer, nullable=False)
    inverter_model: Mapped[str] = mapped_column(String(200), nullable=False)
    inverter_kva: Mapped[float] = mapped_column(Float, nullable=False)
    battery_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    battery_kwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    details: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Full technical specifications snapshot",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="equipment",
        lazy="selectin",
    )

    @classmethod
    def create(
        cls,
        *,
        project_id: uuid.UUID,
        panel_model: str,
        panel_power_wc: int,
        inverter_model: str,
        inverter_kva: float,
        battery_model: str | None = None,
        battery_kwh: float | None = None,
        details: dict | None = None,
    ) -> "Equipment":
        """Construct an Equipment instance (not yet persisted).

        Args:
            project_id: UUID of the parent project.
            panel_model: Full PV panel model name.
            panel_power_wc: Panel peak power in Wp.
            inverter_model: Full inverter model name.
            inverter_kva: Inverter rated power in kVA.
            battery_model: Optional battery model name.
            battery_kwh: Optional battery capacity in kWh.
            details: Optional full technical specification dict.

        Returns:
            A new Equipment instance ready for session.add().
        """
        return cls(
            id=uuid.uuid4(),
            project_id=project_id,
            panel_model=panel_model,
            panel_power_wc=panel_power_wc,
            inverter_model=inverter_model,
            inverter_kva=inverter_kva,
            battery_model=battery_model,
            battery_kwh=battery_kwh,
            details=details,
        )
