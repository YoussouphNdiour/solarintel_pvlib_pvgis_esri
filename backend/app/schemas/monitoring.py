"""Pydantic schemas for MON-001 monitoring endpoints.

Defines request/response models for:
- GET /api/v2/monitoring/{project_id}/stats
- GET /api/v2/monitoring/{project_id}/history
- GET /api/v2/monitoring/{project_id}/monthly
- WebSocket events pushed to connected clients
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProductionStatsResponse(BaseModel):
    """Response model for current production KPIs vs simulation baseline."""

    todayKwh: float
    monthKwh: float
    yearKwh: float
    todayExpectedKwh: float
    monthExpectedKwh: float
    yearExpectedKwh: float
    todayPerformancePct: float
    monthPerformancePct: float
    yearPerformancePct: float
    lastReadingAt: datetime | None
    dataPointsToday: int


class MonitoringReadingResponse(BaseModel):
    """Single telemetry reading from the monitoring table."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    projectId: UUID
    timestamp: datetime
    productionKwh: float
    irradianceWm2: float | None
    temperatureC: float | None
    source: str

    @classmethod
    def from_orm_entry(cls, entry: object) -> "MonitoringReadingResponse":
        """Map ORM Monitoring fields to camelCase response schema.

        Args:
            entry: A ``Monitoring`` ORM instance.

        Returns:
            A populated ``MonitoringReadingResponse``.
        """
        from app.models.monitoring import Monitoring  # local import to avoid circulars

        m: Monitoring = entry  # type: ignore[assignment]
        return cls(
            id=m.id,
            projectId=m.project_id,
            timestamp=m.timestamp,
            productionKwh=m.production_kwh,
            irradianceWm2=m.irradiance_wm2,
            temperatureC=m.temperature_c,
            source=m.source,
        )


class MonitoringHistoryResponse(BaseModel):
    """Cursor-paginated list of monitoring readings."""

    items: list[MonitoringReadingResponse]
    nextCursor: str | None
    total: int


class MonthlyComparisonResponse(BaseModel):
    """Actual vs simulated comparison for a single calendar month."""

    month: int
    year: int
    actualKwh: float
    simulatedKwh: float
    performancePct: float
    irradianceKwhM2: float | None
