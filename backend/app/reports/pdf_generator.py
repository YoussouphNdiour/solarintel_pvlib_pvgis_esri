"""ReportLab PDF generator for SolarIntel v2 reports.

Generates a professional PVSyst-inspired report including:
  - Cover page with project info and KPI summary
  - System specification table
  - Monthly production bar chart (native ReportLab Drawing)
  - SENELEC savings analysis table
  - Cash flow chart with 25-year payback visualisation
  - Monte Carlo confidence intervals chart
  - Sensitivity analysis table
  - QA matrix
  - AI narrative section
  - QR code to online dashboard

Section-building methods live in ``pdf_sections.PDFSectionsMixin``
to keep each file under 300 lines.
"""

from __future__ import annotations

import io
import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

from app.reports.pdf_sections import (
    MARGIN,
    SOLAR_AMBER,
    SOLAR_DARK,
    SOLAR_GRAY,
    SOLAR_GREEN,
    SOLAR_LIGHT,
    PDFSectionsMixin,
)

PAGE_W, PAGE_H = A4


# ── Report data container ──────────────────────────────────────────────────────


@dataclass
class ReportData:
    """All data required to render a complete SolarIntel PDF report."""

    # Project info
    project_name: str
    latitude: float
    longitude: float
    report_date: str
    address: str | None = None
    installer_name: str | None = None
    client_name: str | None = None

    # Simulation results
    panel_count: int = 0
    peak_kwc: float = 0.0
    annual_kwh: float = 0.0
    specific_yield: float = 0.0
    performance_ratio: float = 0.0
    monthly_kwh: list[float] = field(default_factory=list)
    monthly_irradiance: list[float] = field(default_factory=list)

    # Equipment
    panel_model: str = "—"
    inverter_model: str = "—"
    inverter_kva: float = 0.0
    battery_model: str | None = None
    system_type: str = "on-grid"

    # Financial
    installation_cost_xof: float = 0.0
    annual_savings_xof: float = 0.0
    payback_years: float = 0.0
    roi_25yr_pct: float = 0.0
    monthly_savings: list[float] = field(default_factory=list)

    # Advanced analysis
    monte_carlo: Any | None = None
    sensitivity: list[Any] | None = None

    # AI analysis
    qa_criteria: list[dict] | None = None
    report_narrative: str | None = None

    # Assets
    satellite_image_base64: str | None = None
    qr_code_url: str | None = None


# ── Filename helper ────────────────────────────────────────────────────────────


def get_report_filename(report_id: uuid.UUID) -> str:
    """Return the canonical filename for a PDF report.

    Format: ``solarintel_report_{report_id}_{YYYYMMDD}.pdf``

    Args:
        report_id: UUID of the Report record.

    Returns:
        A filename string safe for filesystem and HTTP Content-Disposition.
    """
    today = date.today().strftime("%Y%m%d")
    return f"solarintel_report_{report_id}_{today}.pdf"


# ── Stylesheet factory ─────────────────────────────────────────────────────────


def _make_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "cover_title", parent=base["Title"],
            fontSize=28, textColor=SOLAR_AMBER,
            spaceAfter=6, fontName="Helvetica-Bold",
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub", parent=base["Normal"],
            fontSize=13, textColor=SOLAR_DARK, spaceAfter=4,
        ),
        "section_title": ParagraphStyle(
            "section_title", parent=base["Heading1"],
            fontSize=14, textColor=SOLAR_DARK,
            fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"],
            fontSize=9, textColor=SOLAR_DARK, leading=14,
        ),
        "label": ParagraphStyle(
            "label", parent=base["Normal"],
            fontSize=8, textColor=SOLAR_GRAY,
        ),
    }


# ── PDF Generator ──────────────────────────────────────────────────────────────


class PDFReportGenerator(PDFSectionsMixin):
    """Orchestrates building the full SolarIntel PDF report.

    Inherits section-building methods from ``PDFSectionsMixin``.

    Usage::

        data = ReportData(...)
        gen = PDFReportGenerator(data)
        pdf_bytes = gen.generate()
    """

    def __init__(self, data: ReportData) -> None:
        self.data = data
        self.styles = _make_styles()

    def generate(self) -> bytes:
        """Build the complete PDF and return raw bytes.

        Returns:
            Raw PDF bytes suitable for HTTP streaming or file storage.
        """
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=MARGIN,
            rightMargin=MARGIN,
            topMargin=MARGIN + 1.0 * cm,
            bottomMargin=MARGIN,
            title=f"SolarIntel — {self.data.project_name}",
            author="SolarIntel v2",
        )

        story: list[Any] = []
        story += self._build_cover_page()
        story.append(PageBreak())
        story += self._build_system_specs()
        story.append(PageBreak())
        story.append(Paragraph("Production Mensuelle", self.styles["section_title"]))
        story.append(self._build_production_chart())
        story += self._build_senelec_table()
        story.append(PageBreak())
        story.append(Paragraph("Analyse des Cash-Flows ROI", self.styles["section_title"]))
        story.append(self._build_cashflow_chart())
        story += self._build_monte_carlo_section()
        story.append(PageBreak())
        story += self._build_sensitivity_table()
        story += self._build_qa_matrix()
        story.append(PageBreak())
        story += self._build_narrative_section()
        story += self._build_qr_code()

        doc.build(
            story,
            onFirstPage=self._page_header_footer,
            onLaterPages=self._page_header_footer,
        )
        return buf.getvalue()
