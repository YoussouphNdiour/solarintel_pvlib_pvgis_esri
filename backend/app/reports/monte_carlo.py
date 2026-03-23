"""Monte Carlo simulation for PV production uncertainty analysis.

Runs N=1000 scenarios sampling from uncertainty distributions for:
- Irradiance variability (σ=8% inter-annual)
- Temperature coefficient uncertainty (σ=1%)
- Soiling losses (σ=3%)
- Grid availability (σ=2%)
- Module degradation (0.5%/year)

Returns P10/P50/P90 confidence intervals per month and annually.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class MonteCarloResult:
    """Monte Carlo simulation result with percentile confidence intervals.

    Attributes:
        n_samples: Number of simulated scenarios run.
        annual_p10: 10th percentile annual production (kWh).
        annual_p50: 50th percentile / median annual production (kWh).
        annual_p90: 90th percentile annual production (kWh).
        monthly_p10: 12-element list of monthly P10 values (kWh).
        monthly_p50: 12-element list of monthly P50 values (kWh).
        monthly_p90: 12-element list of monthly P90 values (kWh).
        confidence_band_pct: Width of the P10-P90 band as % of P50.
    """

    n_samples: int
    annual_p10: float
    annual_p50: float
    annual_p90: float
    monthly_p10: list[float]
    monthly_p50: list[float]
    monthly_p90: list[float]
    confidence_band_pct: float


@dataclass
class SensitivityResult:
    """Single electricity price scenario in the sensitivity analysis.

    Attributes:
        price_change_pct: Price change in percent (e.g. -30, +10, +30).
        annual_savings_xof: Annual bill savings in XOF under this scenario.
        payback_years: Simple payback period in years.
        roi_25yr_pct: 25-year return on investment as a percentage.
    """

    price_change_pct: float
    annual_savings_xof: float
    payback_years: float
    roi_25yr_pct: float


_SYSTEM_LIFETIME_YEARS: int = 25

# Uncertainty standard deviations (as fractions of 1.0)
_SIGMA_IRRADIANCE: float = 0.08   # 8% inter-annual irradiance variability
_SIGMA_TEMP: float = 0.01         # 1% temperature coefficient uncertainty
_SIGMA_SOILING: float = 0.03      # 3% soiling losses
_SIGMA_GRID: float = 0.02         # 2% grid availability


def run_monte_carlo(
    base_annual_kwh: float,
    monthly_kwh: list[float],
    n_samples: int = 1000,
    seed: int | None = 42,
) -> MonteCarloResult:
    """Run Monte Carlo simulation on PV production estimates.

    Draws ``n_samples`` realisations by sampling multiplicative uncertainty
    factors from normal distributions and applying them to the base monthly
    production figures.  The four independent factors (irradiance variability,
    temperature coefficient, soiling, grid availability) are combined as a
    product so that their joint effect is multiplicative on each monthly value.

    Args:
        base_annual_kwh: Base annual energy production estimate in kWh.
        monthly_kwh: 12-element list of monthly production estimates in kWh.
        n_samples: Number of Monte Carlo scenarios to simulate.
        seed: NumPy random seed for reproducibility (None = no seed).

    Returns:
        A ``MonteCarloResult`` with P10/P50/P90 percentiles.
    """
    if len(monthly_kwh) != 12:
        raise ValueError(
            f"monthly_kwh must have exactly 12 values, got {len(monthly_kwh)}"
        )

    rng = np.random.default_rng(seed)

    # Sample each uncertainty factor: shape (n_samples,)
    irradiance = rng.normal(loc=1.0, scale=_SIGMA_IRRADIANCE, size=n_samples)
    temperature = rng.normal(loc=1.0, scale=_SIGMA_TEMP, size=n_samples)
    soiling = rng.normal(loc=1.0, scale=_SIGMA_SOILING, size=n_samples)
    grid_avail = rng.normal(loc=1.0, scale=_SIGMA_GRID, size=n_samples)

    # Combined multiplicative factor: shape (n_samples,)
    combined = irradiance * temperature * soiling * grid_avail
    # Clip to prevent physically nonsensical negative or zero production
    combined = np.clip(combined, 0.3, 1.7)

    # Monthly production matrix: shape (n_samples, 12)
    monthly_arr = np.array(monthly_kwh, dtype=float)  # (12,)
    # Apply per-sample combined factor; each sample scales all 12 months equally
    simulated_monthly = combined[:, np.newaxis] * monthly_arr[np.newaxis, :]

    # Annual production per sample: shape (n_samples,)
    simulated_annual = simulated_monthly.sum(axis=1)

    # Annual percentiles
    annual_p10 = float(np.percentile(simulated_annual, 10))
    annual_p50 = float(np.percentile(simulated_annual, 50))
    annual_p90 = float(np.percentile(simulated_annual, 90))

    # Monthly percentiles: shape (12,) each
    monthly_p10 = [float(np.percentile(simulated_monthly[:, i], 10)) for i in range(12)]
    monthly_p50 = [float(np.percentile(simulated_monthly[:, i], 50)) for i in range(12)]
    monthly_p90 = [float(np.percentile(simulated_monthly[:, i], 90)) for i in range(12)]

    confidence_band_pct = (
        (annual_p90 - annual_p10) / annual_p50 * 100.0
        if annual_p50 > 0
        else 0.0
    )

    return MonteCarloResult(
        n_samples=n_samples,
        annual_p10=annual_p10,
        annual_p50=annual_p50,
        annual_p90=annual_p90,
        monthly_p10=monthly_p10,
        monthly_p50=monthly_p50,
        monthly_p90=monthly_p90,
        confidence_band_pct=confidence_band_pct,
    )


def run_sensitivity_analysis(
    base_annual_savings_xof: float,
    installation_cost_xof: float,
    price_changes: list[float] | None = None,
) -> list[SensitivityResult]:
    """Analyse how electricity price changes affect ROI and payback period.

    For each price change percentage, scales the base annual savings linearly
    and recomputes payback and 25-year ROI.

    Args:
        base_annual_savings_xof: Annual bill savings at current electricity price.
        installation_cost_xof: Total installed system cost in XOF.
        price_changes: List of price change percentages to evaluate.
            Defaults to [-30, -20, -10, +10, +20, +30].

    Returns:
        List of ``SensitivityResult`` instances, one per price scenario,
        sorted by price_change_pct ascending.
    """
    if price_changes is None:
        price_changes = [-30.0, -20.0, -10.0, 10.0, 20.0, 30.0]

    results: list[SensitivityResult] = []

    for change_pct in price_changes:
        factor = 1.0 + change_pct / 100.0
        annual_savings = base_annual_savings_xof * factor

        payback_years = (
            installation_cost_xof / annual_savings
            if annual_savings > 0
            else float("inf")
        )

        lifetime_savings = annual_savings * _SYSTEM_LIFETIME_YEARS
        roi_25yr_pct = (
            (lifetime_savings - installation_cost_xof) / installation_cost_xof * 100.0
            if installation_cost_xof > 0
            else 0.0
        )

        results.append(
            SensitivityResult(
                price_change_pct=float(change_pct),
                annual_savings_xof=float(annual_savings),
                payback_years=float(payback_years),
                roi_25yr_pct=float(roi_25yr_pct),
            )
        )

    return sorted(results, key=lambda r: r.price_change_pct)
