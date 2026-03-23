# DEVOPS-001: Production Deployment & Observability Implementation

**Status**: COMPLETE
**Date**: 2026-03-23
**Scope**: SolarIntel v2 — Complete CI/CD, Railway deployment, and Prometheus observability stack

---

## Summary

Implemented a production-grade DevOps stack for SolarIntel v2 with:

1. **Railway.app Deployment Configuration** — Streamlined cloud deployment for both backend and frontend
2. **Prometheus Observability** — Comprehensive metrics instrumentation and monitoring dashboard
3. **Enhanced CI/CD Pipeline** — Security scanning, testing, Docker builds, and automated Railway deployments
4. **Sentry Integration** — Optional error tracking and performance monitoring
5. **Monitoring Stack** — Prometheus + Grafana for local development and observability

---

## Files Implemented

### 1. Railway Configuration
**File**: `/railway.toml`

Configures Railway.app to:
- Build backend using Dockerfile
- Build frontend using Nixpacks (npm ci + npm run build)
- Start backend on `$PORT` environment variable
- Health check via `/api/v2/health` endpoint
- Auto-restart on failure (max 3 retries)

**Key Feature**: Uses Railway's injected `$PORT` variable for dynamic port assignment.

### 2. Prometheus Telemetry Module
**File**: `/backend/app/core/telemetry.py` (102 lines)

Exports metrics via `/metrics` endpoint:

```
REQUEST_COUNT             Counter  http_requests_total{method, endpoint, status_code}
REQUEST_DURATION          Histogram http_request_duration_seconds{method, endpoint}
WS_CONNECTIONS            Gauge     active_websocket_connections{project_id}
SIMULATION_RUNS           Counter   simulation_runs_total{status}
PVGIS_CACHE_HITS          Counter   pvgis_cache_hits_total
PVGIS_CACHE_MISSES        Counter   pvgis_cache_misses_total
DB_POOL_SIZE              Gauge     db_pool_size
REDIS_CONNECTED           Gauge     redis_connected (0 or 1)
```

**Key Features**:
- `PrometheusMiddleware` records all HTTP request metrics
- Normalizes UUID path segments to `{id}` to reduce cardinality
- Skips recording for `/metrics` and `/health` to avoid circular metrics
- Histogram buckets optimized for typical web service latencies

### 3. Updated FastAPI Application
**File**: `/backend/app/main.py` (modified)

**Changes**:
- Added `PrometheusMiddleware` after CORS middleware
- Added `/metrics` endpoint (no auth, returns Prometheus text format)
- Added Sentry initialization in lifespan if `SENTRY_DSN` is set
- Conditional Sentry setup with trace sampling (10% in production, 100% in development)

### 4. Enhanced CI/CD Workflow
**File**: `/.github/workflows/ci.yml` (rewritten, 313 lines)

**Jobs**:

| Job | Purpose | Triggers |
|-----|---------|----------|
| `backend-lint` | Ruff + mypy type checking | All PRs + pushes |
| `backend-test` | pytest with 85% coverage + codecov upload | All PRs + pushes |
| `backend-sast` | bandit + pip-audit security scanning | All PRs + pushes |
| `frontend-quality` | TypeScript + ESLint + Prettier | All PRs + pushes |
| `frontend-build` | Build verification (dist/ directory) | All PRs + pushes |
| `docker-build` | Build + push to GHCR (main branch only) | main branch pushes |
| `deploy-railway` | Deploy to Railway via CLI | main branch pushes |
| `ci-success` | Gate job (all must pass) | All workflows |

**Test Environment** (backend-test):
```env
DATABASE_URL = postgresql+asyncpg://solarintel:solarintel_test@localhost:5432/solarintel_test
REDIS_URL = redis://localhost:6379/0
SECRET_KEY = ci-secret-key-32-characters-long-x
ANTHROPIC_API_KEY = sk-ant-placeholder
ARCGIS_API_KEY = placeholder
ENVIRONMENT = development
```

Services: PostgreSQL 16 + Redis 7 (auto-health-check)

**Docker Build**:
- Uses BuildKit for layer caching
- Tags: `sha-{short_sha}` + `main` (only on main branch)
- Pushes to GHCR: `ghcr.io/{repository}/backend`

**Railway Deployment**:
- Requires `RAILWAY_TOKEN` secret
- Runs `railway up --service backend` after docker-build succeeds
- Only on `main` branch push events

### 5. Updated Dockerfile
**File**: `/backend/Dockerfile` (modified)

**Changes**:
- Added `curl` to runtime image for health check
- Changed user from `solarintel` to `appuser` (standard non-root user)
- Updated HEALTHCHECK to use `curl` instead of httpx (more reliable)
- Added OCI image labels:
  - `org.opencontainers.image.source`
  - `org.opencontainers.image.version`

### 6. Enhanced Requirements
**File**: `/backend/requirements.txt` (modified)

