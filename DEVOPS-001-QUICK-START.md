# DEVOPS-001 Quick Start Guide

## Local Development

### Start All Services
```bash
docker compose up --build
```

### Start with Monitoring (Prometheus + Grafana)
```bash
docker compose --profile monitoring up --build
```

### Access Points
| Service | URL | Auth |
|---------|-----|------|
| **Backend API** | http://localhost:8000 | None |
| **Backend Health** | http://localhost:8000/api/v2/health | None |
| **Metrics** | http://localhost:8000/metrics | None |
| **Swagger Docs** | http://localhost:8000/api/v2/docs | None |
| **Prometheus** | http://localhost:9090 | None |
| **Grafana** | http://localhost:3001 | admin / solarintel |
| **Frontend** | http://localhost:5173 | None |

## View Metrics

### Query Metrics in Prometheus
1. Open http://localhost:9090
2. Search for:
   - `http_requests_total` — total requests
   - `http_request_duration_seconds` — latency histograms
   - `simulation_runs_total` — PV simulations
   - `pvgis_cache_hits_total` — cache stats

### View Dashboard in Grafana
1. Open http://localhost:3001
2. Login: `admin` / `solarintel`
3. Select: **SolarIntel v2 — API & Simulation Dashboard**

## CI/CD Pipeline

### What Runs Automatically
- **On every push**: linting, type checks, tests, security scans
- **On push to main**: Docker build + push to GHCR + deploy to Railway

### View Pipeline Status
1. Go to GitHub repo → **Actions** tab
2. See latest workflow runs
3. Click workflow name to view details

### Common Issues

**Pipeline fails on tests**:
```bash
# Run tests locally before pushing
cd backend
pytest tests/ --cov=app --cov-fail-under=85
```

**Pipeline fails on linting**:
```bash
cd backend
ruff format .        # Auto-fix formatting
ruff check --fix .   # Auto-fix errors
```

**Pipeline fails on type checking**:
```bash
cd backend
mypy app --strict
```

## Railway Deployment

### First-time Setup
1. Get Railway token: https://railway.app/account/tokens
2. Add to GitHub repo secrets:
   - Name: `RAILWAY_TOKEN`
   - Value: `<your-token>`
3. Push to `main` branch → automatic deployment starts

### View Deployment
1. Open https://railway.app
2. Select SolarIntel project → Backend service
3. Check **Logs** tab for deployment status

### Environment Variables (in Railway)
```
ENVIRONMENT=production
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://...
SECRET_KEY=...
ANTHROPIC_API_KEY=...
ARCGIS_API_KEY=...
SENTRY_DSN=...  # Optional, for error tracking
```

## Metrics Guide

### Key Metrics to Monitor

**API Performance**:
- **Request Rate**: `rate(http_requests_total[1m])` — requests/second
- **Latency P95**: `histogram_quantile(0.95, http_request_duration_seconds_bucket)` — max 2s
- **Error Rate**: `rate(http_requests_total{status_code=~"5.."}[1m])` — should be < 1%

**Feature Usage**:
- **Simulations**: `rate(simulation_runs_total[1m])` — simulations/second
- **Cache Hit Rate**: `pvgis_cache_hits_total / (hits + misses) * 100` — target > 80%
- **Active Users**: `active_websocket_connections` — real-time connections

**Infrastructure**:
- **DB Pool**: `db_pool_size` — connection pool utilization
- **Redis**: `redis_connected` — 0=disconnected, 1=connected

### Grafana Dashboard Panels
All 6 panels auto-refresh every 30 seconds.
- **Request Rate** — blue line graph
- **Latency** — P50/P95/P99 with thresholds
- **Error Rate** — red when > threshold
- **WebSocket Connections** — per project_id
- **Simulations** — by status (success/error/cache_hit)
- **Cache Hit Rate** — gauge (red<50%, yellow<80%, green≥80%)

## Troubleshooting

### Backend won't start
```bash
# Check logs
docker compose logs backend

# Verify migrations
docker compose --profile migrate up migrate

# Restart
docker compose restart backend
```

### No metrics appearing in Grafana
```bash
# Check Prometheus can reach backend
curl http://localhost:8000/metrics | head

# Check Prometheus targets
# Open http://localhost:9090/targets → should show "UP"

# Restart Prometheus
docker compose restart prometheus
```

### Deployment to Railway failing
1. Check GitHub Actions logs (Actions tab)
2. Verify `RAILWAY_TOKEN` is set correctly
3. Check Railway logs: https://railway.app → Logs tab
4. Verify health check passes: `curl https://<railway-url>/api/v2/health`

### Environment variables not loading
```bash
# Check running container env vars
docker compose exec backend env | grep -i secret_key

# Verify .env file exists (if used)
cat .env | head
```

## Performance Tips

### Database
- Use connection pooling (default: 10 connections)
- Monitor pool utilization in Grafana

### Redis
- Cache PVGIS responses (TTL: configurable)
- Use for session storage
- Monitor hit rate in Grafana

### Metrics
- Metrics endpoint has minimal overhead (<1ms)
- Prometheus scrapes every 10 seconds (configurable)
- Dashboard refreshes every 30 seconds

## File Locations

```
New in DEVOPS-001:
├── railway.toml                              # Railway deployment config
├── backend/app/core/telemetry.py             # Prometheus instrumentation
├── monitoring/prometheus.yml                 # Prometheus config
├── monitoring/grafana/provisioning/          # Grafana auto-provisioning
└── .github/workflows/ci.yml                  # Enhanced CI pipeline
```

## Next Steps

1. **Set up Railway**: Add `RAILWAY_TOKEN` to GitHub secrets
2. **Configure monitoring**: Set environment variables in Railway
3. **Set up Sentry** (optional): Add `SENTRY_DSN` for error tracking
4. **Configure alerts** (optional): Set up Grafana alert notifications

---

**Questions?** Check `/DEVOPS-001-IMPLEMENTATION.md` for detailed documentation.
