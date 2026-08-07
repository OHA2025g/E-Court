# Easypanel deployment — eCourts PMIS

Panel: [Easypanel on 31.97.207.166](http://31.97.207.166:3000)

| Service | Panel path | Public URL |
|---------|------------|------------|
| Frontend | `/projects/ecourt/app/frontend` | https://ecourt.demo.agrayianailabs.com |
| Backend | `/projects/ecourt/app/backend` | https://ecourt.demoapi.agrayianailabs.com |
| MongoDB | `/projects/ecourt/mongo/ecourtdb` | internal only |

---

## Deploy / rebuild (recommended)

### Known issues (fixed in `redeploy.py`)

| Failure mode | What happened | Fix in script |
|---|---|---|
| Double trigger | Webhook **and** `deployService` fired together → Docker builder overload / HTTP 429 | **Single** webhook trigger only |
| Parallel FE+BE | Frontend and backend rebuilt at once → hangs / timeouts | **Sequential** deploys with cooldown |
| Stale token | `Deploying...` but commit SHA never moved | Refresh deploy token before each webhook |
| No verification | Script exited while build was still queued | Poll until service commit matches GitHub `main` |
| Stale Docker layers | Frontend JS bundle unchanged after locale-only commits | Bump `CACHEBUST` env on frontend |

Do **not** mash Deploy in the panel UI while the script is running — that queues competing builds.

### One-command redeploy

```bash
export EASYPANEL_EMAIL='your-panel-login@example.com'
export EASYPANEL_PASSWORD='...'
chmod +x deploy/easypanel/redeploy.sh deploy/easypanel/redeploy.py
./deploy/easypanel/redeploy.sh both      # or: frontend | backend | status
```

The script:

1. Logs into the panel API  
2. Confirms GitHub source is `OHA2025g/E-Court@main` (`/frontend/` or `/backend/`)  
3. Refreshes the deploy webhook token  
4. Triggers **one** `GET /api/deploy/<token>` per service (sequential)  
5. Waits until the deployed commit SHA matches GitHub `main` (default 15 min/service)

```bash
./deploy/easypanel/redeploy.py status          # compare panel SHAs vs GitHub
./deploy/easypanel/redeploy.py frontend --no-wait
./deploy/easypanel/redeploy.py both --timeout 1200
```

Verify after success:

```bash
curl -sS https://ecourt.demoapi.agrayianailabs.com/api/health
curl -sSI https://ecourt.demo.agrayianailabs.com/ | head -5
```

### Local-first workflow (auto-deploy OFF)

Production **GitHub auto-deploy is disabled** so pushes to `main` do **not** rebuild the live site. Develop and test locally first; deploy only when you choose.

```bash
# Confirm / re-apply disconnect
export EASYPANEL_EMAIL='...'
export EASYPANEL_PASSWORD='...'
./deploy/easypanel/disconnect-autodeploy.sh

# Local app (API on :8001, UI on :5182 via compose — or CRA on :3000)
docker compose up -d --build
# or: cd frontend && yarn start   # uses frontend/.env → http://localhost:8001

# When ready to ship to production (manual only)
./deploy/easypanel/redeploy.sh both
```

`redeploy.py` keeps auto-deploy **off** unless you explicitly set `EASYPANEL_ENABLE_AUTODEPLOY=1`.

### Manual webhook (panel UI)

Easypanel → service → **Deploy** / **Webhooks**: open the deploy URL (or copy token from service settings):

```text
http://31.97.207.166:3000/api/deploy/<service-deploy-token>
```

A `200` body of `Deploying...` means the rebuild started. Prefer `./redeploy.sh` so the SHA is verified.

---

## 1. Diagnosis (historical CSP issue)

Older frontend images served a CSP that blocked the API (`connect-src 'self'` only). Current `main` injects `CSP_API_ORIGIN` via nginx. If the public page shows *"Unable to load progress data"*, redeploy **frontend** with the env vars in §4.

---

## 2. MongoDB (ecourtdb)

See **[MONGO_SETUP.md](./MONGO_SETUP.md)** for full database setup, verify, and restore steps.

Easypanel credentials (internal):

| Field | Value |
|-------|-------|
| User | `mongo` |
| Internal host (backend `MONGO_URL`) | `ecourt_ecourtdb` |
| Internal host (mongo terminal) | `localhost` |
| Port | `27017` |

On the **backend** service set:

```env
MONGO_URL=mongodb://mongo:YOUR_PASSWORD@ecourt_ecourtdb:27017/pmis_ecourts?authSource=admin&tls=false
DB_NAME=pmis_ecourts
```

Take the password from Easypanel → mongo → ecourtdb → **Credentials**.

### Import seed data (first deploy)

From your machine (with repo cloned):

```bash
# Port-forward or use Easypanel mongo shell, then:
mongorestore --drop --uri="mongodb://USER:PASS@HOST:27017" \
  --db pmis_ecourts database/mongodump/pmis_ecourts
```

Or restore via Easypanel terminal into the mongo container.

---

## 3. Backend service

**GitHub repo:** https://github.com/OHA2025g/E-Court  
**Build path:** `backend`  
**Port:** `8001`  
**Domain:** `ecourt.demoapi.agrayianailabs.com`

Copy variables from [`backend.env.example`](./backend.env.example). Minimum required:

```env
MONGO_URL=mongodb://...@ecourtdb:27017/pmis_ecourts?authSource=admin
DB_NAME=pmis_ecourts
CORS_ORIGINS=https://ecourt.demo.agrayianailabs.com
JWT_SECRET=<32+ char random secret>
COOKIE_SECURE=true
```

**Verify after deploy:**

```bash
curl https://ecourt.demoapi.agrayianailabs.com/api/health
curl https://ecourt.demoapi.agrayianailabs.com/api/public/progress
```

---

## 4. Frontend service (CSP fix)

**Build path:** `frontend`  
**Port:** `80`  
**Domain:** `ecourt.demo.agrayianailabs.com`

### Build arguments (Easypanel → Build)

| Name | Value |
|------|-------|
| `REACT_APP_BACKEND_URL` | `https://ecourt.demoapi.agrayianailabs.com` |
| `REACT_APP_SHOW_DEMO` | `true` |

### Runtime environment

| Name | Value |
|------|-------|
| `CSP_API_ORIGIN` | `https://ecourt.demoapi.agrayianailabs.com` |
| `REACT_APP_BACKEND_URL` | `https://ecourt.demoapi.agrayianailabs.com` |

Then **Rebuild & Deploy** the frontend service.

### Verify CSP after redeploy

```bash
curl -sI https://ecourt.demo.agrayianailabs.com/ | grep -i content-security
```

Expected `connect-src` must include:

```
connect-src 'self' https://ecourt.demoapi.agrayianailabs.com
```

---

## 5. Easypanel checklist

- [ ] Mongo `ecourtdb` running; `MONGO_URL` set on backend
- [ ] Backend rebuilt; `/api/health` returns `{"ok":true}`
- [ ] `CORS_ORIGINS=https://ecourt.demo.agrayianailabs.com` on backend
- [ ] Frontend build arg `REACT_APP_BACKEND_URL` set
- [ ] Frontend runtime `CSP_API_ORIGIN` set
- [ ] Frontend redeployed from latest `main` branch
- [ ] Public page loads KPIs (no CSP errors in browser console)

---

## 6. Login test

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@pmis.gov.in | Admin@PMIS2026 |
| CPC | cpc.allahabad@pmis.gov.in | Cpc@PMIS2026 |

---

## 7. Optional: Redis

Not required (`REQUIRE_REDIS=false`). Add a Redis service later for dashboard caching if needed.
