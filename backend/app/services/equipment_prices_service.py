"""Equipment price cache service.

Maintains weekly-refreshed prices for solar equipment from Senegalese suppliers.
Prices stored in Redis with 7-day TTL.

Cache keys:
    equipment:prices:panels      — list of PanelPrice records (JSON)
    equipment:prices:inverters   — list of InverterPrice records (JSON)

TTL: TARIFF_TTL (7 days = 604800 seconds)
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass

from app.db.redis import TARIFF_TTL, redis_client

logger = logging.getLogger(__name__)

_CACHE_KEY_PANELS = "equipment:prices:panels"
_CACHE_KEY_INVERTERS = "equipment:prices:inverters"

# Cost-per-kWc installation estimates (FCFA)
_COST_PER_KWC_ON_GRID: float = 350_000.0
_COST_PER_KWC_HYBRID: float = 550_000.0


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class PanelPrice:
    """Price record for a solar panel model sold in Senegal."""

    model: str
    brand: str
    power_wc: int
    price_xof: float   # FCFA
    price_eur: float
    supplier: str


@dataclass
class InverterPrice:
    """Price record for an inverter sold in Senegal."""

    model: str
    brand: str
    kva: float
    price_xof: float   # FCFA
    supplier: str


# ── Hardcoded fallback prices (Dakar market, 2024) ────────────────────────────

DEFAULT_PANEL_PRICES: list[PanelPrice] = [
    PanelPrice(
        "JA Solar JAM72S30 545W", "JA Solar", 545, 95_000, 145,
        "Sénélec Solaire",
    ),
    PanelPrice(
        "Trina TSM-DE17M 545W", "Trina", 545, 92_000, 140,
        "Solartech Dakar",
    ),
    PanelPrice(
        "Canadian Solar HiKu7 600W", "Canadian Solar", 600, 108_000, 165,
        "EcoSolar SN",
    ),
    PanelPrice(
        "LONGI Hi-MO6 580W", "LONGI", 580, 102_000, 155,
        "Solartech Dakar",
    ),
]

DEFAULT_INVERTER_PRICES: list[InverterPrice] = [
    InverterPrice(
        "GOODWE GW5KT-DT 5kW", "GOODWE", 5.0, 850_000, "Solartech Dakar"
    ),
    InverterPrice(
        "GROWATT SPF 5000ES 5kW", "GROWATT", 5.0, 780_000, "EcoSolar SN"
    ),
    InverterPrice(
        "DEYE SUN-8K-SG04LP3 8kW", "DEYE", 8.0, 1_250_000, "Solartech Dakar"
    ),
    InverterPrice(
        "SMA Sunny Boy 10.0 10kW", "SMA", 10.0, 2_100_000, "Importateur SMA SN"
    ),
]


# ── Service ───────────────────────────────────────────────────────────────────


class EquipmentPricesService:
    """Cache-backed equipment price catalogue service."""

    async def get_panel_prices(self) -> list[PanelPrice]:
        """Return cached panel prices, falling back to defaults on cache miss.

        Returns:
            List of PanelPrice records from Redis or DEFAULT_PANEL_PRICES.
        """
        cached = await redis_client.cache_get(_CACHE_KEY_PANELS)
        if cached:
            try:
                raw: list[dict] = json.loads(cached)  # type: ignore[type-arg]
                return [PanelPrice(**item) for item in raw]
            except Exception as exc:
                logger.warning("Failed to deserialise panel prices: %s", exc)

        return list(DEFAULT_PANEL_PRICES)

    async def get_inverter_prices(self) -> list[InverterPrice]:
        """Return cached inverter prices, falling back to defaults on cache miss.

        Returns:
            List of InverterPrice records from Redis or DEFAULT_INVERTER_PRICES.
        """
        cached = await redis_client.cache_get(_CACHE_KEY_INVERTERS)
        if cached:
            try:
                raw: list[dict] = json.loads(cached)  # type: ignore[type-arg]
                return [InverterPrice(**item) for item in raw]
            except Exception as exc:
                logger.warning("Failed to deserialise inverter prices: %s", exc)

        return list(DEFAULT_INVERTER_PRICES)

    async def refresh_prices(self) -> None:
        """Re-cache default prices with TARIFF_TTL.

        Called weekly via background task (ARQ worker).  In production this
        method would fetch updated prices from a supplier API; currently it
        persists the hardcoded defaults to Redis so the TTL is reset.
        """
        try:
            panels_json = json.dumps([asdict(p) for p in DEFAULT_PANEL_PRICES])
            await redis_client.cache_set(_CACHE_KEY_PANELS, panels_json, TARIFF_TTL)
        except Exception as exc:
            logger.error("Failed to cache panel prices: %s", exc)

        try:
            inverters_json = json.dumps(
                [asdict(i) for i in DEFAULT_INVERTER_PRICES]
            )
            await redis_client.cache_set(
                _CACHE_KEY_INVERTERS, inverters_json, TARIFF_TTL
            )
        except Exception as exc:
            logger.error("Failed to cache inverter prices: %s", exc)

    async def get_installation_cost_estimate(
        self,
        peak_kwc: float,
        system_type: str = "on-grid",
    ) -> float:
        """Estimate total installation cost in FCFA for the given system size.

        Uses rule-of-thumb rates from the Dakar market (2024):
        - on-grid:  ~350,000 FCFA/kWc
        - hybrid:   ~550,000 FCFA/kWc (includes battery pack)

        Args:
            peak_kwc: System peak power in kWp.
            system_type: ``"on-grid"`` or ``"hybrid"`` (default ``"on-grid"``).

        Returns:
            Estimated total cost in FCFA (float).
        """
        rate = (
            _COST_PER_KWC_HYBRID
            if system_type == "hybrid"
            else _COST_PER_KWC_ON_GRID
        )
        return peak_kwc * rate
