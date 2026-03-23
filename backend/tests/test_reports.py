"""PDF-001 TDD test suite for SolarIntel v2 report generation.

Tests are organized into:
- Monte Carlo unit tests
- PDF generation tests (structural, no visual check)
- HTML generation tests
- QR code tests
- API endpoint tests

All tests run against an in-memory SQLite database via the shared
``async_session`` fixture from conftest.py.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

# ── Fixtures and helpers ──────────────────────────────────────────────────────


def _make_monthly_kwh() -> list[float]:
    """Return a realistic 12-month production list (kWh) for Dakar lat≈14.7."""
    return [
        380.0, 410.0, 510.0, 530.0, 490.0, 460.0,
        420.0, 440.0, 470.0, 490.0, 430.0, 360.0,
    ]


def _make_report_data() -> "Any":
    """Build a ReportData instance with realistic values for testing."""
    from app.reports.pdf_generator import ReportData
    from app.reports.monte_carlo import run_monte_carlo, run_sensitivity_analysis

    monthly = _make_monthly_kwh()
    annual = sum(monthly)
    mc = run_monte_carlo(annual, monthly, n_samples=100, seed=42)
    sens = run_sensitivity_analysis(
        base_annual_savings_xof=600_000.0,
        installation_cost_xof=5_000_000.0,
    )

    return ReportData(
        project_name="Test Projet Dakar",
        latitude=14.7167,
        longitude=-17.4677,
        address="Dakar, Sénégal",
        installer_name="SolarIntel SARL",
        client_name="Client Test",
        report_date=str(date.today()),
        panel_count=10,
        peak_kwc=5.45,
        annual_kwh=annual,
        specific_yield=1062.0,
        performance_ratio=0.82,
        monthly_kwh=monthly,
        monthly_irradiance=[5.8, 6.2, 7.1, 7.4, 6.9, 6.5, 6.1, 6.3, 6.7, 6.9, 6.1, 5.5],
        panel_model="JA Solar JAM72S30 545W",
        inverter_model="Huawei SUN2000-5KTL",
        inverter_kva=5.0,
        battery_model=None,
        system_type="on-grid",
        installation_cost_xof=5_000_000.0,
        annual_savings_xof=600_000.0,
        payback_years=8.3,
        roi_25yr_pct=200.0,
        monthly_savings=[50_000.0] * 12,
        monte_carlo=mc,
        sensitivity=sens,
        qa_criteria=[
            {
                "code": "V1",
                "label": "Taux de couverture solaire",
                "status": "PASS",
                "value": 85.0,
                "threshold": ">= 70%",
                "comment": "Bonne couverture solaire.",
            }
        ],
        report_narrative=(
            "Ce système photovoltaïque de 5,45 kWc installé à Dakar produit "
            "environ 5 390 kWh par an, couvrant 85% de la consommation."
        ),
        satellite_image_base64=None,
        qr_code_url="https://solarintel.app/dashboard/test-sim-id",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Monte Carlo unit tests
# ─────────────────────────────────────────────────────────────────────────────


class TestMonteCarlo:
    def test_monte_carlo_returns_1000_samples(self) -> None:
        """N=1000 samples must be generated and stored in the result."""
        from app.reports.monte_carlo import run_monte_carlo

        monthly = _make_monthly_kwh()
        result = run_monte_carlo(
            base_annual_kwh=sum(monthly),
            monthly_kwh=monthly,
            n_samples=1000,
            seed=42,
        )
        assert result.n_samples == 1000

    def test_monte_carlo_confidence_interval(self) -> None:
        """P10/P50/P90 must each be within ±20% of the base annual value."""
        from app.reports.monte_carlo import run_monte_carlo

        monthly = _make_monthly_kwh()
        base = sum(monthly)
        result = run_monte_carlo(base_annual_kwh=base, monthly_kwh=monthly, seed=42)

        tolerance = 0.20
        assert abs(result.annual_p10 - base) / base <= tolerance, (
            f"P10 {result.annual_p10:.1f} deviates > 20% from base {base:.1f}"
        )
        assert abs(result.annual_p50 - base) / base <= tolerance, (
            f"P50 {result.annual_p50:.1f} deviates > 20% from base {base:.1f}"
        )
        assert abs(result.annual_p90 - base) / base <= tolerance, (
            f"P90 {result.annual_p90:.1f} deviates > 20% from base {base:.1f}"
        )
        # P10 <= P50 <= P90 ordering
        assert result.annual_p10 <= result.annual_p50 <= result.annual_p90

    def test_monte_carlo_annual_distribution(self) -> None:
        """Mean of simulated annual values must be within ±10% of base_annual_kwh."""
        import numpy as np

        from app.reports.monte_carlo import run_monte_carlo

        monthly = _make_monthly_kwh()
        base = sum(monthly)
        result = run_monte_carlo(base_annual_kwh=base, monthly_kwh=monthly, seed=42)

        # P50 is the median; for a symmetric distribution close to base
        relative_error = abs(result.annual_p50 - base) / base
        assert relative_error <= 0.10, (
            f"P50 (median) {result.annual_p50:.1f} deviates > 10% from base {base:.1f}"
        )

    def test_sensitivity_price_scenarios(self) -> None:
        """Six price scenarios (±10/20/30%) must all return valid ROI values."""
        from app.reports.monte_carlo import run_sensitivity_analysis

        results = run_sensitivity_analysis(
            base_annual_savings_xof=600_000.0,
            installation_cost_xof=5_000_000.0,
        )

        expected_changes = {-30.0, -20.0, -10.0, 10.0, 20.0, 30.0}
        returned_changes = {r.price_change_pct for r in results}
        assert expected_changes == returned_changes, (
            f"Expected price changes {expected_changes}, got {returned_changes}"
        )

        for r in results:
            assert isinstance(r.roi_25yr_pct, float), "roi_25yr_pct must be a float"
            assert isinstance(r.payback_years, float), "payback_years must be a float"
            assert isinstance(r.annual_savings_xof, float)
            # Positive price change → positive savings (cannot go to zero from +10%)
            if r.price_change_pct > 0:
                assert r.annual_savings_xof > 0, (
                    f"Positive price change should yield positive savings: {r}"
                )


# ─────────────────────────────────────────────────────────────────────────────
# PDF generation tests
# ─────────────────────────────────────────────────────────────────────────────


class TestPDFGeneration:
    def test_pdf_generates_without_error(self) -> None:
        """generate() must return bytes with length > 10_000."""
        from app.reports.pdf_generator import PDFReportGenerator

        data = _make_report_data()
        gen = PDFReportGenerator(data)
        pdf_bytes = gen.generate()

        assert isinstance(pdf_bytes, bytes), "generate() must return bytes"
        assert len(pdf_bytes) > 10_000, (
            f"PDF too small: {len(pdf_bytes)} bytes (expected > 10 000)"
        )

    def test_pdf_contains_required_sections(self) -> None:
        """PDF content must contain 'Production', 'SENELEC', and 'ROI'.

        Uses pdfminer.six to extract text from all pages of the generated PDF
        and checks for the presence of required section headings.
        """
        import io

        from pdfminer.high_level import extract_text

        from app.reports.pdf_generator import PDFReportGenerator

        data = _make_report_data()
        gen = PDFReportGenerator(data)
        pdf_bytes = gen.generate()

        extracted = extract_text(io.BytesIO(pdf_bytes))
        upper = extracted.upper()

        assert "PRODUCTION" in upper, (
            f"PDF text must contain 'Production'. Extracted (first 500 chars): "
            f"{extracted[:500]!r}"
        )
        assert "SENELEC" in upper, (
            "PDF text must contain 'SENELEC'."
        )
        assert "ROI" in upper, (
            "PDF text must contain 'ROI'."
        )

    def test_pdf_filename_format(self) -> None:
        """Filename helper must return pattern solarintel_report_{id}_{date}.pdf."""
        from app.reports.pdf_generator import get_report_filename

        report_id = uuid.uuid4()
        filename = get_report_filename(report_id)

        assert filename.startswith("solarintel_report_"), (
            f"Filename must start with 'solarintel_report_': {filename}"
        )
        assert filename.endswith(".pdf"), f"Filename must end with '.pdf': {filename}"

        # Pattern: solarintel_report_{uuid}_{YYYYMMDD}.pdf
        parts = filename.replace("solarintel_report_", "").replace(".pdf", "").split("_")
        assert len(parts) == 2, (
            f"Expected exactly 2 parts after stripping prefix/suffix, got {parts}"
        )
        date_part = parts[1]
        assert len(date_part) == 8 and date_part.isdigit(), (
            f"Date part must be 8 digits (YYYYMMDD), got '{date_part}'"
        )


# ─────────────────────────────────────────────────────────────────────────────
# HTML generation tests
# ─────────────────────────────────────────────────────────────────────────────


class TestHTMLGeneration:
    def test_html_generates_without_error(self) -> None:
        """generate_html_report() must return a non-empty string."""
        from app.reports.html_generator import generate_html_report

        data = _make_report_data()
        html = generate_html_report(data)

        assert isinstance(html, str), "generate_html_report() must return str"
        assert len(html) > 0, "HTML output must not be empty"

    def test_html_contains_chartjs(self) -> None:
        """HTML output must include the Chart.js CDN script tag."""
        from app.reports.html_generator import generate_html_report

        data = _make_report_data()
        html = generate_html_report(data)

        assert "chart.js" in html.lower(), (
            "HTML must reference chart.js CDN (case-insensitive)"
        )

    def test_html_contains_monthly_data(self) -> None:
        """HTML must embed JSON data for all 12 months."""
        import json
        import re

        from app.reports.html_generator import generate_html_report

        data = _make_report_data()
        html = generate_html_report(data)

        # The monthly data should appear as a JSON array with 12 numbers
        # Find any JSON array of 12 numeric values
        json_array_pattern = re.compile(r"\[[\s\d.,]+\]")
        matches = json_array_pattern.findall(html)

        found_12_month_array = False
        for match in matches:
            try:
                parsed = json.loads(match)
                if isinstance(parsed, list) and len(parsed) == 12:
                    found_12_month_array = True
                    break
            except (json.JSONDecodeError, ValueError):
                continue

        assert found_12_month_array, (
            "HTML must embed a JSON array with exactly 12 monthly values"
        )


# ─────────────────────────────────────────────────────────────────────────────
# QR code tests
# ─────────────────────────────────────────────────────────────────────────────


class TestQRCode:
    def test_qr_code_generates_png_bytes(self) -> None:
        """generate_qr_png() must return bytes whose first 4 bytes are PNG magic."""
        from app.reports.qr_generator import generate_qr_png

        url = "https://solarintel.app/dashboard/test-123"
        png_bytes = generate_qr_png(url)

        assert isinstance(png_bytes, bytes), "generate_qr_png() must return bytes"
        assert len(png_bytes) > 0, "QR PNG bytes must not be empty"

        # PNG magic bytes: 0x89 0x50 0x4E 0x47 (i.e. b'\x89PNG')
        png_magic = b"\x89PNG"
        assert png_bytes[:4] == png_magic, (
            f"First 4 bytes must be PNG magic {png_magic!r}, "
            f"got {png_bytes[:4]!r}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# API endpoint tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture()
async def seeded_simulation(async_session: Any) -> tuple[Any, Any]:
    """Insert a User, Project, and Simulation into the test DB. Returns (user, sim)."""
    from app.models.project import Project
    from app.models.simulation import Simulation
    from app.models.user import User

    user = User.create(
        email="test@example.com",
        role="technicien",
        hashed_password="hashed",
        full_name="Test User",
    )
    async_session.add(user)
    await async_session.flush()

    project = Project.create(
        user_id=user.id,
        name="Projet Dakar",
        latitude=14.7167,
        longitude=-17.4677,
        address="Dakar, Sénégal",
    )
    async_session.add(project)
    await async_session.flush()

    monthly_data = [
        {
            "month": i + 1,
            "energy_kwh": 400.0 + i * 10,
            "irradiance_kwh_m2": 6.0,
            "performance_ratio": 0.82,
        }
        for i in range(12)
    ]
    sim = Simulation.create(
        project_id=project.id,
        panel_count=10,
        peak_kwc=5.45,
        annual_kwh=sum(m["energy_kwh"] for m in monthly_data),
        specific_yield=1062.0,
        performance_ratio=0.82,
        monthly_data=monthly_data,
        senelec_savings_xof=600_000.0,
        payback_years=8.3,
        roi_percent=200.0,
        status="completed",
    )
    async_session.add(sim)
    await async_session.commit()
    return user, sim


def _make_app(async_session: Any, user: Any) -> FastAPI:
    """Build a FastAPI app with overridden DB session and current user."""
    from app.core.security import get_current_user
    from app.db.session import get_async_db
    from app.main import app

    async def override_get_current_user():
        return user

    async def override_get_async_db():
        yield async_session

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_async_db] = override_get_async_db
    return app


class TestReportAPIEndpoints:
    async def test_post_report_authenticated(
        self,
        async_session: Any,
        seeded_simulation: tuple[Any, Any],
    ) -> None:
        """POST /api/v2/reports → 202 with report_id in body."""
        user, sim = seeded_simulation
        app = _make_app(async_session, user)

        from app.services import report_service as rs_module

        with patch.object(rs_module.ReportService, "create_report", new_callable=AsyncMock):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/v2/reports",
                    json={"simulation_id": str(sim.id)},
                    headers={"Authorization": "Bearer fake-token"},
                )

        assert response.status_code == 202, (
            f"Expected 202, got {response.status_code}: {response.text}"
        )
        body = response.json()
        assert "reportId" in body, f"Response must contain 'reportId': {body}"
        assert body["status"] == "pending", f"Initial status must be 'pending': {body}"

    async def test_get_report_status(
        self,
        async_session: Any,
        seeded_simulation: tuple[Any, Any],
    ) -> None:
        """GET /api/v2/reports/{id} → returns status field."""
        from app.models.report import Report

        user, sim = seeded_simulation
        report = Report.create(simulation_id=sim.id, status="pending")
        async_session.add(report)
        await async_session.commit()

        app = _make_app(async_session, user)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                f"/api/v2/reports/{report.id}",
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        body = response.json()
        assert "status" in body, f"Response must contain 'status': {body}"
        assert body["status"] in ("pending", "generating", "ready", "failed")

    async def test_download_report_pdf(
        self,
        async_session: Any,
        seeded_simulation: tuple[Any, Any],
        tmp_path: Any,
    ) -> None:
        """GET /api/v2/reports/{id}/download → 200 with binary PDF content."""
        from app.models.report import Report

        user, sim = seeded_simulation

        pdf_content = b"%PDF-1.4 fake pdf content for testing" + b"\x00" * 10_050
        pdf_file = tmp_path / "report.pdf"
        pdf_file.write_bytes(pdf_content)

        report = Report.create(
            simulation_id=sim.id,
            status="ready",
            pdf_path=str(pdf_file),
        )
        async_session.add(report)
        await async_session.commit()

        app = _make_app(async_session, user)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                f"/api/v2/reports/{report.id}/download",
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        assert "pdf" in response.headers.get("content-type", "").lower(), (
            f"Content-Type must indicate PDF: {response.headers.get('content-type')}"
        )

    async def test_report_wrong_user_forbidden(
        self,
        async_session: Any,
        seeded_simulation: tuple[Any, Any],
    ) -> None:
        """GET /api/v2/reports/{id} → 404 when report belongs to another user."""
        from app.models.report import Report
        from app.models.user import User

        user, sim = seeded_simulation
        report = Report.create(simulation_id=sim.id, status="ready")
        async_session.add(report)
        await async_session.commit()

        # Authenticate as a completely different user with a fresh UUID
        other_user = User.create(
            email="other@example.com",
            role="technicien",
            hashed_password="hashed",
        )
        other_app = _make_app(async_session, other_user)

        async with AsyncClient(
            transport=ASGITransport(app=other_app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                f"/api/v2/reports/{report.id}",
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 404, (
            f"Expected 404 for wrong user, got {response.status_code}: {response.text}"
        )
