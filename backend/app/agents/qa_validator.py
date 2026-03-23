"""Agent QA — validates 8 technical criteria for the PV project.

This agent is pure Python with no LLM call, ensuring deterministic, fast
validation that does not depend on external API availability.

Criteria:
  V1: Peak power coherence — panel_count × panel_power_wc == peak_kwc ± 5%
  V2: Annual yield plausibility — 1200 ≤ specific_yield ≤ 2000 kWh/kWp (Senegal)
  V3: Performance ratio — 0.65 ≤ PR ≤ 0.90
  V4: Inverter sizing ratio — 0.80 ≤ peak_kwc / inverter_kva ≤ 1.20
  V5: Power factor — cosφ ≥ 0.80 if provided, else NA
  V6: Economic coherence — payback 5–20 years for Senegal market
  V7: Battery sizing — if hybrid: battery_kwh ≥ 0.30 × daily_kwh, else NA
  V8: Production vs consumption coverage — 0.30 ≤ coverage_ratio ≤ 1.50
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any

from app.agents.state import AgentState

logger = logging.getLogger(__name__)

# ── Threshold constants ───────────────────────────────────────────────────────

_V1_TOLERANCE = 0.05          # ±5% peak power coherence
_V2_YIELD_MIN = 1200.0        # kWh/kWp minimum for Senegal
_V2_YIELD_MAX = 2000.0        # kWh/kWp maximum for Senegal
_V3_PR_MIN = 0.65             # minimum acceptable performance ratio
_V3_PR_MAX = 0.90             # maximum plausible performance ratio
_V4_RATIO_MIN = 0.80          # minimum inverter sizing ratio (DC/AC)
_V4_RATIO_MAX = 1.20          # maximum inverter sizing ratio (DC/AC)
_V5_PF_MIN = 0.80             # minimum power factor (cosφ)
_V6_PAYBACK_MIN = 5.0         # years — shortest credible payback for Senegal
_V6_PAYBACK_MAX = 20.0        # years — longest acceptable payback
_V7_BATTERY_RATIO_MIN = 0.30  # minimum battery kWh / daily_kwh ratio
_V8_COVERAGE_MIN = 0.30       # minimum production/consumption coverage
_V8_COVERAGE_MAX = 1.50       # maximum plausible coverage ratio


@dataclass
class QACriterion:
    """Result of a single QA validation criterion.

    Attributes:
        code: Criterion identifier (V1 through V8).
        label: Human-readable criterion name.
        status: "PASS", "FAIL", or "NA" (not applicable).
        value: Computed value being checked (float, str, or None).
        threshold: Human-readable threshold description.
        comment: Brief explanation of the result.
    """

    code: str
    label: str
    status: str
    value: float | str | None
    threshold: str
    comment: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict representation.

        Returns:
            Dict with all dataclass fields; ``value`` converted to str or None.
        """
        d = asdict(self)
        # Ensure value is serialisable
        if isinstance(d["value"], float):
            d["value"] = round(d["value"], 4)
        return d


# ── Criterion evaluators ──────────────────────────────────────────────────────


def _check_v1(
    sim: dict[str, Any],
    project: dict[str, Any],
) -> QACriterion:
    """V1: Peak power coherence check."""
    peak_kwc: float = sim.get("peak_kwc", 0.0)
    params = sim.get("params_used", {})
    panel_count: int = project.get("panel_count") or params.get("panel_count", 0)
    panel_power_wc: int = project.get("panel_power_wc") or params.get("panel_power_wc", 0)

    if panel_count <= 0 or panel_power_wc <= 0:
        return QACriterion(
            code="V1",
            label="Cohérence puissance crête",
            status="NA",
            value=None,
            threshold=f"±{_V1_TOLERANCE:.0%}",
            comment="Données panneau insuffisantes pour calculer la puissance théorique.",
        )

    theoretical_kwc = (panel_count * panel_power_wc) / 1000.0
    if theoretical_kwc == 0:
        return QACriterion(
            code="V1", label="Cohérence puissance crête", status="NA",
            value=None, threshold=f"±{_V1_TOLERANCE:.0%}",
            comment="Puissance théorique nulle.",
        )

    deviation = abs(peak_kwc - theoretical_kwc) / theoretical_kwc
    status = "PASS" if deviation <= _V1_TOLERANCE else "FAIL"
    return QACriterion(
        code="V1",
        label="Cohérence puissance crête",
        status=status,
        value=round(peak_kwc, 3),
        threshold=f"théorique {theoretical_kwc:.3f} kWc ± {_V1_TOLERANCE:.0%}",
        comment=(
            f"Puissance simulée {peak_kwc:.3f} kWc vs théorique {theoretical_kwc:.3f} kWc "
            f"(écart {deviation:.1%})."
        ),
    )