**Added**:
```
prometheus-client>=0.20.0    # Prometheus metrics instrumentation
sentry-sdk[fastapi]>=2.0.0   # Sentry error tracking + FastAPI integration
```

Both are optional (graceful fallback if not installed).

### 7. Docker Compose Monitoring Stack
**File**: `/docker-compose.yml` (modified)

**New Services** (profiles: `monitoring`):
```yaml
prometheus:
  image: prom/prometheus:latest
  ports: [9090:9090]
  volumes: [./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml]
  profiles: [monitoring]

grafana:
  image: grafana/grafana:latest
  ports: [3001:3000]
  environment: {GF_SECURITY_ADMIN_PASSWORD: solarintel}
  profiles: [monitoring]
  depends_on: [prometheus]
```

**New Volumes**:
- `prometheus_data` — 30-day retention
- `grafana_data` — Grafana state

**Usage**:
```bash
# Start with monitoring stack:
docker compose --profile monitoring up

# Without monitoring (default):
docker compose up
```

### 8. Prometheus Configuration
**File**: `/monitoring/prometheus.yml` (new)

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'solarintel-backend'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: /metrics
    scrape_interval: 10s
```

Scrapes metrics from backend every 10 seconds.

### 9. Grafana Provisioning
**Files**:
- `/monitoring/grafana/provisioning/datasources/prometheus.yml`
- `/monitoring/grafana/provisioning/dashboards/provisioning.yml`
- `/monitoring/grafana/provisioning/dashboards/solarintel.json`

**Pre-configured**:
- Prometheus data source pointing to `http://prometheus:9090`
- Auto-imports `solarintel.json` dashboard on startup
- No manual setup required

### 10. Grafana Dashboard
**File**: `/monitoring/grafana/provisioning/dashboards/solarintel.json` (1,000+ lines)

**Panels** (6 total):

| Panel | Metric | Visualization |
|-------|--------|---|
| **API Request Rate** | `rate(http_requests_total[1m])` | Time series with table legend |
| **API Latency (P50/P95/P99)** | `histogram_quantile(...)` | Time series with thresholds (yellow@500ms, red@2000ms) |
| **HTTP 5xx Error Rate** | `rate(http_requests_total{status_code=~"5.."}[1m])` | Time series with alert threshold |
| **Active WebSocket Connections** | `active_websocket_connections` | Time series by project_id |
| **Simulation Runs (by Status)** | `rate(simulation_runs_total[1m])` | Time series (success/error/cache_hit) |
| **PVGIS Cache Hit Rate** | `(hits / (hits + misses)) * 100` | Gauge with thresholds (red<50%, yellow<80%, green>=80%) |

**Features**:
- 1-hour time window, 30-second refresh
- Color-coded thresholds for SLO tracking
- Automatic legend with mean/max/min calculations
- Multi-series support with legend tables

---

## Usage & Deployment

### Local Development with Monitoring

```bash
# Start full stack with Prometheus + Grafana
docker compose --profile monitoring up --build

# Services available:
# - Backend: http://localhost:8000
# - Frontend: http://localhost:5173
# - Prometheus: http://localhost:9090
# - Grafana: http://localhost:3001 (admin/solarintel)
```

### View Metrics

**Direct Prometheus Export**:
```bash
curl http://localhost:8000/metrics
```

**Grafana Dashboard**:
1. Open http://localhost:3001
2. Login: `admin` / `solarintel`
3. Navigate to "SolarIntel v2 — API & Simulation Dashboard"

### CI/CD Pipeline

**Automatic on push**:
1. All linting & type checks (backend + frontend)
2. Security scanning (bandit, pip-audit)
3. Unit tests with coverage (85% threshold)
4. Docker build to GHCR (main branch only)
5. Deploy to Railway (main branch only)

**Manual intervention points**:
- PR approval before merge to main
- Railway deployment happens automatically after successful build

### Railway Deployment

**One-time setup**:
```bash
# Get Railway token from https://railway.app/account/tokens
export RAILWAY_TOKEN=<your-token>

# Add to GitHub repository secrets as RAILWAY_TOKEN
```

**Automatic deployment**:
- Every push to `main` automatically deploys to Railway
- Health check validates `/api/v2/health` before marking deployment healthy
- Auto-restart on failure (max 3 retries)

---

## Observability Features

### What's Tracked

**Request Metrics**:
- Count by method, endpoint, status code
- Duration histogram with P50/P95/P99 latency

**Application Metrics**:
- Active WebSocket connections per project
- Simulation run counts by status (success/error/cache_hit)
- PVGIS cache hit/miss rate
- Database pool size
- Redis connection status

**Error Tracking** (optional, via Sentry):
- Unhandled exceptions
- Performance issues (slow endpoints)
- Error rate alerts
- Environment-specific error grouping

### Metrics Endpoint

**Prometheus text format** (standard):
```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{endpoint="/api/v2/projects",method="GET",status_code="200"} 127
http_requests_total{endpoint="/api/v2/projects",method="POST",status_code="201"} 14
...
```

