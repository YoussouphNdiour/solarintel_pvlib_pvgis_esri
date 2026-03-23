"""PDF table and text section builders for SolarIntel v2.

Contains SENELEC savings table, Monte Carlo section, sensitivity table,
QA matrix, AI narrative, QR code, and page header/footer.

Imported as part of ``PDFSectionsMixin`` via ``pdf_sections.py``.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Any

from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

if TYPE_CHECKING:
    from app.reports.pdf_generator import PDFReportGenerator

from app.reports.pdf_sections import (
    MARGIN,
    MONTHS_FR,
    SOLAR_AMBER,
    SOLAR_DARK,
    SOLAR_GRAY,
    SOLAR_GREEN,
    SOLAR_LIGHT,
)

PAGE_W, PAGE_H = A4


class PDFTablesMixin:
    """Mixin providing SENELEC, Monte Carlo, sensitivity, QA, and footer sections."""

    def _build_senelec_table(self: "PDFReportGenerator") -> list:
        d = self.data
        s = self.styles
        story: list[Any] = [
            Spacer(1, 0.3 * cm),
            Paragraph("Analyse des Économies SENELEC", s["section_title"]),
        ]
        savings = d.monthly_savings if d.monthly_savings else [0.0] * 12
        prod = d.monthly_kwh if d.monthly_kwh else [0.0] * 12
        rows = [["Mois", "Production (kWh)", "Économies SENELEC (FCFA)"]] + [
            [MONTHS_FR[i], f"{prod[i]:,.1f}", f"{savings[i]:,.0f}"] for i in range(12)
        ] + [["TOTAL", f"{sum(prod):,.1f}", f"{sum(savings):,.0f}"]]
        col_w = [(PAGE_W - 2 * MARGIN) / 3] * 3
        tbl = Table(rows, colWidths=col_w)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), SOLAR_DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, -1), (-1, -1), SOLAR_AMBER),
            ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [SOLAR_LIGHT, colors.white]),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.3, SOLAR_GRAY),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(tbl)
        return story

    def _build_monte_carlo_section(self: "PDFReportGenerator") -> list:
        d = self.data
        s = self.styles
        mc = d.monte_carlo
        story: list[Any] = [
            Spacer(1, 0.3 * cm),
            Paragraph("Analyse Monte Carlo — Intervalles de Confiance",
                      s["section_title"]),
        ]
        if mc is None:
            story.append(Paragraph("Analyse Monte Carlo non disponible.", s["body"]))
            return story
        rows = [
            ["Percentile", "Production Annuelle (kWh)", "Écart / Base"],
            ["P10 (pessimiste)", f"{mc.annual_p10:,.0f}",
             f"{(mc.annual_p10/d.annual_kwh-1)*100:+.1f}%"],
            ["P50 (médiane)", f"{mc.annual_p50:,.0f}",
             f"{(mc.annual_p50/d.annual_kwh-1)*100:+.1f}%"],
            ["P90 (optimiste)", f"{mc.annual_p90:,.0f}",
             f"{(mc.annual_p90/d.annual_kwh-1)*100:+.1f}%"],
            ["Bande P10-P90", f"{mc.confidence_band_pct:.1f}%", "—"],
        ]
        col_w = [(PAGE_W - 2 * MARGIN) / 3] * 3
        tbl = Table(rows, colWidths=col_w)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), SOLAR_DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [SOLAR_LIGHT, colors.white]),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.3, SOLAR_GRAY),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(tbl)
        return story

    def _build_sensitivity_table(self: "PDFReportGenerator") -> list:
        d = self.data
        s = self.styles
        story: list[Any] = [
            Paragraph("Analyse de Sensibilité — Prix de l'Électricité",
                      s["section_title"]),
        ]
        if not d.sensitivity:
            story.append(Paragraph("Analyse de sensibilité non disponible.", s["body"]))
            return story
        rows = [["Variation Prix", "Économies/an (FCFA)", "Retour (ans)", "ROI 25 ans"]]
        for r in d.sensitivity:
            sign = "+" if r.price_change_pct > 0 else ""
            pb = f"{r.payback_years:.1f}" if r.payback_years != float("inf") else "∞"
            rows.append([
                f"{sign}{r.price_change_pct:.0f}%",
                f"{r.annual_savings_xof:,.0f}",
                pb,
                f"{r.roi_25yr_pct:.1f}%",
            ])
        col_w = [(PAGE_W - 2 * MARGIN) / 4] * 4
        tbl = Table(rows, colWidths=col_w)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), SOLAR_DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [SOLAR_LIGHT, colors.white]),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.3, SOLAR_GRAY),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(tbl)
        return story

    def _build_qa_matrix(self: "PDFReportGenerator") -> list:
        d = self.data
        s = self.styles
        story: list[Any] = [
            Spacer(1, 0.5 * cm),
            Paragraph("Matrice de Contrôle Qualité", s["section_title"]),
        ]
        criteria = d.qa_criteria or []
        if not criteria:
            story.append(Paragraph("Matrice QA non disponible.", s["body"]))
            return story
        rows = [["Code", "Critère", "Statut", "Valeur", "Seuil", "Commentaire"]]
        for c in criteria:
            rows.append([
                c.get("code", ""), c.get("label", ""), c.get("status", ""),
                str(c.get("value", "—")), c.get("threshold", ""), c.get("comment", ""),
            ])
        col_w = [1.2 * cm, 3.5 * cm, 1.5 * cm, 2 * cm, 2.5 * cm, 5.5 * cm]
        tbl = Table(rows, colWidths=col_w)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), SOLAR_DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [SOLAR_LIGHT, colors.white]),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.3, SOLAR_GRAY),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(tbl)
        return story

    def _build_narrative_section(self: "PDFReportGenerator") -> list:
        d = self.data
        s = self.styles
        story: list[Any] = [
            Paragraph("Analyse Technique — Synthèse IA", s["section_title"]),
            HRFlowable(width="100%", thickness=1, color=SOLAR_AMBER),
            Spacer(1, 0.3 * cm),
        ]
        narrative = d.report_narrative or (
            "Aucune analyse narrative disponible pour ce rapport. "
            "Veuillez relancer l'analyse IA depuis le tableau de bord SolarIntel."
        )
        for para in narrative.split("\n\n"):
            if para.strip():
                story.append(Paragraph(para.strip(), s["body"]))
                story.append(Spacer(1, 0.2 * cm))
        return story

    def _build_qr_code(self: "PDFReportGenerator") -> list:
        d = self.data
        s = self.styles
        story: list[Any] = [
            Spacer(1, 0.5 * cm),
            Paragraph("Tableau de Bord Interactif", s["section_title"]),
        ]
        if not d.qr_code_url:
            return story
        try:
            from app.reports.qr_generator import generate_qr_png
            qr_bytes = generate_qr_png(d.qr_code_url, box_size=5)
            qr_img = Image(io.BytesIO(qr_bytes), width=4 * cm, height=4 * cm)
            story.append(qr_img)
        except Exception:
            pass
        story.append(Paragraph(
            f"Tableau de bord en ligne: {d.qr_code_url}", s["body"]
        ))
        return story

    def _page_header_footer(self: "PDFReportGenerator", canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setStrokeColor(SOLAR_AMBER)
        canvas.setLineWidth(1.5)
        canvas.line(MARGIN, PAGE_H - MARGIN + 0.4 * cm,
                    PAGE_W - MARGIN, PAGE_H - MARGIN + 0.4 * cm)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(SOLAR_DARK)
        canvas.drawString(MARGIN, PAGE_H - MARGIN + 0.6 * cm, "SolarIntel v2")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(SOLAR_GRAY)
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - MARGIN + 0.6 * cm,
                               self.data.project_name)
        canvas.setStrokeColor(SOLAR_GRAY)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, MARGIN - 0.4 * cm, PAGE_W - MARGIN, MARGIN - 0.4 * cm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(SOLAR_GRAY)
        canvas.drawString(MARGIN, MARGIN - 0.7 * cm,
                          f"Rapport généré le {self.data.report_date} — Confidentiel")
        canvas.drawRightString(PAGE_W - MARGIN, MARGIN - 0.7 * cm, f"Page {doc.page}")
        canvas.restoreState()
