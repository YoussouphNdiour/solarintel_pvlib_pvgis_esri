# Deploying SolarIntel v2 on Render.com (100% Free Tier)

## What you get for free — all on Render, no external accounts needed

| Service | Render Free | Limitations |
|---------|------------|-------------|
| **Backend** (Web Service) | ✅ Free | Spins down after 15 min idle (cold start ~30s) |
| **Frontend** (Static Site) | ✅ Free | CDN-served, zero cold starts, unlimited bandwidth |
| **PostgreSQL** | ✅ Free | 1 GB storage, expires after **90 days** (upgrade to $7/mo Starter for persistence) |
| **Key Value (Redis)** | ✅ Free | No disk persistence — data lost on restart (fine for SolarIntel caches) |

> **No Upstash, no external services.** Everything lives inside Render.

---

## Prerequisites

- GitHub account with the SolarIntel v2 repo pushed
- Render.com account — [render.com](https://render.com) (free, no credit card required)
- API keys ready: Anthropic, ArcGIS, (optionally: WhatsApp, Google OAuth)

---

## Step 1 — Deploy via Render Blueprint (render.yaml)

The `render.yaml` at the project root defines **all 4 services** (backend, frontend,
PostgreSQL, Key Value). Render reads it automatically when you connect your repository.

1. Go to [dashboard.render.com](https://dashboard.render.com) → **New → Blueprint**
2. Connect your GitHub repository
3. Render detects `render.yaml` and shows a preview of the services to create:
   - `solarintel-backend` (Web Service, Docker, free)
   - `solarintel-frontend` (Static Site, free)
   - `solarintel-redis` (Key Value / Valkey 8, free)
   - `solarintel-db` (PostgreSQL, free)
4. Click **Apply**

`REDIS_URL` is automatically injected into the backend via `fromService` — no manual
copy-paste needed.

---

## Step 2 — Set secret environment variables

After the services are created, set the variables marked `sync: false` in render.yaml.

**In the Render Dashboard → `solarintel-backend` → Environment → Add env var:**

| Key | Value | Required |
|-----|-------|----------|
| `ANTHROPIC_API_KEY` | `sk-ant-...` from console.anthropic.com | ✅ |
| `ARCGIS_API_KEY` | Your ArcGIS JS SDK API key | ✅ |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | ⚠️ optional |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | ⚠️ optional |
| `WHATSAPP_TOKEN` | WhatsApp Business API token | ⚠️ optional |
| `WHATSAPP_PHONE_ID` | WhatsApp Business phone ID | ⚠️ optional |
| `SENTRY_DSN` | Sentry project DSN | ⚠️ optional |

> **`SECRET_KEY`** and **`DATABASE_URL`** and **`REDIS_URL`** are all set automatically
> by Render via Blueprint — do not override them.

---

## Step 3 — Run the initial database migration

After the first deploy succeeds, open the **Shell** tab of `solarintel-backend` in
the Render Dashboard and run:

```bash
alembic upgrade head
```

This creates all 7 tables and seeds the initial SENELEC DPP 2024 tariff.

To run Alembic automatically on every deploy, you can set a custom start command
in render.yaml (trade-off: slower deploys):

```yaml
startCommand: alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

---

## Step 4 — Set up CI/CD Deploy Hooks

To trigger automatic Render deploys from GitHub Actions on push to `main`:

1. Render Dashboard → `solarintel-backend` → **Settings → Deploy Hook** → Copy URL
2. Render Dashboard → `solarintel-frontend` → **Settings → Deploy Hook** → Copy URL
3. GitHub repo → **Settings → Secrets → Actions → New repository secret**:
   - `RENDER_BACKEND_DEPLOY_HOOK` → paste backend hook URL
   - `RENDER_FRONTEND_DEPLOY_HOOK` → paste frontend hook URL

The `.github/workflows/ci.yml` `deploy-render` job calls these hooks automatically
after all CI gates pass on `main`, then polls `/api/v2/health` until the backend is up.

---

## Step 5 — Verify the deployment

```bash
# Backend health check
curl https://solarintel-backend.onrender.com/api/v2/health

# Expected
{"status":"ok","version":"2.0.0","environment":"production"}
```

```bash
# Frontend
open https://solarintel-frontend.onrender.com
```

---

## About Render Key Value (Redis)

SolarIntel uses Redis for:
- PVGIS irradiance cache (`pvgis:{lat}:{lon}` — TTL 30 days)
- SENELEC tariff cache (`tariff:senelec` — TTL 7 days)
- Equipment prices cache (`equipment:prices:*` — TTL 7 days)
- Alert cooldown (`alert:cooldown:{project_id}` — TTL 24h)

All of these are **re-fetchable caches** — if Render restarts the Key Value instance
(which clears data on the free tier), the app simply fetches fresh data on the next
request. No data loss occurs.

The free Key Value instance runs **Valkey 8** (open-source Redis 7.2 fork), with
`allkeys-lru` eviction. It shares your Render private network with the backend service
(same region = Frankfurt), so the `REDIS_URL` uses the fast internal connection:

```
redis://red-<instance-id>:6379
```

No TLS, no password required for internal connections on the private network.

---

## Free tier caveats

### Cold starts
The backend spins down after 15 minutes of inactivity. First request after idle
takes ~30 seconds. To keep the backend warm, set up a GitHub Actions scheduled ping:

```yaml
# .github/workflows/keep-alive.yml
on:
  schedule:
    - cron: "*/14 * * * *"   # every 14 minutes
jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - run: curl -sf https://solarintel-backend.onrender.com/api/v2/health
```

### PostgreSQL expiry (90 days)
The free PostgreSQL database expires after 90 days. You will receive email warnings
at 60 and 80 days.

Options:
- Upgrade to **Starter ($7/mo)** for a permanent database
- Export before expiry: `pg_dump $DATABASE_URL > solarintel_backup.sql`
- Re-create and restore: `psql $NEW_DATABASE_URL < solarintel_backup.sql`

### Key Value restarts
On the free tier, Render may restart the Key Value instance periodically. All cached
data is cleared on restart. SolarIntel handles this gracefully — the next API call
simply re-fetches and re-caches.

---

## Custom domain

1. Render Dashboard → `solarintel-frontend` → **Settings → Custom Domains → Add**
2. Add a CNAME record at your DNS provider → `solarintel-frontend.onrender.com`
3. Render issues a free TLS certificate via Let's Encrypt automatically

Then update the backend `ALLOWED_ORIGINS` env var to include your domain:

```
ALLOWED_ORIGINS=["https://yourapp.com","https://solarintel-frontend.onrender.com"]
```

---

## Environment variables reference

| Variable | Source | Required |
|----------|--------|----------|
| `DATABASE_URL` | Auto — Render Blueprint | ✅ |
| `REDIS_URL` | Auto — Render Blueprint | ✅ |
| `SECRET_KEY` | Auto — `generateValue: true` | ✅ |
| `ENVIRONMENT` | `production` (hardcoded) | ✅ |
| `ANTHROPIC_API_KEY` | Manual | ✅ |
| `ARCGIS_API_KEY` | Manual | ✅ |
| `GOOGLE_CLIENT_ID/SECRET` | Manual | ⚠️ OAuth disabled if absent |
| `WHATSAPP_TOKEN/PHONE_ID` | Manual | ⚠️ WhatsApp disabled if absent |
| `SENTRY_DSN` | Manual | ⚠️ Error tracking disabled if absent |