def _check_v2(sim: dict[str, Any]) -> QACriterion:
    """V2: Annual yield plausibility for Senegal climate."""
    specific_yield: float = sim.get("specific_yield", 0.0)
    if specific_yield <= 0:
        return QACriterion(
            code="V2", label="Plausibilité du rendement annuel", status="NA",
            value=None, threshold=f"{_V2_YIELD_MIN}–{_V2_YIELD_MAX} kWh/kWp",
            comment="Rendement spécifique non disponible.",
        )
    status = "PASS" if _V2_YIELD_MIN <= specific_yield <= _V2_YIELD_MAX else "FAIL"
    return QACriterion(
        code="V2",
        label="Plausibilité du rendement annuel",
        status=status,
        value=round(specific_yield, 1),
        threshold=f"{_V2_YIELD_MIN}–{_V2_YIELD_MAX} kWh/kWp",
        comment=(
            f"Rendement spécifique: {specific_yield:.0f} kWh/kWp — "
            f"{'dans' if status == 'PASS' else 'hors de'} la plage Sénégal."
        ),
    )


def _check_v3(sim: dict[str, Any]) -> QACriterion:
    """V3: Performance ratio validation."""
    pr: float = sim.get("performance_ratio", 0.0)
    if pr <= 0:
        return QACriterion(
            code="V3", label="Ratio de performance (PR)", status="NA",
            value=None, threshold=f"{_V3_PR_MIN:.0%}–{_V3_PR_MAX:.0%}",
            comment="PR non disponible.",
        )
    status = "PASS" if _V3_PR_MIN <= pr <= _V3_PR_MAX else "FAIL"
    return QACriterion(
        code="V3",
        label="Ratio de performance (PR)",
        status=status,
        value=round(pr, 4),
        threshold=f"{_V3_PR_MIN:.0%}–{_V3_PR_MAX:.0%}",
        comment=f"PR = {pr:.1%} — {'acceptable' if status == 'PASS' else 'hors plage acceptable'}.",
    )


def _check_v4(
    sim: dict[str, Any],
    equipment: dict[str, Any] | None,
) -> QACriterion:
    """V4: Inverter sizing ratio (DC/AC ratio)."""
    if not equipment:
        return QACriterion(
            code="V4", label="Ratio de dimensionnement onduleur", status="NA",
            value=None, threshold=f"{_V4_RATIO_MIN}–{_V4_RATIO_MAX}",
            comment="Recommandation équipement non disponible.",
        )
    peak_kwc: float = sim.get("peak_kwc", 0.0)
    inverter_kva: float = equipment.get("inverter_kva", 0.0)
    if inverter_kva <= 0:
        return QACriterion(
            code="V4", label="Ratio de dimensionnement onduleur", status="NA",
            value=None, threshold=f"{_V4_RATIO_MIN}–{_V4_RATIO_MAX}",
            comment="Puissance onduleur nulle.",
        )
    ratio = peak_kwc / inverter_kva
    status = "PASS" if _V4_RATIO_MIN <= ratio <= _V4_RATIO_MAX else "FAIL"
    return QACriterion(
        code="V4",
        label="Ratio de dimensionnement onduleur",
        status=status,
        value=round(ratio, 3),
        threshold=f"{_V4_RATIO_MIN}–{_V4_RATIO_MAX}",
        comment=(
            f"{peak_kwc:.2f} kWc / {inverter_kva} kVA = {ratio:.2f} — "
            f"{'correct' if status == 'PASS' else 'sous/surdimensionné'}."
        ),
    )


