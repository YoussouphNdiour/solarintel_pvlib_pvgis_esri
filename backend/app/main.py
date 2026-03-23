"""SolarIntel v2 — FastAPI Application Entry Point.

Creates and configures the FastAPI application instance with:
- CORS middleware (configured from settings)
- Prometheus telemetry middleware
- /api/v2/ router
- OpenAPI 3.1 metadata
- Lifespan context manager for startup/shutdown events
- /api/v2/health endpoint (no auth required)
- /metrics endpoint (Prometheus metrics, no auth required)
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.api.v2.router import api_v2_router
from app.core.config import get_settings
from app.core.telemetry import PrometheusMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle.

    Startup:
        - Validate database connectivity
        - Initialise Redis connection pool
        - Initialise Sentry error tracking (if SENTRY_DSN is set)

    Shutdown:
        - Gracefully close database and Redis connections
    """
    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info(
        "Starting %s v%s [%s]",
        settings.app_name,
        settings.app_version,
        settings.environment,
    )

    # Initialise Sentry if DSN is provided
    if settings.sentry_dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.fastapi import FastApiIntegration
            from sentry_sdk.integrations.starlette import StarletteIntegration

            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                environment=settings.environment,
                integrations=[
                    StarletteIntegration(),
                    FastApiIntegration(),
                ],
                traces_sample_rate=0.1 if settings.is_production else 1.0,
            )
            logger.info("Sentry error tracking initialised")
        except ImportError:
            logger.warning("Sentry SDK not installed; skipping Sentry init")

    # TODO(INFRA-001): Initialise SQLAlchemy async engine and verify connection
    # TODO(INFRA-001): Initialise Redis connection pool

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("Shutting down %s", settings.app_name)
    # TODO(INFRA-001): Dispose SQLAlchemy engine
    # TODO(INFRA-001): Close Redis connection pool


def create_application() -> FastAPI:
    """Construct and configure the FastAPI application.

    Returns:
        Fully configured FastAPI instance ready to be served by uvicorn.
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "SolarIntel v2 API — PV sizing, simulation, and AI-powered "
            "recommendations for solar installers in West Africa."
        ),
        openapi_url="/api/v2/openapi.json",
        docs_url="/api/v2/docs",
        redoc_url="/api/v2/redoc",
        lifespan=lifespan,
    )

    # ── CORS Middleware ───────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Prometheus Telemetry Middleware ────────────────────────────────────────
    app.add_middleware(PrometheusMiddleware)

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(api_v2_router)

    # ── Health Check (no auth) ────────────────────────────────────────────────
    @app.get(
        "/api/v2/health",
        tags=["health"],
        summary="Health check",
        response_description="Service liveness status",
    )
    async def health_check() -> JSONResponse:
        """Return service health status.

        Used by Docker health checks and Railway health probes.
        Does not require authentication.

        Returns:
            JSON body ``{"status": "ok", "version": "<version>"}`` with HTTP 200.
        """
        return JSONResponse(
            content={
                "status": "ok",
                "version": settings.app_version,
                "environment": settings.environment,
            }
        )

    # ── Prometheus Metrics (no auth) ───────────────────────────────────────────
    @app.get(
        "/metrics",
        tags=["monitoring"],
        summary="Prometheus metrics",
        response_description="Prometheus text format metrics",
        responses={200: {"media_type": "text/plain"}},
    )
    async def metrics() -> Response:
        """Return Prometheus metrics in text format.

        Exposes all instrumented metrics:
        - HTTP request counts, duration, and status codes
        - Active WebSocket connections
        - Simulation run statistics
        - PVGIS cache hit rates
        - Database and Redis connection status

        Does not require authentication.

        Returns:
            Prometheus metrics in text/plain format.
        """
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    return app


app: FastAPI = create_application()


# ── Entry point for uvicorn ───────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # noqa: S104 — intentional for containerised runtime
        port=8000,
        reload=not settings.is_production,
        log_level="info",
    )
