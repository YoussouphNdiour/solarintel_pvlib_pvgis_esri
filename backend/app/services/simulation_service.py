"""PV simulation service using pvlib + PVGIS TMY data with Redis caching.

Fetches hourly TMY irradiance from PVGIS API, runs pvlib ModelChain,
returns monthly energy production and performance metrics.
Results cached in Redis for PVGIS_TTL (30 days) to avoid redundant API calls.

Fallback: if pvlib import fails, returns an estimate of
1650 kWh/kWp × peak_kwc (typical West Africa yield) with PR=0.78.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
import pandas as pd

from app.core.config import get_settings
from app.db.redis import PVGIS_TTL, redis_client

logger = logging.getLogger(__name__)

# ── pvlib import with graceful fallback ───────────────────────────────────────

try:
    import pvlib
    from pvlib.location import Location
    from pvlib.modelchain import ModelChain
    from pvlib.pvsystem import Array, FixedMount, PVSystem

    _PVLIB_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PVLIB_AVAILABLE = False
    logger.warning(
        "pvlib is not installed — simulation will use the 1650 kWh/kWp fallback estimate."
    )


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class SimulationParams:
    """Input parameters for a PV simulation run.

    Attributes:
        latitude: WGS-84 decimal latitude of the installation site.
        longitude: WGS-84 decimal longitude of the installation site.
        panel_count: Number of PV panels in the array.
        panel_power_wc: Nameplate power per panel in Watts.
        panel_efficiency: Panel efficiency fraction (default 0.21 = 21%).
        tilt: Panel tilt from horizontal in degrees (15° typical for Senegal).
        azimuth: Panel azimuth in degrees (180 = south-facing).
        system_losses: Fractional system losses for wiring, soiling, shading (0.14 = 14%).
        inverter_efficiency: AC/DC conversion efficiency fraction.
    """

    latitude: float
    longitude: float
    panel_count: int
    panel_power_wc: int
    panel_efficiency: float = 0.21
    tilt: float = 15.0
    azimuth: float = 180.0
    system_losses: float = 0.14
    inverter_efficiency: float = 0.97


@dataclass
class MonthlyResult:
    """Production and irradiance summary for a single calendar month.

    Attributes:
        month: Calendar month number (1 = January … 12 = December).
        energy_kwh: Estimated AC energy production for the month in kWh.
        irradiance_kwh_m2: Total horizontal irradiance for the month in kWh/m².
        performance_ratio: Monthly performance ratio (0–1 scale).
    """

    month: int
    energy_kwh: float
    irradiance_kwh_m2: float
    performance_ratio: float


@dataclass
class SimulationResult:
    """Aggregated results of a full PV simulation run.

    Attributes:
        annual_kwh: Total estimated annual AC energy production in kWh.
        peak_kwc: System peak power in kWp (panel_count × panel_power_wc / 1000).
        specific_yield: Annual energy yield per kWp in kWh/kWp.
        performance_ratio: Annual system performance ratio (0–1 scale).
        monthly_data: List of 12 monthly production breakdowns.
        params_used: Snapshot of simulation input parameters.
    """

    annual_kwh: float
    peak_kwc: float
    specific_yield: float
    performance_ratio: float
    monthly_data: list[MonthlyResult]
    params_used: dict[str, Any] = field(default_factory=dict)


# ── Service ───────────────────────────────────────────────────────────────────


class SimulationService:
    """PV yield simulation service.

    Fetches TMY irradiance data from the PVGIS REST API (with Redis caching),
    then runs a pvlib ModelChain to compute monthly and annual energy production.
    Falls back to a rule-of-thumb estimate (1650 kWh/kWp) when pvlib is absent.
    """

    async def simulate(self, params: SimulationParams) -> SimulationResult:
        """Run a full PV simulation for the given parameters.

        Retrieves TMY irradiance data (from cache or PVGIS), computes
        AC energy production via pvlib ModelChain, and returns aggregated results.

        Args:
            params: Simulation input parameters.

        Returns:
            A ``SimulationResult`` with monthly breakdown and annual totals.
        """
        if not _PVLIB_AVAILABLE:
            return self._fallback_estimate(params)

        tmy_data = await self._get_tmy_data(params.latitude, params.longitude)
        return self._run_pvlib(params, tmy_data)

    # ── TMY data retrieval ────────────────────────────────────────────────────

    async def _get_tmy_data(self, lat: float, lon: float) -> pd.DataFrame:
        """Fetch TMY data from Redis cache or PVGIS API.

        Cache key format: ``pvgis:{lat:.4f}:{lon:.4f}``
        TTL: PVGIS_TTL (30 days) — PVGIS climate data changes very rarely.

        Args:
            lat: Decimal latitude of the site.
            lon: Decimal longitude of the site.

        Returns:
            A pandas DataFrame with columns: ghi, dni, dhi, temp_air, wind_speed.
            Index is an hourly DatetimeIndex (8760 rows, UTC).

        Raises:
            httpx.HTTPStatusError: If the PVGIS API returns a non-2xx response.
        """
        cache_key = f"pvgis:{lat:.4f}:{lon:.4f}"

        # ── Cache hit ─────────────────────────────────────────────────────────
        cached = await redis_client.cache_get(cache_key)
        if cached:
            logger.debug("PVGIS cache hit for key=%s", cache_key)
            return pd.read_json(io.StringIO(cached), orient="split")

        # ── PVGIS API call ────────────────────────────────────────────────────
        logger.info("Fetching PVGIS TMY for lat=%.4f lon=%.4f", lat, lon)
        settings = get_settings()
        url = f"{settings.pvgis_base_url}/tmy"
        request_params = {
            "lat": lat,
            "lon": lon,
            "outputformat": "json",
            "browser": 0,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, params=request_params)
            resp.raise_for_status()

        data = resp.json()
        hourly = data["outputs"]["tmy_hourly"]
        df = pd.DataFrame(hourly)

        # Rename PVGIS column names to pvlib standard names
        df = df.rename(
            columns={
                "G(h)": "ghi",
                "Gb(n)": "dni",
                "Gd(h)": "dhi",
                "T2m": "temp_air",
                "WS10m": "wind_speed",
            }
        )

        # Assign an hourly UTC DatetimeIndex (year is arbitrary — pvlib uses DoY)
        df.index = pd.date_range("2023-01-01", periods=8760, freq="h", tz="UTC")

        # Persist to cache
        serialised = df.to_json(orient="split")
        await redis_client.cache_set(cache_key, serialised, PVGIS_TTL)
        logger.debug("PVGIS TMY cached under key=%s (TTL=%d s)", cache_key, PVGIS_TTL)

        return df

    # ── pvlib computation ─────────────────────────────────────────────────────

    def _run_pvlib(
        self, params: SimulationParams, tmy: pd.DataFrame
    ) -> SimulationResult:
        """Execute the pvlib ModelChain and aggregate monthly results.

        Uses the SDM (PVWatts-style) model with:
        - ``aoi_model="no_loss"`` — skips cosine loss correction for speed
        - ``spectral_model="no_loss"`` — skips spectral mismatch correction

        System losses (wiring, soiling, shading, …) are applied as a uniform
        post-processing derating factor after the ModelChain run.

        Args:
            params: Simulation input parameters.
            tmy: Hourly TMY DataFrame with ghi, dni, dhi, temp_air, wind_speed.

        Returns:
            A ``SimulationResult`` with monthly breakdown and annual totals.
        """
        peak_kwc = (params.panel_count * params.panel_power_wc) / 1000.0

        location = Location(
            latitude=params.latitude,
            longitude=params.longitude,
            tz="UTC",
        )

        mount = FixedMount(
            surface_tilt=params.tilt,
            surface_azimuth=params.azimuth,
        )

        # PVWatts-style single-diode approximation via pvlib's pvwatts_dc model.
        # pdc0: DC output at STC for the *entire* array.
        module_params: dict[str, float] = {
            "pdc0": float(params.panel_count * params.panel_power_wc),
            "gamma_pdc": -0.004,  # -0.4%/°C temperature coefficient
        }
        inverter_params: dict[str, float] = {
            "pdc0": float(params.panel_count * params.panel_power_wc),
            "eta_inv_nom": params.inverter_efficiency,
        }

        system = PVSystem(
            arrays=[
                Array(
                    mount=mount,
                    module_parameters=module_params,
                    temperature_model_parameters={
                        "a": -3.56,
                        "b": -0.075,
                        "deltaT": 3,
                    },
                )
            ],
            inverter_parameters=inverter_params,
        )

        mc = ModelChain(
            system,
            location,
            aoi_model="no_loss",
            spectral_model="no_loss",
        )
        mc.run_model(tmy)

        # ── Aggregate monthly results ─────────────────────────────────────────
        ac_power: pd.Series = mc.results.ac  # type: ignore[attr-defined]

        # Guard against negative values (clipped at inverter minimum output)
        ac_power = ac_power.clip(lower=0.0)

        # Resample to monthly sums in kWh
        monthly_energy: pd.Series = ac_power.resample("ME").sum() / 1000.0
        monthly_irr: pd.Series = tmy["ghi"].resample("ME").sum() / 1000.0  # kWh/m²

        # Apply uniform system loss derating
        monthly_energy = monthly_energy * (1.0 - params.system_losses)

        annual_kwh = float(monthly_energy.sum())

        # Annual performance ratio: PR = E_ac / (G_poa × peak_kwc)
        # Use effective POA irradiance from ModelChain results, which correctly
        # accounts for AOI projection and is available per-array.
        # ``mc.results.effective_irradiance`` is the per-array effective irradiance
        # (W/m²) after transposition; it can be a list or Series depending on
        # pvlib version. We extract the first array's values.
        try:
            poa_raw = mc.results.effective_irradiance  # type: ignore[attr-defined]
            if isinstance(poa_raw, list):
                poa_series: pd.Series = pd.Series(
                    poa_raw[0], index=ac_power.index
                )
            elif hasattr(poa_raw, "iloc"):
                poa_series = poa_raw  # type: ignore[assignment]
            else:
                raise AttributeError("unexpected type")
            # Only count hours with positive irradiance to exclude night
            poa_annual = float(poa_series[poa_series > 0.0].sum()) / 1000.0
        except (AttributeError, IndexError):
            # Fall back to GHI-based denominator using only positive hours
            ghi_pos = tmy["ghi"][tmy["ghi"] > 0.0]
            poa_annual = float(ghi_pos.sum()) / 1000.0

        pr = annual_kwh / (peak_kwc * poa_annual) if poa_annual > 0 else 0.75

        # Monthly PR uses per-month POA irradiance sum (positive hours only)
        try:
            poa_monthly: pd.Series = (
                poa_series[poa_series > 0.0].resample("ME").sum() / 1000.0  # type: ignore[possibly-undefined]
            )
        except (NameError, AttributeError):
            poa_monthly = (
                tmy["ghi"][tmy["ghi"] > 0.0].resample("ME").sum() / 1000.0
            )

        monthly_results: list[MonthlyResult] = []
        for i in range(12):
            e_month = float(monthly_energy.iloc[i])
            g_month = float(monthly_irr.iloc[i])  # raw GHI for irradianceKwhM2 field
            g_poa_month = float(poa_monthly.iloc[i]) if i < len(poa_monthly) else 0.0
            monthly_pr = (
                e_month / (peak_kwc * g_poa_month) if g_poa_month > 0 else pr
            )
            monthly_results.append(
                MonthlyResult(
                    month=i + 1,
                    energy_kwh=e_month,
                    irradiance_kwh_m2=g_month,
                    performance_ratio=monthly_pr,
                )
            )

        return SimulationResult(
            annual_kwh=annual_kwh,
            peak_kwc=peak_kwc,
            specific_yield=annual_kwh / peak_kwc if peak_kwc > 0 else 0.0,
            performance_ratio=pr,
            monthly_data=monthly_results,
            params_used={
                "panel_count": params.panel_count,
                "panel_power_wc": params.panel_power_wc,
                "tilt": params.tilt,
                "azimuth": params.azimuth,
                "system_losses": params.system_losses,
                "inverter_efficiency": params.inverter_efficiency,
            },
        )

    # ── Fallback estimate ─────────────────────────────────────────────────────

    def _fallback_estimate(self, params: SimulationParams) -> SimulationResult:
        """Return a rule-of-thumb estimate when pvlib is unavailable.

        Uses 1650 kWh/kWp as the typical specific yield for West Africa,
        distributed across 12 months proportionally to the solar resource
        pattern (higher in dry season: Nov-Apr).

        Args:
            params: Simulation input parameters.

        Returns:
            A ``SimulationResult`` with estimated values and PR=0.78.
        """
        peak_kwc = (params.panel_count * params.panel_power_wc) / 1000.0
        specific_yield = 1650.0
        annual_kwh = specific_yield * peak_kwc * (1.0 - params.system_losses)
        pr = 0.78

        # Monthly weights for Senegal (dry season > rainy season)
        weights = [
            0.092,  # Jan
            0.085,  # Feb
            0.090,  # Mar
            0.088,  # Apr
            0.082,  # May
            0.072,  # Jun
            0.068,  # Jul — harmattan / overcast
            0.070,  # Aug
            0.075,  # Sep
            0.082,  # Oct
            0.090,  # Nov
            0.106,  # Dec
        ]
        monthly_results = [
            MonthlyResult(
                month=i + 1,
                energy_kwh=annual_kwh * weights[i],
                irradiance_kwh_m2=annual_kwh * weights[i] / (peak_kwc * pr),
                performance_ratio=pr,
            )
            for i in range(12)
        ]

        return SimulationResult(
            annual_kwh=annual_kwh,
            peak_kwc=peak_kwc,
            specific_yield=annual_kwh / peak_kwc if peak_kwc > 0 else 0.0,
            performance_ratio=pr,
            monthly_data=monthly_results,
            params_used={
                "panel_count": params.panel_count,
                "panel_power_wc": params.panel_power_wc,
                "tilt": params.tilt,
                "azimuth": params.azimuth,
                "system_losses": params.system_losses,
                "fallback": True,
            },
        )
