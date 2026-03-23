"""Agent Dimensionnement — recommends optimal inverter, battery, and panel config.

Uses claude-sonnet-4-6 with structured output to size the complete PV system
based on simulation results and project parameters.

Fallback strategy: if Claude is unavailable (APIError, timeout, JSON parse
failure), a rule-based sizing algorithm returns a deterministic recommendation
without any LLM call.
"""

from __future__ import annotations

import json
import logging
import math
from typing import Any

import anthropic

from app.agents.state import AgentState
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ── Model constant ────────────────────────────────────────────────────────────
DIMENSIONING_MODEL = "claude-sonnet-4-6"
_LLM_TIMEOUT = 25.0  # seconds

# ── Singleton client ──────────────────────────────────────────────────────────
_anthropic_client: anthropic.AsyncAnthropic | None = None


def _get_anthropic_client() -> anthropic.AsyncAnthropic:
    """Return (lazily instantiated) AsyncAnthropic singleton.

    Returns:
        A configured ``anthropic.AsyncAnthropic`` instance using the API key
        from application settings. The instance is created once per process.
    """
    global _anthropic_client  # noqa: PLW0603
    if _anthropic_client is None:
        settings = get_settings()
        _anthropic_client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=_LLM_TIMEOUT,
        )
    return _anthropic_client


# ── Prompt ────────────────────────────────────────────────────────────────────
_DIMENSIONING_PROMPT = """\
Tu es un expert en dimensionnement de systèmes photovoltaïques pour le marché sénégalais.

Données de simulation :
- Puissance crête : {peak_kwc} kWc
- Production annuelle : {annual_kwh} kWh
- Ratio de performance : {pr:.1%}
- Nombre de panneaux : {panel_count}
- Consommation mensuelle : {monthly_consumption} kWh

Recommande le système complet en JSON strict :
{{
  "inverter_model": "marque modèle puissance",
  "inverter_kva": float,
  "inverter_brand": "GOODWE|GROWATT|DEYE|SMA",
  "battery_model": "marque modèle capacité ou null si ongrid",
  "battery_kwh": float ou null,
  "battery_brand": "PYLONTECH|BYD|null",
  "system_type": "on-grid|hybrid|off-grid",
  "wiring_config": "string de câblage recommandé",
  "protection_devices": ["liste des protections requises"],
  "panel_recommendation": "description du panneau recommandé",
  "reasoning": "explication technique en 2-3 phrases"
}}

Règles de dimensionnement :
- Onduleur : 0.8 ≤ peak_kwc/inverter_kva ≤ 1.2
- Batterie : autonomie 1 nuit si hybride (≥ 0.3 × daily_kwh)
- GOODWE/GROWATT pour < 20 kWc, SMA/ABB pour > 20 kWc
- Réponds UNIQUEMENT avec le JSON, sans markdown.
"""


# ── Rule-based fallback ───────────────────────────────────────────────────────


def _rule_based_sizing(simulation_result: dict[str, Any]) -> dict[str, Any]:
    """Compute a deterministic equipment recommendation without LLM.

    Applies industry sizing rules for the Senegalese market:
    - Inverter kVA = ceil(peak_kwc / 1.0) rounded to nearest standard size
    - Brand selection by power class (GOODWE < 20 kWc, SMA ≥ 20 kWc)
    - Hybrid battery sized at 30% of daily consumption for 1-night autonomy

    Args:
        simulation_result: Dict with keys ``peak_kwc``, ``annual_kwh``,
            ``performance_ratio``, ``params_used``.

    Returns:
        Equipment recommendation dict matching the schema expected by
        ``EquipmentRecommendation``.
    """
    peak_kwc: float = simulation_result.get("peak_kwc", 1.0)
    annual_kwh: float = simulation_result.get("annual_kwh", 0.0)
    daily_kwh = annual_kwh / 365.0

    # Standard inverter kVA sizes (kW ratings commonly stocked in Dakar)
    standard_sizes = [1.5, 2.0, 3.0, 3.6, 5.0, 6.0, 8.0, 10.0, 15.0, 20.0, 30.0, 50.0]

    # Target: inverter_kva ≈ peak_kwc (0.8–1.2 ratio)
    target_kva = peak_kwc
    inverter_kva = min(
        (s for s in standard_sizes if s >= target_kva * 0.8),
        default=standard_sizes[-1],
    )

    # Brand selection
    brand = "GOODWE" if peak_kwc < 20.0 else "SMA"
    inverter_model = f"{brand} GW{int(inverter_kva * 1000)}-ES {inverter_kva}kW"

    # Battery: hybrid if daily production > 5 kWh, else on-grid
    battery_model = None
    battery_kwh = None
    battery_brand = None
    system_type = "on-grid"

    if daily_kwh > 5.0:
        system_type = "hybrid"
        battery_kwh = round(max(3.5, daily_kwh * 0.3), 1)
        battery_brand = "PYLONTECH"
        capacity_label = f"{battery_kwh}kWh"
        battery_model = f"PYLONTECH US3000C {capacity_label}"

    panel_count = simulation_result.get("params_used", {}).get("panel_count", 0)
    panel_power = simulation_result.get("params_used", {}).get("panel_power_wc", 545)
    strings = max(1, math.ceil(panel_count / 10))

    return {
        "inverter_model": inverter_model,
        "inverter_kva": float(inverter_kva),
        "inverter_brand": brand,
        "battery_model": battery_model,
        "battery_kwh": battery_kwh,
        "battery_brand": battery_brand,
        "system_type": system_type,
        "wiring_config": (
            f"String {panel_count // strings}×{panel_power}W, "
            f"{strings} string{'s' if strings > 1 else ''}"
        ),
        "protection_devices": [
            "Disjoncteur DC 32A",
            "Parafoudre AC/DC",
            "Sectionneur AC 63A",
        ],
        "panel_recommendation": f"JA Solar JAM72S30 {panel_power}W (série actuelle)",
        "reasoning": (
            f"Dimensionnement règle-de-base: onduleur {inverter_kva} kVA pour "
            f"{peak_kwc:.2f} kWc (ratio {peak_kwc / inverter_kva:.2f}). "
            f"Système {system_type} adapté au profil de consommation."
        ),
    }


