# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies for packages with C extensions (psycopg2, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install dependencies into a prefix directory for clean copying
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install only runtime shared libraries needed by C extensions and health check
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

# Create non-root user for security
RUN addgroup --system appuser && adduser --system --ingroup appuser appuser
RUN chown -R appuser:appuser /app

# Create PDF output directory
RUN mkdir -p /tmp/solarintel/reports && chown -R appuser:appuser /tmp/solarintel

USER appuser

# Expose API port
EXPOSE 8000

# Health check used by Docker Compose and Railway
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/api/v2/health || exit 1

# OCI image labels
LABEL org.opencontainers.image.source="https://github.com/${{ github.repository }}"
LABEL org.opencontainers.image.version="${BUILD_VERSION:-0.0.0}"

# Production command: uvicorn with multiple workers
# Render injects $PORT; default to 8000 for local Docker Compose
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --log-level info"]