def _check_v5(project: dict[str, Any]) -> QACriterion:
    """V5: Power factor check (NA if not provided)."""
    power_factor = project.get("power_factor")
    if power_factor is None:
        return QACriterion(
            code="V5", label="Facteur de puissance (cosφ)", status="NA",
            value=None, threshold=f"≥ {_V5_PF_MIN}",
            comment="Facteur de puissance non renseigné — critère non applicable.",
        )
    pf = float(power_factor)
    status = "PASS" if pf >= _V5_PF_MIN else "FAIL"
    return QACriterion(
        code="V5",
        label="Facteur de puissance (cosφ)",
        status=status,
        value=round(pf, 3),
        threshold=f"≥ {_V5_PF_MIN}",
        comment=(
            f"cosφ = {pf:.2f} — "
            f"{'conforme' if status == 'PASS' else 'non conforme (trop faible)'}."
        ),
    )


def _check_v6(senelec: dict[str, Any]) -> QACriterion:
    """V6: Economic coherence — payback period."""
    payback: float = senelec.get("payback_years", 0.0)
    if payback <= 0 or payback == float("inf"):
        return QACriterion(
            code="V6", label="Cohérence économique (retour sur investissement)", status="NA",
            value=None, threshold=f"{_V6_PAYBACK_MIN}–{_V6_PAYBACK_MAX} ans",
            comment="Période de retour non calculable (économies nulles ou installation gratuite).",
        )
    status = "PASS" if _V6_PAYBACK_MIN <= payback <= _V6_PAYBACK_MAX else "FAIL"
    return QACriterion(
        code="V6",
        label="Cohérence économique (retour sur investissement)",
        status=status,
        value=round(payback, 2),
        threshold=f"{_V6_PAYBACK_MIN}–{_V6_PAYBACK_MAX} ans",
        comment=(
            f"Retour sur investissement: {payback:.1f} ans — "
            f"{'économiquement viable' if status == 'PASS' else 'hors plage marché sénégalais'}."
        ),
    )


def _check_v7(
    sim: dict[str, Any],
    equipment: dict[str, Any] | None,
) -> QACriterion:
    """V7: Battery sizing for hybrid systems."""
    if not equipment:
        return QACriterion(
            code="V7", label="Dimensionnement batterie", status="NA",
            value=None, threshold=f"≥ {_V7_BATTERY_RATIO_MIN} × consommation journalière",
            comment="Recommandation équipement non disponible.",
        )
    system_type: str = equipment.get("system_type", "on-grid")
    if system_type != "hybrid":
        return QACriterion(
            code="V7", label="Dimensionnement batterie", status="NA",
            value=None, threshold=f"≥ {_V7_BATTERY_RATIO_MIN} × consommation journalière",
            comment=f"Système {system_type} — batterie non requise.",
        )
    battery_kwh: float | None = equipment.get("battery_kwh")
    if battery_kwh is None:
        return QACriterion(
            code="V7", label="Dimensionnement batterie", status="FAIL",
            value=None, threshold=f"≥ {_V7_BATTERY_RATIO_MIN} × consommation journalière",
            comment="Système hybride mais aucune batterie spécifiée.",
        )
    annual_kwh: float = sim.get("annual_kwh", 0.0)
    daily_kwh = annual_kwh / 365.0
    min_battery_kwh = _V7_BATTERY_RATIO_MIN * daily_kwh
    status = "PASS" if battery_kwh >= min_battery_kwh else "FAIL"
    return QACriterion(
        code="V7",
        label="Dimensionnement batterie",
        status=status,
        value=round(battery_kwh, 2),
        threshold=f"≥ {min_battery_kwh:.2f} kWh ({_V7_BATTERY_RATIO_MIN:.0%} × {daily_kwh:.1f} kWh/j)",
        comment=(
            f"Batterie {battery_kwh:.1f} kWh vs minimum requis {min_battery_kwh:.1f} kWh — "
            f"{'suffisant' if status == 'PASS' else 'insuffisant pour autonomie nocturne'}."
        ),
    )


