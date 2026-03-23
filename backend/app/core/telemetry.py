"""Prometheus metrics instrumentation for FastAPI.

Exposes /metrics endpoint with:
- http_requests_total (counter, labels: method, endpoint, status_code)
- http_request_duration_seconds (histogram, labels: method, endpoint)
- active_websocket_connections (gauge, labels: project_id)
- simulation_runs_total (counter, labels: status)
- pvgis_cache_hits_total (counter)
- pvgis_cache_misses_total (counter)
- db_pool_size (gauge)
- redis_connected (gauge, 0 or 1)
"""

import re
import time
from typing import Callable

from fastapi import Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware

# Define all metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)
WS_CONNECTIONS = Gauge(
    "active_websocket_connections",
    "Active WebSocket connections",
    ["project_id"],
)
SIMULATION_RUNS = Counter(
    "simulation_runs_total",
    "Total simulation runs",
    ["status"],  # "success" | "error" | "cache_hit"
)
PVGIS_CACHE_HITS = Counter("pvgis_cache_hits_total", "PVGIS cache hits")
PVGIS_CACHE_MISSES = Counter("pvgis_cache_misses_total", "PVGIS cache misses")
DB_POOL_SIZE = Gauge("db_pool_size", "Database connection pool size")
REDIS_CONNECTED = Gauge("redis_connected", "Redis connection status (0 or 1)")


def _normalize_path(path: str) -> str:
    """Replace UUID segments with {id} to reduce metric cardinality.

    Args:
        path: URL path to normalize.

    Returns:
        Normalized path with UUIDs replaced by {id}.
    """
    uuid_pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    return re.sub(uuid_pattern, "{id}", path)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Record request count and duration for all HTTP endpoints.

    Skips recording for /metrics and /health endpoints to avoid circular metrics.
    """

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """Record HTTP request metrics and pass to next middleware.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler callable.

        Returns:
            HTTP response from the handler.
        """
        # Skip metrics recording for /metrics and /health endpoints
        if request.url.path in {"/metrics", "/api/v2/health"}:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        # Normalize endpoint path (replace UUIDs with {id})
        path = _normalize_path(request.url.path)

        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=path,
            status_code=str(response.status_code),
        ).inc()
        REQUEST_DURATION.labels(
            method=request.method,
            endpoint=path,
        ).observe(duration)

        return response
