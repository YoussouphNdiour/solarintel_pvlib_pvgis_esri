"""LangGraph shared state for the SolarIntel multi-agent orchestrator.

AgentState is threaded through every node in the StateGraph. Fields are
progressively populated as agents complete their work. All fields default
to None / empty so the state can be safely constructed from simulation data
alone before agents run.
"""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """Shared state dict threaded through all LangGraph nodes.

    Attributes:
        simulation_id: UUID string of the source Simulation record.
        simulation_result: Dict representation of a SimulationResult dataclass.
        senelec_analysis: Dict representation of a SenelecAnalysis dataclass.
        project_info: Project metadata (lat, lon, name, panel_count, …).
        equipment_recommendation: Output of DimensioningAgent; keyed by
            inverter_model, inverter_kva, battery_model, panel_recommendation, etc.
        report_narrative: Full French narrative text produced by ReportWriterAgent.
        qa_results: Dict with keys ``criteria`` (list of QACriterion dicts),
            ``overall`` ("PASS" | "FAIL"), and ``score`` (int).
        errors: List of error messages accumulated during the run; agents
            append to this instead of raising so parallel siblings still complete.
        completed_agents: Names of agents that finished successfully.
        total_duration_ms: Wall-clock time from orchestrate() start to end.
    """

    # ── Input ────────────────────────────────────────────────────────────────
    simulation_id: str
    simulation_result: dict[str, Any]
    senelec_analysis: dict[str, Any]
    project_info: dict[str, Any]

    # ── Agent outputs ────────────────────────────────────────────────────────
    equipment_recommendation: dict[str, Any] | None
    report_narrative: str | None
    qa_results: dict[str, Any] | None

    # ── Orchestrator metadata ────────────────────────────────────────────────
    errors: list[str]
    completed_agents: list[str]
    total_duration_ms: float | None
