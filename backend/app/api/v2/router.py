"""API v2 root router.

All feature sub-routers are registered here. Add new sub-routers as
tracks are implemented — do not add route handlers directly to this file.
"""

from fastapi import APIRouter

from app.api.v2.ai import router as ai_router
from app.api.v2.auth import router as auth_router
from app.api.v2.monitoring import router as monitoring_router
from app.api.v2.reports import router as reports_router
from app.api.v2.simulate import router as simulate_router
from app.api.v2.webhooks import router as webhooks_router

api_v2_router = APIRouter(prefix="/api/v2")

# ── Health ───────────────────────────────────────────────────────────────────
# Registered directly on the main app in main.py (no auth required).

# ── AUTH-001 ─────────────────────────────────────────────────────────────────
api_v2_router.include_router(auth_router, prefix="/auth")

# ── SIM-001 ───────────────────────────────────────────────────────────────────
api_v2_router.include_router(simulate_router)

# ── AI-001 ────────────────────────────────────────────────────────────────────
api_v2_router.include_router(ai_router)

# ── PDF-001 ───────────────────────────────────────────────────────────────────
api_v2_router.include_router(reports_router)

# ── INTEG-001 ─────────────────────────────────────────────────────────────────
api_v2_router.include_router(webhooks_router)

# ── MON-001 ───────────────────────────────────────────────────────────────────
api_v2_router.include_router(monitoring_router)
