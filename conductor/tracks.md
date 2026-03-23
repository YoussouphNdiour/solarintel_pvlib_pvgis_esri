# SolarIntel v2 — Tracks Registry

## Overview

| Track ID   | Sprint | Title                              | Type    | Priority | Status   | Dependencies        |
|------------|--------|------------------------------------|---------|----------|----------|---------------------|
| INFRA-001  | S1     | Project Scaffolding                | infra   | P0       | done     | —                   |
| DB-001     | S1     | PostgreSQL Schema + Alembic        | feature | P0       | active   | INFRA-001           |
| AUTH-001   | S1     | JWT Auth + Roles + OAuth2 Google   | feature | P0       | pending  | DB-001              |
| REACT-001  | S2     | React 18 + TypeScript Migration    | feature | P0       | pending  | AUTH-001            |
| SIM-001    | S3     | PV Simulation Engine + Cache       | feature | P1       | pending  | REACT-001           |
| AI-001     | S4     | LangGraph Multi-Agent Orchestrator | feature | P1       | pending  | SIM-001             |
| PDF-001    | S5     | PDF + HTML Interactive Reports     | feature | P2       | pending  | AI-001, SIM-001     |
| INTEG-001  | S6     | Open-Meteo + WhatsApp + SunSpec    | feature | P2       | pending  | SIM-001             |
| MON-001    | S7     | WebSocket Monitoring Dashboard     | feature | P2       | pending  | DB-001, INTEG-001   |
| DEVOPS-001 | S7     | CI/CD Render.com + Grafana         | infra   | P1       | done     | INFRA-001           |
| QA-001     | S8     | Coverage 85%+ + Playwright E2E     | quality | P0       | done     | all                 |

---

## DB-001 — PostgreSQL Schema + Alembic Migrations

**Status**: active
**Sprint**: 1 (S1–S2)
**Priority**: P0
**Type**: feature
**Dependencies**: INFRA-001

**Goal**: Establish the full PostgreSQL schema for all v2 entities so every subsequent track builds on a stable, migration-managed foundation. This is the critical path — all other tracks depend on it.

**Database Schema**:
```sql
users          (id UUID, email, hashed_password, role, company, is_active, created_at)
projects       (id UUID, user_id FK, name, latitude, longitude, polygon_geojson JSONB, created_at)
simulations    (id UUID, project_id FK, panel_count, peak_kwc, annual_kwh, pr, monthly_data JSONB, params JSONB, created_at)
equipment      (id UUID, project_id FK, inverter_model, battery_model, panel_model, details JSONB)
reports        (id UUID, simulation_id FK, pdf_path, html_path, status, generated_at)
monitoring     (id UUID, project_id FK, timestamp, production_kwh, irradiance, temperature)
tariff_history (id UUID, tariff_code, effective_date, t1_xof, t2_xof, t3_xof, woyofal_xof)
```

**Redis Key Space**:
- `pvgis:{lat}:{lon}` → TMY results (TTL 30 days)
- `session:{token}` → user data (TTL 24h)
- `tariff:senelec` → current tariff grid (TTL 7 days)

**Deliverables**:
- `backend/app/models/` — SQLAlchemy 2.0 async ORM models (one file per model)
- `backend/app/db/session.py` — async engine + session factory
- `backend/app/db/redis.py` — Redis client wrapper
- `backend/alembic/` — Alembic env + initial migration
- `backend/tests/test_models.py` — model creation + relationship tests (TDD first)

**Acceptance Criteria**:
- `alembic upgrade head` creates all 7 tables on a fresh PostgreSQL DB
- All FK constraints and indexes are in place
- Async session works with SQLAlchemy 2.0 style (`async with session:`)
- Redis client connects and round-trips a cache read/write

---

## AUTH-001 — JWT Auth + Roles + OAuth2 Google

**Status**: pending
**Sprint**: 1 (S1–S2)
**Priority**: P0
**Type**: feature
**Dependencies**: DB-001

**Goal**: Implement secure multi-tenant authentication with roles (Admin / Commercial / Technicien / Client) so each installer's data is isolated.

**Roles**:
- `admin` — full platform access
- `commercial` — create/read all projects in their company
- `technicien` — create/edit projects, run simulations
- `client` — read-only access to their own project reports

**Deliverables**:
- `backend/app/api/v2/auth.py` — register, login, refresh, /me endpoints
- `backend/app/services/auth_service.py` — JWT creation/verification, bcrypt hashing
- `backend/app/core/security.py` — `get_current_user` dependency, role-check decorators
- OAuth2 Google flow (`/api/v2/auth/google`)
- `backend/tests/test_auth.py` — pytest covering all auth endpoints (TDD first)
- Frontend: `LoginPage`, `RegisterPage`, `PrivateRoute` component, auth Zustand store

**Acceptance Criteria**:
- Register → login → receive JWT (access 30min + refresh 7d)
- Role-gated endpoints return 403 for unauthorized roles
- Google OAuth redirects and creates user on first sign-in
- Passwords stored as bcrypt (never plaintext in logs)
- Refresh token rotation on each use

---

## REACT-001 — React 18 + TypeScript Frontend Migration

