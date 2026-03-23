"""TariffHistory ORM model for SolarIntel v2.

Tracks historical Senelec (national utility) electricity tariffs over time.
Used for accurate financial calculations (savings, payback, ROI) per the
applicable tariff on any given date.
"""

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Float

from app.models.base import Base

# Known Senelec tariff plan codes.
TARIFF_CODES = ("DPP", "DMP", "PPP", "PMP", "WOYOFAL")


class TariffHistory(Base):
    """Historical Senelec electricity tariff record.

    Senelec applies a stepped tariff structure:
    - Tranche 1 (T1): First consumption band, lowest rate.
    - Tranche 2 (T2): Second consumption band.
    - Tranche 3 (T3): Optional third band for high consumers.
    - Woyofal: Prepaid (Woyofal) flat rate.

    Attributes:
        tariff_code: Product code — one of ``TARIFF_CODES``.
        effective_date: Calendar date from which this tariff applies.
        t1_xof: Tranche 1 rate in CFA Francs per kWh.
        t2_xof: Tranche 2 rate in CFA Francs per kWh.
        t3_xof: Optional Tranche 3 rate.
        woyofal_xof: Optional prepaid rate for Woyofal subscribers.
        is_current: ``True`` for the currently active tariff of this code.
    """

    __tablename__ = "tariff_history"

    tariff_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Senelec product code: DPP | DMP | PPP | PMP | WOYOFAL",
    )
    effective_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    t1_xof: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Tranche 1 rate in CFA Francs per kWh",
    )
    t2_xof: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Tranche 2 rate in CFA Francs per kWh",
    )
    t3_xof: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Tranche 3 rate in CFA Francs per kWh (high-consumption band)",
    )
    woyofal_xof: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Prepaid (Woyofal) flat rate in CFA Francs per kWh",
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="True when this is the active tariff for the given code",
    )

    @classmethod
    def create(
        cls,
        *,
        tariff_code: str,
        effective_date: date,
        t1_xof: float,
        t2_xof: float,
        t3_xof: float | None = None,
        woyofal_xof: float | None = None,
        is_current: bool = False,
    ) -> "TariffHistory":
        """Construct a TariffHistory entry (not yet persisted).

        Args:
            tariff_code: Senelec product code (must be in TARIFF_CODES).
            effective_date: Date from which this tariff is applicable.
            t1_xof: Tranche 1 rate in XOF/kWh.
            t2_xof: Tranche 2 rate in XOF/kWh.
            t3_xof: Optional Tranche 3 rate in XOF/kWh.
            woyofal_xof: Optional Woyofal prepaid rate in XOF/kWh.
            is_current: Whether this entry represents the active tariff.

        Returns:
            A new TariffHistory instance ready for session.add().

        Raises:
            ValueError: If ``tariff_code`` is not a recognised code.
        """
        if tariff_code not in TARIFF_CODES:
            raise ValueError(
                f"Unknown tariff code '{tariff_code}'. "
                f"Must be one of: {TARIFF_CODES}"
            )
        return cls(
            id=uuid.uuid4(),
            tariff_code=tariff_code,
            effective_date=effective_date,
            t1_xof=t1_xof,
            t2_xof=t2_xof,
            t3_xof=t3_xof,
            woyofal_xof=woyofal_xof,
            is_current=is_current,
        )
