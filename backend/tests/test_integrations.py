"""INTEG-001: Integration tests for WeatherService, WhatsAppService,
EquipmentPricesService, and webhook endpoints.

All external HTTP calls are mocked with respx / unittest.mock.
Redis is replaced with fakeredis (or AsyncMock fallback from conftest).
The FastAPI test client overrides get_async_db with the in-memory SQLite session.

asyncio_mode = "auto" is set in pyproject.toml — no @pytest.mark.asyncio needed.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
import respx
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.redis import redis_client
from app.db.session import get_async_db
from app.main import create_application
from app.models.monitoring import Monitoring
from app.models.project import Project
from app.models.report import Report
from app.models.simulation import Simulation
from app.models.user import User

# ── Constants ──────────────────────────────────────────────────────────────────

_LAT = 14.693
_LON = -17.447
_TODAY = datetime.now(tz=timezone.utc).date().isoformat()
_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
_WHATSAPP_API_URL = "https://graph.facebook.com/v19.0"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _build_open_meteo_response(
    radiation: float = 500.0,
    temperature: float = 28.0,
) -> dict[str, Any]:
    """Build a minimal synthetic Open-Meteo hourly JSON response."""
    hours = 24
    return {
        "latitude": _LAT,
        "longitude": _LON,
        "timezone": "Africa/Dakar",
        "hourly": {
            "time": [f"{_TODAY}T{h:02d}:00" for h in range(hours)],
            "temperature_2m": [temperature] * hours,
            "shortwave_radiation": [radiation] * hours,
            "direct_radiation": [radiation * 0.7] * hours,
            "diffuse_radiation": [radiation * 0.3] * hours,
        },
    }


def _make_hmac_signature(body: bytes, secret: str) -> str:
    """Return a valid HMAC-SHA256 hex signature for body using secret."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


# ── DB session override (matches pattern from test_simulation.py) ─────────────


def _make_db_override(session: AsyncSession):  # type: ignore[return]
    """Return a dependency override factory that yields the given session."""

    async def _override() -> AsyncGenerator[AsyncSession, None]:
        yield session

    return _override


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture()
async def fake_redis(async_redis: Any) -> AsyncGenerator[Any, None]:
    """Patch the module-level redis_client with fakeredis for test isolation."""
    original = redis_client._client
    redis_client._client = async_redis
    yield async_redis
    redis_client._client = original


@pytest_asyncio.fixture()
async def app_client(
    async_session: AsyncSession,
    fake_redis: Any,
) -> AsyncGenerator[AsyncClient, None]:
    """Return an AsyncClient wired to in-memory DB + fake Redis."""
    application: FastAPI = create_application()
    application.dependency_overrides[get_async_db] = _make_db_override(async_session)

    transport = ASGITransport(app=application)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    application.dependency_overrides.clear()


@pytest_asyncio.fixture()
async def db_user(async_session: AsyncSession) -> User:
    """Persist and return a test user."""
    user = User.create(
        email="integ_test@solarintel.sn",
        role="technicien",
        hashed_password="$2b$12$hashed",
    )
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)
    return user


@pytest_asyncio.fixture()
async def db_project(async_session: AsyncSession, db_user: User) -> Project:
    """Persist and return a test project at Dakar coordinates."""
    project = Project.create(
        user_id=db_user.id,
        name="Test Solar Farm",
        latitude=_LAT,
        longitude=_LON,
        address="Dakar, Sénégal",
    )
    async_session.add(project)
    await async_session.commit()
    await async_session.refresh(project)
    return project


@pytest_asyncio.fixture()
async def db_report(
    async_session: AsyncSession,
    db_project: Project,
) -> Report:
    """Persist a completed simulation + ready report for WhatsApp tests."""
    sim = Simulation.create(
        project_id=db_project.id,
        panel_count=10,
        peak_kwc=5.0,
        annual_kwh=8500.0,
        status="completed",
    )
    async_session.add(sim)
    await async_session.flush()

    report = Report.create(
        simulation_id=sim.id,
        status="ready",
        pdf_path="/tmp/solarintel/reports/test_report.pdf",
    )
    async_session.add(report)
    await async_session.commit()
    await async_session.refresh(report)
    return report


