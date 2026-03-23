"""Open-Meteo API integration for real-time weather and irradiance data.

Fetches hourly temperature and shortwave radiation to correct pvlib
simulation estimates with measured conditions.

Cache key: weather:{lat:.3f}:{lon:.3f}:{date}  TTL: 1 hour
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from app.db.redis import redis_client

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_CACHE_TTL: int = 60 * 60  # 1 hour in seconds

# Standard temperature reference for PV derating (STC = 25 °C)
_STC_TEMPERATURE_C: float = 25.0
# Correction factor bounds
_FACTOR_MIN: float = 0.5
_FACTOR_MAX: float = 1.5


@dataclass
class HourlyWeather:
    """Hourly weather data returned by Open-Meteo."""

    timestamp: list[str]               # ISO datetime strings
    temperature_2m: list[float]        # Celsius
    shortwave_radiation: list[float]   # W/m²
    direct_radiation: list[float]      # W/m²
    diffuse_radiation: list[float]     # W/m²


@dataclass
class WeatherCorrection:
    """Measured-vs-simulated irradiance correction result."""

    correction_factor: float           # measured / simulated irradiance ratio
    measured_daily_kwh_m2: float       # sum of shortwave_radiation / 1000
    simulated_daily_kwh_m2: float      # input from caller
    temperature_delta_c: float         # mean(measured) - 25 °C
    date: str                          # YYYY-MM-DD


def _empty_weather() -> HourlyWeather:
    """Return a zero-filled HourlyWeather for graceful error fallback."""
    return HourlyWeather(
        timestamp=[],
        temperature_2m=[],
        shortwave_radiation=[],
        direct_radiation=[],
        diffuse_radiation=[],
    )


def _fallback_correction(simulated_daily_kwh_m2: float) -> WeatherCorrection:
    """Return a neutral correction (factor=1.0) when API call fails."""
    return WeatherCorrection(
        correction_factor=1.0,
        measured_daily_kwh_m2=simulated_daily_kwh_m2,
        simulated_daily_kwh_m2=simulated_daily_kwh_m2,
        temperature_delta_c=0.0,
        date=datetime.now(tz=timezone.utc).date().isoformat(),
    )


class WeatherService:
    """Fetches real-time weather data from Open-Meteo and computes correction."""

    # ── Public API ────────────────────────────────────────────────────────────

    async def fetch_hourly(
        self,
        lat: float,
        lon: float,
        days: int = 1,
    ) -> HourlyWeather:
        """Fetch hourly weather from Open-Meteo. Cached 1 hour in Redis.

        Args:
            lat: WGS-84 decimal latitude.
            lon: WGS-84 decimal longitude.
            days: Number of forecast days to retrieve (default 1).

        Returns:
            HourlyWeather dataclass with 24-element (or more) lists.
            On any error returns an empty HourlyWeather (graceful fallback).

        Cache key: ``weather:{lat:.3f}:{lon:.3f}:{today}``
        """
        today = datetime.now(tz=timezone.utc).date().isoformat()
        cache_key = f"weather:{lat:.3f}:{lon:.3f}:{today}"

        cached = await redis_client.cache_get(cache_key)
        if cached:
            try:
                data = json.loads(cached)
                return HourlyWeather(**data)
            except Exception:
                logger.warning("Failed to deserialise cached weather data for %s", cache_key)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    OPEN_METEO_URL,
                    params={
                        "latitude": lat,
                        "longitude": lon,
                        "hourly": (
                            "temperature_2m,"
                            "shortwave_radiation,"
                            "direct_radiation,"
                            "diffuse_radiation"
                        ),
                        "forecast_days": days,
                        "timezone": "Africa/Dakar",
                    },
                )
                response.raise_for_status()
        except Exception as exc:
            logger.error("Open-Meteo request failed: %s", exc)
            return _empty_weather()

        try:
            body = response.json()
            hourly = body["hourly"]
            weather = HourlyWeather(
                timestamp=hourly["time"],
                temperature_2m=hourly["temperature_2m"],
                shortwave_radiation=hourly["shortwave_radiation"],
                direct_radiation=hourly["direct_radiation"],
                diffuse_radiation=hourly["diffuse_radiation"],
            )
        except (KeyError, ValueError) as exc:
            logger.error("Unexpected Open-Meteo response shape: %s", exc)
            return _empty_weather()

        try:
            payload = json.dumps(
                {
                    "timestamp": weather.timestamp,
                    "temperature_2m": weather.temperature_2m,
                    "shortwave_radiation": weather.shortwave_radiation,
                    "direct_radiation": weather.direct_radiation,
                    "diffuse_radiation": weather.diffuse_radiation,
                }
            )
            await redis_client.cache_set(cache_key, payload, WEATHER_CACHE_TTL)
        except Exception as exc:
            logger.warning("Failed to cache weather data: %s", exc)

        return weather

    async def compute_correction(
        self,
        lat: float,
        lon: float,
        simulated_daily_kwh_m2: float,
    ) -> WeatherCorrection:
        """Compare measured vs simulated irradiance to get correction factor.

        Args:
            lat: Site latitude.
            lon: Site longitude.
            simulated_daily_kwh_m2: Daily irradiance from pvlib model (kWh/m²).

        Returns:
            WeatherCorrection with factor clamped to [0.5, 1.5].
            On any error returns WeatherCorrection(correction_factor=1.0, ...).
        """
        today = datetime.now(tz=timezone.utc).date().isoformat()

        try:
            weather = await self.fetch_hourly(lat, lon, days=1)

            if not weather.shortwave_radiation:
                return _fallback_correction(simulated_daily_kwh_m2)

            # Integrate hourly W/m² to daily kWh/m²  (each step = 1 h)
            measured_daily = sum(weather.shortwave_radiation) / 1000.0

            if simulated_daily_kwh_m2 <= 0:
                return _fallback_correction(simulated_daily_kwh_m2)

            raw_factor = measured_daily / simulated_daily_kwh_m2
            clamped_factor = max(_FACTOR_MIN, min(_FACTOR_MAX, raw_factor))

            mean_temp = (
                sum(weather.temperature_2m) / len(weather.temperature_2m)
                if weather.temperature_2m
                else _STC_TEMPERATURE_C
            )
            temp_delta = mean_temp - _STC_TEMPERATURE_C

            return WeatherCorrection(
                correction_factor=clamped_factor,
                measured_daily_kwh_m2=measured_daily,
                simulated_daily_kwh_m2=simulated_daily_kwh_m2,
                temperature_delta_c=temp_delta,
                date=today,
            )
        except Exception as exc:
            logger.error("compute_correction failed: %s", exc)
            return _fallback_correction(simulated_daily_kwh_m2)
