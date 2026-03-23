"""AI-001: Multi-agent PV analysis endpoints with SSE streaming.

Provides:
- POST /api/v2/ai/analyze    — run all agents and stream results as SSE events
- GET  /api/v2/ai/sessions/{session_id} — retrieve a cached analysis result

SSE event stream format:
  event: status
  data: {"agent": "dimensioning", "status": "running"}

  event: result
  data: {"agent": "dimensioning", "data": {...}}

  event: complete
  data: {"analysis": <AnalysisResult>}

  event: error
  data: {"message": "..."}
"""

from __future__ import annotations

import json
import logging
import uuid as _uuid
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.agents.orchestrator import orchestrate
from app.core.security import get_current_user
from app.db.redis import SESSION_TTL, redis_client
from app.db.session import get_async_db
from app.models.equipment import Equipment
from app.models.project import Project
from app.models.simulation import Simulation
from app.models.user import User
from app.schemas.ai import AnalysisResult, AnalyzeRequest, EquipmentRecommendation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])

_AI_SESSION_PREFIX = "ai:session:"


# ── SSE event generator ───────────────────────────────────────────────────────


async def _analysis_event_generator(
    simulation: Simulation,
    project: Project,
) -> AsyncGenerator[dict[str, Any], None]:
    """Async generator yielding SSE-compatible dicts for the analysis pipeline.

    Emits 'status' events as agents start, 'result' events as they complete,
    a 'complete' event with the full AnalysisResult, and 'error' events for
    non-fatal failures.

    Does NOT accept a db session — it creates its own short-lived session for
    the equipment upsert to avoid leaking the request-scoped connection when
    clients disconnect mid-stream.

    Args:
        simulation: The ORM Simulation instance to analyse.
        project: The owning Project (provides lat/lon and metadata).

    Yields:
        Dicts with ``event`` and ``data`` keys compatible with
        ``sse_starlette.sse.EventSourceResponse``.
    """
    # Emit initial status events for each agent
    for agent_name in ("dimensioning", "report_writer", "qa_validator"):
        yield {
            "event": "status",
            "data": json.dumps({"agent": agent_name, "status": "running"}),
        }

    # Build input dicts from ORM objects
    simulation_result: dict[str, Any] = {
        "annual_kwh": simulation.annual_kwh,
        "peak_kwc": simulation.peak_kwc,
        "specific_yield": simulation.specific_yield or 0.0,
        "performance_ratio": simulation.performance_ratio or 0.0,
        "monthly_data": simulation.monthly_data or [],
        "params_used": simulation.params or {},
    }

    params = simulation.params or {}
    senelec_analysis: dict[str, Any] = {
        "tariff_code": params.get("tariff_code", "DPP"),
        "before_solar_monthly_xof": 0.0,
        "after_solar_monthly_xof": 0.0,
        "annual_savings_xof": simulation.senelec_savings_xof or 0.0,
        "payback_years": simulation.payback_years or 0.0,
        "roi_25yr_percent": simulation.roi_percent or 0.0,
        "monthly_breakdown": [],
    }

    project_info: dict[str, Any] = {
        "latitude": project.latitude,
        "longitude": project.longitude,
        "name": project.name,
        "panel_count": simulation.panel_count,
        "panel_power_wc": params.get("panel_power_wc", 545),
        "monthly_consumption_kwh": params.get("monthly_consumption_kwh", 400.0),
        "installation_cost_xof": params.get("installation_cost_xof", 0.0),
    }

    # Run orchestrator
    try:
        final_state = await orchestrate(
            simulation_id=str(simulation.id),
            simulation_result=simulation_result,
            senelec_analysis=senelec_analysis,
            project_info=project_info,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Orchestrator failed: %s", exc)
        yield {
            "event": "error",
            "data": json.dumps({"message": f"Analysis failed: {exc}"}),
        }
        return

    # Emit result events for each agent
    if final_state.get("equipment_recommendation"):
        yield {
            "event": "result",
            "data": json.dumps({
                "agent": "dimensioning",
                "data": final_state["equipment_recommendation"],
            }),
        }

    if final_state.get("qa_results"):
        yield {
            "event": "result",
            "data": json.dumps({
                "agent": "qa_validator",
                "data": final_state["qa_results"],
            }),
        }

    if final_state.get("report_narrative"):
        yield {
            "event": "result",
            "data": json.dumps({
                "agent": "report_writer",
                "data": {"narrative_length": len(final_state["report_narrative"])},
            }),
        }

    # Build the complete AnalysisResult
    analysis = AnalysisResult.from_agent_state(
        simulation_id=simulation.id,
        state=final_state,
    )

    # Persist equipment recommendation to DB using an independent session so
    # that the request-scoped session (already committed/closed by FastAPI's
    # dependency cleanup) is not reused here, preventing connection leaks.
    equipment_data = final_state.get("equipment_recommendation") or {}
    if equipment_data:
        from app.db.session import AsyncSessionLocal  # noqa: PLC0415
        async with AsyncSessionLocal() as _db:
            await _upsert_equipment(simulation, project, equipment_data, _db)
            await _db.commit()

    # Cache the result in Redis (TTL = SESSION_TTL = 24 h)
    session_id = str(_uuid.uuid4())
    try:
        await redis_client.cache_set(
            f"{_AI_SESSION_PREFIX}{session_id}",
            analysis.model_dump_json(),
            SESSION_TTL,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis cache write failed for session %s: %s", session_id, exc)

    # Emit errors (non-fatal) if any
    for err in final_state.get("errors", []):
        yield {
            "event": "error",
            "data": json.dumps({"message": err}),
        }

    # Final 'complete' event
    yield {
        "event": "complete",
        "data": json.dumps({
            "analysis": analysis.model_dump(mode="json"),
            "session_id": session_id,
        }),
    }


async def _upsert_equipment(
    simulation: Simulation,
    project: Project,
    equipment_data: dict[str, Any],
    db: AsyncSession,
) -> None:
    """Create or update the Equipment record for the project.

    Args:
        simulation: The source simulation (used for panel metadata).
        project: The owning project.
        equipment_data: Dict from DimensioningAgent (inverter_model, etc.).
        db: Async database session.
    """
    params = simulation.params or {}
    panel_power_wc = int(params.get("panel_power_wc", 545))
    panel_model = equipment_data.get(
        "panel_recommendation",
        f"JA Solar JAM72S30 {panel_power_wc}W",
    )

    result = await db.execute(
        select(Equipment).where(Equipment.project_id == project.id)
    )
    existing: Equipment | None = result.scalar_one_or_none()

    if existing is not None:
        existing.inverter_model = equipment_data.get("inverter_model", existing.inverter_model)
        existing.inverter_kva = float(equipment_data.get("inverter_kva", existing.inverter_kva))
        existing.battery_model = equipment_data.get("battery_model", existing.battery_model)
        existing.battery_kwh = equipment_data.get("battery_kwh", existing.battery_kwh)
        existing.details = equipment_data
        logger.info("Updated Equipment for project %s", project.id)
    else:
        new_equipment = Equipment.create(
            project_id=project.id,
            panel_model=panel_model,
            panel_power_wc=panel_power_wc,
            inverter_model=equipment_data.get("inverter_model", "Unknown"),
            inverter_kva=float(equipment_data.get("inverter_kva", 0.0)),
            battery_model=equipment_data.get("battery_model"),
            battery_kwh=equipment_data.get("battery_kwh"),
            details=equipment_data,
        )
        db.add(new_equipment)
        logger.info("Created Equipment for project %s", project.id)


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "/analyze",
    summary="Run multi-agent AI analysis and stream results as SSE",
    response_description="Server-Sent Events stream with analysis progress and results",
)
async def analyze_simulation(
    body: AnalyzeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),  # used only for ownership checks
) -> EventSourceResponse:
    """Run all AI agents on the given simulation and stream results as SSE.

    The endpoint streams the following event types in order:
    1. ``status`` events (one per agent) as agents begin
    2. ``result`` events (one per agent) as agents complete
    3. ``error`` events for any non-fatal agent failures
    4. ``complete`` event with the full ``AnalysisResult`` payload

    Args:
        body: Request body containing ``simulation_id``.
        current_user: Authenticated user resolved from the Bearer token.
        db: Async database session.

    Returns:
        An ``EventSourceResponse`` (HTTP 200, ``text/event-stream`` content type).

    Raises:
        HTTPException: 404 if the simulation does not exist or belongs to
            a project owned by a different user.
    """
    # Load simulation, verify it belongs to current_user via project ownership
    result = await db.execute(
        select(Simulation)
        .join(Project, Simulation.project_id == Project.id)
        .where(
            Simulation.id == body.simulation_id,
            Project.user_id == current_user.id,
        )
    )
    simulation: Simulation | None = result.scalar_one_or_none()
    if simulation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation not found or access denied.",
        )

    # Load the owning project (needed for lat/lon + name)
    project_result = await db.execute(
        select(Project).where(Project.id == simulation.project_id)
    )
    project: Project | None = project_result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    return EventSourceResponse(
        _analysis_event_generator(simulation, project),
        media_type="text/event-stream",
    )


@router.get(
    "/sessions/{session_id}",
    response_model=AnalysisResult,
    summary="Retrieve a cached AI analysis result",
    status_code=status.HTTP_200_OK,
)
async def get_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    db: AsyncSession = Depends(get_async_db),  # noqa: ARG001
) -> AnalysisResult:
    """Retrieve a previously computed analysis result from Redis cache.

    Session results are stored with key ``ai:session:{uuid}`` and a 24-hour TTL.

    Args:
        session_id: UUID of the analysis session to retrieve.
        current_user: Authenticated user (ensures endpoint is protected;
            session data is not user-scoped as it is keyed only by UUID).
        db: Async database session (injected but unused — Redis only).

    Returns:
        The cached ``AnalysisResult`` as a JSON response.

    Raises:
        HTTPException: 404 if the session has expired or was never created.
    """
    cache_key = f"{_AI_SESSION_PREFIX}{session_id}"
    cached_json: str | None = None

    try:
        cached_json = await redis_client.cache_get(cache_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis read failed for session %s: %s", session_id, exc)

    if cached_json is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found or expired (TTL=24h).",
        )

    try:
        return AnalysisResult.model_validate_json(cached_json)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to deserialise session %s: %s", session_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deserialise cached session data.",
        ) from exc
