"""SIM-001: PV simulation API endpoints.

Provides:
- POST /api/v2/simulate — run a new PV simulation for a project
- GET  /api/v2/simulate/{simulation_id} — retrieve a completed simulation

All endpoints require a valid Bearer token. Simulations are scoped to the
authenticated user: the owning project must belong to the current user.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_async_db
from app.models.project import Project
from app.models.simulation import Simulation
from app.models.user import User
from app.schemas.simulation import (
    MonthlyDataResponse,
    SimulationRequest,
    SimulationResponse,
)
from app.services.senelec_service import SenelecService
from app.services.simulation_service import SimulationParams, SimulationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simulate", tags=["simulation"])

# ── Module-level service singletons (stateless, safe to share) ────────────────
_sim_service = SimulationService()
_senelec_service = SenelecService()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _build_monthly_response(monthly_data: list | None) -> list[MonthlyDataResponse]:
    """Convert the JSONB monthly_data list to ``MonthlyDataResponse`` instances.

    Each element in ``monthly_data`` is a dict with keys matching the
    ``MonthlyResult`` dataclass fields (snake_case).

    Args:
        monthly_data: Raw list from the Simulation.monthly_data JSONB column,
            or ``None`` if not available.

    Returns:
        List of 12 ``MonthlyDataResponse`` instances, or an empty list.
    """
    if not monthly_data:
        return []
    return [
        MonthlyDataResponse(
            month=int(entry["month"]),
            energyKwh=float(entry["energy_kwh"]),
            irradianceKwhM2=float(entry["irradiance_kwh_m2"]),
            performanceRatio=float(entry["performance_ratio"]),
        )
        for entry in monthly_data
    ]


def _simulation_to_response(sim: Simulation) -> SimulationResponse:
    """Build a ``SimulationResponse`` from an ORM ``Simulation`` instance.

    Args:
        sim: A fully loaded Simulation ORM instance.

    Returns:
        A validated ``SimulationResponse`` ready for serialisation.
    """
    monthly = _build_monthly_response(sim.monthly_data)
    response = SimulationResponse.model_validate(sim)
    # Overwrite monthly_data with parsed MonthlyDataResponse objects
    # (model_validate would set it to the raw list; we replace it)
    return response.model_copy(update={"monthlyData": monthly})


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=SimulationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run a PV simulation for a project",
)
async def create_simulation(
    body: SimulationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> SimulationResponse:
    """Run a new PV yield simulation and persist the results.

    Steps:
    1. Verify the requested project exists and belongs to ``current_user``.
    2. Extract project coordinates (lat/lon) for PVGIS.
    3. Run ``SimulationService.simulate()`` (fetches TMY from PVGIS or cache).
    4. Run ``SenelecService.analyze_savings()`` for financial metrics.
    5. Persist a ``Simulation`` record and return the response.

    Args:
        body: Simulation request payload.
        current_user: Authenticated user resolved by ``get_current_user``.
        db: Async database session.

    Returns:
        The newly created ``SimulationResponse`` (HTTP 201).

    Raises:
        HTTPException: 404 if the project does not exist or belongs to another user.
        HTTPException: 500 if the PVGIS API is unreachable and no cache is available.
    """
    # ── 1. Authorise project access ───────────────────────────────────────────
    result = await db.execute(
        select(Project).where(
            Project.id == body.project_id,
            Project.user_id == current_user.id,
        )
    )
    project: Project | None = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied.",
        )

    # ── 2. Build simulation parameters from request + project geometry ────────
    sim_params = SimulationParams(
        latitude=project.latitude,
        longitude=project.longitude,
        panel_count=body.panel_count,
        panel_power_wc=body.panel_power_wc,
        tilt=body.tilt,
        azimuth=body.azimuth,
        system_losses=body.system_losses,
    )

    # ── 3. Run PV simulation ──────────────────────────────────────────────────
    logger.info(
        "Starting simulation for project=%s user=%s panels=%d×%dW",
        project.id,
        current_user.id,
        body.panel_count,
        body.panel_power_wc,
    )
    sim_result = await _sim_service.simulate(sim_params)

    # ── 4. Senelec financial analysis ─────────────────────────────────────────
    monthly_production = [m.energy_kwh for m in sim_result.monthly_data]
    senelec_analysis = _senelec_service.analyze_savings(
        monthly_consumption_kwh=body.monthly_consumption_kwh,
        monthly_production_kwh=monthly_production,
        tariff_code=body.tariff_code,
        installation_cost_xof=body.installation_cost_xof,
    )

    # ── 5. Persist simulation record ──────────────────────────────────────────
    monthly_data_json = [
        {
            "month": m.month,
            "energy_kwh": m.energy_kwh,
            "irradiance_kwh_m2": m.irradiance_kwh_m2,
            "performance_ratio": m.performance_ratio,
        }
        for m in sim_result.monthly_data
    ]

    simulation = Simulation.create(
        project_id=body.project_id,
        panel_count=body.panel_count,
        peak_kwc=sim_result.peak_kwc,
        annual_kwh=sim_result.annual_kwh,
        specific_yield=sim_result.specific_yield,
        performance_ratio=sim_result.performance_ratio,
        monthly_data=monthly_data_json,
        params=sim_result.params_used,
        senelec_savings_xof=senelec_analysis.annual_savings_xof,
        payback_years=senelec_analysis.payback_years,
        roi_percent=senelec_analysis.roi_25yr_percent,
        status="completed",
    )
    db.add(simulation)
    await db.flush()  # obtain the id before committing

    logger.info(
        "Simulation %s completed: annual_kwh=%.1f PR=%.3f payback=%.1f yrs",
        simulation.id,
        sim_result.annual_kwh,
        sim_result.performance_ratio,
        senelec_analysis.payback_years,
    )

    # ── 6. Build and return response ──────────────────────────────────────────
    # We build MonthlyDataResponse directly from the dataclass results (not
    # from the JSONB-persisted dict) to avoid the camelCase/snake_case round-trip.
    monthly_response = [
        MonthlyDataResponse.model_validate(
            {
                "energy_kwh": m.energy_kwh,
                "irradiance_kwh_m2": m.irradiance_kwh_m2,
                "performance_ratio": m.performance_ratio,
                "month": m.month,
            }
        )
        for m in sim_result.monthly_data
    ]

    # Build SimulationResponse from the ORM object; monthly_data will be
    # validated from the JSONB dicts but we immediately overwrite it.
    response = SimulationResponse.model_validate(simulation)
    return response.model_copy(update={"monthlyData": monthly_response})


@router.get(
    "/{simulation_id}",
    response_model=SimulationResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a simulation by ID",
)
async def get_simulation(
    simulation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> SimulationResponse:
    """Retrieve a simulation record by its UUID.

    The simulation is only returned if its owning project belongs to
    ``current_user``, enforcing per-user data isolation.

    Args:
        simulation_id: UUID of the simulation to retrieve.
        current_user: Authenticated user resolved by ``get_current_user``.
        db: Async database session.

    Returns:
        The ``SimulationResponse`` for the requested simulation.

    Raises:
        HTTPException: 404 if the simulation does not exist or belongs to
            a project owned by a different user.
    """
    result = await db.execute(
        select(Simulation)
        .join(Project, Simulation.project_id == Project.id)
        .where(
            Simulation.id == simulation_id,
            Project.user_id == current_user.id,
        )
    )
    simulation: Simulation | None = result.scalar_one_or_none()

    if simulation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation not found or access denied.",
        )

    return _simulation_to_response(simulation)
