"""Pydantic v2 schemas for AI analysis endpoints (AI-001).

Defines request bodies and response models for:
- POST /api/v2/ai/analyze — run multi-agent analysis and stream SSE
- GET  /api/v2/ai/sessions/{id} — retrieve a cached analysis result

SSE event types emitted by /analyze:
  - 'status'           {"agent": "dimensioning", "status": "running"}
  - 'result'           {"agent": "dimensioning", "data": {...}}
  - 'narrative_token'  {"token": "..."} (streaming tokens from report_writer)
  - 'complete'         {"analysis": AnalysisResult}
  - 'error'            {"message": "..."}
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AnalyzeRequest(BaseModel):
    """Request body for POST /api/v2/ai/analyze.

    Attributes:
        simulation_id: UUID of an existing completed Simulation record that
            belongs to the authenticated user.
    """

    simulation_id: UUID = Field(
        description="UUID of an existing completed Simulation to analyse."
    )


class QACriterionResponse(BaseModel):
    """Serialised QA criterion result.

    Attributes:
        code: Criterion identifier (V1 through V8).
        label: Human-readable criterion name.
        status: Validation outcome — one of "PASS", "FAIL", or "NA".
        value: Computed value (numeric or string), or None if not applicable.
        threshold: Human-readable threshold description.
        comment: Brief explanation of the result.
    """

    model_config = ConfigDict(populate_by_name=True)

    code: str
    label: str
    status: str = Field(description='"PASS" | "FAIL" | "NA"')
    value: str | float | None = None
    threshold: str
    comment: str


class EquipmentRecommendation(BaseModel):
    """Inverter, battery, and wiring recommendation from DimensioningAgent.

    Attributes:
        inverterModel: Full inverter model string.
        inverterKva: Inverter rated apparent power in kVA.
        inverterBrand: Inverter manufacturer name.
        batteryModel: Optional battery model string.
        batteryKwh: Optional battery usable capacity in kWh.
        systemType: "on-grid", "hybrid", or "off-grid".
        wiringConfig: String wiring configuration description.
        protectionDevices: List of required protection device names.
        panelRecommendation: Recommended panel model description.
        reasoning: Technical justification in 2-3 sentences.
    """

    model_config = ConfigDict(populate_by_name=True)

    inverterModel: str = Field(validation_alias="inverter_model", default="")
    inverterKva: float = Field(validation_alias="inverter_kva", default=0.0)
    inverterBrand: str = Field(validation_alias="inverter_brand", default="")
    batteryModel: str | None = Field(validation_alias="battery_model", default=None)
    batteryKwh: float | None = Field(validation_alias="battery_kwh", default=None)
    batteryBrand: str | None = Field(validation_alias="battery_brand", default=None)
    systemType: str = Field(validation_alias="system_type", default="on-grid")
    wiringConfig: str = Field(validation_alias="wiring_config", default="")
    protectionDevices: list[str] = Field(
        validation_alias="protection_devices", default_factory=list
    )
    panelRecommendation: str = Field(
        validation_alias="panel_recommendation", default=""
    )
    reasoning: str = Field(default="")


class AnalysisResult(BaseModel):
    """Full AI analysis result returned in the SSE 'complete' event and session GET.

    Attributes:
        simulationId: UUID of the analysed Simulation record.
        equipmentRecommendation: Sizing recommendation from DimensioningAgent.
        reportNarrative: French technical narrative from ReportWriterAgent.
        qaResults: QA validation results with criteria list, overall status,
            and score.
        durationMs: Wall-clock time for the full analysis in milliseconds.
        errors: List of non-fatal error messages accumulated during the run.
    """

    model_config = ConfigDict(populate_by_name=True)

    simulationId: UUID
    equipmentRecommendation: EquipmentRecommendation
    reportNarrative: str
    qaResults: dict[str, Any]
    durationMs: float
    errors: list[str] = Field(default_factory=list)

    @classmethod
    def from_agent_state(
        cls,
        simulation_id: UUID,
        state: dict[str, Any],
    ) -> "AnalysisResult":
        """Build an AnalysisResult from a completed AgentState dict.

        Args:
            simulation_id: UUID of the analysed simulation.
            state: Final AgentState dict returned by the orchestrator.

        Returns:
            A populated ``AnalysisResult`` instance.
        """
        equipment_raw = state.get("equipment_recommendation") or {}
        equipment = EquipmentRecommendation.model_validate(equipment_raw)

        return cls(
            simulationId=simulation_id,
            equipmentRecommendation=equipment,
            reportNarrative=state.get("report_narrative") or "",
            qaResults=state.get("qa_results") or {"criteria": [], "overall": "NA", "score": 0},
            durationMs=state.get("total_duration_ms") or 0.0,
            errors=state.get("errors") or [],
        )
