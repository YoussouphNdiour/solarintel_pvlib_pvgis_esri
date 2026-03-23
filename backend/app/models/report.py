"""Report ORM model for SolarIntel v2.

Tracks the generation of PDF/HTML reports derived from a Simulation.
Each Simulation may produce at most one Report (one-to-one).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import DateTime

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.simulation import Simulation

REPORT_STATUSES = ("pending", "generating", "ready", "failed")


class Report(Base):
    """PDF/HTML report generation record.

    Attributes:
        simulation_id: FK to the Simulation; unique (one report per simulation).
        pdf_path: Filesystem path to the generated PDF file (None until ready).
        html_path: Filesystem path to the generated HTML file (None until ready).
        status: Generation lifecycle status.
        error_message: Human-readable error detail when status is ``failed``.
        generated_at: Timestamp when the report became ready (None until then).
        simulation: Back-reference to the source Simulation.
    """

    __tablename__ = "reports"

    simulation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("simulations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # Enforces the one-to-one relationship
        index=True,
    )
    pdf_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    html_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(*REPORT_STATUSES, name="report_status"),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    simulation: Mapped["Simulation"] = relationship(
        "Simulation",
        back_populates="report",
        lazy="selectin",
    )

    @classmethod
    def create(
        cls,
        *,
        simulation_id: uuid.UUID,
        status: str = "pending",
        pdf_path: str | None = None,
        html_path: str | None = None,
    ) -> "Report":
        """Construct a Report instance (not yet persisted).

        Args:
            simulation_id: UUID of the source simulation.
            status: Initial lifecycle status; defaults to ``"pending"``.
            pdf_path: Optional path to an already-generated PDF.
            html_path: Optional path to an already-generated HTML file.

        Returns:
            A new Report instance ready for session.add().

        Raises:
            ValueError: If ``status`` is not a valid report status.
        """
        if status not in REPORT_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. Must be one of: {REPORT_STATUSES}"
            )
        return cls(
            id=uuid.uuid4(),
            simulation_id=simulation_id,
            status=status,
            pdf_path=pdf_path,
            html_path=html_path,
        )
