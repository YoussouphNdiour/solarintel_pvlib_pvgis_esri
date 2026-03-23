"""Pydantic v2 schemas for PDF-001 report endpoints.

Defines request bodies and response models for:
- POST /api/v2/reports      — trigger async report generation
- GET  /api/v2/reports/{id} — retrieve report status
- GET  /api/v2/reports/{id}/download — stream generated PDF
- GET  /api/v2/reports/{id}/html     — return interactive HTML report

camelCase field aliases are used for JSON serialisation to match the
frontend TypeScript convention.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReportRequest(BaseModel):
    """Request body for POST /api/v2/reports.

    Attributes:
        simulation_id: UUID of a completed Simulation to generate a report for.
        client_name: Optional client name to embed in the report cover.
        installer_name: Optional installer name to embed in the report cover.
        dashboard_url: Optional base URL for the QR code deep link.
    """

    simulation_id: UUID = Field(description="UUID of the completed Simulation.")
    client_name: str | None = Field(default=None, description="Client display name.")
    installer_name: str | None = Field(
        default=None, description="Installer company name."
    )
    dashboard_url: str | None = Field(
        default=None,
        description="Base URL for dashboard QR code (e.g. https://solarintel.app).",
    )


class ReportStatusResponse(BaseModel):
    """Serialised Report record returned to clients.

    Attributes:
        id: UUID primary key of the Report record.
        simulationId: UUID of the source Simulation.
        status: Generation lifecycle status (pending / generating / ready / failed).
        pdfPath: Filesystem path to the generated PDF (None until ready).
        htmlPath: Filesystem path to the generated HTML (None until ready).
        generatedAt: Timestamp when the report became ready (None until then).
        createdAt: UTC timestamp when the Report record was created.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    simulationId: UUID = Field(validation_alias="simulation_id")
    status: str
    pdfPath: str | None = Field(validation_alias="pdf_path", default=None)
    htmlPath: str | None = Field(validation_alias="html_path", default=None)
    generatedAt: datetime | None = Field(
        validation_alias="generated_at", default=None
    )
    createdAt: datetime = Field(validation_alias="created_at")


class ReportCreateResponse(BaseModel):
    """Response body for the POST /api/v2/reports 202 Accepted response.

    Attributes:
        reportId: UUID of the newly created Report record.
        status: Always ``"pending"`` at creation time.
        message: Human-readable description of the accepted operation.
    """

    reportId: UUID
    status: str
    message: str
