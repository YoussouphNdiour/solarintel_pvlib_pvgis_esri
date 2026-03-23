"""SolarIntel v2 AI agents package.

Exports:
- AgentState: Shared TypedDict threaded through all LangGraph nodes.
- orchestrate: Top-level entry point for the multi-agent analysis pipeline.
- build_orchestrator: Construct the compiled LangGraph StateGraph.

Imports are kept lazy (deferred to function call time) so that unit tests
for individual agents (dimensioning, qa_validator, etc.) do not require
langgraph to be importable at test collection time.
"""

from app.agents.state import AgentState

__all__ = ["AgentState"]


def get_orchestrate():  # type: ignore[return]
    """Lazily import and return the orchestrate entry point.

    Returns:
        The ``orchestrate`` coroutine function from ``app.agents.orchestrator``.
    """
    from app.agents.orchestrator import orchestrate  # noqa: PLC0415

    return orchestrate


def get_build_orchestrator():  # type: ignore[return]
    """Lazily import and return the build_orchestrator factory.

    Returns:
        The ``build_orchestrator`` function from ``app.agents.orchestrator``.
    """
    from app.agents.orchestrator import build_orchestrator  # noqa: PLC0415

    return build_orchestrator
