"""Webhook endpoints for inverter data ingestion and weather data pulls.

POST /api/v2/webhooks/inverter        — SunSpec data, HMAC-authenticated
GET  /api/v2/webhooks/weather/{id}    — On-demand Open-Meteo fetch
POST /api/v2/webhooks/whatsapp/send-report — PDF delivery via WhatsApp

Cache key: weather:correction:{project_id}  TTL: 1 hour
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import get_current_user
from app.db.redis import redis_client
from app.db.session import get_async_db
from app.models.monitoring import Monitoring
from app.models.project import Project
from app.models.report import Report
from app.models.simulation import Simulation
from app.models.user import User
from app.schemas.webhook import SendReportRequest
from app.services.weather_service import WeatherService
from app.services.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_WEATHER_CORRECTION_TTL: int = 60 * 60  # 1 hour


# ── Pydantic models ───────────────────────────────────────────────────────────


class InverterPayload(BaseModel):
    """SunSpec inverter telemetry payload from a field device."""

    project_id: str
    timestamp: str
    production_kwh: float
    power_kw: float | None = None
    irradiance_wm2: float | None = None
    temperature_c: float | None = None
    device_id: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────


def _verify_signature(body: bytes, header_sig: str | None, secret: str) -> bool:
    """Return True if header_sig matches HMAC-SHA256(secret, body)."""
    if not header_sig:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header_sig)


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/inverter")
async def receive_inverter_data(
    request: Request,
    x_webhook_signature: str | None = Header(default=None),
    db: AsyncSession = Depends(get_async_db),
) -> dict:  # type: ignore[type-arg]
    """Receive SunSpec inverter data. Saves a Monitoring record.

    Raises 401 on bad/missing HMAC signature, 404 on unknown project.
    """
    settings = get_settings()
    secret = settings.webhook_secret or settings.secret_key
    body = await request.body()

    if not _verify_signature(body, x_webhook_signature, secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing webhook signature.",
        )

    try:
        payload = InverterPayload(**json.loads(body))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid payload: {exc}",
        ) from exc

    try:
        project_uuid = UUID(payload.project_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="project_id is not a valid UUID.",
        ) from exc

    result = await db.execute(select(Project).where(Project.id == project_uuid))
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {payload.project_id} not found.",
        )

    try:
        ts = datetime.fromisoformat(payload.timestamp)
    except ValueError:
        ts = datetime.now(tz=timezone.utc)

    monitoring = Monitoring.create(
        project_id=project_uuid,
        timestamp=ts,
        production_kwh=payload.production_kwh,
        irradiance_wm2=payload.irradiance_wm2,
        temperature_c=payload.temperature_c,
        source="webhook",
    )
    db.add(monitoring)
    await db.flush()

    logger.info("Monitoring %s saved for project %s", monitoring.id, project_uuid)

    # Broadcast to any WebSocket clients watching this project
    try:
        from app.core.websocket_manager import ws_manager

        await ws_manager.broadcast(str(project_uuid), {
            "type": "reading",
            "data": {
                "timestamp": monitoring.timestamp.isoformat(),
                "production_kwh": monitoring.production_kwh,
                "irradiance_wm2": monitoring.irradiance_wm2,
            },
        })
    except Exception as exc:  # pragma: no cover
        logger.warning("WS broadcast failed for project %s: %s", project_uuid, exc)

    return {"status": "ok", "monitoring_id": str(monitoring.id)}


@router.get("/weather/{project_id}")
async def pull_weather_data(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> dict:  # type: ignore[type-arg]
    """Pull Open-Meteo data for a project. Caches correction under
    ``weather:correction:{project_id}`` with a 1-hour TTL.

    Raises 404 if project missing, 403 if owned by another user.
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project: Project | None = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found.",
        )
    if project.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to this project is not allowed.",
        )

    # Dakar annual mean baseline ≈ 5.5 kWh/m²/day
    svc = WeatherService()
    correction = await svc.compute_correction(
        lat=project.latitude,
        lon=project.longitude,
        simulated_daily_kwh_m2=5.5,
    )

    correction_dict = {
        "correction_factor": correction.correction_factor,
        "measured_daily_kwh_m2": correction.measured_daily_kwh_m2,
        "simulated_daily_kwh_m2": correction.simulated_daily_kwh_m2,
        "temperature_delta_c": correction.temperature_delta_c,
        "date": correction.date,
    }

    try:
        await redis_client.cache_set(
            f"weather:correction:{project_id}",
            json.dumps(correction_dict),
            _WEATHER_CORRECTION_TTL,
        )
    except Exception as exc:
        logger.warning("Failed to cache weather correction: %s", exc)

    return correction_dict


@router.post("/whatsapp/send-report")
async def send_report_whatsapp(
    body: SendReportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> dict:  # type: ignore[type-arg]
    """Send a ready PDF report via WhatsApp. Verifies ownership chain.

    Raises 404 (report/sim not found), 403 (wrong owner), 400 (not ready
    or bad phone), 500 (WhatsApp API failure).
    """
    report_result = await db.execute(select(Report).where(Report.id == body.report_id))
    report: Report | None = report_result.scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report {body.report_id} not found.",
        )
    if report.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Report is not ready (status: {report.status}).",
        )

    sim_result = await db.execute(
        select(Simulation).where(Simulation.id == report.simulation_id)
    )
    simulation: Simulation | None = sim_result.scalar_one_or_none()
    if simulation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation associated with report not found.",
        )

    proj_result = await db.execute(
        select(Project).where(Project.id == simulation.project_id)
    )
    project: Project | None = proj_result.scalar_one_or_none()
    if project is None or project.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to this report is not allowed.",
        )

    pdf_path = report.pdf_path or ""
    filename = pdf_path.split("/")[-1] if pdf_path else f"report_{body.report_id}.pdf"
    pdf_url = f"https://solarintel.app/reports/{body.report_id}/download"
    caption = body.caption or f"Rapport SolarIntel — {project.name}"

    svc = WhatsAppService()
    try:
        normalised_phone = svc.normalize_phone(body.phone)
        await svc.send_pdf_quote(
            phone=normalised_phone,
            pdf_url=pdf_url,
            filename=filename,
            caption=caption,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("WhatsApp send-report failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send WhatsApp message.",
        ) from exc

    return {"status": "sent", "to": normalised_phone}
