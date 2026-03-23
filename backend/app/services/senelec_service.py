"""Senelec tariff calculation and solar savings analysis service.

Implements the 2024 Senelec tariff structure for Senegal:

DPP / PPP (Domestic — post-paid and progressive post-paid):
  T1 :  0 – 150 kWh/month →  84 FCFA/kWh
  T2 : 151 – 300 kWh/month → 121 FCFA/kWh
  T3 :   > 300 kWh/month   → 158 FCFA/kWh
  Fixed charge: 1 500 FCFA/month

DMP (Medium voltage, post-paid):
  Flat rate: 98 FCFA/kWh (no fixed charge)

PMP (Medium-power prepaid):
  Flat rate: 108 FCFA/kWh (no fixed charge)

WOYOFAL (Domestic prepaid token):
  Flat rate: 105 FCFA/kWh (no fixed charge)

All monetary values are stored and returned as float (XOF).
No integer rounding is applied to preserve precision for financial calculations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── Tariff constants (2024) ───────────────────────────────────────────────────

_DPP_T1_LIMIT_KWH: float = 150.0   # upper bound of Tranche 1
_DPP_T2_LIMIT_KWH: float = 300.0   # upper bound of Tranche 2

_DPP_T1_XOF: float = 84.0          # FCFA/kWh — Tranche 1
_DPP_T2_XOF: float = 121.0         # FCFA/kWh — Tranche 2
_DPP_T3_XOF: float = 158.0         # FCFA/kWh — Tranche 3

_DPP_FIXED_XOF: float = 1_500.0    # FCFA/month fixed subscription charge

_DMP_FLAT_XOF: float = 98.0        # FCFA/kWh — medium voltage flat rate
_PMP_FLAT_XOF: float = 108.0       # FCFA/kWh — medium-power prepaid
_WOYOFAL_FLAT_XOF: float = 105.0   # FCFA/kWh — Woyofal prepaid

_SYSTEM_LIFETIME_YEARS: int = 25    # Assumed system lifetime for ROI calculation


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class TariffBill:
    """Calculated electricity bill for a given consumption and tariff.

    Attributes:
        monthly_consumption_kwh: The consumption used to calculate this bill.
        monthly_cost_xof: Total monthly electricity cost in XOF.
        annual_cost_xof: Annual cost (monthly × 12) in XOF.
    """

    monthly_consumption_kwh: float
    monthly_cost_xof: float
    annual_cost_xof: float


@dataclass
class SenelecAnalysis:
    """Financial analysis of solar savings against a Senelec tariff.

    Attributes:
        tariff_code: The Senelec tariff plan used for the analysis.
        before_solar_monthly_xof: Monthly electricity cost without solar in XOF.
        after_solar_monthly_xof: Average monthly electricity cost with solar in XOF.
        annual_savings_xof: Estimated annual bill savings in XOF.
        payback_years: Simple payback period in years.
        roi_25yr_percent: Return on investment over 25 years as a percentage.
        monthly_breakdown: Month-by-month savings detail (12 entries).
    """

    tariff_code: str
    before_solar_monthly_xof: float
    after_solar_monthly_xof: float
    annual_savings_xof: float
    payback_years: float
    roi_25yr_percent: float
    monthly_breakdown: list[dict[str, float]] = field(default_factory=list)


# ── Service ───────────────────────────────────────────────────────────────────


class SenelecService:
    """Senelec tariff calculator and solar savings analyser.

    Implements the 2024 tiered domestic tariff (DPP/PPP), medium-voltage
    flat rates (DMP, PMP), and the Woyofal prepaid rate. Used to estimate
    electricity bill savings when solar offsets part of grid consumption.
    """

    def calculate_bill(
        self, consumption_kwh: float, tariff_code: str = "DPP"
    ) -> TariffBill:
        """Calculate the monthly and annual electricity bill.

        For DPP and PPP: applies a stepped (tiered) tariff across three
        consumption brackets plus a fixed monthly subscription charge.
        For DMP, PMP, and WOYOFAL: applies a flat per-kWh rate with no
        fixed charge.

        Args:
            consumption_kwh: Monthly electricity consumption in kWh.
            tariff_code: Senelec tariff plan code. One of: DPP, PPP, DMP,
                PMP, WOYOFAL.

        Returns:
            A ``TariffBill`` with monthly and annual cost in XOF.

        Raises:
            ValueError: If ``tariff_code`` is not a recognised plan code.
        """
        tariff_upper = tariff_code.upper()
        monthly_cost: float

        if tariff_upper in ("DPP", "PPP"):
            monthly_cost = self._calculate_dpp(consumption_kwh)
        elif tariff_upper == "DMP":
            monthly_cost = consumption_kwh * _DMP_FLAT_XOF
        elif tariff_upper == "PMP":
            monthly_cost = consumption_kwh * _PMP_FLAT_XOF
        elif tariff_upper == "WOYOFAL":
            monthly_cost = consumption_kwh * _WOYOFAL_FLAT_XOF
        else:
            raise ValueError(
                f"Unknown tariff code '{tariff_code}'. "
                f"Supported codes: DPP, PPP, DMP, PMP, WOYOFAL."
            )

        return TariffBill(
            monthly_consumption_kwh=consumption_kwh,
            monthly_cost_xof=monthly_cost,
            annual_cost_xof=monthly_cost * 12.0,
        )

    def analyze_savings(
        self,
        monthly_consumption_kwh: float,
        monthly_production_kwh: list[float],
        tariff_code: str,
        installation_cost_xof: float,
    ) -> SenelecAnalysis:
        """Estimate financial savings, payback, and ROI from a solar installation.

        For each of the 12 months:
        1. Net grid consumption = max(0, monthly_consumption - solar_production)
        2. After-solar bill = bill(net_consumption)
        3. Monthly savings = before_bill - after_bill

        Simple payback = installation_cost / annual_savings.
        ROI over 25 years = (25-year savings - installation_cost) / installation_cost × 100.

        Args:
            monthly_consumption_kwh: Average monthly electricity consumption in kWh.
                Applied uniformly to all 12 months.
            monthly_production_kwh: List of 12 monthly solar production values in kWh.
            tariff_code: Senelec tariff plan code for bill calculations.
            installation_cost_xof: Total installed cost of the solar system in XOF.

        Returns:
            A ``SenelecAnalysis`` with annual savings, payback, ROI, and
            a month-by-month breakdown.

        Raises:
            ValueError: If ``monthly_production_kwh`` does not have exactly 12 items.
            ValueError: If ``tariff_code`` is not recognised.
        """
        if len(monthly_production_kwh) != 12:
            raise ValueError(
                f"monthly_production_kwh must have exactly 12 values, "
                f"got {len(monthly_production_kwh)}."
            )

        before_bill = self.calculate_bill(monthly_consumption_kwh, tariff_code)
        before_monthly_xof = before_bill.monthly_cost_xof

        total_savings_xof: float = 0.0
        monthly_breakdown: list[dict[str, float]] = []

        for month_idx, production in enumerate(monthly_production_kwh):
            # Net consumption after solar offset (cannot go negative)
            net_consumption = max(0.0, monthly_consumption_kwh - production)
            after_bill = self.calculate_bill(net_consumption, tariff_code)
            monthly_savings = before_monthly_xof - after_bill.monthly_cost_xof
            total_savings_xof += monthly_savings

            monthly_breakdown.append(
                {
                    "month": float(month_idx + 1),
                    "production_kwh": production,
                    "net_consumption_kwh": net_consumption,
                    "before_cost_xof": before_monthly_xof,
                    "after_cost_xof": after_bill.monthly_cost_xof,
                    "savings_xof": monthly_savings,
                }
            )

        annual_savings = total_savings_xof

        # Simple payback period (years)
        payback_years = (
            installation_cost_xof / annual_savings
            if annual_savings > 0
            else float("inf")
        )

        # 25-year ROI: (total_lifetime_savings - investment) / investment × 100
        lifetime_savings = annual_savings * _SYSTEM_LIFETIME_YEARS
        roi_25yr = (
            (lifetime_savings - installation_cost_xof) / installation_cost_xof * 100.0
            if installation_cost_xof > 0
            else 0.0
        )

        # Average after-solar monthly cost (for response field)
        avg_after_monthly = sum(
            m["after_cost_xof"] for m in monthly_breakdown
        ) / 12.0

        return SenelecAnalysis(
            tariff_code=tariff_code.upper(),
            before_solar_monthly_xof=before_monthly_xof,
            after_solar_monthly_xof=avg_after_monthly,
            annual_savings_xof=annual_savings,
            payback_years=payback_years,
            roi_25yr_percent=roi_25yr,
            monthly_breakdown=monthly_breakdown,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _calculate_dpp(self, consumption_kwh: float) -> float:
        """Compute the monthly DPP/PPP tiered bill including the fixed charge.

        Tariff tranches:
        - T1: first 150 kWh at  84 FCFA/kWh
        - T2: next  150 kWh at 121 FCFA/kWh (kWh 151–300)
        - T3: remainder     at 158 FCFA/kWh (kWh > 300)
        - Fixed charge: 1 500 FCFA/month

        Args:
            consumption_kwh: Monthly consumption in kWh (must be >= 0).

        Returns:
            Total monthly bill in XOF including the fixed subscription charge.
        """
        cost: float = _DPP_FIXED_XOF  # start with fixed charge

        if consumption_kwh <= 0.0:
            return cost

        # Tranche 1: 0 – 150 kWh
        t1_kwh = min(consumption_kwh, _DPP_T1_LIMIT_KWH)
        cost += t1_kwh * _DPP_T1_XOF

        if consumption_kwh > _DPP_T1_LIMIT_KWH:
            # Tranche 2: 151 – 300 kWh
            t2_kwh = min(
                consumption_kwh - _DPP_T1_LIMIT_KWH,
                _DPP_T2_LIMIT_KWH - _DPP_T1_LIMIT_KWH,
            )
            cost += t2_kwh * _DPP_T2_XOF

        if consumption_kwh > _DPP_T2_LIMIT_KWH:
            # Tranche 3: > 300 kWh
            t3_kwh = consumption_kwh - _DPP_T2_LIMIT_KWH
            cost += t3_kwh * _DPP_T3_XOF

        return cost
