"""Pydantic v2 schemas for simulation endpoints.

Defines request bodies and response models for:
- POST /api/v2/simulate — run a new PV simulation
- GET /api/v2/simulate/{id} — retrieve a completed simulation

All monetary values are expressed in XOF (CFA Francs) as floats.
All energy values are in kWh; power values in kWc (kWp).
camelCase field aliases are used for JSON serialisation to match
the frontend TypeScript convention.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SimulationRequest(BaseModel):
    """Request body for POST /api/v2/simulate.

    Attributes:
        project_id: UUID of the owning Project (must belong to current user).
        panel_count: Number of PV panels in the array.
        panel_power_wc: Nameplate power of each panel in Watts.
        panel_model: Human-readable panel model label.
        tilt: Panel tilt angle in degrees from horizontal.
        azimuth: Panel azimuth in degrees (180 = south-facing).
        system_losses: Fraction of losses due to wiring, soiling, shading, etc.
        monthly_consumption_kwh: Average household monthly electricity consumption.
        tariff_code: Senelec tariff plan code (DPP, DMP, WOYOFAL, …).
        installation_cost_xof: Total installed system cost in XOF.
    """

    project_id: UUID
    panel_count: int = Field(ge=1, le=10000, description="Number of PV panels")
    panel_power_wc: int = Field(
        ge=100, le=800, default=545, description="Panel nameplate power in Watts"
    )
    panel_model: str = Field(
        default="JA Solar JAM72S30 545W",
        description="Human-readable panel model label",
    )
    tilt: float = Field(
        ge=0, le=90, default=15.0, description="Tilt angle in degrees from horizontal"
    )
    azimuth: float = Field(
        ge=0,
        le=360,
        default=180.0,
        description="Azimuth in degrees (180 = south-facing)",
    )
    system_losses: float = Field(
        ge=0,
        le=0.5,
        default=0.14,
        description="Total system losses as a fraction (0.14 = 14%)",
    )
    monthly_consumption_kwh: float = Field(
        ge=0,
        default=400.0,
        description="Average monthly electricity consumption in kWh",
    )
    tariff_code: str = Field(
        default="DPP",
        description="Senelec tariff plan code (DPP, DMP, PPP, PMP, WOYOFAL)",
    )
    installation_cost_xof: float = Field(
        ge=0,
        default=5_000_000.0,
        description="Total installed cost in XOF (CFA Francs)",
    )


class MonthlyDataResponse(BaseModel):
    """One month of simulation output.

    Uses ``validation_alias`` so that both snake_case input (from the DB
    JSONB column: ``energy_kwh``, ``irradiance_kwh_m2``, ``performance_ratio``)
    and camelCase input (from the API request: ``energyKwh``, …) are accepted.
    Output serialisation always uses camelCase field names.

    Attributes:
        month: Calendar month number (1 = January … 12 = December).
        energyKwh: Estimated AC energy production for the month in kWh.
        irradianceKwhM2: Total in-plane irradiance for the month in kWh/m².
        performanceRatio: Monthly performance ratio (0–1 scale).
    """

    model_config = ConfigDict(populate_by_name=True)

    month: int = Field(ge=1, le=12, description="Calendar month (1-12)")
    energyKwh: float = Field(
        validation_alias="energy_kwh",
        description="Monthly AC energy production in kWh",
    )
    irradianceKwhM2: float = Field(
        validation_alias="irradiance_kwh_m2",
        description="Monthly in-plane irradiance in kWh/m²",
    )
    performanceRatio: float = Field(
        validation_alias="performance_ratio",
        description="Monthly performance ratio (0-1)",
    )


class SimulationResponse(BaseModel):
    """Serialised simulation record returned to clients.

    Attributes:
        id: UUID primary key of the simulation record.
        projectId: UUID of the owning project.
        panelCount: Number of PV panels in the array.
        peakKwc: System peak power in kWp.
        annualKwh: Estimated annual AC energy production in kWh.
        specificYield: Annual energy yield per kWp (kWh/kWp).
        performanceRatio: Annual system performance ratio (0–1).
        monthlyData: List of 12 monthly production records.
        senelecSavingsXof: Estimated annual electricity bill savings in XOF.
        paybackYears: Simple payback period in years.
        roiPercent: Return on investment percentage over 25 years.
        status: Simulation lifecycle status.
        createdAt: UTC timestamp when the simulation was created.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    projectId: UUID = Field(validation_alias="project_id")
    panelCount: int = Field(validation_alias="panel_count")
    peakKwc: float = Field(validation_alias="peak_kwc")
    annualKwh: float = Field(validation_alias="annual_kwh")
    specificYield: float = Field(
        validation_alias="specific_yield", default=0.0
    )
    performanceRatio: float = Field(
        validation_alias="performance_ratio", default=0.0
    )
    monthlyData: list[MonthlyDataResponse] = Field(
        validation_alias="monthly_data", default_factory=list
    )
    senelecSavingsXof: float | None = Field(
        validation_alias="senelec_savings_xof", default=None
    )
    paybackYears: float | None = Field(
        validation_alias="payback_years", default=None
    )
    roiPercent: float | None = Field(
        validation_alias="roi_percent", default=None
    )
    status: str
    createdAt: datetime = Field(validation_alias="created_at")

    @classmethod
    def from_orm_with_monthly(
        cls,
        sim: object,
        monthly_data: list[MonthlyDataResponse],
    ) -> "SimulationResponse":
        """Build a SimulationResponse from an ORM Simulation instance.

        Merges structured monthly_data (built from the JSONB list) with
        the top-level Simulation fields.

        Args:
            sim: An ORM ``Simulation`` instance with ``from_attributes=True``.
            monthly_data: Pre-parsed list of ``MonthlyDataResponse`` instances.

        Returns:
            A fully populated ``SimulationResponse``.
        """
        base = cls.model_validate(sim)
        object.__setattr__(base, "monthlyData", monthly_data)
        return base
