"""Agent Rédaction — generates PVSyst-style narrative using claude-opus-4-6.

Produces a professional French-language technical narrative for the PDF report,
including production analysis, financial analysis, and recommendations.

claude-opus-4-6 is used specifically for this agent because high-quality
fluent French technical prose requires the most capable model.

Fallback: a structured template-based narrative is generated when Claude is
unavailable, ensuring the report pipeline never returns an empty narrative.
"""

from __future__ import annotations

import logging
from typing import Any

import anthropic

from app.agents.state import AgentState
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ── Model constant (exported for test assertions) ─────────────────────────────
REPORT_WRITER_MODEL = "claude-opus-4-6"
_LLM_TIMEOUT = 30.0  # slightly longer for narrative generation

# ── Singleton client ──────────────────────────────────────────────────────────
_anthropic_client: anthropic.AsyncAnthropic | None = None


def _get_anthropic_client() -> anthropic.AsyncAnthropic:
    """Return (lazily instantiated) AsyncAnthropic singleton.

    Returns:
        A configured ``anthropic.AsyncAnthropic`` instance.
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
_REPORT_WRITER_PROMPT = """\
Tu es un ingénieur solaire senior rédigeant un rapport PVSyst professionnel en français.

Données du projet :
{project_summary}

Rédige une analyse narrative complète avec ces sections :
1. **Analyse de la ressource solaire** (2-3 phrases sur l'irradiance du site)
2. **Analyse de la production** (rendement, PR, comparaison avec moyenne régionale)
3. **Analyse économique** (économies SENELEC, retour sur investissement, période de remboursement)
4. **Recommandations techniques** (optimisations possibles, maintenance préventive)
5. **Conclusion** (synthèse en 2-3 phrases)

Ton : professionnel, précis, adapté à un installateur et son client.
Longueur : 400-600 mots.
"""


def _build_project_summary(state: AgentState) -> str:
    """Compile a human-readable project summary string for the prompt.

    Args:
        state: Current AgentState with simulation_result, senelec_analysis,
            project_info, and optionally equipment_recommendation.

    Returns:
        A multiline string summarising the project for the LLM prompt.
    """
    sim = state.get("simulation_result", {})
    senelec = state.get("senelec_analysis", {})
    project = state.get("project_info", {})
    equipment = state.get("equipment_recommendation") or {}

    lines = [
        f"Projet : {project.get('name', 'N/A')}",
        f"Localisation : lat={project.get('latitude', 'N/A')}, lon={project.get('longitude', 'N/A')}",
        f"Puissance crête : {sim.get('peak_kwc', 0):.2f} kWc ({project.get('panel_count', 'N/A')} panneaux)",
        f"Production annuelle : {sim.get('annual_kwh', 0):.0f} kWh",
        f"Rendement spécifique : {sim.get('specific_yield', 0):.0f} kWh/kWp",
        f"Ratio de performance : {sim.get('performance_ratio', 0):.1%}",
        f"Consommation mensuelle : {project.get('monthly_consumption_kwh', 400):.0f} kWh",
        f"Économies annuelles : {senelec.get('annual_savings_xof', 0):,.0f} FCFA",
        f"Retour sur investissement : {senelec.get('payback_years', 0):.1f} ans",
        f"ROI 25 ans : {senelec.get('roi_25yr_percent', 0):.0f}%",
    ]

    if equipment:
        lines += [
            f"Onduleur : {equipment.get('inverter_model', 'N/A')} ({equipment.get('inverter_kva', 0)} kVA)",
            f"Type de système : {equipment.get('system_type', 'N/A')}",
        ]
        if equipment.get("battery_model"):
            lines.append(f"Batterie : {equipment['battery_model']} ({equipment.get('battery_kwh', 0)} kWh)")

    return "\n".join(lines)


def _fallback_narrative(state: AgentState) -> str:
    """Generate a template-based narrative when Claude is unavailable.

    Args:
        state: Current AgentState.

    Returns:
        A minimal but complete French narrative string (> 200 chars).
    """
    sim = state.get("simulation_result", {})
    senelec = state.get("senelec_analysis", {})
    project = state.get("project_info", {})
    peak_kwc = sim.get("peak_kwc", 0.0)
    annual_kwh = sim.get("annual_kwh", 0.0)
    pr = sim.get("performance_ratio", 0.78)
    specific_yield = sim.get("specific_yield", 0.0)
    savings = senelec.get("annual_savings_xof", 0.0)
    payback = senelec.get("payback_years", 0.0)
    roi = senelec.get("roi_25yr_percent", 0.0)
    project_name = project.get("name", "ce projet")

    return (
        f"## Analyse de la ressource solaire\n\n"
        f"Le site de {project_name} bénéficie d'un ensoleillement favorable, "
        f"typique des zones côtières du Sénégal avec une irradiance globale "
        f"horizontale moyenne supérieure à 5,4 kWh/m²/jour.\n\n"
        f"## Analyse de la production\n\n"
        f"Le système de {peak_kwc:.2f} kWc produit {annual_kwh:.0f} kWh/an, "
        f"soit un rendement spécifique de {specific_yield:.0f} kWh/kWp. "
        f"Le ratio de performance de {pr:.0%} est conforme aux standards "
        f"internationaux pour une installation sans ombrage significatif.\n\n"
        f"## Analyse économique\n\n"
        f"Les économies annuelles estimées à {savings:,.0f} FCFA permettent "
        f"un retour sur investissement en {payback:.1f} ans, avec un ROI de "
        f"{roi:.0f}% sur 25 ans.\n\n"
        f"## Recommandations techniques\n\n"
        f"Un nettoyage trimestriel des panneaux est recommandé pour maintenir "
        f"le ratio de performance. La vérification annuelle des connexions DC "
        f"et AC est indispensable pour la sécurité et la durabilité du système.\n\n"
        f"## Conclusion\n\n"
        f"Ce projet solaire présente une rentabilité avérée pour le marché sénégalais. "
        f"Il contribuera significativement à la réduction de la dépendance au réseau "
        f"SENELEC et à la maîtrise des coûts énergétiques sur le long terme."
    )


# ── Main agent function ───────────────────────────────────────────────────────


async def run_report_writer_agent(state: AgentState) -> AgentState:
    """Generate narrative report text using claude-opus-4-6 with streaming.

    Assembles the project summary, calls Claude with a streaming message,
    concatenates all text delta tokens into a full narrative, and stores the
    result in ``state['report_narrative']``.

    Falls back to a structured template narrative on any Claude error.

    Args:
        state: Current AgentState with simulation_result, senelec_analysis,
            project_info, and optionally equipment_recommendation.

    Returns:
        Updated AgentState with ``report_narrative`` populated and
        ``"report_writer"`` appended to ``completed_agents``.
    """
    project_summary = _build_project_summary(state)
    prompt = _REPORT_WRITER_PROMPT.format(project_summary=project_summary)

    narrative: str | None = None

    try:
        client = _get_anthropic_client()
        tokens: list[str] = []

        async with client.messages.stream(
            model=REPORT_WRITER_MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for chunk in stream:
                if (
                    hasattr(chunk, "type")
                    and chunk.type == "content_block_delta"
                    and hasattr(chunk, "delta")
                    and hasattr(chunk.delta, "type")
                    and chunk.delta.type == "text_delta"
                ):
                    tokens.append(chunk.delta.text)

        narrative = "".join(tokens).strip()
        if not narrative:
            raise ValueError("Claude returned an empty narrative")

    except (anthropic.APIError, anthropic.APIConnectionError, anthropic.RateLimitError) as exc:
        logger.warning(
            "ReportWriterAgent: Anthropic API error — using template fallback. error=%s",
            exc,
        )
        errors: list[str] = list(state.get("errors", []))
        errors.append(f"report_writer_agent: {type(exc).__name__}: {exc}")
        state = dict(state)  # type: ignore[assignment]
        state["errors"] = errors

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "ReportWriterAgent: unexpected error — using template fallback. error=%s",
            exc,
        )
        errors = list(state.get("errors", []))
        errors.append(f"report_writer_agent_unexpected: {exc}")
        state = dict(state)  # type: ignore[assignment]
        state["errors"] = errors

    if narrative is None:
        narrative = _fallback_narrative(state)

    completed = list(state.get("completed_agents", []))
    completed.append("report_writer")

    return {
        **state,  # type: ignore[misc]
        "report_narrative": narrative,
        "completed_agents": completed,
    }
