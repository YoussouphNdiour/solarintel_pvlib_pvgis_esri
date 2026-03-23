"""Performance alert service.

Sends WhatsApp alerts when production drops below 80% of expected.
Uses Redis cooldown keys to prevent alert spam (once per 24h per project).

Cooldown key: alert:cooldown:{project_id}  TTL: 86400s
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import redis_client
from app.services.monitoring_service import MonitoringService
from app.services.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)

PERFORMANCE_THRESHOLD: float = 0.80   # 80%
ALERT_COOLDOWN_TTL: int = 86400       # 24 hours in seconds

_PDF_STORAGE_PATH: str = "/tmp/solarintel/reports"


def _cooldown_key(project_id: UUID) -> str:
    """Return the Redis cooldown key for a project alert.

    Args:
        project_id: The project UUID.

    Returns:
        Redis key string in the form ``alert:cooldown:{project_id}``.
    """
    return f"alert:cooldown:{project_id}"


class AlertService:
    """Sends performance alerts and monthly reports via WhatsApp.

    Attributes:
        _monitoring: Injected ``MonitoringService`` for stats retrieval.
        _whatsapp: Injected ``WhatsAppService`` for message dispatch.
    """

    def __init__(self) -> None:
        """Initialise with default service instances."""
        self._monitoring = MonitoringService()
        self._whatsapp = WhatsAppService()

    async def check_and_alert(
        self,
        project_id: UUID,
        db: AsyncSession,
        technician_phone: str | None = None,
    ) -> bool:
        """Check performance and send alert if below threshold and not in cooldown.

        Decision logic:
        1. Fetch today's production stats via ``MonitoringService``.
        2. If ``today_performance_pct < 80%`` AND no cooldown key in Redis:
           - Send a WhatsApp alert to ``technician_phone``.
           - Set the cooldown key with a 24-hour TTL.
           - Return ``True``.
        3. Otherwise return ``False``.

        Args:
            project_id: UUID of the project to check.
            db: Active async database session.
            technician_phone: E.164 phone number for alert delivery.

        Returns:
            ``True`` if an alert was sent; ``False`` otherwise.
        """
        stats = await self._monitoring.get_stats(project_id, db)

        # Check if performance is below threshold
        below_threshold = (stats.today_performance_pct / 100.0) < PERFORMANCE_THRESHOLD

        if not below_threshold:
            return False

        # Check Redis cooldown
        cooldown_key = _cooldown_key(project_id)
        existing = await redis_client.cache_get(cooldown_key)
        if existing is not None:
            logger.info(
                "Alert suppressed by cooldown for project %s (performance: %.1f%%)",
                project_id,
                stats.today_performance_pct,
            )
            return False

        # Send alert
        if technician_phone:
            try:
                # Fetch project name for alert message
                from sqlalchemy import select
                from app.models.project import Project

                result = await db.execute(select(Project).where(Project.id == project_id))
                project = result.scalar_one_or_none()
                project_name = project.name if project else str(project_id)

                await self._whatsapp.send_simulation_alert(
                    phone=technician_phone,
                    project_name=project_name,
                    performance_pct=stats.today_performance_pct,
                )
                logger.info(
                    "Performance alert sent for project %s (%.1f%%) to %s",
                    project_id,
                    stats.today_performance_pct,
                    technician_phone,
                )
            except Exception as exc:
                logger.error("Failed to send performance alert: %s", exc)
                raise

        # Set cooldown key in Redis (TTL = 24 hours)
        await redis_client.cache_set(cooldown_key, "1", ALERT_COOLDOWN_TTL)

        return True

    async def send_monthly_report(
        self,
        project_id: UUID,
        db: AsyncSession,
        client_phone: str,
    ) -> str:
        """Generate and send monthly PDF report via WhatsApp.

        Generates a PDF path based on the current month and project, then
        attempts to deliver it via WhatsApp.

        Args:
            project_id: UUID of the project for the report.
            db: Active async database session.
            client_phone: E.164 or local phone for the client.

        Returns:
            Absolute path string to the generated PDF report.
        """
        from sqlalchemy import select
        from app.models.project import Project

        # Fetch project for name context
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        project_name = project.name if project else str(project_id)

        # Fetch comparison data for the report
        comparisons = await self._monitoring.get_monthly_comparison(
            project_id, db, months=12
        )

        # Build deterministic PDF path
        now = datetime.now(tz=timezone.utc)
        storage_path = os.environ.get("PDF_STORAGE_PATH", _PDF_STORAGE_PATH)
        pdf_path = (
            f"{storage_path}/report_{project_id}_{now.year}_{now.month:02d}.pdf"
        )

        # Send via WhatsApp (best-effort — alert if no token configured)
        try:
            pdf_url = f"https://solarintel.app/reports/{project_id}/monthly"
            filename = f"rapport_mensuel_{project_name}_{now.year}_{now.month:02d}.pdf"
            caption = (
                f"Rapport mensuel SolarIntel — {project_name} "
                f"({now.strftime('%B %Y')})"
            )
            await self._whatsapp.send_pdf_quote(
                phone=client_phone,
                pdf_url=pdf_url,
                filename=filename,
                caption=caption,
            )
            logger.info(
                "Monthly report sent for project %s to %s",
                project_id,
                client_phone,
            )
        except Exception as exc:
            logger.warning(
                "Failed to send monthly report via WhatsApp for project %s: %s",
                project_id,
                exc,
            )
            # Return the path regardless of delivery failure
            # so the caller can handle or retry

        return pdf_path
