"""AI-001 agent test suite — written first (TDD).

Tests cover:
- DimensioningAgent unit tests (mock Claude API)
- ReportWriterAgent unit tests (mock Claude API)
- QAValidator unit tests (pure Python — no mock needed)
- Orchestrator integration tests (mock all agents)
- API endpoint tests (SSE streaming, auth, 404)

All async tests use pytest-asyncio with asyncio_mode="auto" (configured in
pyproject.toml). Anthropic API is mocked via unittest.mock.AsyncMock so no
real API key or network is needed.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

# ─────────────────────────────────────────────────────────────────────────────
# Helpers — canned Anthropic response factories
# ─────────────────────────────────────────────────────────────────────────────

_CANNED_EQUIPMENT: dict[str, Any] = {
    "inverter_model": "GOODWE GW5000-ES 5kW",
    "inverter_kva": 5.0,
    "inverter_brand": "GOODWE",
    "battery_model": "PYLONTECH US3000C 3.5kWh",
    "battery_kwh": 3.5,
    "battery_brand": "PYLONTECH",
    "system_type": "hybrid",
    "wiring_config": "String 10×545W, 2 strings en parallèle",
    "protection_devices": ["Disjoncteur DC 32A", "Parafoudre AC/DC", "Sectionneur AC"],
    "reasoning": "Le système hybride 5 kWc nécessite un onduleur GOODWE 5 kVA avec batterie PYLONTECH pour autonomie nocturne.",
}

_CANNED_NARRATIVE = (
    "## Analyse de la ressource solaire\n\n"
    "Le site bénéficie d'une irradiance globale horizontale de 5,8 kWh/m²/jour, "
    "supérieure à la moyenne nationale de 5,4 kWh/m²/jour. Les conditions d'ensoleillement "
    "sont particulièrement favorables entre novembre et avril (saison sèche).\n\n"
    "## Analyse de la production\n\n"
    "La production annuelle estimée de 8 910 kWh représente un rendement spécifique "
    "de 1 634 kWh/kWp, légèrement au-dessus de la moyenne régionale de 1 580 kWh/kWp. "
    "Le ratio de performance de 78 % est conforme aux standards internationaux pour "
    "les installations sans ombrage.\n\n"
    "## Analyse économique\n\n"
    "Les économies annuelles estimées à 1 078 410 FCFA permettent un retour sur "
    "investissement en 6,5 ans pour un coût d'installation de 7 000 000 FCFA. "
    "Le ROI sur 25 ans atteint 285 %, confirmant la rentabilité du projet.\n\n"
    "## Recommandations techniques\n\n"
    "Il est recommandé de nettoyer les panneaux trimestriellement pour maintenir "
    "le ratio de performance. L'orientation optimale sud (180°) avec une inclinaison "
    "de 15° minimise les pertes liées à l'angle d'incidence.\n\n"
    "## Conclusion\n\n"
    "Ce projet solaire de 5,45 kWc est techniquement et économiquement viable "
    "pour le site de Dakar. Il permettra une réduction significative de la dépendance "
    "au réseau SENELEC et des économies substantielles sur le long terme."
)


def _make_claude_message_mock(content: str) -> MagicMock:
    """Build a mock matching anthropic.types.Message structure."""
    msg = MagicMock()
    msg.content = [MagicMock()]
    msg.content[0].text = content
    return msg


def _make_stream_mock(tokens: list[str]) -> AsyncMock:
    """Build an async context manager mock that streams text tokens."""

    async def _aiter():  # type: ignore[return]
        for token in tokens:
            chunk = MagicMock()
            chunk.type = "content_block_delta"
            chunk.delta = MagicMock()
            chunk.delta.type = "text_delta"
            chunk.delta.text = token
            yield chunk

    stream = AsyncMock()
    stream.__aenter__ = AsyncMock(return_value=stream)
    stream.__aexit__ = AsyncMock(return_value=False)
    stream.__aiter__ = _aiter
    return stream


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def simulation_result_dict() -> dict[str, Any]:
    """Minimal SimulationResult-style dict for a 5.45 kWc system.

    Values are chosen so all 8 QA criteria pass with the default test fixtures:
    - annual_kwh=8910, monthly_consumption=800 → coverage=0.928 (V8 PASS)
    - battery_kwh=10.0, daily=24.4 kWh → 10.0 ≥ 0.3×24.4=7.32 (V7 PASS)
    - PR=0.78 (V3 PASS), specific_yield=1634.9 (V2 PASS), payback=6.5 (V6 PASS)
    """
    return {
        "annual_kwh": 8910.0,
        "peak_kwc": 5.45,
        "specific_yield": 1634.9,
        "performance_ratio": 0.78,
        "monthly_data": [
            {"month": i + 1, "energy_kwh": 742.5, "irradiance_kwh_m2": 180.0, "performance_ratio": 0.78}
            for i in range(12)
        ],
        "params_used": {"panel_count": 10, "panel_power_wc": 545},
    }


@pytest.fixture()
def senelec_analysis_dict() -> dict[str, Any]:
    """Minimal SenelecAnalysis-style dict.

    payback_years=6.5 keeps V6 in the [5, 20] year range.
    """
    return {
        "tariff_code": "DPP",
        "before_solar_monthly_xof": 98900.0,
        "after_solar_monthly_xof": 8200.0,
        "annual_savings_xof": 1_078_410.0,
        "payback_years": 6.5,
        "roi_25yr_percent": 285.0,
        "monthly_breakdown": [
            {
                "month": float(i + 1),
                "production_kwh": 742.5,
                "net_consumption_kwh": 57.5,
                "before_cost_xof": 98900.0,
                "after_cost_xof": 8200.0,
                "savings_xof": 90700.0,
            }
            for i in range(12)
        ],
    }


@pytest.fixture()
def project_info_dict() -> dict[str, Any]:
    """Minimal project info dict.

    monthly_consumption_kwh=800 so that coverage ratio = 8910/(800×12)=0.928,
    which is within V8's [0.3, 1.5] range.
    """
    return {
        "latitude": 14.693425,
        "longitude": -17.447938,
        "name": "Villa Sacré-Coeur",
        "panel_count": 10,
        "panel_power_wc": 545,
        "monthly_consumption_kwh": 800.0,
        "installation_cost_xof": 7_000_000.0,
    }


@pytest.fixture()
def base_agent_state(
    simulation_result_dict: dict[str, Any],
    senelec_analysis_dict: dict[str, Any],
    project_info_dict: dict[str, Any],
) -> dict[str, Any]:
    """Full AgentState dict suitable for passing to agents."""
    return {
        "simulation_id": str(uuid.uuid4()),
        "simulation_result": simulation_result_dict,
        "senelec_analysis": senelec_analysis_dict,
        "project_info": project_info_dict,
        "equipment_recommendation": None,
        "report_narrative": None,
        "qa_results": None,
        "errors": [],
        "completed_agents": [],
        "total_duration_ms": None,
    }


@pytest.fixture()
def mock_anthropic() -> MagicMock:
    """Patch anthropic.AsyncAnthropic and return canned responses.

    Returns a MagicMock whose ``.messages.create`` is an AsyncMock returning
    the canned equipment JSON, and whose ``.messages.stream`` returns a
    streaming mock for narrative tokens.
    """
    with patch("anthropic.AsyncAnthropic") as MockClass:
        client_instance = MagicMock()
        MockClass.return_value = client_instance

        # Non-streaming (dimensioning + QA if it used LLM)
        client_instance.messages = MagicMock()
        client_instance.messages.create = AsyncMock(
            return_value=_make_claude_message_mock(json.dumps(_CANNED_EQUIPMENT))
        )

        # Streaming (report writer)
        narrative_tokens = _CANNED_NARRATIVE.split(" ")
        client_instance.messages.stream = MagicMock(
            return_value=_make_stream_mock(narrative_tokens)
        )

        yield client_instance


# ─────────────────────────────────────────────────────────────────────────────
# DimensioningAgent unit tests
# ─────────────────────────────────────────────────────────────────────────────


class TestDimensioningAgent:
    """Unit tests for run_dimensioning_agent()."""

    async def test_dimensioning_agent_returns_equipment(
        self,
        base_agent_state: dict[str, Any],
        mock_anthropic: MagicMock,
    ) -> None:
        """Given a simulation result, agent returns a dict with required equipment keys."""
        from app.agents.dimensioning import run_dimensioning_agent  # noqa: PLC0415

        with patch("app.agents.dimensioning._get_anthropic_client", return_value=mock_anthropic):
            result_state = await run_dimensioning_agent(base_agent_state)

        rec = result_state["equipment_recommendation"]
        assert rec is not None, "equipment_recommendation must not be None"
        assert "inverter_model" in rec
        assert "inverter_kva" in rec
        assert "battery_model" in rec
        assert "panel_recommendation" in rec or "system_type" in rec

    async def test_dimensioning_agent_kva_sizing(
        self,
        base_agent_state: dict[str, Any],
        mock_anthropic: MagicMock,
    ) -> None:
        """For a 5.45 kWp system, inverter_kva must be between 5.0 and 7.0."""
        from app.agents.dimensioning import run_dimensioning_agent  # noqa: PLC0415

        with patch("app.agents.dimensioning._get_anthropic_client", return_value=mock_anthropic):
            result_state = await run_dimensioning_agent(base_agent_state)

        kva = result_state["equipment_recommendation"]["inverter_kva"]
        assert 5.0 <= kva <= 7.0, f"inverter_kva={kva} outside [5.0, 7.0]"

    async def test_dimensioning_agent_fallback_on_error(
        self,
        base_agent_state: dict[str, Any],
    ) -> None:
        """When Claude raises an exception, agent returns rule-based fallback."""
        from app.agents.dimensioning import run_dimensioning_agent  # noqa: PLC0415

        failing_client = MagicMock()
        failing_client.messages = MagicMock()
        failing_client.messages.create = AsyncMock(
            side_effect=Exception("API unavailable")
        )

        with patch("app.agents.dimensioning._get_anthropic_client", return_value=failing_client):
            result_state = await run_dimensioning_agent(base_agent_state)

        # Fallback must still produce a valid recommendation
        rec = result_state["equipment_recommendation"]
        assert rec is not None
        assert "inverter_kva" in rec
        assert isinstance(rec["inverter_kva"], float)


# ─────────────────────────────────────────────────────────────────────────────
# ReportWriterAgent unit tests
# ─────────────────────────────────────────────────────────────────────────────


class TestReportWriterAgent:
    """Unit tests for run_report_writer_agent()."""

    async def test_report_writer_returns_narrative(
        self,
        base_agent_state: dict[str, Any],
        mock_anthropic: MagicMock,
    ) -> None:
        """Given full analysis data, agent returns a non-empty string > 200 chars."""
        from app.agents.report_writer import run_report_writer_agent  # noqa: PLC0415

        with patch("app.agents.report_writer._get_anthropic_client", return_value=mock_anthropic):
            result_state = await run_report_writer_agent(base_agent_state)

        narrative = result_state["report_narrative"]
        assert narrative is not None, "report_narrative must not be None"
        assert isinstance(narrative, str)
        assert len(narrative) > 200, f"narrative too short: {len(narrative)} chars"

    async def test_report_writer_uses_opus_model(
        self,
        base_agent_state: dict[str, Any],
        mock_anthropic: MagicMock,
    ) -> None:
        """ReportWriterAgent must call Claude with the opus model."""
        from app.agents.report_writer import run_report_writer_agent, REPORT_WRITER_MODEL  # noqa: PLC0415

        assert "opus" in REPORT_WRITER_MODEL.lower(), (
            f"report_writer must use opus model, got: {REPORT_WRITER_MODEL}"
        )

        with patch("app.agents.report_writer._get_anthropic_client", return_value=mock_anthropic):
            await run_report_writer_agent(base_agent_state)

    async def test_report_writer_fallback_on_error(
        self,
        base_agent_state: dict[str, Any],
    ) -> None:
        """When Claude raises, report_writer returns a non-empty fallback narrative."""
        from app.agents.report_writer import run_report_writer_agent  # noqa: PLC0415

        failing_client = MagicMock()
        failing_client.messages = MagicMock()
        failing_client.messages.stream = MagicMock(
            side_effect=Exception("Stream failed")
        )

        with patch("app.agents.report_writer._get_anthropic_client", return_value=failing_client):
            result_state = await run_report_writer_agent(base_agent_state)

        narrative = result_state["report_narrative"]
        assert narrative is not None
        assert len(narrative) > 50


# ─────────────────────────────────────────────────────────────────────────────
# QAValidator unit tests (pure Python — no LLM mock needed)
# ─────────────────────────────────────────────────────────────────────────────


class TestQAValidator:
    """Unit tests for run_qa_validator() — pure deterministic logic."""

    def _make_state_with_equipment(
        self,
        base_agent_state: dict[str, Any],
        inverter_kva: float = 5.0,
        battery_kwh: float | None = 10.0,
        power_factor: float | None = None,
    ) -> dict[str, Any]:
        """Helper: clone state and inject equipment recommendation.

        battery_kwh defaults to 10.0 kWh so V7 passes:
        10.0 ≥ 0.3 × (8910/365) = 7.32 kWh.
        """
        import copy

        state = copy.deepcopy(base_agent_state)
        state["equipment_recommendation"] = {
            "inverter_model": "GOODWE GW5000-ES",
            "inverter_kva": inverter_kva,
            "inverter_brand": "GOODWE",
            "battery_model": "PYLONTECH US5000 10kWh" if battery_kwh else None,
            "battery_kwh": battery_kwh,
            "battery_brand": "PYLONTECH" if battery_kwh else None,
            "system_type": "hybrid" if battery_kwh else "on-grid",
            "wiring_config": "String 10×545W",
            "protection_devices": [],
            "reasoning": "Test.",
        }
        if power_factor is not None:
            state["project_info"]["power_factor"] = power_factor
        return state

    async def test_qa_validator_passes_valid_project(
        self,
        base_agent_state: dict[str, Any],
    ) -> None:
        """8 criteria all pass for a valid 5 kWp system."""
        from app.agents.qa_validator import run_qa_validator  # noqa: PLC0415

        state = self._make_state_with_equipment(base_agent_state)
        result_state = await run_qa_validator(state)

        qa = result_state["qa_results"]
        assert qa is not None
        assert "criteria" in qa
        assert "overall" in qa

        # All applicable criteria must pass
        failed = [c for c in qa["criteria"] if c["status"] == "FAIL"]
        assert len(failed) == 0, f"Unexpected FAIL criteria: {failed}"
        assert qa["overall"] == "PASS"

    async def test_qa_validator_fails_low_pr(
        self,
        base_agent_state: dict[str, Any],
    ) -> None:
        """PR=0.50 → criterion V3 (performance ratio) must FAIL."""
        import copy
        from app.agents.qa_validator import run_qa_validator  # noqa: PLC0415

        state = self._make_state_with_equipment(base_agent_state)
        state["simulation_result"]["performance_ratio"] = 0.50

        result_state = await run_qa_validator(state)

        qa = result_state["qa_results"]
        v3 = next((c for c in qa["criteria"] if c["code"] == "V3"), None)
        assert v3 is not None, "V3 criterion not found"
        assert v3["status"] == "FAIL", f"V3 should FAIL for PR=0.50, got {v3['status']}"
        assert qa["overall"] == "FAIL"

    async def test_qa_validator_fails_fp_below_threshold(
        self,
        base_agent_state: dict[str, Any],
    ) -> None:
        """power_factor=0.75 → criterion V5 (power factor) must FAIL."""
        from app.agents.qa_validator import run_qa_validator  # noqa: PLC0415

        state = self._make_state_with_equipment(
            base_agent_state, power_factor=0.75
        )

        result_state = await run_qa_validator(state)

        qa = result_state["qa_results"]
        v5 = next((c for c in qa["criteria"] if c["code"] == "V5"), None)
        assert v5 is not None, "V5 criterion not found"
        assert v5["status"] == "FAIL", f"V5 should FAIL for pf=0.75, got {v5['status']}"

    async def test_qa_validator_v5_na_when_no_power_factor(
        self,
        base_agent_state: dict[str, Any],
    ) -> None:
        """V5 should be NA when power_factor is not provided."""
        from app.agents.qa_validator import run_qa_validator  # noqa: PLC0415

        state = self._make_state_with_equipment(base_agent_state)
        # Ensure no power_factor key
        state["project_info"].pop("power_factor", None)

        result_state = await run_qa_validator(state)

        qa = result_state["qa_results"]
        v5 = next((c for c in qa["criteria"] if c["code"] == "V5"), None)
        assert v5 is not None
        assert v5["status"] == "NA"

    async def test_qa_validator_score_is_count_of_passes(
        self,
        base_agent_state: dict[str, Any],
    ) -> None:
        """score field equals count of PASS criteria."""
        from app.agents.qa_validator import run_qa_validator  # noqa: PLC0415

        state = self._make_state_with_equipment(base_agent_state)
        result_state = await run_qa_validator(state)

        qa = result_state["qa_results"]
        expected_score = sum(1 for c in qa["criteria"] if c["status"] == "PASS")
        assert qa["score"] == expected_score


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator tests
# ─────────────────────────────────────────────────────────────────────────────


class TestOrchestrator:
    """Integration tests for the LangGraph orchestrator."""

    def _make_agent_mock(
        self,
        output_key: str,
        output_value: Any,
        delay: float = 0.0,
    ) -> AsyncMock:
        """Return an AsyncMock that updates state[output_key] after delay."""

        async def _side_effect(state: dict[str, Any]) -> dict[str, Any]:
            if delay > 0:
                await asyncio.sleep(delay)
            updated = dict(state)
            updated[output_key] = output_value
            updated["completed_agents"] = state.get("completed_agents", []) + [output_key]
            return updated

        return AsyncMock(side_effect=_side_effect)

    async def test_orchestrator_runs_all_agents(
        self,
        base_agent_state: dict[str, Any],
    ) -> None:
        """Verify all 4 agents are called and final state has all required keys."""
        mock_dim = self._make_agent_mock(
            "equipment_recommendation", _CANNED_EQUIPMENT
        )
        mock_report = self._make_agent_mock("report_narrative", _CANNED_NARRATIVE)
        mock_qa = self._make_agent_mock(
            "qa_results",
            {"criteria": [], "overall": "PASS", "score": 8},
        )

        with (
            patch("app.agents.orchestrator.run_dimensioning_agent", mock_dim),
            patch("app.agents.orchestrator.run_report_writer_agent", mock_report),
            patch("app.agents.orchestrator.run_qa_validator", mock_qa),
        ):
            from app.agents.orchestrator import orchestrate  # noqa: PLC0415

            final_state = await orchestrate(
                simulation_id=base_agent_state["simulation_id"],
                simulation_result=base_agent_state["simulation_result"],
                senelec_analysis=base_agent_state["senelec_analysis"],
                project_info=base_agent_state["project_info"],
            )

        assert mock_dim.called, "dimensioning agent was not called"
        assert mock_report.called, "report writer agent was not called"
        assert mock_qa.called, "QA validator was not called"

        assert final_state["equipment_recommendation"] is not None
        assert final_state["report_narrative"] is not None
        assert final_state["qa_results"] is not None

    async def test_orchestrator_completes_under_30s(
        self,
        base_agent_state: dict[str, Any],
    ) -> None:
        """With 0.1 s mock delays, total time must be < 5 s (parallel execution)."""
        import time

        mock_dim = self._make_agent_mock("equipment_recommendation", _CANNED_EQUIPMENT, delay=0.1)
        mock_report = self._make_agent_mock("report_narrative", _CANNED_NARRATIVE, delay=0.1)
        mock_qa = self._make_agent_mock(
            "qa_results",
            {"criteria": [], "overall": "PASS", "score": 8},
            delay=0.1,
        )

        with (
            patch("app.agents.orchestrator.run_dimensioning_agent", mock_dim),
            patch("app.agents.orchestrator.run_report_writer_agent", mock_report),
            patch("app.agents.orchestrator.run_qa_validator", mock_qa),
        ):
            from app.agents.orchestrator import orchestrate  # noqa: PLC0415

            start = time.monotonic()
            await orchestrate(
                simulation_id=base_agent_state["simulation_id"],
                simulation_result=base_agent_state["simulation_result"],
                senelec_analysis=base_agent_state["senelec_analysis"],
                project_info=base_agent_state["project_info"],
            )
            elapsed = time.monotonic() - start

        assert elapsed < 5.0, f"Orchestrator took {elapsed:.2f} s — expected < 5 s"

    async def test_orchestrator_fallback_on_claude_error(
        self,
        base_agent_state: dict[str, Any],
    ) -> None:
        """If dimensioning agent raises APIError, fallback values returned with error recorded."""
        import anthropic

        async def _failing_dim(state: dict[str, Any]) -> dict[str, Any]:
            raise anthropic.APIError(  # type: ignore[call-arg]
                message="rate limit",
                request=MagicMock(),
                body=None,
            )

        mock_report = self._make_agent_mock("report_narrative", _CANNED_NARRATIVE)
        mock_qa = self._make_agent_mock(
            "qa_results",
            {"criteria": [], "overall": "PASS", "score": 8},
        )

        with (
            patch("app.agents.orchestrator.run_dimensioning_agent", AsyncMock(side_effect=_failing_dim)),
            patch("app.agents.orchestrator.run_report_writer_agent", mock_report),
            patch("app.agents.orchestrator.run_qa_validator", mock_qa),
        ):
            from app.agents.orchestrator import orchestrate  # noqa: PLC0415

            final_state = await orchestrate(
                simulation_id=base_agent_state["simulation_id"],
                simulation_result=base_agent_state["simulation_result"],
                senelec_analysis=base_agent_state["senelec_analysis"],
                project_info=base_agent_state["project_info"],
            )

        # Errors list must record the failure
        assert len(final_state["errors"]) > 0, "errors list should be non-empty"
        # Other agents still ran
        assert final_state["report_narrative"] is not None
        assert final_state["qa_results"] is not None


# ─────────────────────────────────────────────────────────────────────────────
# API endpoint tests
# ─────────────────────────────────────────────────────────────────────────────


def _build_test_app() -> FastAPI:
    """Create a minimal FastAPI test app with the AI router mounted."""
    from app.main import create_application  # noqa: PLC0415
    return create_application()


@pytest.fixture()
def test_app() -> FastAPI:
    """Return the full FastAPI app for endpoint tests."""
    return _build_test_app()


@pytest.fixture()
def test_user_token(async_session: Any) -> str:  # noqa: ANN401
    """Create a test user and return a valid JWT access token."""
    import uuid as _uuid
    from app.core.security import create_access_token  # noqa: PLC0415

    user_id = _uuid.uuid4()
    return create_access_token(user_id=user_id, role="technicien")


class TestAIEndpoints:
    """Tests for POST /api/v2/ai/analyze and GET /api/v2/ai/sessions/{id}."""

    async def test_post_analyze_unauthenticated(
        self,
        test_app: FastAPI,
    ) -> None:
        """POST /api/v2/ai/analyze without token returns 403."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v2/ai/analyze",
                json={"simulation_id": str(uuid.uuid4())},
            )
        assert resp.status_code in (401, 403), (
            f"Expected 401/403, got {resp.status_code}"
        )

    async def test_analyze_invalid_simulation_id(
        self,
        test_app: FastAPI,
        async_session: Any,
    ) -> None:
        """POST /api/v2/ai/analyze with unknown simulation_id returns 404."""
        import uuid as _uuid
        from app.core.security import create_access_token  # noqa: PLC0415
        from app.models.user import User  # noqa: PLC0415

        # Create and persist a real user
        user = User.create(
            email="analyst@test.com",
            role="technicien",
            hashed_password="x",
        )
        async_session.add(user)
        await async_session.flush()

        token = create_access_token(user_id=user.id, role="technicien")

        # Override get_async_db to use test session
        from app.db.session import get_async_db  # noqa: PLC0415

        async def _override_db():  # type: ignore[return]
            yield async_session

        test_app.dependency_overrides[get_async_db] = _override_db

        try:
            async with AsyncClient(
                transport=ASGITransport(app=test_app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/v2/ai/analyze",
                    json={"simulation_id": str(_uuid.uuid4())},
                    headers={"Authorization": f"Bearer {token}"},
                )
            assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        finally:
            test_app.dependency_overrides.pop(get_async_db, None)

    async def test_post_analyze_authenticated(
        self,
        test_app: FastAPI,
        async_session: Any,
    ) -> None:
        """POST /api/v2/ai/analyze with valid auth and simulation returns 200 SSE."""
        import uuid as _uuid
        from app.core.security import create_access_token  # noqa: PLC0415
        from app.models.user import User  # noqa: PLC0415
        from app.models.project import Project  # noqa: PLC0415
        from app.models.simulation import Simulation  # noqa: PLC0415
        from app.db.session import get_async_db  # noqa: PLC0415

        # Seed DB
        user = User.create(email="analyst2@test.com", role="technicien", hashed_password="x")
        async_session.add(user)
        await async_session.flush()

        project = Project.create(
            user_id=user.id,
            name="Test Project",
            latitude=14.69,
            longitude=-17.44,
        )
        async_session.add(project)
        await async_session.flush()

        sim = Simulation.create(
            project_id=project.id,
            panel_count=10,
            peak_kwc=5.45,
            annual_kwh=8910.0,
            specific_yield=1634.9,
            performance_ratio=0.78,
            monthly_data=[
                {"month": i + 1, "energy_kwh": 742.5, "irradiance_kwh_m2": 180.0, "performance_ratio": 0.78}
                for i in range(12)
            ],
            params={"panel_count": 10, "panel_power_wc": 545},
            senelec_savings_xof=1_078_410.0,
            payback_years=6.5,
            roi_percent=285.0,
        )
        async_session.add(sim)
        await async_session.flush()

        token = create_access_token(user_id=user.id, role="technicien")

        # Mock the orchestrate function so we don't need real Claude
        mock_final_state = {
            "simulation_id": str(sim.id),
            "simulation_result": {},
            "senelec_analysis": {},
            "project_info": {},
            "equipment_recommendation": _CANNED_EQUIPMENT,
            "report_narrative": _CANNED_NARRATIVE,
            "qa_results": {"criteria": [], "overall": "PASS", "score": 8},
            "errors": [],
            "completed_agents": ["dimensioning", "report_writer", "qa_validator"],
            "total_duration_ms": 1200.0,
        }

        async def _override_db():  # type: ignore[return]
            yield async_session

        test_app.dependency_overrides[get_async_db] = _override_db

        try:
            with patch("app.api.v2.ai.orchestrate", AsyncMock(return_value=mock_final_state)):
                async with AsyncClient(
                    transport=ASGITransport(app=test_app), base_url="http://test"
                ) as client:
                    resp = await client.post(
                        "/api/v2/ai/analyze",
                        json={"simulation_id": str(sim.id)},
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Accept": "text/event-stream",
                        },
                    )
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        finally:
            test_app.dependency_overrides.pop(get_async_db, None)

    async def test_get_session(
        self,
        test_app: FastAPI,
        async_session: Any,
    ) -> None:
        """GET /api/v2/ai/sessions/{id} returns 200 with cached result."""
        import uuid as _uuid
        from app.core.security import create_access_token  # noqa: PLC0415
        from app.models.user import User  # noqa: PLC0415
        from app.db.session import get_async_db  # noqa: PLC0415
        from app.db.redis import redis_client  # noqa: PLC0415

        user = User.create(email="session_user@test.com", role="technicien", hashed_password="x")
        async_session.add(user)
        await async_session.flush()

        token = create_access_token(user_id=user.id, role="technicien")
        session_id = str(_uuid.uuid4())

        cached_result = {
            "simulationId": str(_uuid.uuid4()),
            "equipmentRecommendation": {
                "inverterModel": "GOODWE GW5000-ES",
                "inverterKva": 5.0,
                "inverterBrand": "GOODWE",
                "batteryModel": None,
                "batteryKwh": None,
                "systemType": "on-grid",
                "reasoning": "Test.",
            },
            "reportNarrative": _CANNED_NARRATIVE,
            "qaResults": {"criteria": [], "overall": "PASS", "score": 8},
            "durationMs": 1200.0,
            "errors": [],
        }

        mock_redis = AsyncMock()
        mock_redis.cache_get = AsyncMock(return_value=json.dumps(cached_result))

        async def _override_db():  # type: ignore[return]
            yield async_session

        test_app.dependency_overrides[get_async_db] = _override_db

        try:
            with patch("app.api.v2.ai.redis_client", mock_redis):
                async with AsyncClient(
                    transport=ASGITransport(app=test_app), base_url="http://test"
                ) as client:
                    resp = await client.get(
                        f"/api/v2/ai/sessions/{session_id}",
                        headers={"Authorization": f"Bearer {token}"},
                    )
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
            data = resp.json()
            assert "reportNarrative" in data
        finally:
            test_app.dependency_overrides.pop(get_async_db, None)
