"""Monitoring endpoints: REST history/stats + WebSocket real-time feed.

Routes:
  GET  /monitoring/{project_id}/stats    — today/month/year KPIs
  GET  /monitoring/{project_id}/history  — cursor-paginated readings
  GET  /monitoring/{project_id}/monthly  — actual vs simulated (N months)
  WS   /monitoring/{project_id}/ws       — real-time push feed

WebSocket auth: JWT passed as ``?token=`` query param (browsers cannot set
custom headers for WebSocket upgrades).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import (
    APIRouter, Depends, HTTPException, Query,
    WebSocket, WebSocketDisconnect, status,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token, get_current_user
from app.core.websocket_manager import ws_manager
from app.db.session import get_async_db
from app.models.monitoring import Monitoring
from app.models.project import Project
from app.models.user import User
from app.schemas.monitoring import (
    MonitoringHistoryResponse,
    MonitoringReadingResponse,
    MonthlyComparisonResponse,
    ProductionStatsResponse,
)
from app.services.monitoring_service import MonitoringService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

_svc = MonitoringService()
_WS_STATS_INTERVAL: int = 30  # seconds between keep-alive stats pushes


def _to_response(stats: object) -> ProductionStatsResponse:
    """Map ProductionStats dataclass to Pydantic response schema."""
    from app.services.monitoring_service import ProductionStats

    s: ProductionStats = stats  # type: ignore[assignment]
    return ProductionStatsResponse(
        todayKwh=s.today_kwh,
        monthKwh=s.month_kwh,
        yearKwh=s.year_kwh,
        todayExpectedKwh=s.today_expected_kwh,
        monthExpectedKwh=s.month_expected_kwh,
        yearExpectedKwh=s.year_expected_kwh,
        todayPerformancePct=s.today_performance_pct,
        monthPerformancePct=s.month_performance_pct,
        yearPerformancePct=s.year_performance_pct,
        lastReadingAt=s.last_reading_at,
        dataPointsToday=s.data_points_today,
    )


async def _verify_ownership(
    project_id: UUID, user: User, db: AsyncSession
) -> Project:
    """Return the project or raise 404 if missing / owned by another user."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project: Project | None = result.scalar_one_or_none()
    if project is None or project.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found.",
        )
    return project


# ── WebSocket ─────────────────────────────────────────────────────────────────


@router.websocket("/{project_id}/ws")
async def monitoring_ws(
    project_id: UUID,
    ws: WebSocket,
    token: str = Query(...),
    db: AsyncSession = Depends(get_async_db),
) -> None:
    """WebSocket endpoint for real-time monitoring data.

    Auth: JWT passed as ``?token=...`` query parameter.

    Events pushed to client:
      ``{"type": "stats",   "data": ProductionStatsResponse}``  on connect + every 30 s
      ``{"type": "reading", "data": {...}}``                     on new inverter data
      ``{"type": "alert",   "data": {"message": "..."}}``        on performance alert

    On auth failure the socket is closed with code 4001 before acceptance.
    """
    # 1. Validate JWT
    try:
        payload = decode_token(token)
        user_id_str: str | None = payload.get("sub")
        if not user_id_str:
            await ws.close(code=4001)
            return
        user_id = UUID(user_id_str)
    except Exception:
        await ws.close(code=4001)
        return

    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalar_one_or_none()
    if user is None or not user.is_active:
        await ws.close(code=4001)
        return

    # 2. Verify project ownership
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project: Project | None = proj_result.scalar_one_or_none()
    if project is None or project.user_id != user.id:
        await ws.close(code=4001)
        return

    # 3. Accept and register
    await ws_manager.connect(str(project_id), ws)

    try:
        # 4. Initial stats snapshot
        stats = await _svc.get_stats(project_id, db)
        await ws.send_json({"type": "stats", "data": _to_response(stats).model_dump(mode="json")})

        # 5. Keep-alive loop — refresh stats every 30 s
        while True:
            try:
                await asyncio.wait_for(ws.receive_text(), timeout=_WS_STATS_INTERVAL)
            except asyncio.TimeoutError:
                stats = await _svc.get_stats(project_id, db)
                await ws.send_json({"type": "stats", "data": _to_response(stats).model_dump(mode="json")})
            except WebSocketDisconnect:
                break
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(str(project_id), ws)


# ── REST endpoints ────────────────────────────────────────────────────────────


@router.get("/{project_id}/stats", response_model=ProductionStatsResponse)
async def get_stats(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> ProductionStatsResponse:
    """Get today/month/year production KPIs vs simulation baseline.

    Raises 404 when project not found or owned by another user.
    """
    await _verify_ownership(project_id, current_user, db)
    return _to_response(await _svc.get_stats(project_id, db))


@router.get("/{project_id}/history", response_model=MonitoringHistoryResponse)
async def get_history(
    project_id: UUID,
    limit: int = Query(default=100, le=500),
    cursor: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> MonitoringHistoryResponse:
    """Cursor-paginated monitoring history (descending by timestamp).

    Pass ``nextCursor`` from a previous response as ``cursor`` for next page.
    Raises 404 when project not found or owned by another user.
    """
    await _verify_ownership(project_id, current_user, db)

    cursor_dt: datetime | None = None
    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid cursor format: {cursor!r}",
            ) from exc

    rows, next_cursor = await _svc.get_history(project_id, db, limit=limit, cursor=cursor_dt)

    total_result = await db.execute(
        select(func.count()).where(Monitoring.project_id == project_id)
    )
    total = int(total_result.scalar() or 0)

    return MonitoringHistoryResponse(
        items=[MonitoringReadingResponse.from_orm_entry(r) for r in rows],
        nextCursor=next_cursor.isoformat() if next_cursor else None,
        total=total,
    )


@router.get("/{project_id}/monthly", response_model=list[MonthlyComparisonResponse])
async def get_monthly_comparison(
    project_id: UUID,
    months: int = Query(default=12, le=36),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> list[MonthlyComparisonResponse]:
    """Actual vs simulated production comparison for the last N months.

    Raises 404 when project not found or owned by another user.
    """
    await _verify_ownership(project_id, current_user, db)
    comparisons = await _svc.get_monthly_comparison(project_id, db, months=months)
    return [
        MonthlyComparisonResponse(
            month=c.month,
            year=c.year,
            actualKwh=c.actual_kwh,
            simulatedKwh=c.simulated_kwh,
            performancePct=c.performance_pct,
            irradianceKwhM2=c.irradiance_kwh_m2,
        )
        for c in comparisons
    ]
