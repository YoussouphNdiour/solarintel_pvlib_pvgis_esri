"""LangGraph StateGraph orchestrating all SolarIntel agents in parallel.

Flow:
  START → parallel_agents (dimensioning + report_writer + qa_validator) → END

All three agents run concurrently via asyncio.gather(). Individual agent
failures are caught, recorded in state['errors'], and do not block sibling
agents from completing. Total timeout: 25 seconds.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.dimensioning import run_dimensioning_agent
from app.agents.qa_validator import run_qa_validator
from app.agents.report_writer import run_report_writer_agent
from app.agents.state import AgentState

logger = logging.getLogger(__name__)

_ORCHESTRATOR_TIMEOUT = 25.0  # seconds — hard deadline for all agents


# ── Parallel node ─────────────────────────────────────────────────────────────


async def run_parallel_agents(state: AgentState) -> AgentState:
    """Run dimensioning, report writer, and QA validator concurrently.

    Calls all three agents via ``asyncio.gather(return_exceptions=True)`` so
    that a failure in one agent does not cancel the others. Exceptions are
    caught and appended to ``state['errors']``.

    Agent functions are imported from the module namespace at call time (not
    at compile time) so that unit test patches applied to
    ``app.agents.orchestrator.run_dimensioning_agent`` etc. take effect
    correctly even after the LangGraph is compiled.

    Args:
        state: Current AgentState with simulation_result, senelec_analysis,
            and project_info populated.

    Returns:
        Merged AgentState with all three agents' output fields populated
        (or None + error recorded if an agent raised).
    """
    import app.agents.orchestrator as _self  # noqa: PLC0415 — late import for patch support

    results = await asyncio.gather(
        _self.run_dimensioning_agent(state),
        _self.run_report_writer_agent(state),
        _self.run_qa_validator(state),
        return_exceptions=True,
    )

    # Start from the current state and merge agent outputs
    merged: dict[str, Any] = dict(state)
    errors: list[str] = list(state.get("errors", []))
    completed_agents: list[str] = list(state.get("completed_agents", []))

    agent_names = ["dimensioning", "report_writer", "qa_validator"]
    output_keys = ["equipment_recommendation", "report_narrative", "qa_results"]

    for agent_name, output_key, result in zip(agent_names, output_keys, results):
        if isinstance(result, BaseException):
            err_msg = f"{agent_name}: {type(result).__name__}: {result}"
            logger.error("Parallel agent failed: %s", err_msg)
            errors.append(err_msg)
            # Keep existing None for output_key (already in merged from state)
        else:
            # Merge the agent's updated state into our merged state
            agent_state = dict(result)
            merged[output_key] = agent_state.get(output_key)
            # Merge errors from the agent's state
            agent_errors = agent_state.get("errors", [])
            for e in agent_errors:
                if e not in errors:
                    errors.append(e)
            # Merge completed_agents from the agent's state
            for name in agent_state.get("completed_agents", []):
                if name not in completed_agents:
                    completed_agents.append(name)

    merged["errors"] = errors
    merged["completed_agents"] = completed_agents
    return merged  # type: ignore[return-value]


# ── Graph builder ─────────────────────────────────────────────────────────────


def build_orchestrator() -> Any:
    """Build and compile the LangGraph StateGraph.

    Defines a single ``parallel_agents`` node that runs all three agents
    concurrently.

    Returns:
        A compiled LangGraph runnable (``CompiledStateGraph``).
    """
    graph: StateGraph = StateGraph(AgentState)
    graph.add_node("parallel_agents", run_parallel_agents)
    graph.add_edge(START, "parallel_agents")
    graph.add_edge("parallel_agents", END)
    return graph.compile()


# Module-level compiled graph — built once per process
_compiled_graph: Any = None


def _get_compiled_graph() -> Any:
    """Return (lazily compiled) orchestrator graph.

    Returns:
        The compiled LangGraph runnable instance.
    """
    global _compiled_graph  # noqa: PLW0603
    if _compiled_graph is None:
        _compiled_graph = build_orchestrator()
    return _compiled_graph


# ── Public entry point ────────────────────────────────────────────────────────


async def orchestrate(
    simulation_id: str,
    simulation_result: dict[str, Any],
    senelec_analysis: dict[str, Any],
    project_info: dict[str, Any],
) -> AgentState:
    """Build initial state, run the LangGraph graph, return the final state.

    Wraps the full graph invocation in ``asyncio.wait_for`` with a 25-second
    timeout so that runaway agents cannot block the API indefinitely.

    Args:
        simulation_id: UUID string of the source Simulation record.
        simulation_result: Dict built from a SimulationResult dataclass.
        senelec_analysis: Dict built from a SenelecAnalysis dataclass.
        project_info: Project metadata dict (lat, lon, name, panel_count, …).

    Returns:
        Final AgentState with all agent outputs and orchestrator metadata.

    Raises:
        asyncio.TimeoutError: If the graph exceeds ``_ORCHESTRATOR_TIMEOUT``.
    """
    start_ms = time.monotonic() * 1000.0

    initial_state: AgentState = {
        "simulation_id": simulation_id,
        "simulation_result": simulation_result,
        "senelec_analysis": senelec_analysis,
        "project_info": project_info,
        "equipment_recommendation": None,
        "report_narrative": None,
        "qa_results": None,
        "errors": [],
        "completed_agents": [],
        "total_duration_ms": None,
    }

    graph = _get_compiled_graph()

    try:
        final_state: AgentState = await asyncio.wait_for(
            graph.ainvoke(initial_state),
            timeout=_ORCHESTRATOR_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.error(
            "Orchestrator timed out after %.0f s for simulation_id=%s",
            _ORCHESTRATOR_TIMEOUT,
            simulation_id,
        )
        elapsed_ms = time.monotonic() * 1000.0 - start_ms
        initial_state["errors"] = [f"orchestrator_timeout: exceeded {_ORCHESTRATOR_TIMEOUT}s"]
        initial_state["total_duration_ms"] = elapsed_ms
        return initial_state

    elapsed_ms = time.monotonic() * 1000.0 - start_ms
    final_state = dict(final_state)  # type: ignore[assignment]
    final_state["total_duration_ms"] = elapsed_ms

    logger.info(
        "Orchestrator completed simulation_id=%s duration_ms=%.0f errors=%d",
        simulation_id,
        elapsed_ms,
        len(final_state.get("errors", [])),
    )

    return final_state  # type: ignore[return-value]
