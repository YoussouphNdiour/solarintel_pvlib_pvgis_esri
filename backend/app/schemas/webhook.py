"""Pydantic schemas for INTEG-001 webhook endpoints.

Defines request / response models for:
- POST /api/v2/webhooks/inverter      — SunSpec inverter data ingestion
- GET  /api/v2/webhooks/weather/{id}  — On-demand weather pull
- POST /api/v2/webhooks/whatsapp/send-report — PDF delivery via WhatsApp
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class SendReportRequest(BaseModel):
    """Request body for POST /api/v2/webhooks/whatsapp/send-report.

    Attributes:
        report_id: UUID of an existing Report record with status ``"ready"``.
        phone: Client phone number in any supported Senegalese format.
        caption: Optional custom caption; defaults to a generic message.
    """

    report_id: UUID = Field(description="UUID of the ready Report record.")
    phone: str = Field(
        description="Client phone number (e.g. 771234567, +221771234567)."
    )
    caption: str | None = Field(
        default=None,
        description="Custom caption for the PDF document message.",
    )