**Status**: pending
**Sprint**: 2 (S3–S4)
**Priority**: P0
**Type**: feature
**Dependencies**: AUTH-001

**Goal**: Migrate v1 Vanilla JS single-file (2100+ lines) to a structured React 18 + TypeScript app with Zustand, React Router v6, ArcGIS @arcgis/core, and PWA support.

**Deliverables**:
- `frontend/src/stores/` — Zustand stores (auth, project, simulation, ui)
- `frontend/src/components/Map/ArcGISMap.tsx` — ArcGIS JS SDK 4.30 wrapper
- `frontend/src/components/Map/PolygonDrawer.tsx` — sketch widget for zone drawing
- `frontend/src/pages/` — Login, Register, Dashboard, Project, Simulate, Report, Monitor
- `frontend/src/hooks/` — useSimulation, useProject, useAuth custom hooks
- `frontend/public/manifest.json` + `src/sw.ts` — PWA service worker
- `frontend/tests/` — Playwright E2E for full user journey (draw zone → simulate → download)

**Acceptance Criteria**:
- All v1 features reproduced in React (calepinage, simulation, SENELEC tariffs, PDF)
- PWA installable on Android/iOS
- ArcGIS map works at all viewport sizes
- TypeScript strict mode — zero `any` types, zero `ts-ignore`

---

## SIM-001 — PV Simulation Engine + Redis Cache

**Status**: pending
**Sprint**: 3 (S5–S6)
**Priority**: P1
**Type**: feature
**Dependencies**: REACT-001

**Goal**: Deliver a fast, cached PV simulation API backed by pvlib + PVGIS TMY, with results stored per project and cached in Redis (TTL 30 days).

**Deliverables**:
- `backend/app/services/simulation_service.py` — pvlib simulation (refactored from v1)
- `backend/app/services/senelec_service.py` — DPP/DMP/PPP/PMP/Woyofal tariff logic
- `backend/app/api/v2/simulate.py` — POST /simulate, GET /simulate/{id}
- Simulation result stored to DB (JSONB monthly data)
- Redis cache for PVGIS TMY results (key: `pvgis:{lat}:{lon}`, TTL 30d)
- `SimulationForm`, `SimulationResults`, `MonthlyChart` React components
- `backend/tests/test_simulation.py` — pytest with Dakar reference data (TDD first)

**Acceptance Criteria**:
- First simulation call hits PVGIS API (< 10s)
- Second call returns from Redis cache (< 500ms)
- Annual yield for Dakar within 5% of PVGIS web interface
- Senelec savings calculation matches manual T1/T2/T3 calculation

---

## AI-001 — LangGraph Multi-Agent Orchestrator

**Status**: pending
**Sprint**: 4 (S7–S8)
**Priority**: P1
**Type**: feature
**Dependencies**: SIM-001

**Goal**: Implement a LangGraph StateGraph orchestrating 4 parallel specialized agents that together produce sizing recommendations, narrative analysis, and QA validation in under 30 seconds.

**Agent Architecture**:
```
Orchestrator (LangGraph StateGraph)
├── Agent Dimensionnement (claude-sonnet-4-6) → onduleur kVA, batterie Ah, nb panneaux
├── Agent Simulation (pvlib sync) → production mensuelle + PR
├── Agent SENELEC (Python calc) → économies annuelles, payback, ROI
└── Agent Rédaction (claude-opus-4-6) → narrative PVSyst-style
↓ (parallel, timeout 25s)
Agent QA (claude-sonnet-4-6) → 8 critères V1-V8 (FP, kVA, coverage, ROI…)
↓
SolarReport v2 → PDF + HTML + WhatsApp payload
```

**Deliverables**:
- `backend/app/agents/orchestrator.py` — LangGraph StateGraph
- `backend/app/agents/dimensioning.py` — equipment sizing agent
- `backend/app/agents/prediction.py` — production vs simulated analysis
- `backend/app/agents/report_writer.py` — narrative generation (Opus 4.6)
- `backend/app/agents/qa_validator.py` — 8-criteria QA check
- `backend/app/api/v2/ai.py` — POST /ai/analyze (SSE streaming), GET /ai/sessions/{id}
- `AISizingChat` React component with token-by-token streaming
- `backend/tests/test_agents.py` — pytest with mocked Claude API (TDD first)

**Acceptance Criteria**:
- Full orchestration completes in < 30s (parallel execution)
- QA report lists pass/fail for all 8 criteria (V1–V8)
- SSE streaming renders tokens in real-time in chat UI
- Graceful fallback if Claude API unavailable

---

## PDF-001 — PDF + HTML Interactive Reports

**Status**: pending
**Sprint**: 5 (S9–S10)
**Priority**: P2
**Type**: feature
**Dependencies**: AI-001, SIM-001

**Goal**: Generate professional PVSyst-inspired PDF reports and interactive HTML exports with Chart.js, including Monte Carlo confidence intervals and multi-scenario comparison.

