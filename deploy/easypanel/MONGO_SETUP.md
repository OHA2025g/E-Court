# MongoDB setup — Easypanel ecourtdb

Credentials from Easypanel (internal network only):

| Field | Value |
|-------|-------|
| User | `mongo` |
| Password | *(from panel — do not commit)* |
| Host (from backend) | `ecourt_ecourtdb` |
| Host (inside mongo container) | `localhost` |
| Port | `27017` |

---

## Step 1 — Backend environment (required)

On [backend service](http://31.97.207.166:3000/projects/ecourt/app/backend) set:

```env
MONGO_URL=mongodb://mongo:YOUR_PASSWORD@ecourt_ecourtdb:27017/pmis_ecourts?authSource=admin&tls=false
DB_NAME=pmis_ecourts
```

Replace `YOUR_PASSWORD` with the password from the Easypanel credentials screen.

**Redeploy backend** after saving.

---

## Step 2 — Verify connection

### Option A — API (after backend redeploy)

```bash
curl https://ecourt.demoapi.agrayianailabs.com/api/health
curl https://ecourt.demoapi.agrayianailabs.com/api/public/progress
```

### Option B — Mongo terminal

Open [mongo ecourtdb](http://31.97.207.166:3000/projects/ecourt/mongo/ecourtdb) → **Terminal**, then:

```bash
mongosh "mongodb://mongo:YOUR_PASSWORD@localhost:27017/pmis_ecourts?authSource=admin&tls=false" --eval "db.high_courts.countDocuments()"
```

---

## Step 3 — Seed or restore data

### If database is empty (counts = 0)

**Automatic seed (minimal):** Restart backend with `MONGO_URL` set. On first start the app creates:

- 28 High Courts, components, indicators, KPIs, periods
- Demo users (admin, CPC, viewer)
- Baseline rows from `backend/seed_data.json`

### Full production data (~4100 rows)

In **mongo container terminal**:

```bash
apt-get update && apt-get install -y curl mongodb-database-tools
curl -fsSL https://raw.githubusercontent.com/OHA2025g/E-Court/main/deploy/easypanel/restore-mongo-in-container.sh -o /tmp/restore.sh
chmod +x /tmp/restore.sh
MONGO_URI="mongodb://mongo:YOUR_PASSWORD@localhost:27017/?authSource=admin&tls=false" /tmp/restore.sh
```

Or copy `deploy/easypanel/restore-mongo-in-container.sh` from the repo and run it.

Then **restart backend**.

---

## Step 4 — Login test

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@pmis.gov.in | Admin@PMIS2026 |
| CPC | cpc.allahabad@pmis.gov.in | Cpc@PMIS2026 |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Backend crash on start | Check `MONGO_URL` host is `ecourt_ecourtdb` (not `localhost`) on **backend** |
| `Authentication failed` | Add `?authSource=admin` to URI |
| Empty dashboard | Run restore script or restart backend for auto-seed |
| Frontend no data | Set `CSP_API_ORIGIN` on frontend (see main README) |
