"""SIM-001: PV simulation API endpoints.

Provides:
- POST /api/v2/simulate — run a new PV simulation for a project
- GET  /api/v2/simulate/{simulation_id} — retrieve a completed simulation

All endpoints require a valid Bearer token. Simulations are scoped to the
authenticated user: the owning project must belong to the current user.
"""

from __future__ import annotations

import logging
import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_async_db
from app.models.project import Project
from app.models.simulation import Simulation
from app.models.user import User
from app.schemas.simulation import (
    MonthlyDataResponse,
    SimulationPage,
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


def _auto_panel_count(
    monthly_consumption_kwh: float,
    panel_power_wc: int,
    panel_efficiency: float = 0.21,
    system_losses: float = 0.14,
    available_area_m2: float | None = None,
    specific_yield_kwh_kwp: float = 1_650.0,
) -> int:
    """Calculate the minimum panel count to cover monthly energy consumption.

    Uses a pre-simulation specific yield estimate (West Africa average) to
    derive the required kWp, then converts to panel count.  When
    ``available_area_m2`` is given, the result is capped so the array fits
    within the usable roof/ground space (15 % inter-row spacing buffer).

    Args:
        monthly_consumption_kwh: Average monthly electricity consumption in kWh.
        panel_power_wc: Nameplate power per panel in Watts.
        panel_efficiency: Panel efficiency fraction (default 0.21 = 21 %).
        system_losses: Total system losses fraction (default 0.14 = 14 %).
        available_area_m2: Usable installation area in m² (optional ceiling).
        specific_yield_kwh_kwp: Pre-estimate of annual kWh per kWp for the
            region (1 650 kWh/kWp is typical for Senegal/West Africa).

    Returns:
        Panel count ≥ 1, bounded by the space constraint when supplied.
    """
    # Energy-based requirement
    annual_consumption_kwh = monthly_consumption_kwh * 12.0
    # Net yield after system losses
    net_yield = specific_yield_kwh_kwp * (1.0 - system_losses)
    required_kwp = annual_consumption_kwh / net_yield
    panel_count_energy = math.ceil(required_kwp * 1_000.0 / panel_power_wc)

    if available_area_m2 is None:
        return max(1, panel_count_energy)

    # Space-based ceiling
    # Physical panel area (m²): W / (W·m⁻² at STC × efficiency) = W / (1000 × η)
    panel_area_m2 = panel_power_wc / (1_000.0 * panel_efficiency)
    # Add 15 % footprint buffer for inter-row spacing and access paths
    panel_footprint_m2 = panel_area_m2 * 1.15
    max_panels_space = int(available_area_m2 / panel_footprint_m2)

    return max(1, min(panel_count_energy, max_panels_space))


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


@router.get(
    "",
    response_model=SimulationPage,
    summary="List simulations for a project",
)
async def list_simulations(
    project_id: UUID = Query(..., description="Project UUID to list simulations for"),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> SimulationPage:
    """Return a cursor-paginated list of simulations for a project.

    Only returns simulations whose project belongs to the authenticated user.
    """
    # Verify project ownership
    proj_result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == current_user.id,
        )
    )
    if proj_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    # Total count
    count_result = await db.execute(
        select(func.count()).select_from(Simulation).where(Simulation.project_id == project_id)
    )
    total: int = count_result.scalar_one()

    query = (
        select(Simulation)
        .where(Simulation.project_id == project_id)
        .order_by(Simulation.created_at.desc())
        .limit(limit + 1)
    )
    if cursor is not None:
        try:
            from datetime import datetime
            ts_str, id_str = cursor.split("|", 1)
            ts = datetime.fromisoformat(ts_str)
            uid = UUID(id_str)
            query = query.where(
                (Simulation.created_at < ts)
                | ((Simulation.created_at == ts) & (Simulation.id < uid))
            )
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid cursor.")

    result = await db.execute(query)
    rows = list(result.scalars().all())

    has_more = len(rows) > limit
    items = rows[:limit]

    next_cursor: str | None = None
    if has_more and items:
        last = items[-1]
        next_cursor = f"{last.created_at.isoformat()}|{last.id}"

    return SimulationPage(
        items=[_simulation_to_response(s) for s in items],
        next_cursor=next_cursor,
        total=total,
    )


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
    # Resolve panel count: use explicit value if provided, otherwise auto-calculate
    # from energy need (monthly_consumption_kwh) capped by available area.
    if body.panel_count is not None:
        panel_count = body.panel_count
        auto_calculated = False
    else:
        panel_count = _auto_panel_count(
            monthly_consumption_kwh=body.monthly_consumption_kwh,
            panel_power_wc=body.panel_power_wc,
            system_losses=body.system_losses,
            available_area_m2=body.available_area_m2,
        )
        auto_calculated = True

    sim_params = SimulationParams(
        latitude=project.latitude,
        longitude=project.longitude,
        panel_count=panel_count,
        panel_power_wc=body.panel_power_wc,
        tilt=body.tilt,
        azimuth=body.azimuth,
        system_losses=body.system_losses,
    )

    # ── 3. Run PV simulation ──────────────────────────────────────────────────
    logger.info(
        "Starting simulation for project=%s user=%s panels=%d×%dW%s",
        project.id,
        current_user.id,
        panel_count,
        body.panel_power_wc,
        " (auto-calculated)" if auto_calculated else "",
    )
    sim_result = await _sim_service.simulate(sim_params)
    # Enrich params with auto-calculation metadata for audit/display
    sim_result.params_used["panel_count_auto"] = auto_calculated
    if body.available_area_m2 is not None:
        sim_result.params_used["available_area_m2"] = body.available_area_m2

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
        panel_count=panel_count,
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