# ═══════════════════════════════════════════════════════════════════════════════
# WeatherService tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestWeatherService:
    """Unit tests for WeatherService — Open-Meteo calls mocked with respx."""

    @respx.mock
    async def test_open_meteo_fetch_hourly(self, fake_redis: Any) -> None:
        """fetch_hourly returns HourlyWeather with temperature_2m and
        shortwave_radiation lists of length 24."""
        from app.services.weather_service import WeatherService

        mock_body = _build_open_meteo_response()
        respx.get(_OPEN_METEO_URL).mock(
            return_value=Response(200, json=mock_body)
        )

        svc = WeatherService()
        result = await svc.fetch_hourly(_LAT, _LON, days=1)

        assert len(result.timestamp) == 24
        assert len(result.temperature_2m) == 24
        assert len(result.shortwave_radiation) == 24
        assert result.temperature_2m[0] == 28.0
        assert result.shortwave_radiation[0] == 500.0

    @respx.mock
    async def test_weather_correction_factor(self, fake_redis: Any) -> None:
        """correction_factor = measured/simulated and is clamped to [0.5, 1.5]."""
        from app.services.weather_service import WeatherService

        # 500 W/m² × 24h ÷ 1000 = 12 kWh/m² daily measured
        mock_body = _build_open_meteo_response(radiation=500.0)
        respx.get(_OPEN_METEO_URL).mock(
            return_value=Response(200, json=mock_body)
        )

        svc = WeatherService()
        correction = await svc.compute_correction(
            lat=_LAT,
            lon=_LON,
            simulated_daily_kwh_m2=12.0,
        )

        assert 0.5 <= correction.correction_factor <= 1.5
        assert correction.measured_daily_kwh_m2 > 0
        assert correction.simulated_daily_kwh_m2 == 12.0

    async def test_weather_cache_ttl(self, fake_redis: Any) -> None:
        """Second call within TTL window uses cached data — HTTP called once."""
        from app.services.weather_service import WeatherService

        mock_body = _build_open_meteo_response()

        with respx.mock() as mock:
            mock.get(_OPEN_METEO_URL).mock(
                return_value=Response(200, json=mock_body)
            )

            svc = WeatherService()
            await svc.fetch_hourly(_LAT, _LON, days=1)
            await svc.fetch_hourly(_LAT, _LON, days=1)

            # HTTP must have been called exactly once; second call used the cache
            assert mock.calls.call_count == 1

    @respx.mock
    async def test_weather_invalid_location(self, fake_redis: Any) -> None:
        """API 500 error returns graceful fallback with correction_factor=1.0."""
        from app.services.weather_service import WeatherService

        respx.get(_OPEN_METEO_URL).mock(
            return_value=Response(500, text="Internal Server Error")
        )

        svc = WeatherService()
        correction = await svc.compute_correction(
            lat=999.0,
            lon=999.0,
            simulated_daily_kwh_m2=10.0,
        )

        assert correction.correction_factor == 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# WhatsAppService tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestWhatsAppService:
    """Unit tests for WhatsAppService — Meta API calls mocked."""

    @respx.mock
    async def test_send_pdf_quote_success(self) -> None:
        """send_pdf_quote POSTs a document payload to the WhatsApp API."""
        from app.services.whatsapp_service import WhatsAppService

        phone_id = "12345678"
        respx.post(f"{_WHATSAPP_API_URL}/{phone_id}/messages").mock(
            return_value=Response(200, json={"messages": [{"id": "wamid.test"}]})
        )

        with patch("app.services.whatsapp_service.get_settings") as mock_settings:
            settings = MagicMock()
            settings.whatsapp_token = "test_token_abc"
            settings.whatsapp_phone_id = phone_id
            mock_settings.return_value = settings

            svc = WhatsAppService()
            result = await svc.send_pdf_quote(
                phone="+221771234567",
                pdf_url="https://example.com/report.pdf",
                filename="rapport_solaire.pdf",
                caption="Votre rapport SolarIntel",
            )

        assert result.get("messages") is not None
        assert respx.calls.call_count == 1
        request_body = json.loads(respx.calls[0].request.content)
        assert request_body["type"] == "document"
        assert request_body["document"]["link"] == "https://example.com/report.pdf"

    async def test_send_pdf_quote_no_token(self) -> None:
        """send_pdf_quote raises ValueError when WHATSAPP_TOKEN is not set."""
        from app.services.whatsapp_service import WhatsAppService

        with patch("app.services.whatsapp_service.get_settings") as mock_settings:
            settings = MagicMock()
            settings.whatsapp_token = None
            settings.whatsapp_phone_id = None
            mock_settings.return_value = settings

            svc = WhatsAppService()
            with pytest.raises(ValueError, match="WHATSAPP_TOKEN"):
                await svc.send_pdf_quote(
                    phone="+221771234567",
                    pdf_url="https://example.com/report.pdf",
                    filename="report.pdf",
                    caption="Test",
                )

    @respx.mock
    async def test_send_text_message(self) -> None:
        """send_text sends a plain text message to the given phone number."""
        from app.services.whatsapp_service import WhatsAppService

        phone_id = "99887766"
        respx.post(f"{_WHATSAPP_API_URL}/{phone_id}/messages").mock(
            return_value=Response(200, json={"messages": [{"id": "wamid.text"}]})
        )

        with patch("app.services.whatsapp_service.get_settings") as mock_settings:
            settings = MagicMock()
            settings.whatsapp_token = "test_token_xyz"
            settings.whatsapp_phone_id = phone_id
            mock_settings.return_value = settings

            svc = WhatsAppService()
            await svc.send_text(
                phone="+221781234567",
                message="Bonjour! Votre simulation est prête.",
            )

        assert respx.calls.call_count == 1
        request_body = json.loads(respx.calls[0].request.content)
        assert request_body["type"] == "text"
        assert "Bonjour" in request_body["text"]["body"]

    async def test_whatsapp_phone_format(self) -> None:
        """normalize_phone handles all Senegalese number formats correctly."""
        from app.services.whatsapp_service import WhatsAppService

        svc = WhatsAppService()

        # Local 9-digit format
        assert svc.normalize_phone("771234567") == "+221771234567"
        # With country code prefix, no +
        assert svc.normalize_phone("221771234567") == "+221771234567"
        # Already E.164
        assert svc.normalize_phone("+221771234567") == "+221771234567"
        # With spaces
        assert svc.normalize_phone("77 123 45 67") == "+221771234567"
        # With dashes
        assert svc.normalize_phone("77-123-45-67") == "+221771234567"
        # 78 prefix (Orange Money)
        assert svc.normalize_phone("781234567") == "+221781234567"
        # 76 prefix (Expresso)
        assert svc.normalize_phone("761234567") == "+221761234567"
        # 70 prefix (Free)
        assert svc.normalize_phone("701234567") == "+221701234567"
        # 33 prefix (fixed line)
        assert svc.normalize_phone("331234567") == "+221331234567"


