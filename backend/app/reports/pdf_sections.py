"""PDF cover page, system specs, and chart section builders for SolarIntel v2.

Contains the first set of section-building methods extracted from
``PDFReportGenerator``.  Table and text sections are in ``pdf_tables.py``.
Both are composed into ``PDFSectionsMixin`` which ``PDFReportGenerator``
inherits.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

if TYPE_CHECKING:
    from app.reports.pdf_generator import PDFReportGenerator

# ── Brand colours (exported for re-use in pdf_tables.py and pdf_generator.py) ─
SOLAR_AMBER = colors.HexColor("#f59e0b")
SOLAR_DARK = colors.HexColor("#1f2937")
SOLAR_GRAY = colors.HexColor("#6b7280")
SOLAR_GREEN = colors.HexColor("#10b981")
SOLAR_RED = colors.HexColor("#ef4444")
SOLAR_LIGHT = colors.HexColor("#f3f4f6")

MONTHS_FR = [
    "Jan", "Fév", "Mar", "Avr", "Mai", "Jun",
    "Jul", "Aoû", "Sep", "Oct", "Nov", "Déc",
]

PAGE_W, PAGE_H = A4
MARGIN = 2.0 * cm


class PDFChartsMixin:
    """Mixin providing cover page, system specs, and chart section builders."""

    def _build_cover_page(self: "PDFReportGenerator") -> list:
        d = self.data
        s = self.styles
        story: list[Any] = [Spacer(1, 2 * cm)]
        story.append(Paragraph("SolarIntel v2", s["cover_title"]))
        story.append(Paragraph("Rapport d'Étude Photovoltaïque", s["cover_sub"]))
        story.append(HRFlowable(width="100%", thickness=2, color=SOLAR_AMBER))
        story.append(Spacer(1, 0.5 * cm))
        info_data = [
            ["Projet", d.project_name],
            ["Client", d.client_name or "—"],
            ["Installateur", d.installer_name or "SolarIntel SARL"],
            ["Localisation", d.address or f"{d.latitude:.4f}°N, {d.longitude:.4f}°E"],
            ["Date du rapport", d.report_date],
        ]
        tbl = Table(info_data, colWidths=[5 * cm, 12 * cm])
        tbl.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TEXTCOLOR", (0, 0), (0, -1), SOLAR_GRAY),
            ("TEXTCOLOR", (1, 0), (1, -1), SOLAR_DARK),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [SOLAR_LIGHT, colors.white]),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 1 * cm))
        kpi_data = [
            [f"{d.peak_kwc:.2f} kWc", f"{d.annual_kwh:,.0f} kWh/an",
             f"{d.payback_years:.1f} ans", f"{d.roi_25yr_pct:.0f}%"],
            ["Puissance crête", "Production annuelle",
             "Retour sur investissement", "ROI 25 ans"],
        ]
        kpi_tbl = Table(kpi_data, colWidths=[4.5 * cm] * 4)
        kpi_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), SOLAR_AMBER),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 16),
            ("TEXTCOLOR", (0, 1), (-1, 1), SOLAR_GRAY),
            ("FONTSIZE", (0, 1), (-1, 1), 8),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.white),
        ]))
        story.append(kpi_tbl)
        return story

    def _build_system_specs(self: "PDFReportGenerator") -> list:
        d = self.data
        s = self.styles
        story: list[Any] = [Paragraph("Spécifications du Système", s["section_title"])]
        rows = [
            ["Paramètre", "Valeur", "Unité"],
            ["Nombre de panneaux", str(d.panel_count), "unités"],
            ["Modèle de panneau", d.panel_model, "—"],
            ["Puissance crête", f"{d.peak_kwc:.2f}", "kWc"],
            ["Onduleur", d.inverter_model, "—"],
            ["Puissance onduleur", f"{d.inverter_kva:.1f}", "kVA"],
            ["Type de système", d.system_type, "—"],
            ["Batterie", d.battery_model or "Aucune", "—"],
            ["Production annuelle", f"{d.annual_kwh:,.1f}", "kWh/an"],
            ["Rendement spécifique", f"{d.specific_yield:,.0f}", "kWh/kWc/an"],
            ["Performance Ratio", f"{d.performance_ratio:.2%}", "—"],
            ["Coût d'installation", f"{d.installation_cost_xof:,.0f}", "FCFA"],
            ["Économies annuelles SENELEC", f"{d.annual_savings_xof:,.0f}", "FCFA/an"],
        ]
        col_w = [(PAGE_W - 2 * MARGIN) / 3] * 3
        tbl = Table(rows, colWidths=col_w)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), SOLAR_DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [SOLAR_LIGHT, colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.3, SOLAR_GRAY),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("ALIGN", (1, 0), (2, -1), "CENTER"),
        ]))
        story.append(tbl)
        return story

    def _build_production_chart(self: "PDFReportGenerator") -> Drawing:
        d = self.data
        monthly = d.monthly_kwh if d.monthly_kwh else [0.0] * 12
        chart_w = PAGE_W - 2 * MARGIN - 1 * cm
        chart_h = 7 * cm
        drawing = Drawing(chart_w, chart_h + 1.5 * cm)
        bc = VerticalBarChart()
        bc.x, bc.y = 40, 25
        bc.width, bc.height = chart_w - 60, chart_h
        bc.data = [monthly]
        bc.bars[0].fillColor = SOLAR_AMBER
        bc.bars[0].strokeColor = None
        bc.categoryAxis.categoryNames = MONTHS_FR
        bc.categoryAxis.labels.fontSize = 7
        bc.valueAxis.labelTextFormat = "%.0f"
        bc.valueAxis.labels.fontSize = 7
        bc.groupSpacing = 5
        drawing.add(bc)
        lbl = String(chart_w / 2, chart_h + 1.3 * cm, "Production mensuelle (kWh)",
                     textAnchor="middle", fontSize=9, fillColor=SOLAR_DARK)
        drawing.add(lbl)
        return drawing

    def _build_cashflow_chart(self: "PDFReportGenerator") -> Drawing:
        d = self.data
        years = list(range(26))
        cf = [-d.installation_cost_xof + d.annual_savings_xof * yr for yr in years]
        chart_w = PAGE_W - 2 * MARGIN - 1 * cm
        chart_h = 7 * cm
        drawing = Drawing(chart_w, chart_h + 2 * cm)
        lc = HorizontalLineChart()
        lc.x, lc.y = 50, 30
        lc.width, lc.height = chart_w - 70, chart_h
        lc.data = [cf]
        lc.lines[0].strokeColor = SOLAR_GREEN
        lc.lines[0].strokeWidth = 1.5
        lc.categoryAxis.categoryNames = [str(y) for y in years]
        lc.categoryAxis.labels.fontSize = 6
        lc.valueAxis.labelTextFormat = "%.0f"
        lc.valueAxis.labels.fontSize = 6
        drawing.add(lc)
        lbl = String(chart_w / 2, chart_h + 1.7 * cm,
                     "Flux de Trésorerie Cumulé (FCFA) — 25 ans",
                     textAnchor="middle", fontSize=9, fillColor=SOLAR_DARK)
        drawing.add(lbl)
        return drawing


# Composite mixin that inherits both sets of section builders
from app.reports.pdf_tables import PDFTablesMixin  # noqa: E402


class PDFSectionsMixin(PDFChartsMixin, PDFTablesMixin):
    """Combined mixin providing all section-building methods for PDFReportGenerator."""
