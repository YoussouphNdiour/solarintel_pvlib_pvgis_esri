"""Equipment pricing reference data endpoint.

GET /api/v2/equipment/prices — return static panel and inverter price list.

Prices are in XOF (West African CFA franc) and EUR, sourced from typical
West African distributor catalogues (2024).
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/equipment", tags=["equipment"])


class PanelPrice(BaseModel):
    model: str
    brand: str
    power_wc: int
    price_xof: int
    price_eur: float
    supplier: str


class InverterPrice(BaseModel):
    model: str
    brand: str
    kva: float
    price_xof: int
    supplier: str


class EquipmentPricesResponse(BaseModel):
    panels: list[PanelPrice]
    inverters: list[InverterPrice]


_PANELS: list[PanelPrice] = [
    PanelPrice(model="JA Solar JAM72S30-545/MR", brand="JA Solar", power_wc=545, price_xof=85_000, price_eur=130, supplier="Senergy Dakar"),
    PanelPrice(model="LONGi LR5-72HIH-545M", brand="LONGi", power_wc=545, price_xof=88_000, price_eur=134, supplier="Senergy Dakar"),
    PanelPrice(model="Canadian Solar CS6W-545MS", brand="Canadian Solar", power_wc=545, price_xof=82_000, price_eur=125, supplier="SolarTech Abidjan"),
    PanelPrice(model="Jinko Tiger Neo JKM580N-72HL4", brand="Jinko Solar", power_wc=580, price_xof=92_000, price_eur=140, supplier="EcoSolar Sénégal"),
    PanelPrice(model="Risen RSM132-8-650BMDG", brand="Risen Energy", power_wc=650, price_xof=105_000, price_eur=160, supplier="SolarTech Abidjan"),
]

_INVERTERS: list[InverterPrice] = [
    InverterPrice(model="Victron MultiPlus-II 3kVA", brand="Victron Energy", kva=3.0, price_xof=450_000, supplier="Senergy Dakar"),
    InverterPrice(model="Victron MultiPlus-II 5kVA", brand="Victron Energy", kva=5.0, price_xof=720_000, supplier="Senergy Dakar"),
    InverterPrice(model="Deye SUN-5K-SG04LP1", brand="Deye", kva=5.0, price_xof=380_000, supplier="EcoSolar Sénégal"),
    InverterPrice(model="Deye SUN-8K-SG03LP1", brand="Deye", kva=8.0, price_xof=520_000, supplier="EcoSolar Sénégal"),
    InverterPrice(model="Growatt SPF 5000ES", brand="Growatt", kva=5.0, price_xof=350_000, supplier="SolarTech Abidjan"),
    InverterPrice(model="Growatt SPF 10000T DVM", brand="Growatt", kva=10.0, price_xof=650_000, supplier="SolarTech Abidjan"),
    InverterPrice(model="SMA Sunny Boy 6.0", brand="SMA", kva=6.0, price_xof=680_000, supplier="Senergy Dakar"),
    InverterPrice(model="Huawei SUN2000-10KTL-M1", brand="Huawei", kva=10.0, price_xof=590_000, supplier="EcoSolar Sénégal"),
]


@router.get("/prices", response_model=EquipmentPricesResponse, summary="Get panel and inverter price list")
async def get_equipment_prices() -> EquipmentPricesResponse:
    """Return the reference price list for panels and inverters available in West Africa."""
    return EquipmentPricesResponse(panels=_PANELS, inverters=_INVERTERS)
