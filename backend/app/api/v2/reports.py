"""PDF-001: Report generation API endpoints for SolarIntel v2.

Provides:
- POST /api/v2/reports              — trigger async report generation (202)
- GET  /api/v2/reports/{id}         — poll report status
- GET  /api/v2/reports/{id}/download — stream the generated PDF
- GET  /api/v2/reports/{id}/html     — return the interactive HTML report

All endpoints require a valid Bearer token. Reports are scoped to the
authenticated user: the source Simulation's owning Project must belong to
``current_user``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_async_db
from app.models.project import Project
from app.models.report import Report
from app.models.simulation import Simulation
from app.models.user import User
from app.schemas.report import ReportCreateResponse, ReportRequest, ReportStatusResponse
from app.services.report_service import ReportService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["reports"])

_report_service = ReportService()


# ── Helper ─────────────────────────────────────────────────────────────────────


async def _get_user_report(
    report_id: UUID,
    current_user: User,
    db: AsyncSession,
) -> Report:
    """Fetch a Report owned by current_user, or raise 404."""
    result = await db.execute(
        select(Report)
        .join(Simulation, Report.simulation_id == Simulation.id)
        .join(Project, Simulation.project_id == Project.id)
        .where(
            Report.id == report_id,
            Project.user_id == current_user.id,
        )
    )
    report: Report | None = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found or access denied.",
        )
    return report


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=ReportCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger asynchronous report generation",
)
async def create_report(
    body: ReportRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> ReportCreateResponse:
    """Accept the request and schedule background report generation."""
    # ── 1. Verify simulation ownership ────────────────────────────────────────
    sim_result = await db.execute(
        select(Simulation)
        .join(Project, Simulation.project_id == Project.id)
        .where(
            Simulation.id == body.simulation_id,
            Project.user_id == current_user.id,
        )
    )
    simulation: Simulation | None = sim_result.scalar_one_or_none()
    if simulation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation not found or access denied.",
        )

    # ── 2. Prevent duplicate reports ──────────────────────────────────────────
    existing = await db.execute(
        select(Report).where(Report.simulation_id == body.simulation_id)
    )
    existing_report: Report | None = existing.scalar_one_or_none()
    if existing_report is not None:
        # Return the existing report_id so the client can poll it
        return ReportCreateResponse(
            reportId=existing_report.id,
            status=existing_report.status,
            message="Un rapport existe déjà pour cette simulation.",
        )

    # ── 3. Create pending Report record ───────────────────────────────────────
    report = Report.create(simulation_id=body.simulation_id, status="pending")
    db.add(report)
    await db.flush()

    dashboard_url = body.dashboard_url or "https://solarintel.app"

    # ── 4. Schedule background generation ─────────────────────────────────────
    background_tasks.add_task(
        _run_report_in_background,
        report_id=report.id,
        simulation_id=body.simulation_id,
        dashboard_base_url=dashboard_url,
        client_name=body.client_name,
        installer_name=body.installer_name,
    )

    logger.info(
        "Report %s scheduled for simulation %s by user %s",
        report.id,
        body.simulation_id,
        current_user.id,
    )

    return ReportCreateResponse(
        reportId=report.id,
        status="pending",
        message="Génération du rapport acceptée. Consultez le statut via GET /reports/{id}.",
    )


async def _run_report_in_background(
    report_id: UUID,
    simulation_id: UUID,
    dashboard_base_url: str,
    client_name: str | None,
    installer_name: str | None,
) -> None:
    """Background task wrapper: open a new DB session and generate the report.

    FastAPI background tasks run outside the request's session scope, so we
    must create an independent session here.
    """
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        try:
            await _report_service.create_report(
                report_id=report_id,
                simulation_id=simulation_id,
                db=session,
                dashboard_base_url=dashboard_base_url,
                client_name=client_name,
                installer_name=installer_name,
            )
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Background report generation failed: report=%s", report_id)


@router.get(
    "",
    response_model=list[ReportStatusResponse],
    summary="List reports for a simulation",
)
async def list_reports_by_simulation(
    simulation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> list[ReportStatusResponse]:
    """Return all reports for a simulation owned by the current user."""
    result = await db.execute(
        select(Report)
        .join(Simulation, Report.simulation_id == Simulation.id)
        .join(Project, Simulation.project_id == Project.id)
        .where(
            Report.simulation_id == simulation_id,
            Project.user_id == current_user.id,
        )
        .order_by(Report.created_at.desc())
    )
    reports = list(result.scalars().all())
    return [ReportStatusResponse.model_validate(r) for r in reports]


@router.get(
    "/{report_id}",
    response_model=ReportStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Poll report generation status",
)
async def get_report_status(
    report_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> ReportStatusResponse:
    """Return the current generation status of a Report."""
    report = await _get_user_report(report_id, current_user, db)
    return ReportStatusResponse.model_validate(report)


@router.get(
    "/{report_id}/download",
    summary="Download the generated PDF report",
)
async def download_report_pdf(
    report_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> FileResponse:
    """Stream the generated PDF; 404 if not yet ready."""
    report = await _get_user_report(report_id, current_user, db)

    if report.status != "ready" or not report.pdf_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Le rapport n'est pas encore disponible. "
                f"Statut actuel: {report.status}."
            ),
        )

    pdf_path = Path(report.pdf_path)
    if not pdf_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Le fichier PDF est introuvable sur le serveur.",
        )

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=pdf_path.name,
        headers={
            "Content-Disposition": f'attachment; filename="{pdf_path.name}"',
        },
    )


@router.get(
    "/{report_id}/html",
    summary="Return the interactive HTML report",
)
async def download_report_html(
    report_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> HTMLResponse:
    """Return the interactive HTML report; 404 if not yet ready."""
    report = await _get_user_report(report_id, current_user, db)

    if report.status != "ready" or not report.html_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Le rapport HTML n'est pas encore disponible. "
                f"Statut actuel: {report.status}."
            ),
        )

    html_path = Path(report.html_path)
    if not html_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Le fichier HTML est introuvable sur le serveur.",
        )

    html_content = html_path.read_text(encoding="utf-8")
    return HTMLResponse(content=html_content, status_code=200)
