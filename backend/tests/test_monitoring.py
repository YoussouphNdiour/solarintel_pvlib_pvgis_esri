"""TDD tests for MON-001: monitoring service, alert service, WebSocket, and API.

Test categories:
- AlertService: threshold logic, cooldown, monthly report
- MonitoringService: daily/monthly/yearly aggregation, comparison, performance
- WebSocket: auth, events, clean disconnect
- API: history pagination, stats endpoint, ownership enforcement
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.monitoring import Monitoring
from app.models.project import Project
from app.models.simulation import Simulation
from app.models.user import User
from app.services.alert_service import AlertService, PERFORMANCE_THRESHOLD, ALERT_COOLDOWN_TTL
from app.services.monitoring_service import MonitoringService, ProductionStats


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_user(db: AsyncSession) -> User:
    user = User.create(email=f"user_{uuid.uuid4().hex[:8]}@test.com", role="client")
    db.add(user)
    return user


def _make_project(user_id: uuid.UUID, db: AsyncSession) -> Project:
    project = Project.create(
        user_id=user_id,
        name="Test Solar Farm",
        latitude=14.71,
        longitude=-17.44,
    )
    db.add(project)
    return project


def _make_simulation(
    project_id: uuid.UUID,
    db: AsyncSession,
    annual_kwh: float = 3650.0,
    monthly_data: list | None = None,
) -> Simulation:
    if monthly_data is None:
        # 12 equal months of 10 kWh/day × ~30 days = 304.2 kWh each
        monthly_data = [{"month": i, "energy_kwh": annual_kwh / 12} for i in range(1, 13)]
    sim = Simulation.create(
        project_id=project_id,
        panel_count=10,
        peak_kwc=3.0,
        annual_kwh=annual_kwh,
        monthly_data=monthly_data,
    )
    db.add(sim)
    return sim


def _make_monitoring_entry(
    project_id: uuid.UUID,
    db: AsyncSession,
    timestamp: datetime,
    production_kwh: float = 1.0,
) -> Monitoring:
    entry = Monitoring.create(
        project_id=project_id,
        timestamp=timestamp,
        production_kwh=production_kwh,
        source="webhook",
    )
    db.add(entry)
    return entry


# ── MonitoringService tests ───────────────────────────────────────────────────


async def test_get_today_production(async_session: AsyncSession) -> None:
    """Sum of monitoring entries for today returns correct total."""
    user = _make_user(async_session)
    await async_session.flush()
    project = _make_project(user.id, async_session)
    _make_simulation(project.id, async_session)
    await async_session.flush()

    today = datetime.now(tz=timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)

    _make_monitoring_entry(project.id, async_session, today, production_kwh=5.0)
    _make_monitoring_entry(project.id, async_session, today - timedelta(hours=2), production_kwh=3.0)
    _make_monitoring_entry(project.id, async_session, yesterday, production_kwh=100.0)
    await async_session.flush()

    svc = MonitoringService()
    stats = await svc.get_stats(project.id, async_session, reference_date=today.date())

    assert stats.today_kwh == pytest.approx(8.0, rel=1e-3)


async def test_get_monthly_production(async_session: AsyncSession) -> None:
    """Sum for current month excludes entries from other months."""
    user = _make_user(async_session)
    await async_session.flush()
    project = _make_project(user.id, async_session)
    _make_simulation(project.id, async_session)
    await async_session.flush()

    now = datetime.now(tz=timezone.utc)
    this_month = now.replace(day=1, hour=10)
    last_month = (now.replace(day=1) - timedelta(days=1)).replace(hour=10)

    _make_monitoring_entry(project.id, async_session, this_month, production_kwh=50.0)
    _make_monitoring_entry(project.id, async_session, this_month + timedelta(days=1), production_kwh=30.0)
    _make_monitoring_entry(project.id, async_session, last_month, production_kwh=999.0)
    await async_session.flush()

    svc = MonitoringService()
    stats = await svc.get_stats(project.id, async_session, reference_date=now.date())

    assert stats.month_kwh == pytest.approx(80.0, rel=1e-3)


async def test_get_yearly_production(async_session: AsyncSession) -> None:
    """Sum for current year excludes entries from the prior year."""
    user = _make_user(async_session)
    await async_session.flush()
    project = _make_project(user.id, async_session)
    _make_simulation(project.id, async_session)
    await async_session.flush()

    now = datetime.now(tz=timezone.utc)
    this_year = now.replace(month=1, day=15, hour=10)
    prior_year = this_year.replace(year=this_year.year - 1)

    _make_monitoring_entry(project.id, async_session, this_year, production_kwh=200.0)
    _make_monitoring_entry(project.id, async_session, this_year + timedelta(days=30), production_kwh=150.0)
    _make_monitoring_entry(project.id, async_session, prior_year, production_kwh=9999.0)
    await async_session.flush()

    svc = MonitoringService()
    stats = await svc.get_stats(project.id, async_session, reference_date=now.date())

    assert stats.year_kwh == pytest.approx(350.0, rel=1e-3)


async def test_production_vs_simulated(async_session: AsyncSession) -> None:
    """Monthly comparison returns actual vs expected values for last N months."""
    user = _make_user(async_session)
    await async_session.flush()
    project = _make_project(user.id, async_session)
    _make_simulation(project.id, async_session, annual_kwh=1200.0)
    await async_session.flush()

    now = datetime.now(tz=timezone.utc)
    _make_monitoring_entry(project.id, async_session, now, production_kwh=75.0)
    await async_session.flush()

    svc = MonitoringService()
    comparisons = await svc.get_monthly_comparison(project.id, async_session, months=1)

    assert len(comparisons) == 1
    assert comparisons[0].actual_kwh == pytest.approx(75.0, rel=1e-3)
    # simulated should be approx 100 kWh/month (1200/12)
    assert comparisons[0].simulated_kwh == pytest.approx(100.0, rel=1e-2)


async def test_performance_percentage(async_session: AsyncSession) -> None:
    """Performance is actual/expected * 100, clamped to [0, 150]."""
    user = _make_user(async_session)
    await async_session.flush()
    project = _make_project(user.id, async_session)
    # Give it 3650 annual_kwh → 10 kWh/day expected
    _make_simulation(project.id, async_session, annual_kwh=3650.0)
    await async_session.flush()

    now = datetime.now(tz=timezone.utc)
    today = now.date()

    # Expected today = 3650 / 365 ≈ 10.0 kWh
    # Actual = 8.5 → performance ≈ 85%
    _make_monitoring_entry(project.id, async_session, now, production_kwh=8.5)
    await async_session.flush()

    svc = MonitoringService()
    stats = await svc.get_stats(project.id, async_session, reference_date=today)

    assert 0.0 <= stats.today_performance_pct <= 150.0
    # With 8.5 actual vs ~10.0 expected, pct should be roughly 85
    assert stats.today_performance_pct == pytest.approx(85.0, rel=0.05)


# ── AlertService tests ────────────────────────────────────────────────────────


async def test_alert_fires_when_production_below_threshold(
    async_session: AsyncSession,
) -> None:
    """75% of expected production → alert triggered, WhatsApp called."""
    user = _make_user(async_session)
    await async_session.flush()
    project = _make_project(user.id, async_session)
    # 3650 / 365 = 10 kWh/day expected; 7.5 kWh = 75% → below 80%
    _make_simulation(project.id, async_session, annual_kwh=3650.0)
    await async_session.flush()

    now = datetime.now(tz=timezone.utc)
    _make_monitoring_entry(project.id, async_session, now, production_kwh=7.5)
    await async_session.flush()

    fake_redis = AsyncMock()
    fake_redis.cache_get = AsyncMock(return_value=None)  # no cooldown
    fake_redis.cache_set = AsyncMock()

    fake_whatsapp = AsyncMock()
    fake_whatsapp.send_simulation_alert = AsyncMock(return_value={})

    svc = AlertService()
    svc._whatsapp = fake_whatsapp

    with patch("app.services.alert_service.redis_client", fake_redis):
        sent = await svc.check_and_alert(
            project_id=project.id,
            db=async_session,
            technician_phone="+221771234567",
        )

    assert sent is True
    fake_whatsapp.send_simulation_alert.assert_awaited_once()
    fake_redis.cache_set.assert_awaited_once()


async def test_alert_suppressed_when_above_threshold(
    async_session: AsyncSession,
) -> None:
    """85% of expected production → no alert sent."""
    user = _make_user(async_session)
    await async_session.flush()
    project = _make_project(user.id, async_session)
    # 10 kWh/day expected; 8.5 kWh = 85% → above 80%
    _make_simulation(project.id, async_session, annual_kwh=3650.0)
    await async_session.flush()

    now = datetime.now(tz=timezone.utc)
    _make_monitoring_entry(project.id, async_session, now, production_kwh=8.5)
    await async_session.flush()

    fake_redis = AsyncMock()
    fake_redis.cache_get = AsyncMock(return_value=None)
    fake_redis.cache_set = AsyncMock()

    fake_whatsapp = AsyncMock()
    fake_whatsapp.send_simulation_alert = AsyncMock(return_value={})

    svc = AlertService()
    svc._whatsapp = fake_whatsapp

    with patch("app.services.alert_service.redis_client", fake_redis):
        sent = await svc.check_and_alert(
            project_id=project.id,
            db=async_session,
            technician_phone="+221771234567",
        )

    assert sent is False
    fake_whatsapp.send_simulation_alert.assert_not_awaited()
    fake_redis.cache_set.assert_not_awaited()


async def test_alert_cooldown(async_session: AsyncSession) -> None:
    """Second alert within 24h is suppressed via Redis cooldown key."""
    user = _make_user(async_session)
    await async_session.flush()
    project = _make_project(user.id, async_session)
    # Below threshold: 5.0 out of 10.0 expected = 50%
    _make_simulation(project.id, async_session, annual_kwh=3650.0)
    await async_session.flush()

    now = datetime.now(tz=timezone.utc)
    _make_monitoring_entry(project.id, async_session, now, production_kwh=5.0)
    await async_session.flush()

    # Simulate cooldown key already present in Redis
    fake_redis = AsyncMock()
    fake_redis.cache_get = AsyncMock(return_value="1")  # cooldown active
    fake_redis.cache_set = AsyncMock()

    fake_whatsapp = AsyncMock()
    fake_whatsapp.send_simulation_alert = AsyncMock(return_value={})

    svc = AlertService()
    svc._whatsapp = fake_whatsapp

    with patch("app.services.alert_service.redis_client", fake_redis):
        sent = await svc.check_and_alert(
            project_id=project.id,
            db=async_session,
            technician_phone="+221771234567",
        )

    assert sent is False
    fake_whatsapp.send_simulation_alert.assert_not_awaited()


async def test_monthly_report_generates_pdf_path(async_session: AsyncSession) -> None:
    """Monthly report task returns a valid file path string ending in .pdf."""
    user = _make_user(async_session)
    await async_session.flush()
    project = _make_project(user.id, async_session)
    _make_simulation(project.id, async_session, annual_kwh=3650.0)
    await async_session.flush()

    fake_whatsapp = AsyncMock()
    fake_whatsapp.send_pdf_quote = AsyncMock(return_value={})

    svc = AlertService()
    svc._whatsapp = fake_whatsapp

    pdf_path = await svc.send_monthly_report(
        project_id=project.id,
        db=async_session,
        client_phone="+221771234567",
    )

    assert isinstance(pdf_path, str)
    assert pdf_path.endswith(".pdf")


# ── WebSocket tests ───────────────────────────────────────────────────────────
#
# These tests use starlette's synchronous TestClient which has native WebSocket
# support. Each test creates its own in-memory SQLite engine+session so that
# the synchronous TestClient's internal event loop can access the DB without
# sharing an async session that was created on a different loop.


def _make_sync_app_with_data():
    """Return (app, user, project, token) with a fresh in-memory SQLite DB.

    The app has get_async_db overridden with a session backed by that engine
    so that TestClient's internal event loop can drive all DB queries.
    """
    import asyncio
    import json as _json
    from app.core.security import create_access_token
    from app.db.session import get_async_db
    from app.api.v2.monitoring import router as monitoring_router
    from app.models import Base
    from sqlalchemy.dialects.postgresql import JSONB
    from sqlalchemy.types import JSON, TypeDecorator

    class _JsonbCompat(TypeDecorator):  # type: ignore[type-arg]
        impl = JSON
        cache_ok = True

        def process_bind_param(self, value, dialect):
            return None if value is None else _json.dumps(value)

        def process_result_value(self, value, dialect):
            if value is None:
                return None
            return _json.loads(value) if isinstance(value, str) else value

    # Patch JSONB columns for SQLite
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = _JsonbCompat()

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
        session = factory()

        user = User.create(email=f"ws_{uuid.uuid4().hex[:8]}@test.com", role="client")
        session.add(user)
        await session.flush()

        project = Project.create(user_id=user.id, name="WS Project", latitude=14.7, longitude=-17.4)
        session.add(project)

        sim = Simulation.create(project_id=project.id, panel_count=10, peak_kwc=3.0, annual_kwh=3650.0)
        session.add(sim)
        await session.flush()
        await session.commit()
        return session, user, project

    session, user, project = asyncio.get_event_loop().run_until_complete(_setup())
    token = create_access_token(user.id, user.role)

    app = FastAPI()
    app.include_router(monitoring_router)

    async def override_db():
        yield session

    app.dependency_overrides[get_async_db] = override_db
    return app, user, project, token, session


def test_websocket_connect_authenticated() -> None:
    """JWT in query param → WebSocket connection accepted, stats received."""
    from fastapi.testclient import TestClient

    app, user, project, token, _ = _make_sync_app_with_data()

    with TestClient(app) as client:
        with client.websocket_connect(
            f"/monitoring/{project.id}/ws?token={token}"
        ) as ws:
            data = ws.receive_json()
            assert data["type"] == "stats"
            assert "data" in data


def test_websocket_connect_unauthenticated() -> None:
    """No valid token → WebSocket connection rejected (closed with 4001)."""
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect as StarletteDisconnect

    app, _, project, _, _ = _make_sync_app_with_data()

    with TestClient(app) as client:
        with pytest.raises(StarletteDisconnect) as exc_info:
            with client.websocket_connect(
                f"/monitoring/{project.id}/ws?token=bad.token.value"
            ) as ws:
                ws.receive_json()  # should raise on bad auth

        assert exc_info.value.code == 4001


def test_websocket_receives_monitoring_event() -> None:
    """After a broadcast, the connected WS client receives the JSON event."""
    import asyncio
    from fastapi.testclient import TestClient
    from app.core.websocket_manager import ws_manager

    app, _, project, token, _ = _make_sync_app_with_data()
    project_id_str = str(project.id)

    with TestClient(app) as client:
        with client.websocket_connect(
            f"/monitoring/{project_id_str}/ws?token={token}"
        ) as ws:
            initial = ws.receive_json()
            assert initial["type"] == "stats"

            # Trigger a broadcast from outside the WS handler
            asyncio.get_event_loop().run_until_complete(
                ws_manager.broadcast(project_id_str, {
                    "type": "reading",
                    "data": {"timestamp": "2025-01-01T10:00:00Z", "production_kwh": 4.5},
                })
            )

            event = ws.receive_json()
            assert event["type"] == "reading"
            assert event["data"]["production_kwh"] == pytest.approx(4.5)


def test_websocket_disconnect_clean() -> None:
    """Client disconnect removes the connection from the manager without errors."""
    from fastapi.testclient import TestClient
    from app.core.websocket_manager import ws_manager

    app, _, project, token, _ = _make_sync_app_with_data()
    project_id_str = str(project.id)

    before_count = ws_manager.active_connections(project_id_str)

    with TestClient(app) as client:
        with client.websocket_connect(
            f"/monitoring/{project_id_str}/ws?token={token}"
        ) as ws:
            ws.receive_json()  # consume initial stats
            in_session_count = ws_manager.active_connections(project_id_str)
            assert in_session_count > before_count
        # Context exit triggers clean disconnect

    after_count = ws_manager.active_connections(project_id_str)
    assert after_count == before_count


# ── API tests ─────────────────────────────────────────────────────────────────


async def test_get_monitoring_history(async_session: AsyncSession) -> None:
    """GET /monitoring/{project_id}/history returns paginated list."""
    from app.core.security import create_access_token, get_current_user
    from app.db.session import get_async_db
    from app.api.v2.monitoring import router as monitoring_router

    user = _make_user(async_session)
    await async_session.flush()
    project = _make_project(user.id, async_session)
    _make_simulation(project.id, async_session)
    await async_session.flush()

    now = datetime.now(tz=timezone.utc)
    for i in range(5):
        _make_monitoring_entry(
            project.id, async_session,
            now - timedelta(hours=i),
            production_kwh=float(i + 1),
        )
    await async_session.flush()

    token = create_access_token(user.id, user.role)
    app = FastAPI()
    app.include_router(monitoring_router)

    async def override_db():
        yield async_session

    async def override_user():
        return user

    app.dependency_overrides[get_async_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/monitoring/{project.id}/history",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert len(body["items"]) == 5
    assert "nextCursor" in body
    assert "total" in body


async def test_get_monitoring_stats(async_session: AsyncSession) -> None:
    """GET /monitoring/{project_id}/stats returns today/month/year KPIs."""
    from app.core.security import create_access_token, get_current_user
    from app.db.session import get_async_db
    from app.api.v2.monitoring import router as monitoring_router

    user = _make_user(async_session)
    await async_session.flush()
    project = _make_project(user.id, async_session)
    _make_simulation(project.id, async_session, annual_kwh=3650.0)
    await async_session.flush()

    now = datetime.now(tz=timezone.utc)
    _make_monitoring_entry(project.id, async_session, now, production_kwh=9.0)
    await async_session.flush()

    token = create_access_token(user.id, user.role)
    app = FastAPI()
    app.include_router(monitoring_router)

    async def override_db():
        yield async_session

    async def override_user():
        return user

    app.dependency_overrides[get_async_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/monitoring/{project.id}/stats",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    body = resp.json()
    required_keys = {
        "todayKwh", "monthKwh", "yearKwh",
        "todayExpectedKwh", "monthExpectedKwh", "yearExpectedKwh",
        "todayPerformancePct", "monthPerformancePct", "yearPerformancePct",
        "lastReadingAt", "dataPointsToday",
    }
    assert required_keys.issubset(body.keys())
    assert body["todayKwh"] == pytest.approx(9.0, rel=1e-3)


async def test_monitoring_wrong_user(async_session: AsyncSession) -> None:
    """GET /monitoring/{project_id}/stats returns 404 for another user's project."""
    from app.core.security import create_access_token, get_current_user
    from app.db.session import get_async_db
    from app.api.v2.monitoring import router as monitoring_router

    owner = _make_user(async_session)
    intruder = _make_user(async_session)
    await async_session.flush()

    project = _make_project(owner.id, async_session)
    _make_simulation(project.id, async_session)
    await async_session.flush()

    # intruder tries to access owner's project
    app = FastAPI()
    app.include_router(monitoring_router)

    async def override_db():
        yield async_session

    async def override_user():
        return intruder  # authenticated but wrong user

    app.dependency_overrides[get_async_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    token = create_access_token(intruder.id, intruder.role)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/monitoring/{project.id}/stats",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 404
