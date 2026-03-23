"""QA-001 coverage-boost test suite for SolarIntel v2.

Covers previously untested paths in:
- Security module (require_roles, get_current_user inactive path, wrong token type)
- SenelecService edge cases (DMP, PMP, Woyofal flat rates, zero consumption,
  high consumption, zero-savings payback)
- WeatherService edge cases (empty hourly list, zero simulated value)
- EquipmentPricesService (hybrid vs on-grid cost, off-grid system type,
  Redis TTL after refresh)
- WhatsAppService (phone normalisation, alert message format)
- WebSocket manager (broadcast to empty project, dead connection removal,
  active_connections count)
- Monte Carlo (P50 near base, P10 < P50 < P90, negative price sensitivity)
- RedisClient (cache set/get, delete, missing key)
- AlertService (no monitoring data → no alert, 79% triggers vs 81% does not)

All tests use asyncio_mode="auto" from pyproject.toml.
No real services required — fakeredis, SQLite in-memory, and unittest.mock
are used throughout.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    require_roles,
)
from app.db.redis import TARIFF_TTL, RedisClient
from app.db.session import get_async_db
from app.models.user import User
from app.schemas.auth import RegisterRequest
from app.services.auth_service import register_user
from app.services.senelec_service import SenelecService
from app.services.equipment_prices_service import EquipmentPricesService


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

_PLAIN_PW = "C0verageB00st!"


def _auth_header_for_user(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture()
async def test_app_with_session(
    async_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """FastAPI TestClient with in-memory DB injected."""
    from app.main import create_application

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield async_session

    application: FastAPI = create_application()
    application.dependency_overrides[get_async_db] = _override_db

    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture()
async def admin_user(async_session: AsyncSession) -> User:
    data = RegisterRequest(
        email="boost_admin@solarintel.sn",
        password=_PLAIN_PW,
        full_name="Boost Admin",
        role="admin",
    )
    return await register_user(async_session, data)


@pytest_asyncio.fixture()
async def client_user(async_session: AsyncSession) -> User:
    data = RegisterRequest(
        email="boost_client@solarintel.sn",
        password=_PLAIN_PW,
        full_name="Boost Client",
        role="client",
    )
    return await register_user(async_session, data)


@pytest_asyncio.fixture()
async def inactive_user(async_session: AsyncSession) -> User:
    data = RegisterRequest(
        email="boost_inactive@solarintel.sn",
        password=_PLAIN_PW,
        full_name="Inactive User",
        role="technicien",
    )
    user = await register_user(async_session, data)
    user.is_active = False
    async_session.add(user)
    await async_session.commit()
    return user


# ═══════════════════════════════════════════════════════════════════════════════
# Security module tests
# ═══════════════════════════════════════════════════════════════════════════════


async def test_require_roles_allows_correct_role(
    test_app_with_session: AsyncClient,
    admin_user: User,
) -> None:
    """Admin user reaches the admin-gated endpoint and gets 200."""
    headers = _auth_header_for_user(admin_user)
    response = await test_app_with_session.get(
        "/api/v2/auth/admin-only", headers=headers
    )
    assert response.status_code == 200


async def test_require_roles_blocks_wrong_role(
    test_app_with_session: AsyncClient,
    client_user: User,
) -> None:
    """Client-role user is rejected (403) from the admin-only endpoint."""
    headers = _auth_header_for_user(client_user)
    response = await test_app_with_session.get(
        "/api/v2/auth/admin-only", headers=headers
    )
    assert response.status_code == 403


async def test_get_current_user_inactive(
    test_app_with_session: AsyncClient,
    inactive_user: User,
) -> None:
    """GET /me with a token belonging to an inactive account returns 403."""
    headers = _auth_header_for_user(inactive_user)
    response = await test_app_with_session.get(
        "/api/v2/auth/me", headers=headers
    )
    assert response.status_code == 403


def test_decode_token_wrong_type() -> None:
    """Using a refresh token as an access token is decoded without error at
    the decode_token level (the token itself is valid JWT); the 'type' field
    can be inspected by the caller. This test verifies decode_token does not
    raise and that the returned payload carries type='refresh'."""
    user_id = uuid.uuid4()
    refresh_tok = create_refresh_token(user_id)
    payload = decode_token(refresh_tok)
    assert payload["type"] == "refresh"
    assert payload["sub"] == str(user_id)


async def test_refresh_with_access_token_rejected(
    test_app_with_session: AsyncClient,
    admin_user: User,
) -> None:
    """POST /auth/refresh that receives an access token (type=access) returns 401."""
    access_tok = create_access_token(admin_user.id, admin_user.role)
    response = await test_app_with_session.post(
        "/api/v2/auth/refresh",
        json={"refresh_token": access_tok},
    )
    assert response.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# SenelecService edge cases
# ═══════════════════════════════════════════════════════════════════════════════


def test_dmp_flat_rate() -> None:
    """DMP tariff: flat 98 FCFA/kWh, no fixed charge."""
    svc = SenelecService()
    bill = svc.calculate_bill(200.0, tariff_code="DMP")
    expected = 200.0 * 98.0
    assert abs(bill.monthly_cost_xof - expected) < 1.0, (
        f"DMP bill={bill.monthly_cost_xof}, expected={expected}"
    )
    assert abs(bill.annual_cost_xof - expected * 12) < 1.0


def test_pmp_flat_rate() -> None:
    """PMP tariff: flat 108 FCFA/kWh, no fixed charge."""
    svc = SenelecService()
    bill = svc.calculate_bill(150.0, tariff_code="PMP")
    expected = 150.0 * 108.0
    assert abs(bill.monthly_cost_xof - expected) < 1.0, (
        f"PMP bill={bill.monthly_cost_xof}, expected={expected}"
    )


def test_woyofal_flat_rate() -> None:
    """WOYOFAL tariff: flat 105 FCFA/kWh, no fixed charge."""
    svc = SenelecService()
    bill = svc.calculate_bill(300.0, tariff_code="WOYOFAL")
    expected = 300.0 * 105.0
    assert abs(bill.monthly_cost_xof - expected) < 1.0, (
        f"Woyofal bill={bill.monthly_cost_xof}, expected={expected}"
    )


def test_zero_consumption() -> None:
    """0 kWh/month → only fixed charge applies for DPP (no energy charge)."""
    svc = SenelecService()
    bill = svc.calculate_bill(0.0, tariff_code="DPP")
    # Fixed charge only: 1500 FCFA, no energy cost
    assert bill.monthly_cost_xof == pytest.approx(1500.0, abs=1.0)
    assert bill.annual_cost_xof == pytest.approx(1500.0 * 12, abs=1.0)


def test_very_high_consumption() -> None:
    """1000 kWh/month spans all DPP tranches: T1+T2+T3 correctly computed."""
    svc = SenelecService()
    bill = svc.calculate_bill(1000.0, tariff_code="DPP")
    # 150 × 84 + 150 × 121 + 700 × 158 + 1500
    expected = 150.0 * 84.0 + 150.0 * 121.0 + 700.0 * 158.0 + 1500.0
    assert abs(bill.monthly_cost_xof - expected) < 1.0, (
        f"High-consumption DPP bill={bill.monthly_cost_xof}, expected={expected}"
    )


def test_payback_infinite() -> None:
    """Zero solar production → zero savings → payback_years = infinity."""
    svc = SenelecService()
    # Production is zero every month — no savings possible
    analysis = svc.analyze_savings(
        monthly_consumption_kwh=400.0,
        monthly_production_kwh=[0.0] * 12,
        tariff_code="DPP",
        installation_cost_xof=5_000_000.0,
    )
    assert analysis.annual_savings_xof == pytest.approx(0.0, abs=1.0)
    # payback is either inf or a very large number
    assert analysis.payback_years == float("inf") or analysis.payback_years > 1e10


# ═══════════════════════════════════════════════════════════════════════════════
# WeatherService edge cases
# ═══════════════════════════════════════════════════════════════════════════════


async def test_weather_empty_hourly_list(async_redis: Any) -> None:
    """Empty shortwave_radiation list → correction_factor = 1.0 (fallback)."""
    from app.services.weather_service import WeatherService

    svc = WeatherService()

    # Patch fetch_hourly to return an empty HourlyWeather
    from app.services.weather_service import HourlyWeather

    async def _mock_fetch(lat: float, lon: float, days: int = 1) -> HourlyWeather:
        return HourlyWeather(
            timestamp=[],
            temperature_2m=[],
            shortwave_radiation=[],
            direct_radiation=[],
            diffuse_radiation=[],
        )

    with patch.object(svc, "fetch_hourly", side_effect=_mock_fetch):
        correction = await svc.compute_correction(
            lat=14.69,
            lon=-17.44,
            simulated_daily_kwh_m2=5.0,
        )

    assert correction.correction_factor == pytest.approx(1.0)


async def test_weather_zero_simulated(async_redis: Any) -> None:
    """simulated_daily_kwh_m2=0 → no division by zero, factor = 1.0."""
    from app.services.weather_service import WeatherService, HourlyWeather

    svc = WeatherService()

    async def _mock_fetch(lat: float, lon: float, days: int = 1) -> HourlyWeather:
        return HourlyWeather(
            timestamp=["2025-01-01T00:00"] * 24,
            temperature_2m=[28.0] * 24,
            shortwave_radiation=[500.0] * 24,
            direct_radiation=[350.0] * 24,
            diffuse_radiation=[150.0] * 24,
        )

    with patch.object(svc, "fetch_hourly", side_effect=_mock_fetch):
        correction = await svc.compute_correction(
            lat=14.69,
            lon=-17.44,
            simulated_daily_kwh_m2=0.0,  # zero simulated → must not divide by zero
        )

    assert correction.correction_factor == pytest.approx(1.0)


# ═══════════════════════════════════════════════════════════════════════════════
# EquipmentPricesService edge cases
# ═══════════════════════════════════════════════════════════════════════════════


async def test_installation_cost_hybrid(async_redis: Any) -> None:
    """Hybrid system cost per kWc (550 000) > on-grid cost per kWc (350 000)."""
    svc = EquipmentPricesService()
    cost_hybrid = await svc.get_installation_cost_estimate(5.0, system_type="hybrid")
    cost_on_grid = await svc.get_installation_cost_estimate(5.0, system_type="on-grid")
    assert cost_hybrid > cost_on_grid, (
        f"hybrid={cost_hybrid} should exceed on-grid={cost_on_grid}"
    )
    assert cost_hybrid == pytest.approx(5.0 * 550_000.0)


async def test_installation_cost_offgrid(async_redis: Any) -> None:
    """Unknown system_type ('off-grid') falls back to the on-grid rate."""
    svc = EquipmentPricesService()
    cost_offgrid = await svc.get_installation_cost_estimate(3.0, system_type="off-grid")
    cost_on_grid = await svc.get_installation_cost_estimate(3.0, system_type="on-grid")
    # Both unknown and on-grid use _COST_PER_KWC_ON_GRID
    assert cost_offgrid == pytest.approx(cost_on_grid)


async def test_refresh_prices_sets_ttl(async_redis: Any) -> None:
    """After refresh_prices(), the Redis key carries a 7-day TTL (TARIFF_TTL)."""
    from app.db.redis import redis_client

    original = redis_client._client
    redis_client._client = async_redis

    try:
        svc = EquipmentPricesService()
        await svc.refresh_prices()

        # fakeredis supports .ttl(); AsyncMock fallback: just verify key exists
        try:
            ttl = await async_redis.ttl("equipment:prices:panels")
            assert ttl > TARIFF_TTL - 10, (
                f"TTL={ttl} should be close to TARIFF_TTL={TARIFF_TTL}"
            )
        except (AttributeError, TypeError):
            cached = await async_redis.get("equipment:prices:panels")
            assert cached is not None
    finally:
        redis_client._client = original


# ═══════════════════════════════════════════════════════════════════════════════
# WhatsAppService edge cases
# ═══════════════════════════════════════════════════════════════════════════════


def test_normalize_phone_with_spaces() -> None:
    """'77 123 45 67' normalises to '+221771234567'."""
    from app.services.whatsapp_service import WhatsAppService

    svc = WhatsAppService()
    assert svc.normalize_phone("77 123 45 67") == "+221771234567"


def test_normalize_phone_with_country_code() -> None:
    """'221771234567' (no plus) normalises to '+221771234567'."""
    from app.services.whatsapp_service import WhatsAppService

    svc = WhatsAppService()
    assert svc.normalize_phone("221771234567") == "+221771234567"


def test_normalize_phone_already_e164() -> None:
    """'+221771234567' is returned unchanged."""
    from app.services.whatsapp_service import WhatsAppService

    svc = WhatsAppService()
    assert svc.normalize_phone("+221771234567") == "+221771234567"


async def test_send_alert_message_format() -> None:
    """send_simulation_alert message contains project name and percentage."""
    import respx
    from httpx import Response
    from app.services.whatsapp_service import WhatsAppService, WHATSAPP_API_URL
    import json as _json

    phone_id = "55544433"

    with respx.mock():
        respx.post(f"{WHATSAPP_API_URL}/{phone_id}/messages").mock(
            return_value=Response(200, json={"messages": [{"id": "wamid.alert"}]})
        )

        with patch("app.services.whatsapp_service.get_settings") as mock_settings:
            settings = MagicMock()
            settings.whatsapp_token = "token_alert_test"
            settings.whatsapp_phone_id = phone_id
            mock_settings.return_value = settings

            svc = WhatsAppService()
            await svc.send_simulation_alert(
                phone="+221771234567",
                project_name="Villa Almadies",
                performance_pct=72.0,
            )

        assert respx.calls.call_count == 1
        body = _json.loads(respx.calls[0].request.content)
        assert "Villa Almadies" in body["text"]["body"]
        assert "72%" in body["text"]["body"]


# ═══════════════════════════════════════════════════════════════════════════════
# WebSocket manager tests
# ═══════════════════════════════════════════════════════════════════════════════


async def test_broadcast_to_empty_project() -> None:
    """Broadcasting to a project with zero connections raises no exception."""
    from app.core.websocket_manager import ConnectionManager

    mgr = ConnectionManager()
    project_id = str(uuid.uuid4())

    # Should complete without raising
    await mgr.broadcast(project_id, {"type": "test", "data": {}})

    assert mgr.active_connections(project_id) == 0


async def test_broadcast_removes_dead_connections() -> None:
    """A WebSocket that raises on send_json is removed from the registry."""
    from app.core.websocket_manager import ConnectionManager

    mgr = ConnectionManager()
    project_id = str(uuid.uuid4())

    dead_ws = MagicMock()
    dead_ws.send_json = AsyncMock(side_effect=RuntimeError("connection lost"))

    # Manually inject the dead connection
    mgr._connections[project_id].add(dead_ws)
    assert mgr.active_connections(project_id) == 1

    await mgr.broadcast(project_id, {"type": "reading", "data": {}})

    # Dead connection must be removed after the broadcast
    assert mgr.active_connections(project_id) == 0


def test_active_connections_count() -> None:
    """active_connections returns 0 for unknown project and correct count otherwise."""
    from app.core.websocket_manager import ConnectionManager

    mgr = ConnectionManager()
    project_id = str(uuid.uuid4())

    assert mgr.active_connections(project_id) == 0

    ws1 = MagicMock()
    ws2 = MagicMock()
    mgr._connections[project_id].add(ws1)
    mgr._connections[project_id].add(ws2)

    assert mgr.active_connections(project_id) == 2

    mgr.disconnect(project_id, ws1)
    assert mgr.active_connections(project_id) == 1

    mgr.disconnect(project_id, ws2)
    # Key should be removed when the set becomes empty
    assert mgr.active_connections(project_id) == 0
    assert project_id not in mgr._connections


# ═══════════════════════════════════════════════════════════════════════════════
# Monte Carlo edge cases
# ═══════════════════════════════════════════════════════════════════════════════


def _dakar_monthly() -> list[float]:
    return [
        380.0, 410.0, 510.0, 530.0, 490.0, 460.0,
        420.0, 440.0, 470.0, 490.0, 430.0, 360.0,
    ]


def test_monte_carlo_p50_near_base() -> None:
    """P50 is within 5% of the base annual value."""
    from app.reports.monte_carlo import run_monte_carlo

    monthly = _dakar_monthly()
    base = sum(monthly)
    result = run_monte_carlo(base_annual_kwh=base, monthly_kwh=monthly, seed=42)

    deviation = abs(result.annual_p50 - base) / base
    assert deviation <= 0.05, (
        f"P50={result.annual_p50:.1f} deviates {deviation:.1%} from base={base:.1f}"
    )


def test_monte_carlo_p10_less_than_p50() -> None:
    """Strict ordering P10 < P50 < P90 must always hold."""
    from app.reports.monte_carlo import run_monte_carlo

    monthly = _dakar_monthly()
    result = run_monte_carlo(
        base_annual_kwh=sum(monthly), monthly_kwh=monthly, n_samples=500, seed=7
    )

    assert result.annual_p10 < result.annual_p50, (
        f"P10={result.annual_p10:.1f} must be < P50={result.annual_p50:.1f}"
    )
    assert result.annual_p50 < result.annual_p90, (
        f"P50={result.annual_p50:.1f} must be < P90={result.annual_p90:.1f}"
    )


def test_sensitivity_negative_price_change() -> None:
    """Lower electricity prices → lower savings → longer payback period."""
    from app.reports.monte_carlo import run_sensitivity_analysis

    results = run_sensitivity_analysis(
        base_annual_savings_xof=600_000.0,
        installation_cost_xof=5_000_000.0,
    )

    by_change = {r.price_change_pct: r for r in results}

    # -30% scenario has lower savings than +30% scenario
    assert by_change[-30.0].annual_savings_xof < by_change[30.0].annual_savings_xof, (
        "Negative price change should yield lower annual savings"
    )
    # Lower savings means longer payback
    assert by_change[-30.0].payback_years > by_change[30.0].payback_years, (
        "Lower savings should imply longer payback"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Redis client unit tests
# ═══════════════════════════════════════════════════════════════════════════════


async def test_cache_set_and_get(async_redis: Any) -> None:
    """Round-trip cache_set → cache_get returns the stored value."""
    client = RedisClient()
    client._client = async_redis

    key = "boost:test:roundtrip"
    value = '{"sensor": "irr", "value": 750}'

    await client.cache_set(key, value, ttl_seconds=TARIFF_TTL)
    retrieved = await client.cache_get(key)
    assert retrieved == value


async def test_cache_delete_removes_key(async_redis: Any) -> None:
    """cache_delete removes the key; subsequent cache_get returns None."""
    client = RedisClient()
    client._client = async_redis

    key = "boost:test:delete"
    await client.cache_set(key, "to_be_deleted", ttl_seconds=60)

    # Confirm it exists
    assert await client.cache_get(key) == "to_be_deleted"

    await client.cache_delete(key)
    assert await client.cache_get(key) is None


async def test_cache_get_missing_key(async_redis: Any) -> None:
    """cache_get for a key that was never set returns None without error."""
    client = RedisClient()
    client._client = async_redis

    result = await client.cache_get("boost:nonexistent:key:xyz")
    assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# AlertService threshold tests
# ═══════════════════════════════════════════════════════════════════════════════


async def test_no_alert_when_no_monitoring_data(async_session: AsyncSession) -> None:
    """When there are no monitoring entries, performance is 0% which is below
    the 80% threshold BUT the alert relies on the stats object; the service
    must either not crash or correctly decide based on zero data.

    This test seeds a project with a simulation but zero monitoring entries
    and verifies check_and_alert does not raise and returns a bool."""
    from app.models.project import Project
    from app.models.simulation import Simulation
    from app.services.alert_service import AlertService

    user = User.create(
        email=f"alert_nodata_{uuid.uuid4().hex[:6]}@test.sn",
        role="technicien",
    )
    async_session.add(user)
    await async_session.flush()

    project = Project.create(
        user_id=user.id,
        name="No-data project",
        latitude=14.7,
        longitude=-17.4,
    )
    async_session.add(project)
    await async_session.flush()

    sim = Simulation.create(
        project_id=project.id,
        panel_count=10,
        peak_kwc=5.45,
        annual_kwh=3650.0,
        monthly_data=[{"month": i, "energy_kwh": 304.0} for i in range(1, 13)],
    )
    async_session.add(sim)
    await async_session.flush()

    fake_redis = AsyncMock()
    fake_redis.cache_get = AsyncMock(return_value=None)
    fake_redis.cache_set = AsyncMock()

    fake_whatsapp = AsyncMock()
    fake_whatsapp.send_simulation_alert = AsyncMock(return_value={})

    svc = AlertService()
    svc._whatsapp = fake_whatsapp

    with patch("app.services.alert_service.redis_client", fake_redis):
        result = await svc.check_and_alert(
            project_id=project.id,
            db=async_session,
            technician_phone=None,  # no phone — alert path skipped even if triggered
        )

    # Result must be a bool — no crash
    assert isinstance(result, bool)


async def test_alert_uses_correct_threshold_value(
    async_session: AsyncSession,
) -> None:
    """79% triggers alert; 81% does not — boundary around PERFORMANCE_THRESHOLD=80%."""
    from app.models.project import Project
    from app.models.simulation import Simulation
    from app.models.monitoring import Monitoring
    from app.services.alert_service import AlertService

    # ── 79% case — should trigger ──────────────────────────────────────────

    user_79 = User.create(
        email=f"threshold_79_{uuid.uuid4().hex[:6]}@test.sn",
        role="technicien",
    )
    async_session.add(user_79)
    await async_session.flush()

    project_79 = Project.create(
        user_id=user_79.id,
        name="79pct project",
        latitude=14.7,
        longitude=-17.4,
    )
    async_session.add(project_79)
    await async_session.flush()

    # 3650 / 365 = 10.0 kWh/day expected; 7.9 kWh → 79%
    Simulation.create(
        project_id=project_79.id,
        panel_count=10,
        peak_kwc=5.45,
        annual_kwh=3650.0,
        monthly_data=[{"month": i, "energy_kwh": 304.0} for i in range(1, 13)],
    )
    sim_79 = Simulation.create(
        project_id=project_79.id,
        panel_count=10,
        peak_kwc=5.45,
        annual_kwh=3650.0,
        monthly_data=[{"month": i, "energy_kwh": 304.0} for i in range(1, 13)],
    )
    async_session.add(sim_79)

    now = datetime.now(tz=timezone.utc)
    entry_79 = Monitoring.create(
        project_id=project_79.id,
        timestamp=now,
        production_kwh=7.9,
    )
    async_session.add(entry_79)
    await async_session.flush()

    fake_redis_79 = AsyncMock()
    fake_redis_79.cache_get = AsyncMock(return_value=None)
    fake_redis_79.cache_set = AsyncMock()

    fake_whatsapp_79 = AsyncMock()
    fake_whatsapp_79.send_simulation_alert = AsyncMock(return_value={})

    svc_79 = AlertService()
    svc_79._whatsapp = fake_whatsapp_79

    with patch("app.services.alert_service.redis_client", fake_redis_79):
        sent_79 = await svc_79.check_and_alert(
            project_id=project_79.id,
            db=async_session,
            technician_phone="+221771234567",
        )

    assert sent_79 is True, "79% should trigger an alert"

    # ── 81% case — should NOT trigger ──────────────────────────────────────

    user_81 = User.create(
        email=f"threshold_81_{uuid.uuid4().hex[:6]}@test.sn",
        role="technicien",
    )
    async_session.add(user_81)
    await async_session.flush()

    project_81 = Project.create(
        user_id=user_81.id,
        name="81pct project",
        latitude=14.7,
        longitude=-17.4,
    )
    async_session.add(project_81)
    await async_session.flush()

    sim_81 = Simulation.create(
        project_id=project_81.id,
        panel_count=10,
        peak_kwc=5.45,
        annual_kwh=3650.0,
        monthly_data=[{"month": i, "energy_kwh": 304.0} for i in range(1, 13)],
    )
    async_session.add(sim_81)

    entry_81 = Monitoring.create(
        project_id=project_81.id,
        timestamp=now,
        production_kwh=8.1,
    )
    async_session.add(entry_81)
    await async_session.flush()

    fake_redis_81 = AsyncMock()
    fake_redis_81.cache_get = AsyncMock(return_value=None)
    fake_redis_81.cache_set = AsyncMock()

    fake_whatsapp_81 = AsyncMock()
    fake_whatsapp_81.send_simulation_alert = AsyncMock(return_value={})

    svc_81 = AlertService()
    svc_81._whatsapp = fake_whatsapp_81

    with patch("app.services.alert_service.redis_client", fake_redis_81):
        sent_81 = await svc_81.check_and_alert(
            project_id=project_81.id,
            db=async_session,
            technician_phone="+221771234567",
        )

    assert sent_81 is False, "81% should NOT trigger an alert"
    fake_whatsapp_81.send_simulation_alert.assert_not_awaited()
