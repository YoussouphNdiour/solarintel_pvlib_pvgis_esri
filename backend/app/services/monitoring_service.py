"""Monitoring data aggregation service.

Computes production statistics (daily/monthly/yearly) from the monitoring table
and compares against expected values from the linked simulation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.monitoring import Monitoring
from app.models.simulation import Simulation


@dataclass
class ProductionStats:
    """Aggregated production KPIs for today/month/year vs simulation baseline."""

    today_kwh: float
    month_kwh: float
    year_kwh: float
    today_expected_kwh: float
    month_expected_kwh: float
    year_expected_kwh: float
    today_performance_pct: float   # clamped [0, 150]
    month_performance_pct: float
    year_performance_pct: float
    last_reading_at: datetime | None
    data_points_today: int


@dataclass
class MonthlyComparison:
    """Actual vs simulated comparison for a single calendar month."""

    month: int
    year: int
    actual_kwh: float
    simulated_kwh: float
    performance_pct: float
    irradiance_kwh_m2: float | None


def _clamp_pct(actual: float, expected: float) -> float:
    """Return actual / expected * 100 clamped to [0, 150]. 0 when expected <= 0."""
    if expected <= 0:
        return 0.0
    return min(max(actual / expected * 100.0, 0.0), 150.0)


def _day_bounds(ref: date) -> tuple[datetime, datetime]:
    """UTC [start_of_day, start_of_next_day) for ref."""
    start = datetime(ref.year, ref.month, ref.day, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def _month_bounds(ref: date) -> tuple[datetime, datetime]:
    """UTC [first_of_month, first_of_next_month) for ref."""
    start = datetime(ref.year, ref.month, 1, tzinfo=timezone.utc)
    if ref.month == 12:
        end = datetime(ref.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(ref.year, ref.month + 1, 1, tzinfo=timezone.utc)
    return start, end


def _year_bounds(ref: date) -> tuple[datetime, datetime]:
    """UTC [Jan 1, Jan 1 next year) for ref."""
    return (
        datetime(ref.year, 1, 1, tzinfo=timezone.utc),
        datetime(ref.year + 1, 1, 1, tzinfo=timezone.utc),
    )


class MonitoringService:
    """Aggregates monitoring telemetry and compares it against simulation data."""

    async def _sum_production(
        self, project_id: UUID, db: AsyncSession, start: datetime, end: datetime
    ) -> float:
        """Sum production_kwh within [start, end). Returns 0.0 when no rows."""
        stmt = select(func.coalesce(func.sum(Monitoring.production_kwh), 0.0)).where(
            Monitoring.project_id == project_id,
            Monitoring.timestamp >= start,
            Monitoring.timestamp < end,
        )
        result = await db.execute(stmt)
        return float(result.scalar() or 0.0)

    async def _count_entries(
        self, project_id: UUID, db: AsyncSession, start: datetime, end: datetime
    ) -> int:
        """Count monitoring rows within [start, end)."""
        stmt = select(func.count()).where(
            Monitoring.project_id == project_id,
            Monitoring.timestamp >= start,
            Monitoring.timestamp < end,
        )
        result = await db.execute(stmt)
        return int(result.scalar() or 0)

    async def _latest_timestamp(
        self, project_id: UUID, db: AsyncSession
    ) -> datetime | None:
        """Return the most recent monitoring timestamp, or None."""
        stmt = select(func.max(Monitoring.timestamp)).where(
            Monitoring.project_id == project_id
        )
        result = await db.execute(stmt)
        return result.scalar()  # type: ignore[return-value]

    async def _get_latest_simulation(
        self, project_id: UUID, db: AsyncSession
    ) -> Simulation | None:
        """Fetch the most recently created completed simulation."""
        stmt = (
            select(Simulation)
            .where(
                Simulation.project_id == project_id,
                Simulation.status == "completed",
            )
            .order_by(Simulation.id.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    def _expected_daily_kwh(self, sim: Simulation | None) -> float:
        """annual_kwh / 365, or 0 when no simulation."""
        if sim is None or sim.annual_kwh <= 0:
            return 0.0
        return sim.annual_kwh / 365.0

    def _expected_monthly_kwh(self, sim: Simulation | None, month: int) -> float:
        """Expected kWh for a month from monthly_data or annual/12."""
        if sim is None:
            return 0.0
        if sim.monthly_data:
            for entry in sim.monthly_data:
                if isinstance(entry, dict) and entry.get("month") == month:
                    return float(entry.get("energy_kwh", 0.0))
        return sim.annual_kwh / 12.0

    def _expected_yearly_kwh(self, sim: Simulation | None) -> float:
        """annual_kwh from simulation, or 0."""
        return 0.0 if sim is None else sim.annual_kwh

    async def get_stats(
        self,
        project_id: UUID,
        db: AsyncSession,
        reference_date: date | None = None,
    ) -> ProductionStats:
        """Compute today/month/year production vs simulation.

        Args:
            project_id: UUID of the project to aggregate.
            db: Active async database session.
            reference_date: Override "today" for testing; defaults to UTC today.

        Returns:
            A ``ProductionStats`` dataclass with all KPI fields populated.
        """
        ref = reference_date or datetime.now(tz=timezone.utc).date()
        day_start, day_end = _day_bounds(ref)
        month_start, month_end = _month_bounds(ref)
        year_start, year_end = _year_bounds(ref)

        today_kwh = await self._sum_production(project_id, db, day_start, day_end)
        month_kwh = await self._sum_production(project_id, db, month_start, month_end)
        year_kwh = await self._sum_production(project_id, db, year_start, year_end)
        data_points_today = await self._count_entries(project_id, db, day_start, day_end)
        last_reading_at = await self._latest_timestamp(project_id, db)
        sim = await self._get_latest_simulation(project_id, db)

        today_exp = self._expected_daily_kwh(sim)
        month_exp = self._expected_monthly_kwh(sim, ref.month)
        year_exp = self._expected_yearly_kwh(sim)

        return ProductionStats(
            today_kwh=today_kwh,
            month_kwh=month_kwh,
            year_kwh=year_kwh,
            today_expected_kwh=today_exp,
            month_expected_kwh=month_exp,
            year_expected_kwh=year_exp,
            today_performance_pct=_clamp_pct(today_kwh, today_exp),
            month_performance_pct=_clamp_pct(month_kwh, month_exp),
            year_performance_pct=_clamp_pct(year_kwh, year_exp),
            last_reading_at=last_reading_at,
            data_points_today=data_points_today,
        )

    async def get_monthly_comparison(
        self,
        project_id: UUID,
        db: AsyncSession,
        months: int = 12,
    ) -> list[MonthlyComparison]:
        """Compare actual vs simulated production for the last N months.

        Args:
            project_id: UUID of the project.
            db: Active async database session.
            months: How many past calendar months to include (default 12).

        Returns:
            List of ``MonthlyComparison`` ordered from oldest to newest.
        """
        sim = await self._get_latest_simulation(project_id, db)
        now = datetime.now(tz=timezone.utc)
        results: list[MonthlyComparison] = []

        for offset in range(months - 1, -1, -1):
            year = now.year
            month = now.month - offset
            while month <= 0:
                month += 12
                year -= 1

            m_start, m_end = _month_bounds(date(year, month, 1))
            actual = await self._sum_production(project_id, db, m_start, m_end)
            simulated = self._expected_monthly_kwh(sim, month)

            results.append(MonthlyComparison(
                month=month,
                year=year,
                actual_kwh=actual,
                simulated_kwh=simulated,
                performance_pct=_clamp_pct(actual, simulated),
                irradiance_kwh_m2=None,
            ))

        return results

    async def get_history(
        self,
        project_id: UUID,
        db: AsyncSession,
        limit: int = 100,
        cursor: datetime | None = None,
    ) -> tuple[list[Monitoring], datetime | None]:
        """Paginated monitoring history, cursor-based on timestamp (descending).

        Args:
            project_id: UUID of the project.
            db: Active async database session.
            limit: Max entries per page (server-side cap at 500).
            cursor: Exclusive upper-bound timestamp from previous page.

        Returns:
            Tuple of (rows, next_cursor). ``next_cursor`` is None on last page.
        """
        stmt = (
            select(Monitoring)
            .where(Monitoring.project_id == project_id)
            .order_by(Monitoring.timestamp.desc())
        )
        if cursor is not None:
            stmt = stmt.where(Monitoring.timestamp < cursor)

        stmt = stmt.limit(limit + 1)
        result = await db.execute(stmt)
        rows = list(result.scalars().all())

        next_cursor: datetime | None = None
        if len(rows) > limit:
            rows = rows[:limit]
            next_cursor = rows[-1].timestamp

        return rows, next_cursor
