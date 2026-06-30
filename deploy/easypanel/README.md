# Easypanel deployment — eCourts PMIS

Panel: [Easypanel on 31.97.207.166](http://31.97.207.166:3000)

| Service | Panel path | Public URL |
|---------|------------|------------|
| Frontend | `/projects/ecourt/app/frontend` | https://ecourt.demo.agrayianailabs.com |
| Backend | `/projects/ecourt/app/backend` | https://ecourt.demoapi.agrayianailabs.com |
| MongoDB | `/projects/ecourt/mongo/ecourtdb` | internal only |

---

## 1. Diagnosis (current production issue)

The live frontend still serves an **old CSP** that blocks the API:

```
connect-src 'self'          ← blocks https://ecourt.demoapi.agrayianailabs.com
script-src 'self'           ← blocks inline scripts (CRA + PostHog)
style-src without fonts.googleapis.com
```

**Symptom:** Public page shows *"Unable to load progress data"*.

**Backend is OK** — `GET https://ecourt.demoapi.agrayianailabs.com/api/public/progress` returns data and CORS already allows `https://ecourt.demo.agrayianailabs.com`.

**Fix:** Redeploy **frontend** from the latest GitHub code with the env vars below.

---

## 2. MongoDB (ecourtdb)

Easypanel internal host: **`ecourt_ecourtdb`** (not `ecourtdb`).

On the **backend** service set:

```env
MONGO_URL=mongodb://mongo:YOUR_PASSWORD@ecourt_ecourtdb:27017/pmis_ecourts?authSource=admin&tls=false
DB_NAME=pmis_ecourts
```

Take the URI from [mongo ecourtdb](http://31.97.207.166:3000/projects/ecourt/mongo/ecourtdb) and add `/pmis_ecourts?authSource=admin` before `&tls=false` if missing.

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
