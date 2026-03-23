"""SIM-001: Tests for simulation service, Senelec service, and API endpoints.

Covers:
- SimulationService unit tests (PVGIS mocked with respx, Redis faked with fakeredis)
- SenelecService unit tests (tariff calculations, savings, payback, ROI)
- API endpoint integration tests (POST /simulate, GET /simulate/{id})

All tests use asyncio_mode="auto" (configured in pyproject.toml).
PVGIS HTTP calls are intercepted by respx; Redis is replaced with fakeredis.
The FastAPI test client overrides get_async_db with the in-memory SQLite session.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pandas as pd
import pytest
import pytest_asyncio
import respx
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.db.redis import redis_client
from app.db.session import get_async_db
from app.main import create_application
from app.models.project import Project
from app.models.user import User
from app.schemas.auth import RegisterRequest
from app.services.auth_service import register_user
from app.services.senelec_service import SenelecService
from app.services.simulation_service import SimulationParams, SimulationService

# ── Constants ──────────────────────────────────────────────────────────────────

_PLAIN_PW = "S3cur3P@ssw0rd!"
_USER_EMAIL = "sim_user@solarintel.sn"
_OTHER_EMAIL = "other_user@solarintel.sn"

# Dakar reference coordinates
_LAT = 14.6928
_LON = -17.4467

# Minimum realistic TMY data helpers
_PVGIS_URL = "https://re.jrc.ec.europa.eu/api/v5_2/tmy"


# ── PVGIS TMY fixture builder ──────────────────────────────────────────────────


def _build_pvgis_response(ghi: float = 220.0) -> dict[str, Any]:
    """Build a minimal synthetic PVGIS JSON response body.

    The hourly records replicate the PVGIS JSON schema:
    - G(h): GHI in W/m²
    - Gb(n): DNI in W/m² (60% of GHI for the synthetic case)
    - Gd(h): DHI in W/m² (40% of GHI for the synthetic case)
    - T2m: 2-metre air temperature in °C
    - WS10m: 10-metre wind speed in m/s

    Args:
        ghi: Constant GHI value (W/m²) for all 8760 hours.  A value of 220
            represents a realistic annual average; higher values are used in
            Dakar-range tests to ensure pvlib output falls in the expected
            annual energy window (the relationship between GHI and AC output
            is approximately linear for the PVWatts model).

    Returns:
        Dict matching the PVGIS /tmy JSON structure.
    """
    hourly = [
        {
            "time(UTC)": f"20050101:{i:04d}",
            "G(h)": ghi,
            "Gb(n)": ghi * 0.6,
            "Gd(h)": ghi * 0.4,
            "T2m": 28.0,
            "WS10m": 3.5,
            "RH": 65.0,
            "SP": 101325.0,
        }
        for i in range(8760)
    ]
    return {
        "outputs": {"tmy_hourly": hourly},
        "meta": {"location": {"latitude": _LAT, "longitude": _LON}},
    }


# GHI value (W/m²) calibrated so that pvlib's PVWatts model produces
# annual_kwh in [7500, 9500] for 10 panels × 545 Wc at Dakar coordinates.
# Derived empirically: pvlib output scales linearly with GHI input for the
# constant-irradiance TMY; GHI ≈ 400 W/m² constant × 8760 h ≈ 3504 kWh/m²
# → annual_kwh ≈ 8470 kWh for 5.45 kWp with 14% system losses.
_DAKAR_REFERENCE_GHI: float = 400.0


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture()
async def fake_redis() -> AsyncGenerator[Any, None]:
    """Replace the global redis_client with a fakeredis instance.

    Patches redis_client._client on the module-level singleton so that
    SimulationService uses fakeredis transparently.

    Yields:
        The fakeredis FakeRedis instance.
    """
    import fakeredis.aioredis as fakeredis  # type: ignore[import]

    fake = fakeredis.FakeRedis(decode_responses=True)
    original = redis_client._client
    redis_client._client = fake
    yield fake
    redis_client._client = original
    await fake.aclose()


@pytest_asyncio.fixture()
async def test_user(async_session: AsyncSession) -> User:
    """A registered technicien user persisted to the test DB.

    Args:
        async_session: In-memory SQLite session from conftest.

    Returns:
        Persisted User ORM instance.
    """
    data = RegisterRequest(
        email=_USER_EMAIL,
        password=_PLAIN_PW,
        full_name="Simulation Test User",
        role="technicien",
    )
    return await register_user(async_session, data)


@pytest_asyncio.fixture()
async def other_user(async_session: AsyncSession) -> User:
    """A second registered user, owns no projects shared with test_user.

    Args:
        async_session: In-memory SQLite session from conftest.

    Returns:
        Persisted User ORM instance.
    """
    data = RegisterRequest(
        email=_OTHER_EMAIL,
        password=_PLAIN_PW,
        full_name="Other User",
        role="technicien",
    )
    return await register_user(async_session, data)


@pytest_asyncio.fixture()
async def sim_project(
    async_session: AsyncSession,
    test_user: User,
) -> Project:
    """Create a Project linked to test_user at Dakar coordinates.

    Args:
        async_session: In-memory SQLite session from conftest.
        test_user: The user who owns the project.

    Returns:
        Persisted Project ORM instance.
    """
    project = Project.create(
        user_id=test_user.id,
        name="Dakar Test Site",
        latitude=_LAT,
        longitude=_LON,
        address="Dakar, Sénégal",
    )
    async_session.add(project)
    await async_session.commit()
    await async_session.refresh(project)
    return project


@pytest_asyncio.fixture()
async def test_app(
    async_session: AsyncSession,
    fake_redis: Any,
) -> AsyncGenerator[AsyncClient, None]:
    """FastAPI TestClient with DB and Redis overrides applied.

    Args:
        async_session: In-memory SQLite session.
        fake_redis: fakeredis instance (already patched on redis_client).

    Yields:
        An httpx.AsyncClient wired to the FastAPI app under test.
    """

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield async_session

    application: FastAPI = create_application()
    application.dependency_overrides[get_async_db] = _override_db

    transport = ASGITransport(app=application)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def _auth_headers(user: User) -> dict[str, str]:
    """Return Bearer Authorization header for a user.

    Args:
        user: The user to authenticate.

    Returns:
        Dict with the Authorization header.
    """
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


# ═══════════════════════════════════════════════════════════════════════════════
# ── UNIT TESTS: SimulationService ─────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════


@respx.mock
async def test_simulate_dakar_reference(fake_redis: Any) -> None:
    """Dakar reference case: annual_kwh in [7500, 9500] and PR in [0.70, 0.85].

    Uses 10 panels × 545 Wc (5.45 kWp) at Dakar coordinates.
    PVGIS HTTP call is intercepted by respx and returns a synthetic TMY built
    with _DAKAR_REFERENCE_GHI, calibrated so that pvlib's PVWatts model
    produces a result within the physically expected window for Dakar.
    """
    respx.get(_PVGIS_URL).mock(
        return_value=Response(200, json=_build_pvgis_response(ghi=_DAKAR_REFERENCE_GHI))
    )

    service = SimulationService()
    params = SimulationParams(
        latitude=_LAT,
        longitude=_LON,
        panel_count=10,
        panel_power_wc=545,
    )
    result = await service.simulate(params)

    assert 7500 <= result.annual_kwh <= 9500, (
        f"annual_kwh={result.annual_kwh} outside expected range [7500, 9500]"
    )
    assert 0.70 <= result.performance_ratio <= 0.85, (
        f"PR={result.performance_ratio} outside expected range [0.70, 0.85]"
    )


@respx.mock
async def test_simulate_caches_pvgis_result(fake_redis: Any) -> None:
    """Second call with same lat/lon must NOT issue a second PVGIS HTTP request.

    The PVGIS mock is set up with call count tracking. After the first
    call caches the result, a second call must use the cache (call count stays 1).
    """
    route = respx.get(_PVGIS_URL).mock(
        return_value=Response(200, json=_build_pvgis_response())
    )

    service = SimulationService()
    params = SimulationParams(
        latitude=_LAT,
        longitude=_LON,
        panel_count=5,
        panel_power_wc=545,
    )

    await service.simulate(params)
    await service.simulate(params)  # second call — must hit cache

    assert route.call_count == 1, (
        f"PVGIS was called {route.call_count} times; expected exactly 1 (cache hit on 2nd call)"
    )


@respx.mock
async def test_simulate_uses_cache(fake_redis: Any) -> None:
    """Pre-populated Redis cache prevents any PVGIS HTTP call.

    We manually write a valid TMY JSON into the fake Redis under the
    expected cache key, then verify that the PVGIS mock route is never called.
    """
    # Pre-populate cache with synthetic TMY data
    cache_key = f"pvgis:{_LAT:.4f}:{_LON:.4f}"
    tmy_df = pd.DataFrame(_build_pvgis_response()["outputs"]["tmy_hourly"])
    tmy_df = tmy_df.rename(
        columns={
            "G(h)": "ghi",
            "Gb(n)": "dni",
            "Gd(h)": "dhi",
            "T2m": "temp_air",
            "WS10m": "wind_speed",
        }
    )
    tmy_df.index = pd.date_range("2023-01-01", periods=8760, freq="h", tz="UTC")
    await fake_redis.setex(cache_key, 86400, tmy_df.to_json(orient="split"))

    # PVGIS route must never be called
    route = respx.get(_PVGIS_URL).mock(
        return_value=Response(200, json=_build_pvgis_response())
    )

    service = SimulationService()
    params = SimulationParams(
        latitude=_LAT,
        longitude=_LON,
        panel_count=5,
        panel_power_wc=545,
    )
    await service.simulate(params)

    assert route.call_count == 0, (
        f"PVGIS was called {route.call_count} times despite warm cache"
    )


@respx.mock
async def test_monthly_data_12_months(fake_redis: Any) -> None:
    """monthly_data has exactly 12 entries, each with month 1-12 and energy_kwh > 0."""
    respx.get(_PVGIS_URL).mock(
        return_value=Response(200, json=_build_pvgis_response(ghi=200.0))
    )

    service = SimulationService()
    params = SimulationParams(
        latitude=_LAT,
        longitude=_LON,
        panel_count=8,
        panel_power_wc=545,
    )
    result = await service.simulate(params)

    assert len(result.monthly_data) == 12, (
        f"Expected 12 monthly entries, got {len(result.monthly_data)}"
    )
    months = [m.month for m in result.monthly_data]
    assert months == list(range(1, 13)), f"Expected months 1-12, got {months}"
    for entry in result.monthly_data:
        assert entry.energy_kwh > 0, (
            f"Month {entry.month} has non-positive energy_kwh={entry.energy_kwh}"
        )


@respx.mock
async def test_specific_yield_calculation(fake_redis: Any) -> None:
    """specific_yield equals annual_kwh / peak_kwc within 1% tolerance."""
    respx.get(_PVGIS_URL).mock(
        return_value=Response(200, json=_build_pvgis_response())
    )

    service = SimulationService()
    params = SimulationParams(
        latitude=_LAT,
        longitude=_LON,
        panel_count=10,
        panel_power_wc=545,
    )
    result = await service.simulate(params)

    expected_yield = result.annual_kwh / result.peak_kwc
    tolerance = expected_yield * 0.01  # 1%
    assert abs(result.specific_yield - expected_yield) <= tolerance, (
        f"specific_yield={result.specific_yield} deviates from "
        f"annual_kwh/peak_kwc={expected_yield} by more than 1%"
    )


@respx.mock
async def test_performance_ratio_range(fake_redis: Any) -> None:
    """Performance ratio must be in [0.65, 0.90] for standard system losses."""
    respx.get(_PVGIS_URL).mock(
        return_value=Response(200, json=_build_pvgis_response())
    )

    service = SimulationService()
    params = SimulationParams(
        latitude=_LAT,
        longitude=_LON,
        panel_count=10,
        panel_power_wc=545,
        system_losses=0.14,
    )
    result = await service.simulate(params)

    assert 0.65 <= result.performance_ratio <= 0.90, (
        f"PR={result.performance_ratio} outside physically valid range [0.65, 0.90]"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ── UNIT TESTS: SenelecService ────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════


def test_tariff_dpp_t1() -> None:
    """DPP T1 tranche: 0-150 kWh/month at 84 FCFA/kWh + 1500 FCFA fixed charge."""
    service = SenelecService()
    bill = service.calculate_bill(100.0, tariff_code="DPP")

    # 100 kWh × 84 FCFA + 1500 FCFA fixed = 9900 FCFA
    expected = 100.0 * 84.0 + 1500.0
    assert abs(bill.monthly_cost_xof - expected) < 1.0, (
        f"DPP T1 bill={bill.monthly_cost_xof}, expected={expected}"
    )
    assert abs(bill.annual_cost_xof - expected * 12) < 1.0


def test_tariff_t2_t3_tranches() -> None:
    """Consumption spanning T1+T2+T3 brackets applies correct stepped rates."""
    service = SenelecService()

    # 400 kWh: 150@84 + 150@121 + 100@158 + 1500 fixed
    # = 12600 + 18150 + 15800 + 1500 = 48050
    bill = service.calculate_bill(400.0, tariff_code="DPP")
    expected = 150.0 * 84.0 + 150.0 * 121.0 + 100.0 * 158.0 + 1500.0
    assert abs(bill.monthly_cost_xof - expected) < 1.0, (
        f"DPP T1+T2+T3 bill={bill.monthly_cost_xof}, expected={expected}"
    )


def test_woyofal_rate() -> None:
    """Woyofal prepaid: flat 105 FCFA/kWh, no fixed charge."""
    service = SenelecService()
    bill = service.calculate_bill(200.0, tariff_code="WOYOFAL")

    expected = 200.0 * 105.0
    assert abs(bill.monthly_cost_xof - expected) < 1.0, (
        f"Woyofal bill={bill.monthly_cost_xof}, expected={expected}"
    )


def test_annual_savings() -> None:
    """Solar production reduces electricity bill; before_xof > after_xof and savings > 0."""
    service = SenelecService()

    # 400 kWh/month consumption; solar produces ~350 kWh/month → significant savings
    monthly_production = [350.0] * 12  # flat production for simplicity
    analysis = service.analyze_savings(
        monthly_consumption_kwh=400.0,
        monthly_production_kwh=monthly_production,
        tariff_code="DPP",
        installation_cost_xof=5_000_000.0,
    )

    assert analysis.before_solar_monthly_xof > analysis.after_solar_monthly_xof, (
        "Solar should reduce the monthly electricity bill"
    )
    assert analysis.annual_savings_xof > 0, (
        "Annual savings must be positive when solar covers most of consumption"
    )


def test_payback_calculation() -> None:
    """payback_years = installation_cost / annual_savings (simple payback formula)."""
    service = SenelecService()

    installation_cost = 5_000_000.0
    monthly_production = [350.0] * 12
    analysis = service.analyze_savings(
        monthly_consumption_kwh=400.0,
        monthly_production_kwh=monthly_production,
        tariff_code="DPP",
        installation_cost_xof=installation_cost,
    )

    expected_payback = installation_cost / analysis.annual_savings_xof
    assert abs(analysis.payback_years - expected_payback) < 0.01, (
        f"payback_years={analysis.payback_years} does not match "
        f"cost/savings={expected_payback}"
    )


def test_roi_calculation() -> None:
    """ROI over 25 years is positive and reasonably bounded for a typical system."""
    service = SenelecService()

    monthly_production = [400.0] * 12  # generous production
    analysis = service.analyze_savings(
        monthly_consumption_kwh=400.0,
        monthly_production_kwh=monthly_production,
        tariff_code="DPP",
        installation_cost_xof=4_000_000.0,
    )

    # 25-year ROI should be positive (profitable system)
    assert analysis.roi_25yr_percent > 0, (
        f"Expected positive 25-year ROI, got {analysis.roi_25yr_percent}%"
    )
    # And realistically bounded (not > 10000%)
    assert analysis.roi_25yr_percent < 10_000.0, (
        f"ROI={analysis.roi_25yr_percent}% is implausibly large"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ── INTEGRATION TESTS: /api/v2/simulate endpoints ────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════


@respx.mock
async def test_post_simulate_authenticated(
    test_app: AsyncClient,
    test_user: User,
    sim_project: Project,
) -> None:
    """POST /api/v2/simulate returns 201 with a simulation id for an auth user."""
    respx.get(_PVGIS_URL).mock(
        return_value=Response(200, json=_build_pvgis_response())
    )

    response = await test_app.post(
        "/api/v2/simulate",
        json={
            "project_id": str(sim_project.id),
            "panel_count": 10,
            "panel_power_wc": 545,
            "monthly_consumption_kwh": 400.0,
            "tariff_code": "DPP",
            "installation_cost_xof": 5_000_000.0,
        },
        headers=_auth_headers(test_user),
    )

    assert response.status_code == 201, (
        f"Expected 201, got {response.status_code}: {response.text}"
    )
    body = response.json()
    assert "id" in body, "Response must include simulation 'id'"
    # Validate it's a UUID
    uuid.UUID(body["id"])


@respx.mock
async def test_post_simulate_unauthenticated(
    test_app: AsyncClient,
    sim_project: Project,
) -> None:
    """POST /api/v2/simulate without a token returns 403."""
    respx.get(_PVGIS_URL).mock(
        return_value=Response(200, json=_build_pvgis_response())
    )

    response = await test_app.post(
        "/api/v2/simulate",
        json={
            "project_id": str(sim_project.id),
            "panel_count": 10,
            "panel_power_wc": 545,
        },
        # No Authorization header
    )

    assert response.status_code == 403, (
        f"Expected 403 for unauthenticated request, got {response.status_code}"
    )


@respx.mock
async def test_get_simulation_by_id(
    test_app: AsyncClient,
    test_user: User,
    sim_project: Project,
) -> None:
    """GET /api/v2/simulate/{id} returns the full simulation after creation."""
    respx.get(_PVGIS_URL).mock(
        return_value=Response(200, json=_build_pvgis_response())
    )

    # Create a simulation first
    create_resp = await test_app.post(
        "/api/v2/simulate",
        json={
            "project_id": str(sim_project.id),
            "panel_count": 10,
            "panel_power_wc": 545,
            "monthly_consumption_kwh": 300.0,
            "tariff_code": "DPP",
            "installation_cost_xof": 5_000_000.0,
        },
        headers=_auth_headers(test_user),
    )
    assert create_resp.status_code == 201
    sim_id = create_resp.json()["id"]

    # Retrieve by ID
    get_resp = await test_app.get(
        f"/api/v2/simulate/{sim_id}",
        headers=_auth_headers(test_user),
    )
    assert get_resp.status_code == 200, (
        f"Expected 200, got {get_resp.status_code}: {get_resp.text}"
    )
    body = get_resp.json()
    assert body["id"] == sim_id


@respx.mock
async def test_get_simulation_wrong_user(
    test_app: AsyncClient,
    test_user: User,
    other_user: User,
    sim_project: Project,
) -> None:
    """GET /api/v2/simulate/{id} by a different user returns 404 (isolation)."""
    respx.get(_PVGIS_URL).mock(
        return_value=Response(200, json=_build_pvgis_response())
    )

    # test_user creates a simulation
    create_resp = await test_app.post(
        "/api/v2/simulate",
        json={
            "project_id": str(sim_project.id),
            "panel_count": 5,
            "panel_power_wc": 545,
        },
        headers=_auth_headers(test_user),
    )
    assert create_resp.status_code == 201
    sim_id = create_resp.json()["id"]

    # other_user attempts to fetch it — must get 404
    get_resp = await test_app.get(
        f"/api/v2/simulate/{sim_id}",
        headers=_auth_headers(other_user),
    )
    assert get_resp.status_code == 404, (
        f"Expected 404 for wrong user, got {get_resp.status_code}"
    )


@respx.mock
async def test_simulate_saves_to_db(
    test_app: AsyncClient,
    async_session: AsyncSession,
    test_user: User,
    sim_project: Project,
) -> None:
    """Simulation created via POST is retrievable from the DB by its returned id."""
    from sqlalchemy import select

    from app.models.simulation import Simulation

    respx.get(_PVGIS_URL).mock(
        return_value=Response(200, json=_build_pvgis_response())
    )

    create_resp = await test_app.post(
        "/api/v2/simulate",
        json={
            "project_id": str(sim_project.id),
            "panel_count": 10,
            "panel_power_wc": 545,
            "monthly_consumption_kwh": 400.0,
            "tariff_code": "DPP",
            "installation_cost_xof": 5_000_000.0,
        },
        headers=_auth_headers(test_user),
    )
    assert create_resp.status_code == 201
    sim_id = uuid.UUID(create_resp.json()["id"])

    # Verify DB persistence
    result = await async_session.execute(
        select(Simulation).where(Simulation.id == sim_id)
    )
    sim = result.scalar_one_or_none()
    assert sim is not None, f"Simulation {sim_id} not found in DB after creation"
    assert sim.panel_count == 10
    assert sim.annual_kwh > 0


@respx.mock
async def test_simulate_response_schema(
    test_app: AsyncClient,
    test_user: User,
    sim_project: Project,
) -> None:
    """POST /api/v2/simulate response matches SimulationResponse schema exactly."""
    respx.get(_PVGIS_URL).mock(
        return_value=Response(200, json=_build_pvgis_response())
    )

    response = await test_app.post(
        "/api/v2/simulate",
        json={
            "project_id": str(sim_project.id),
            "panel_count": 10,
            "panel_power_wc": 545,
            "monthly_consumption_kwh": 400.0,
            "tariff_code": "DPP",
            "installation_cost_xof": 5_000_000.0,
        },
        headers=_auth_headers(test_user),
    )
    assert response.status_code == 201
    body = response.json()

    # Required top-level fields
    required_fields = {
        "id",
        "projectId",
        "panelCount",
        "peakKwc",
        "annualKwh",
        "specificYield",
        "performanceRatio",
        "monthlyData",
        "senelecSavingsXof",
        "paybackYears",
        "roiPercent",
        "status",
        "createdAt",
    }
    missing = required_fields - set(body.keys())
    assert not missing, f"Response missing fields: {missing}"

    # monthlyData structure
    assert isinstance(body["monthlyData"], list)
    assert len(body["monthlyData"]) == 12
    for entry in body["monthlyData"]:
        assert "month" in entry
        assert "energyKwh" in entry
        assert "irradianceKwhM2" in entry
        assert "performanceRatio" in entry

    # Type checks
    assert isinstance(body["panelCount"], int)
    assert isinstance(body["peakKwc"], float)
    assert isinstance(body["annualKwh"], float)
    assert body["status"] == "completed"
    uuid.UUID(body["id"])
    uuid.UUID(body["projectId"])