# ── Main agent function ───────────────────────────────────────────────────────


async def run_dimensioning_agent(state: AgentState) -> AgentState:
    """Recommend inverter, battery, and wiring configuration via Claude.

    Builds the dimensioning prompt from the simulation result and project info,
    calls ``claude-sonnet-4-6`` with a structured JSON prompt, parses the
    response, and injects the recommendation into ``state``.

    Falls back to ``_rule_based_sizing`` when Claude is unreachable or returns
    malformed JSON.

    Args:
        state: Current AgentState with populated ``simulation_result`` and
            ``project_info`` fields.

    Returns:
        Updated AgentState with ``equipment_recommendation`` populated and
        ``"dimensioning"`` appended to ``completed_agents``.
    """
    sim_result = state["simulation_result"]
    project_info = state.get("project_info", {})

    monthly_consumption = project_info.get("monthly_consumption_kwh", 400.0)

    prompt = _DIMENSIONING_PROMPT.format(
        peak_kwc=sim_result.get("peak_kwc", 0.0),
        annual_kwh=sim_result.get("annual_kwh", 0.0),
        pr=sim_result.get("performance_ratio", 0.78),
        panel_count=project_info.get("panel_count", sim_result.get("params_used", {}).get("panel_count", 0)),
        monthly_consumption=monthly_consumption,
    )

    recommendation: dict[str, Any] | None = None

    try:
        client = _get_anthropic_client()
        message = await client.messages.create(
            model=DIMENSIONING_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text: str = message.content[0].text.strip()

        # Strip accidental markdown fences
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        raw_text = raw_text.strip()

        parsed = json.loads(raw_text)

        # Validate required keys
        required = {"inverter_model", "inverter_kva", "inverter_brand", "system_type"}
        if not required.issubset(parsed.keys()):
            raise ValueError(f"Missing required keys in LLM response: {required - parsed.keys()}")

        # Ensure panel_recommendation is present (may be absent from older prompts)
        if "panel_recommendation" not in parsed:
            panel_power = project_info.get("panel_power_wc", 545)
            parsed["panel_recommendation"] = f"JA Solar JAM72S30 {panel_power}W"

        recommendation = parsed

    except (anthropic.APIError, anthropic.APIConnectionError, anthropic.RateLimitError) as exc:
        logger.warning(
            "DimensioningAgent: Anthropic API error — using rule-based fallback. error=%s",
            exc,
        )
        errors: list[str] = list(state.get("errors", []))
        errors.append(f"dimensioning_agent: {type(exc).__name__}: {exc}")
        state = dict(state)  # type: ignore[assignment]
        state["errors"] = errors

    except (json.JSONDecodeError, ValueError, KeyError) as exc:
        logger.warning(
            "DimensioningAgent: JSON parse/validation error — using fallback. error=%s",
            exc,
        )
        errors = list(state.get("errors", []))
        errors.append(f"dimensioning_agent_parse: {exc}")
        state = dict(state)  # type: ignore[assignment]
        state["errors"] = errors

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "DimensioningAgent: unexpected error — using fallback. error=%s",
            exc,
        )
        errors = list(state.get("errors", []))
        errors.append(f"dimensioning_agent_unexpected: {exc}")
        state = dict(state)  # type: ignore[assignment]
        state["errors"] = errors

    # Apply fallback if LLM path failed
    if recommendation is None:
        recommendation = _rule_based_sizing(sim_result)

    completed = list(state.get("completed_agents", []))
    completed.append("dimensioning")

    return {
        **state,  # type: ignore[misc]
        "equipment_recommendation": recommendation,
        "completed_agents": completed,
    }