**Report Sections**:
1. Cover page (logo, site info, date)
2. System specification table
3. Monthly energy yield chart
4. SENELEC savings analysis (before/after, 12 months)
5. Cash flow + payback chart
6. Monte Carlo confidence intervals (N=1000, ±15%)
7. Sensitivity analysis (electricity price ±10/20/30%)
8. Scenario comparison (on-grid vs hybrid vs off-grid)
9. QA matrix (8 criteria V1–V8)
10. AI narrative (from Agent Rédaction)
11. ArcGIS satellite capture (base64 embed)
12. QR code → online project dashboard

**Deliverables**:
- `backend/app/services/report_service.py` — orchestrates PDF + HTML generation
- `backend/app/reports/pdf_generator.py` — ReportLab (refactored from v1, expanded)
- `backend/app/reports/html_generator.py` — Chart.js interactive HTML export
- `backend/app/reports/monte_carlo.py` — Monte Carlo simulation service
- `backend/app/api/v2/reports.py` — POST /reports, GET /reports/{id}, GET /reports/{id}/download
- Frontend: PDF download + HTML preview modal
- `backend/tests/test_reports.py` — pytest for report content validation (TDD first)

**Acceptance Criteria**:
- PDF: 12+ pages, ArcGIS satellite embed, all charts present
- HTML: interactive Chart.js charts, works offline
- Monte Carlo: 1000 iterations, ±15% confidence band on monthly yield
- PDF generation < 30s, queued via Redis

---

## INTEG-001 — Open-Meteo + WhatsApp + SunSpec Webhooks

**Status**: pending
**Sprint**: 6 (S11–S12)
**Priority**: P2
**Type**: feature
**Dependencies**: SIM-001

**Goal**: Connect SolarIntel v2 to real-world data sources and communication channels.

**Deliverables**:
- `backend/app/services/weather_service.py` — Open-Meteo hourly data for production correction
- `backend/app/services/whatsapp_service.py` — WhatsApp Business API PDF delivery
- `backend/app/api/v2/webhooks.py` — SunSpec/Modbus inverter data receiver
- `backend/app/services/equipment_prices.py` — weekly Senegalese supplier price cache (Redis)
- `backend/tests/test_integrations.py` — pytest with mocked external APIs (TDD first)

**Acceptance Criteria**:
- Open-Meteo data corrects pvlib simulation by measured temperature delta
- WhatsApp sends PDF quote to client phone number successfully
- Webhook endpoint accepts SunSpec JSON and stores to monitoring table
- Equipment prices cached in Redis, auto-refresh weekly

---

## MON-001 — WebSocket Monitoring Dashboard

**Status**: pending
**Sprint**: 7 (S13–S14)
**Priority**: P2
**Type**: feature
**Dependencies**: DB-001, INTEG-001

**Goal**: Real-time post-installation monitoring showing production vs simulation with automatic performance alerts.

**Deliverables**:
- `backend/app/api/v2/monitoring.py` — WebSocket endpoint + REST GET /monitoring/{project_id}
- Background task: check production < 80% threshold → trigger SMS + email alert
- `backend/app/services/alert_service.py` — Twilio SMS + email alerts
- Monthly auto-report: PDF + WhatsApp delivery
- `MonitoringDashboard` React component with real-time Chart.js + WebSocket
- `backend/tests/test_monitoring.py` — pytest WebSocket tests (TDD first)

**Acceptance Criteria**:
- WebSocket pushes real production data within 1s of ingestion
- Alert fires when production < 80% of expected for 24h window
- Monthly report auto-sends on 1st of each month
- Dashboard shows: kWh today / this month / this year vs simulated

---

## DEVOPS-001 — CI/CD Railway + Grafana Monitoring

**Status**: pending
**Sprint**: 7 (S13–S14)
**Priority**: P1
**Type**: infra
**Dependencies**: INFRA-001

**Goal**: Automated deployment pipeline and production observability.

**Deliverables**:
- `railway.toml` — Railway.app deployment config (backend + frontend services)
- Updated `.github/workflows/ci.yml` — full pipeline: ruff + mypy + pytest (90%) + playwright + docker build + SAST + deploy Railway
- `backend/app/core/telemetry.py` — Prometheus metrics (request latency, error rate, simulation count)
- Grafana Cloud dashboard: FastAPI latency P50/P95/P99, 5xx rate, DB pool usage, Redis hit rate
- Sentry DSN integration for exception tracking
- `backend/tests/test_ci.py` — smoke tests for Railway health check

**Acceptance Criteria**:
- Push to `main` triggers full CI pipeline (< 10min)
- Railway auto-deploys on CI success
- Grafana dashboard shows all key metrics
- SAST (Bandit + pip-audit) passes with zero HIGH findings

---

## QA-001 — Coverage + E2E Tests (ongoing)

**Status**: ongoing
**Sprint**: all sprints
**Priority**: P0
**Type**: quality
**Dependencies**: all tracks

**Goal**: Maintain 90%+ backend coverage and 80%+ frontend coverage throughout development.

**Acceptance Criteria**:
- `pytest --cov` reports ≥ 90% for `backend/app/`
- Playwright E2E covers: register → login → create project → draw zone → simulate → download PDF
- All CI gates pass before any PR merge
- Zero `ruff` violations, zero `mypy` errors in strict mode
