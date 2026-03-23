"""PDF-001: Report generation service for SolarIntel v2.

Orchestrates the full pipeline:
  1. Load Simulation + Project from the database.
  2. Load AI analysis from Redis cache (if available).
  3. Run Monte Carlo uncertainty analysis (N=1000, seed=42).
  4. Run sensitivity analysis for 6 electricity price scenarios.
  5. Build a ReportData container.
  6. Generate PDF and HTML concurrently.
  7. Persist files to {PDF_STORAGE_PATH}/{simulation_id}/.
  8. Generate QR code for the dashboard deep link.
  9. Update the Report record (status → "ready", paths set).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.project import Project
from app.models.report import Report
from app.models.simulation import Simulation
from app.reports.html_generator import generate_html_report
from app.reports.monte_carlo import run_monte_carlo, run_sensitivity_analysis
from app.reports.pdf_generator import PDFReportGenerator, ReportData

logger = logging.getLogger(__name__)


class ReportService:
    """Orchestrates PDF and HTML report generation for a Simulation."""

    async def create_report(
        self,
        report_id: UUID,
        simulation_id: UUID,
        db: AsyncSession,
        dashboard_base_url: str = "https://solarintel.app",
        client_name: str | None = None,
        installer_name: str | None = None,
    ) -> Report:
        """Execute the full report generation pipeline and persist results.

        Updates the Report record's status at each lifecycle stage so that
        callers polling ``GET /api/v2/reports/{id}`` can track progress.

        Args:
            report_id: UUID of the Report record to update throughout.
            simulation_id: UUID of the Simulation to build the report from.
            db: Async SQLAlchemy session.
            dashboard_base_url: Base URL for the QR code deep link.
            client_name: Optional client name override for the cover page.
            installer_name: Optional installer name override for the cover page.

        Returns:
            The updated Report record with status ``"ready"`` and file paths set.

        Raises:
            Exception: Any uncaught exception marks the report as ``"failed"``
                and re-raises to allow the caller to log it.
        """
        settings = get_settings()

        # ── Fetch Report record ────────────────────────────────────────────────
        result = await db.execute(select(Report).where(Report.id == report_id))
        report: Report | None = result.scalar_one_or_none()
        if report is None:
            raise ValueError(f"Report {report_id} not found in database.")

        try:
            # ── Update status → generating ─────────────────────────────────────
            report.status = "generating"
            await db.flush()

            # ── 1. Load Simulation + Project ───────────────────────────────────
            sim_result = await db.execute(
                select(Simulation)
                .join(Project, Simulation.project_id == Project.id)
                .where(Simulation.id == simulation_id)
            )
            sim: Simulation | None = sim_result.scalar_one_or_none()
            if sim is None:
                raise ValueError(f"Simulation {simulation_id} not found.")

            project = sim.project

            # ── 2. Extract monthly data ────────────────────────────────────────
            monthly_data = sim.monthly_data or []
            monthly_kwh = [float(m.get("energy_kwh", 0)) for m in monthly_data]
            monthly_irradiance = [
                float(m.get("irradiance_kwh_m2", 0)) for m in monthly_data
            ]
            # Pad to 12 months if necessary
            while len(monthly_kwh) < 12:
                monthly_kwh.append(0.0)
            while len(monthly_irradiance) < 12:
                monthly_irradiance.append(0.0)

            annual_kwh = sim.annual_kwh or sum(monthly_kwh)

            # ── 3. Run Monte Carlo ─────────────────────────────────────────────
            mc_result = run_monte_carlo(
                base_annual_kwh=annual_kwh,
                monthly_kwh=monthly_kwh[:12],
                n_samples=1000,
                seed=42,
            )

            # ── 4. Run Sensitivity Analysis ────────────────────────────────────
            sensitivity = run_sensitivity_analysis(
                base_annual_savings_xof=sim.senelec_savings_xof or 0.0,
                installation_cost_xof=(sim.params or {}).get(
                    "installation_cost_xof", 5_000_000.0
                ),
            )

            # ── 5. Derive monthly savings from senelec params ──────────────────
            annual_savings = sim.senelec_savings_xof or 0.0
            monthly_savings = [annual_savings / 12.0] * 12

            # ── 6. Build ReportData ────────────────────────────────────────────
            from datetime import date

            params = sim.params or {}
            report_data = ReportData(
                project_name=project.name,
                latitude=project.latitude,
                longitude=project.longitude,
                address=project.address,
                installer_name=installer_name or params.get("installer_name"),
                client_name=client_name or params.get("client_name"),
                report_date=str(date.today()),
                panel_count=sim.panel_count,
                peak_kwc=sim.peak_kwc,
                annual_kwh=annual_kwh,
                specific_yield=sim.specific_yield or 0.0,
                performance_ratio=sim.performance_ratio or 0.0,
                monthly_kwh=monthly_kwh[:12],
                monthly_irradiance=monthly_irradiance[:12],
                panel_model=params.get("panel_model", "JA Solar JAM72S30 545W"),
                inverter_model=params.get("inverter_model", "Huawei SUN2000"),
                inverter_kva=float(params.get("inverter_kva", sim.peak_kwc)),
                battery_model=params.get("battery_model"),
                system_type=params.get("system_type", "on-grid"),
                installation_cost_xof=float(
                    params.get("installation_cost_xof", 5_000_000.0)
                ),
                annual_savings_xof=annual_savings,
                payback_years=sim.payback_years or 0.0,
                roi_25yr_pct=sim.roi_percent or 0.0,
                monthly_savings=monthly_savings,
                monte_carlo=mc_result,
                sensitivity=sensitivity,
                qa_criteria=params.get("qa_criteria"),
                report_narrative=params.get("report_narrative"),
                satellite_image_base64=None,
                qr_code_url=f"{dashboard_base_url}/dashboard/{simulation_id}",
            )

            # ── 7. Generate PDF + HTML concurrently ────────────────────────────
            pdf_bytes, html_str = await asyncio.gather(
                asyncio.to_thread(self._generate_pdf, report_data),
                asyncio.to_thread(generate_html_report, report_data),
            )

            # ── 8. Persist files ───────────────────────────────────────────────
            storage_dir = Path(settings.pdf_storage_path) / str(simulation_id)
            storage_dir.mkdir(parents=True, exist_ok=True)

            pdf_path = storage_dir / "report.pdf"
            html_path = storage_dir / "report.html"

            pdf_path.write_bytes(pdf_bytes)
            html_path.write_text(html_str, encoding="utf-8")

            # ── 9. Update Report record → ready ───────────────────────────────
            report.status = "ready"
            report.pdf_path = str(pdf_path)
            report.html_path = str(html_path)
            report.generated_at = datetime.now(tz=timezone.utc)
            await db.flush()

            logger.info(
                "Report %s generated successfully for simulation %s",
                report_id,
                simulation_id,
            )
            return report

        except Exception as exc:
            logger.exception(
                "Report generation failed for simulation %s: %s",
                simulation_id,
                exc,
            )
            report.status = "failed"
            report.error_message = str(exc)[:500]
            await db.flush()
            raise

    @staticmethod
    def _generate_pdf(report_data: ReportData) -> bytes:
        """Synchronous PDF generation — run in a thread via asyncio.to_thread."""
        gen = PDFReportGenerator(report_data)
        return gen.generate()