# ═══════════════════════════════════════════════════════════════════════════════
# EquipmentPricesService tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestEquipmentPricesService:
    """Unit tests for EquipmentPricesService — Redis interaction tested."""

    async def test_get_prices_from_cache(self, fake_redis: Any) -> None:
        """Returns cached prices when the Redis key is populated."""
        from app.services.equipment_prices_service import (
            DEFAULT_PANEL_PRICES,
            EquipmentPricesService,
        )

        panels_json = json.dumps(
            [
                {
                    "model": p.model,
                    "brand": p.brand,
                    "power_wc": p.power_wc,
                    "price_xof": p.price_xof,
                    "price_eur": p.price_eur,
                    "supplier": p.supplier,
                }
                for p in DEFAULT_PANEL_PRICES
            ]
        )
        await fake_redis.setex("equipment:prices:panels", 604800, panels_json)

        svc = EquipmentPricesService()
        prices = await svc.get_panel_prices()

        assert len(prices) == len(DEFAULT_PANEL_PRICES)
        assert prices[0].model == DEFAULT_PANEL_PRICES[0].model

    async def test_get_prices_cache_miss_returns_defaults(
        self, fake_redis: Any
    ) -> None:
        """Falls back to DEFAULT_PANEL_PRICES when the Redis cache is empty."""
        from app.services.equipment_prices_service import (
            DEFAULT_PANEL_PRICES,
            EquipmentPricesService,
        )

        # No prior setex — cache is empty
        svc = EquipmentPricesService()
        prices = await svc.get_panel_prices()

        assert len(prices) == len(DEFAULT_PANEL_PRICES)
        assert prices[0].brand == DEFAULT_PANEL_PRICES[0].brand

    async def test_price_cache_key_format(self, fake_redis: Any) -> None:
        """After refresh_prices, keys follow the pattern equipment:prices:{category}."""
        from app.services.equipment_prices_service import EquipmentPricesService

        svc = EquipmentPricesService()
        await svc.refresh_prices()

        panels_cached = await fake_redis.get("equipment:prices:panels")
        inverters_cached = await fake_redis.get("equipment:prices:inverters")

        assert panels_cached is not None
        assert inverters_cached is not None

    async def test_price_weekly_refresh(self, fake_redis: Any) -> None:
        """Prices are stored with TARIFF_TTL (604800 s = 7 days) after refresh."""
        from app.db.redis import TARIFF_TTL
        from app.services.equipment_prices_service import EquipmentPricesService

        svc = EquipmentPricesService()
        await svc.refresh_prices()

        # fakeredis supports TTL inspection via .ttl()
        try:
            ttl = await fake_redis.ttl("equipment:prices:panels")
            # Allow a tiny delta for test execution time
            assert ttl > TARIFF_TTL - 5
        except (AttributeError, TypeError):
            # AsyncMock fallback — just confirm the key was written
            cached = await fake_redis.get("equipment:prices:panels")
            assert cached is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Webhook endpoint tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestWebhookEndpoints:
    """Integration tests for /api/v2/webhooks/* endpoints."""

    async def test_sunspec_webhook_valid_payload(
        self,
        app_client: AsyncClient,
        db_project: Project,
    ) -> None:
        """POST /api/v2/webhooks/inverter creates a Monitoring record."""
        settings = get_settings()
        secret = settings.webhook_secret or settings.secret_key

        payload = {
            "project_id": str(db_project.id),
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "production_kwh": 3.75,
            "power_kw": 4.2,
            "irradiance_wm2": 650.0,
            "temperature_c": 32.5,
            "device_id": "INV-001",
        }
        body = json.dumps(payload).encode()
        signature = _make_hmac_signature(body, secret)

        response = await app_client.post(
            "/api/v2/webhooks/inverter",
            content=body,
            headers={
                "Content-Type": "application/json",
                "x-webhook-signature": signature,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "monitoring_id" in data

    async def test_sunspec_webhook_invalid_project(
        self,
        app_client: AsyncClient,
    ) -> None:
        """POST /api/v2/webhooks/inverter returns 404 for an unknown project_id."""
        settings = get_settings()
        secret = settings.webhook_secret or settings.secret_key

        payload = {
            "project_id": str(uuid.uuid4()),  # does not exist in DB
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "production_kwh": 1.0,
            "power_kw": None,
            "irradiance_wm2": None,
            "temperature_c": None,
            "device_id": None,
        }
        body = json.dumps(payload).encode()
        signature = _make_hmac_signature(body, secret)

        response = await app_client.post(
            "/api/v2/webhooks/inverter",
            content=body,
            headers={
                "Content-Type": "application/json",
                "x-webhook-signature": signature,
            },
        )

        assert response.status_code == 404

    async def test_webhook_signature_verification(
        self,
        app_client: AsyncClient,
        db_project: Project,
    ) -> None:
        """POST /api/v2/webhooks/inverter rejects a payload with wrong signature."""
        payload = {
            "project_id": str(db_project.id),
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "production_kwh": 2.0,
            "power_kw": None,
            "irradiance_wm2": None,
            "temperature_c": None,
            "device_id": None,
        }
        body = json.dumps(payload).encode()

        response = await app_client.post(
            "/api/v2/webhooks/inverter",
            content=body,
            headers={
                "Content-Type": "application/json",
                "x-webhook-signature": "deadbeef_this_is_a_wrong_signature",
            },
        )

        assert response.status_code == 401

    @respx.mock
    async def test_open_meteo_webhook(
        self,
        app_client: AsyncClient,
        db_project: Project,
        db_user: User,
        fake_redis: Any,
    ) -> None:
        """GET /api/v2/webhooks/weather/{id} triggers fetch, returns correction,
        and caches the result under weather:correction:{project_id}."""
        mock_body = _build_open_meteo_response()
        respx.get(_OPEN_METEO_URL).mock(
            return_value=Response(200, json=mock_body)
        )

        response = await app_client.get(
            f"/api/v2/webhooks/weather/{db_project.id}",
            headers=_auth_header(db_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert "correction_factor" in data
        assert 0.5 <= data["correction_factor"] <= 1.5

        # Correction must be cached in Redis
        cache_key = f"weather:correction:{db_project.id}"
        cached = await fake_redis.get(cache_key)
        assert cached is not None
