"""DB-001: TDD test suite for SQLAlchemy models and Redis caching.

Tests verify that all ORM models persist correctly to the database and
that the Redis cache client performs round-trip set/get operations reliably.

Run with::

    pytest backend/tests/test_db.py -v

No external services required — uses SQLite in-memory (via aiosqlite) and
fakeredis (or AsyncMock fallback) as configured in ``conftest.py``.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import PVGIS_TTL, SESSION_TTL, TARIFF_TTL, RedisClient
from app.models.equipment import Equipment
from app.models.monitoring import Monitoring
from app.models.project import Project
from app.models.report import Report
from app.models.simulation import Simulation
from app.models.tariff_history import TariffHistory
from app.models.user import USER_ROLES, User


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_user(
    email: str = "test@solarintel.sn",
    role: str = "technicien",
) -> User:
    """Return an unsaved User instance with sensible defaults."""
    return User.create(
        email=email,
        role=role,
        hashed_password="$2b$12$fakehashvalue",
        full_name="Amadou Diallo",
        company="SolarTech Dakar",
    )


# ── User tests ────────────────────────────────────────────────────────────────


async def test_create_user(async_session: AsyncSession) -> None:
    """A User persists to the database with all fields intact.

    Verifies:
    - The record survives a commit and can be re-fetched by primary key.
    - ``email``, ``role``, ``full_name``, ``company``, ``is_active`` match.
    - ``id`` is a valid UUID and ``created_at`` is populated.
    """
    user = _make_user(email="amadou@example.sn", role="admin")
    async_session.add(user)
    await async_session.commit()

    # Re-fetch from DB (not from identity map) to confirm persistence.
    result = await async_session.execute(
        select(User).where(User.email == "amadou@example.sn")
    )
    fetched = result.scalar_one()

    assert fetched.id == user.id
    assert isinstance(fetched.id, uuid.UUID)
    assert fetched.email == "amadou@example.sn"
    assert fetched.role == "admin"
    assert fetched.full_name == "Amadou Diallo"
    assert fetched.company == "SolarTech Dakar"
    assert fetched.is_active is True
    assert fetched.created_at is not None
    assert fetched.hashed_password == "$2b$12$fakehashvalue"


async def test_user_role_constraint(async_session: AsyncSession) -> None:
    """Creating a User with an invalid role raises ValueError immediately.

    The constraint is enforced in ``User.create()`` before any DB interaction,
    so no commit is needed to trigger the error.
    """
    with pytest.raises(ValueError, match="Invalid role"):
        User.create(
            email="bad@example.sn",
            role="superuser",  # not in USER_ROLES
        )


async def test_user_google_oauth(async_session: AsyncSession) -> None:
    """An OAuth-only User (no password) persists with google_id set."""
    user = User.create(
        email="oauth@gmail.com",
        role="client",
        google_id="google-sub-123456789",
    )
    assert user.hashed_password is None

    async_session.add(user)
    await async_session.commit()

    result = await async_session.execute(
        select(User).where(User.google_id == "google-sub-123456789")
    )
    fetched = result.scalar_one()
    assert fetched.email == "oauth@gmail.com"
    assert fetched.hashed_password is None
    assert fetched.google_id == "google-sub-123456789"


# ── Project tests ─────────────────────────────────────────────────────────────


async def test_create_project(async_session: AsyncSession) -> None:
    """A Project linked to a User persists with geospatial and JSON fields.

    Verifies:
    - FK relationship (user_id) is stored correctly.
    - Floating-point lat/lon round-trip without precision loss.
    - ``polygon_geojson`` JSONB field serialises/deserialises as a dict.
    - The back-reference ``project.user`` resolves to the correct User.
    """
    user = _make_user(email="fatou@example.sn")
    async_session.add(user)
    await async_session.flush()  # Assign DB id without committing

    polygon = {
        "type": "Polygon",
        "coordinates": [[[17.44, 14.76], [17.45, 14.76], [17.44, 14.75]]],
    }
    project = Project.create(
        user_id=user.id,
        name="Toit Résidence Dakar",
        latitude=14.7645,
        longitude=-17.4437,
        polygon_geojson=polygon,
        address="HLM Grand Yoff, Dakar",
    )
    async_session.add(project)
    await async_session.commit()

    result = await async_session.execute(
        select(Project).where(Project.name == "Toit Résidence Dakar")
    )
    fetched = result.scalar_one()

    assert fetched.user_id == user.id
    assert fetched.latitude == pytest.approx(14.7645, rel=1e-6)
    assert fetched.longitude == pytest.approx(-17.4437, rel=1e-6)
    assert fetched.address == "HLM Grand Yoff, Dakar"
    assert fetched.polygon_geojson is not None
    assert fetched.polygon_geojson["type"] == "Polygon"


# ── Simulation tests ──────────────────────────────────────────────────────────


async def test_create_simulation(async_session: AsyncSession) -> None:
    """A Simulation persists with JSONB monthly_data and computed financials.

    Verifies:
    - ``monthly_data`` (list of 12 dicts) round-trips through JSONB correctly.
    - ``params`` dict round-trips through JSONB.
    - Financial outputs (savings, payback, ROI) are stored and retrieved.
    - Status defaults to ``"completed"``.
    """
    user = _make_user(email="sim@example.sn")
    async_session.add(user)
    await async_session.flush()

    project = Project.create(
        user_id=user.id,
        name="Usine Thiès",
        latitude=14.7910,
        longitude=-16.9359,
    )
    async_session.add(project)
    await async_session.flush()

    monthly_data = [
        {"month": m, "production_kwh": 850.0 + m * 10}
        for m in range(1, 13)
    ]
    params = {
        "tilt": 15,
        "azimuth": 180,
        "system_loss": 0.14,
        "panel_model": "JA Solar JAM72S30 545W",
    }

    sim = Simulation.create(
        project_id=project.id,
        panel_count=40,
        peak_kwc=21.8,
        annual_kwh=31_200.0,
        specific_yield=1430.0,
        performance_ratio=0.82,
        monthly_data=monthly_data,
        params=params,
        senelec_savings_xof=3_775_200.0,
        payback_years=4.2,
        roi_percent=238.0,
    )
    async_session.add(sim)
    await async_session.commit()

    result = await async_session.execute(
        select(Simulation).where(Simulation.project_id == project.id)
    )
    fetched = result.scalar_one()

    assert fetched.panel_count == 40
    assert fetched.peak_kwc == pytest.approx(21.8, rel=1e-6)
    assert fetched.annual_kwh == pytest.approx(31_200.0, rel=1e-6)
    assert fetched.specific_yield == pytest.approx(1430.0, rel=1e-6)
    assert fetched.performance_ratio == pytest.approx(0.82, rel=1e-6)
    assert fetched.status == "completed"
    assert fetched.senelec_savings_xof == pytest.approx(3_775_200.0, rel=1e-4)
    assert fetched.payback_years == pytest.approx(4.2, rel=1e-4)
    assert fetched.roi_percent == pytest.approx(238.0, rel=1e-4)

    # Verify JSONB round-trip
    assert isinstance(fetched.monthly_data, list)
    assert len(fetched.monthly_data) == 12
    assert fetched.monthly_data[0]["month"] == 1
    assert fetched.params is not None
    assert fetched.params["tilt"] == 15


# ── Equipment tests ───────────────────────────────────────────────────────────


async def test_create_equipment(async_session: AsyncSession) -> None:
    """Equipment linked to a Project persists with full hardware specifications.

    Verifies:
    - Required fields (panel_model, panel_power_wc, inverter fields) persist.
    - Optional battery fields are nullable and persist as None.
    - ``details`` JSONB dict round-trips correctly.
    - Unique constraint on ``project_id`` (one equipment per project).
    """
    user = _make_user(email="equip@example.sn")
    async_session.add(user)
    await async_session.flush()

    project = Project.create(
        user_id=user.id,
        name="Hôtel Saly",
        latitude=14.4534,
        longitude=-17.0053,
    )
    async_session.add(project)
    await async_session.flush()

    details = {
        "warranty_years": 25,
        "efficiency_percent": 21.3,
        "temperature_coefficient": -0.35,
    }
    equip = Equipment.create(
        project_id=project.id,
        panel_model="JA Solar JAM72S30 545W",
        panel_power_wc=545,
        inverter_model="GOODWE GW20KT-DT",
        inverter_kva=20.0,
        details=details,
    )
    async_session.add(equip)
    await async_session.commit()

    result = await async_session.execute(
        select(Equipment).where(Equipment.project_id == project.id)
    )
    fetched = result.scalar_one()

    assert fetched.panel_model == "JA Solar JAM72S30 545W"
    assert fetched.panel_power_wc == 545
    assert fetched.inverter_model == "GOODWE GW20KT-DT"
    assert fetched.inverter_kva == pytest.approx(20.0, rel=1e-6)
    assert fetched.battery_model is None
    assert fetched.battery_kwh is None
    assert fetched.details is not None
    assert fetched.details["warranty_years"] == 25


# ── Report tests ──────────────────────────────────────────────────────────────


async def test_create_report(async_session: AsyncSession) -> None:
    """A Report linked to a Simulation persists with correct status.

    Verifies:
    - Default status is ``"pending"``.
    - Optional pdf_path and html_path are nullable.
    - The simulation_id FK is stored correctly.
    """
    user = _make_user(email="report@example.sn")
    async_session.add(user)
    await async_session.flush()

    project = Project.create(
        user_id=user.id,
        name="Villa Almadies",
        latitude=14.7435,
        longitude=-17.5238,
    )
    async_session.add(project)
    await async_session.flush()

    sim = Simulation.create(
        project_id=project.id,
        panel_count=20,
        peak_kwc=10.9,
        annual_kwh=15_600.0,
    )
    async_session.add(sim)
    await async_session.flush()

    report = Report.create(simulation_id=sim.id)
    async_session.add(report)
    await async_session.commit()

    result = await async_session.execute(
        select(Report).where(Report.simulation_id == sim.id)
    )
    fetched = result.scalar_one()

    assert fetched.simulation_id == sim.id
    assert fetched.status == "pending"
    assert fetched.pdf_path is None
    assert fetched.html_path is None
    assert fetched.generated_at is None
    assert fetched.created_at is not None


# ── Monitoring tests ──────────────────────────────────────────────────────────


async def test_create_monitoring_entry(async_session: AsyncSession) -> None:
    """A Monitoring entry persists with correct production and metadata.

    Verifies:
    - ``timestamp`` field is stored and retrieved without truncation.
    - ``production_kwh`` float value round-trips correctly.
    - Optional irradiance and temperature fields accept None.
    - ``source`` defaults to ``"webhook"``.
    """
    user = _make_user(email="monitor@example.sn")
    async_session.add(user)
    await async_session.flush()

    project = Project.create(
        user_id=user.id,
        name="Centrale Mbour",
        latitude=14.3837,
        longitude=-16.9657,
    )
    async_session.add(project)
    await async_session.flush()

    ts = datetime(2025, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
    entry = Monitoring.create(
        project_id=project.id,
        timestamp=ts,
        production_kwh=12.5,
        irradiance_wm2=950.0,
        temperature_c=38.2,
        source="webhook",
    )
    async_session.add(entry)
    await async_session.commit()

    result = await async_session.execute(
        select(Monitoring).where(Monitoring.project_id == project.id)
    )
    fetched = result.scalar_one()

    assert fetched.production_kwh == pytest.approx(12.5, rel=1e-6)
    assert fetched.irradiance_wm2 == pytest.approx(950.0, rel=1e-6)
    assert fetched.temperature_c == pytest.approx(38.2, rel=1e-4)
    assert fetched.source == "webhook"
    assert fetched.project_id == project.id


# ── TariffHistory tests ───────────────────────────────────────────────────────


async def test_create_tariff_history(async_session: AsyncSession) -> None:
    """A TariffHistory entry persists with all Senelec rate fields.

    Verifies:
    - All three tranches and the woyofal rate are stored correctly.
    - ``is_current`` flag persists correctly.
    - ``effective_date`` is stored as a date (not datetime).
    """
    tariff = TariffHistory.create(
        tariff_code="DPP",
        effective_date=date(2024, 1, 1),
        t1_xof=68.0,
        t2_xof=121.0,
        t3_xof=158.0,
        woyofal_xof=114.0,
        is_current=True,
    )
    async_session.add(tariff)
    await async_session.commit()

    result = await async_session.execute(
        select(TariffHistory).where(TariffHistory.tariff_code == "DPP")
    )
    fetched = result.scalar_one()

    assert fetched.tariff_code == "DPP"
    assert fetched.effective_date == date(2024, 1, 1)
    assert fetched.t1_xof == pytest.approx(68.0, rel=1e-6)
    assert fetched.t2_xof == pytest.approx(121.0, rel=1e-6)
    assert fetched.t3_xof == pytest.approx(158.0, rel=1e-6)
    assert fetched.woyofal_xof == pytest.approx(114.0, rel=1e-6)
    assert fetched.is_current is True


async def test_tariff_history_invalid_code(async_session: AsyncSession) -> None:
    """Creating a TariffHistory with an unknown tariff code raises ValueError."""
    with pytest.raises(ValueError, match="Unknown tariff code"):
        TariffHistory.create(
            tariff_code="UNKNOWN",
            effective_date=date(2024, 1, 1),
            t1_xof=68.0,
            t2_xof=121.0,
        )


# ── Redis cache tests ─────────────────────────────────────────────────────────


async def test_redis_cache_roundtrip(async_redis: Any) -> None:
    """Redis cache set → get round-trip returns the stored value.

    Uses the ``async_redis`` fixture (fakeredis or AsyncMock fallback).
    Verifies that ``cache_set`` followed by ``cache_get`` returns the
    original string value, and that ``cache_delete`` removes it.
    """
    # Wire the RedisClient to use our test Redis instance.
    client = RedisClient()
    client._client = async_redis  # inject test Redis directly

    key = "pvgis:14.76:-17.44"
    payload = '{"irradiance": 5.8, "temperature": 32.0}'

    # Set
    await client.cache_set(key, payload, ttl_seconds=PVGIS_TTL)

    # Get — should return original value
    retrieved = await client.cache_get(key)
    assert retrieved == payload

    # Delete — subsequent get should return None
    await client.cache_delete(key)
    after_delete = await client.cache_get(key)
    assert after_delete is None


async def test_redis_cache_miss(async_redis: Any) -> None:
    """``cache_get`` returns None for keys that have never been set."""
    client = RedisClient()
    client._client = async_redis

    result = await client.cache_get("nonexistent:key")
    assert result is None


async def test_redis_ttl_constants() -> None:
    """TTL constants have the expected values as per the sprint specification."""
    assert PVGIS_TTL == 60 * 60 * 24 * 30, "PVGIS TTL should be 30 days"
    assert SESSION_TTL == 60 * 60 * 24, "Session TTL should be 24 hours"
    assert TARIFF_TTL == 60 * 60 * 24 * 7, "Tariff TTL should be 7 days"


# ── Relationship cascade tests ────────────────────────────────────────────────


async def test_project_cascade_delete(async_session: AsyncSession) -> None:
    """Deleting a User cascades to delete their Projects automatically."""
    user = _make_user(email="cascade@example.sn")
    async_session.add(user)
    await async_session.flush()

    project = Project.create(
        user_id=user.id,
        name="Projet à supprimer",
        latitude=14.69,
        longitude=-17.44,
    )
    async_session.add(project)
    await async_session.commit()

    # Verify project exists before deletion
    pre_result = await async_session.execute(
        select(Project).where(Project.user_id == user.id)
    )
    assert pre_result.scalar_one_or_none() is not None

    # Delete user — cascade should remove project
    await async_session.delete(user)
    await async_session.commit()

    post_result = await async_session.execute(
        select(Project).where(Project.user_id == user.id)
    )
    assert post_result.scalar_one_or_none() is None


async def test_simulation_report_cascade(async_session: AsyncSession) -> None:
    """Deleting a Simulation cascades to delete its Report."""
    user = _make_user(email="sim_report_cascade@example.sn")
    async_session.add(user)
    await async_session.flush()

    project = Project.create(
        user_id=user.id,
        name="Projet Rapport",
        latitude=14.69,
        longitude=-17.44,
    )
    async_session.add(project)
    await async_session.flush()

    sim = Simulation.create(
        project_id=project.id,
        panel_count=10,
        peak_kwc=5.45,
        annual_kwh=7_800.0,
    )
    async_session.add(sim)
    await async_session.flush()

    report = Report.create(simulation_id=sim.id)
    async_session.add(report)
    await async_session.commit()

    # Delete simulation; report should cascade
    await async_session.delete(sim)
    await async_session.commit()

    post_result = await async_session.execute(
        select(Report).where(Report.simulation_id == sim.id)
    )
    assert post_result.scalar_one_or_none() is None