def _check_v8(
    sim: dict[str, Any],
    project: dict[str, Any],
) -> QACriterion:
    """V8: Production vs consumption coverage ratio."""
    annual_kwh: float = sim.get("annual_kwh", 0.0)
    monthly_consumption: float = project.get("monthly_consumption_kwh", 0.0)
    if monthly_consumption <= 0 or annual_kwh <= 0:
        return QACriterion(
            code="V8", label="Couverture production/consommation", status="NA",
            value=None, threshold=f"{_V8_COVERAGE_MIN}–{_V8_COVERAGE_MAX}",
            comment="Données de consommation ou de production manquantes.",
        )
    annual_consumption = monthly_consumption * 12.0
    coverage_ratio = annual_kwh / annual_consumption
    status = "PASS" if _V8_COVERAGE_MIN <= coverage_ratio <= _V8_COVERAGE_MAX else "FAIL"
    return QACriterion(
        code="V8",
        label="Couverture production/consommation",
        status=status,
        value=round(coverage_ratio, 3),
        threshold=f"{_V8_COVERAGE_MIN}–{_V8_COVERAGE_MAX}",
        comment=(
            f"{annual_kwh:.0f} kWh/an ÷ {annual_consumption:.0f} kWh/an = "
            f"{coverage_ratio:.0%} couverture — "
            f"{'acceptable' if status == 'PASS' else 'sous/surdimensionné'}."
        ),
    )


# ── Main agent function ───────────────────────────────────────────────────────


async def run_qa_validator(state: AgentState) -> AgentState:
    """Validate all 8 QA criteria using pure deterministic Python logic.

    No LLM call is made. All criteria are evaluated synchronously against
    the simulation result, senelec analysis, project info, and equipment
    recommendation present in ``state``.

    Args:
        state: Current AgentState; must have ``simulation_result``,
            ``senelec_analysis``, and ``project_info`` populated.
            ``equipment_recommendation`` is optional but enables V4/V7.

    Returns:
        Updated AgentState with ``qa_results`` set to a dict containing:
        - ``criteria``: list of 8 QACriterion dicts
        - ``overall``: "PASS" if no criterion FAILs, else "FAIL"
        - ``score``: count of PASS criteria
    """
    sim: dict[str, Any] = state.get("simulation_result", {})
    senelec: dict[str, Any] = state.get("senelec_analysis", {})
    project: dict[str, Any] = state.get("project_info", {})
    equipment: dict[str, Any] | None = state.get("equipment_recommendation")

    criteria: list[QACriterion] = [
        _check_v1(sim, project),
        _check_v2(sim),
        _check_v3(sim),
        _check_v4(sim, equipment),
        _check_v5(project),
        _check_v6(senelec),
        _check_v7(sim, equipment),
        _check_v8(sim, project),
    ]

    score = sum(1 for c in criteria if c.status == "PASS")
    has_failure = any(c.status == "FAIL" for c in criteria)
    overall = "FAIL" if has_failure else "PASS"

    logger.info(
        "QAValidator: overall=%s score=%d/8 failures=%d",
        overall,
        score,
        sum(1 for c in criteria if c.status == "FAIL"),
    )

    qa_results: dict[str, Any] = {
        "criteria": [c.to_dict() for c in criteria],
        "overall": overall,
        "score": score,
    }

    completed = list(state.get("completed_agents", []))
    completed.append("qa_validator")

    return {
        **state,  # type: ignore[misc]
        "qa_results": qa_results,
        "completed_agents": completed,
    }