**No authentication required** — secure via network policy in production.

---

## Security & Best Practices

### Implemented

✅ Non-root Docker user (`appuser`)
✅ Health check HTTP endpoint (for orchestrators)
✅ OCI image labels for supply chain tracking
✅ Secrets via GitHub Actions secret references
✅ Environment-based configuration (no hardcoded secrets)
✅ SAST scanning (bandit, pip-audit)
✅ Dependency audit (pip-audit)
✅ Type safety enforcement (mypy --strict)

### Recommendations for Production

1. **Network Policy**: Restrict `/metrics` access to internal Prometheus only
2. **Sentry**: Set `SENTRY_DSN` in Railway environment for error tracking
3. **Alerting**: Configure Grafana alerts for:
   - HTTP 5xx error rate > 1%
   - API P95 latency > 2s
   - Active WebSocket connections > threshold
4. **Retention**: Adjust Prometheus retention (currently 30 days)
5. **RBAC**: Lock down Railway environment variables to deployment role

---

## File Locations

```
/Users/yusper/Downloads/solarintelV2/

├── railway.toml                                          # Railway config
├── backend/
│   ├── Dockerfile                                        # Updated (curl, appuser, labels)
│   ├── requirements.txt                                  # Updated (prometheus, sentry)
│   ├── app/
│   │   ├── main.py                                       # Updated (telemetry, sentry, /metrics)
│   │   └── core/
│   │       └── telemetry.py                             # NEW (Prometheus middleware)
├── .github/workflows/
│   └── ci.yml                                           # Rewritten (7 jobs, GHCR + Railway)
├── docker-compose.yml                                   # Updated (prometheus, grafana services)
└── monitoring/
    ├── prometheus.yml                                   # NEW (scrape config)
    └── grafana/provisioning/
        ├── datasources/
        │   └── prometheus.yml                           # NEW (data source config)
        └── dashboards/
            ├── provisioning.yml                         # NEW (dashboard loader)
            └── solarintel.json                          # NEW (6-panel dashboard)
```

---

## Testing the Implementation

### 1. Verify Telemetry Module
```bash
cd backend
python -c "from app.core.telemetry import PrometheusMiddleware; print('✓ Telemetry module loads')"
```

### 2. Check FastAPI Integration
```bash
cd backend
python -c "from app.main import app; print('✓ FastAPI app starts with telemetry')"
```

### 3. Test Prometheus JSON
```bash
# Validate Grafana dashboard JSON
python3 -m json.tool monitoring/grafana/provisioning/dashboards/solarintel.json > /dev/null
echo "✓ Dashboard JSON is valid"
```

### 4. Local Dev Stack
```bash
# Start with monitoring
docker compose --profile monitoring up --build

# In another terminal, trigger some API calls:
for i in {1..10}; do curl -s http://localhost:8000/api/v2/health; done

# View metrics
curl http://localhost:8000/metrics | head -20

# Open Grafana
open http://localhost:3001  # admin / solarintel
```

### 5. CI/CD Validation
- Create a PR → all CI gates should pass
- Merge to main → docker-build + deploy-railway jobs run
- Check GitHub Actions for deployment logs

---

## Secrets Configuration (GitHub)

**Required for CI/CD**:
```
RAILWAY_TOKEN = <your-railway-api-token>  # For deployment
```

**Optional for production**:
```
SENTRY_DSN = https://...@sentry.io/...    # Error tracking (set in Railway env vars)
```

---

## Troubleshooting

### Metrics endpoint returns 404
- Ensure `PrometheusMiddleware` is added to FastAPI app
- Check that `from prometheus_client import generate_latest` is imported

### Grafana dashboard shows "No Data"
- Verify Prometheus can scrape backend: http://localhost:9090/targets
- Check backend `/metrics` returns valid Prometheus text
- Ensure `backend` service is healthy: `docker compose ps`

### CI workflow fails on docker-build
- Check Docker BuildKit is available: `docker buildx version`
- Verify GHCR authentication: `docker login ghcr.io`
- Check Dockerfile syntax: `docker build --dry-run`

### Railway deployment hangs
- Verify `RAILWAY_TOKEN` is set in GitHub secrets
- Check Railway service can reach health endpoint
- View logs: `railway logs --service backend`

---

## Next Steps (Post-DEVOPS-001)

1. **INFRA-001**: Initialize SQLAlchemy async engine and Redis connection pool
2. **Monitor-001**: Set up Grafana alerts and notification channels
3. **Security-001**: Implement network policies for `/metrics` endpoint
4. **Performance-001**: Optimize histogram bucket sizes based on real data
5. **Scaling-001**: Configure Railway auto-scaling based on metrics

---

**Implementation by**: Deployment Engineer
**Last updated**: 2026-03-23
**Reviewed by**: DEVOPS-001 specification
