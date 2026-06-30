# eCourts Phase III — PMIS (Project Monitoring Information System)

A role-based web platform for India's Department of Justice, PMU, e-Committee and
28 High Courts to capture, validate, monitor and report eCourts Phase III progress.

> Stack: **FastAPI + React 19 + MongoDB**
> Coverage: ~97 % of the combined BRD + SoW scope
> Tested: **99 backend pytest** + **47 Playwright E2E** + **18 axe a11y** specs

---

## 1. Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | ≥ 3.11 | for the FastAPI backend |
| Node.js | ≥ 18 | for the React frontend |
| Yarn | ≥ 1.22 | **MUST** use yarn (not npm) |
| MongoDB | ≥ 6.x | local install or Docker |

> Tip: install Mongo via Docker — `docker run -d -p 27017:27017 --name pmis-mongo mongo:7`

---

## 2. Quick Start

### 2.1  Clone & unpack
```bash
unzip ecourts-pmis.zip
cd ecourts-pmis
```

### 2.2  Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # adjust if needed
# Backend runs on port 8001
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

The first start seeds:
- 28 High Courts, 17 BRD components, 19 outcome subjects, KPIs, reporting periods
- ~4,100 baseline rows from the included dummy data
- 3 demo accounts (see § 5)
- Sample districts, DPR deliverables, PMU tasks

### 2.3  Frontend
In a **new terminal**:
```bash
cd frontend
yarn install                       # NEVER use npm — see § 7
cp .env.example .env
yarn start                         # opens http://localhost:3000
```

### 2.4  Sign in
Open `http://localhost:3000` and use the demo accounts in **§ 5 Test Credentials**.

---

## 3. Project Structure

```
ecourts-pmis/
├── backend/
│   ├── server.py              # FastAPI app shell (routes registered from modules)
│   ├── startup.py             # migrations, seeding, scheduler lifespan
│   ├── dashboard_routes.py    # dashboard + public transparency APIs
│   ├── bulk_routes.py         # bulk Excel upload + init-period
│   ├── tracker_routes.py      # physical/financial/outcome CRUD
│   ├── scheduler_routes.py    # weekly cabinet brief job + deliveries
│   ├── email_worker.py        # SMTP outbox drain (when configured)
│   ├── file_routes.py         # uploads (Emergent or local fallback)
│   ├── cabinet_brief.py       # shared PDF builder
│   ├── seed_constants.py      # 17 components + 28 HCs + indicators master
│   ├── seed_data.json         # baseline dummy data
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.js
│   │   ├── pages/             # 15 pages incl. trackers, dashboard, master, etc.
│   │   ├── components/        # Layout, NotificationBell, Choropleth, Skeletons, etc.
│   │   ├── lib/               # api.js, auth.jsx, useMinLoading.js
│   │   └── components/ui/     # shadcn/ui primitives
│   ├── package.json
│   ├── tailwind.config.js
│   └── .env.example
├── docs/
│   └── SCOPE_CHARTER.md       # 17 vs 24 component decision, A-001..A-005
├── memory/
│   ├── PRD.md
│   └── test_credentials.md
└── README.md                  # this file
```

---

## 4. Feature Overview

### Modules implemented (all 12 from BRD + SoW)

1. **Login & RBAC** — JWT cookies + body, brute-force lockout with CAPTCHA after 3 fails,
   mandatory Admin TOTP 2FA, forced password change, session list/revoke, password policy,
   Admin IP allowlist, magic-byte upload validation.
2. **Master Data** — full CRUD UI for HCs, Districts, Components, Indicators,
   Outcome Subjects, KPIs, Reporting Periods, configurable RAG thresholds.
3. **Physical Tracker** — HC × Component × Indicator × Month, auto % + RAG,
   district selector, bulk Excel upload with downloadable template.
4. **Financial Tracker** — ₹ Cr cumulative, util %, variance, RAG, district selector.
5. **Outcome Tracker** — 19 subjects, Absolute / Relative KPIs, granularity, baseline.
6. **Global Dashboard** — KPI cards, RAG donut, trend, component bar, HC bar,
   **India Choropleth** (36 states), Cabinet Brief PDF download.
7. **Reports & Export** — multi-filter, sortable, drill-down, Excel + PDF.
8. **Audit Trail** — field-level old/new with user + timestamp on every CUD.
9. **PMU Tasks** — Kanban (Open/InProgress/Completed/Overdue) with attachments.
10. **DPR Deliverables** — milestones with attachments and delay reasons.
11. **iJuris Integration** — STUB endpoint; config-driven live-binding ready
    (`IJURIS_BASE_URL` + `IJURIS_TOKEN`).
12. **Baseline + Monthly Period** — period locking, future-month block,
    Admin overrides logged.

### Iteration 4 additions
- **Submit / Approval workflow** with overdue HC tracker
- **In-app notification bell** + **email outbox** (MOCKED — db.email_outbox)
- **Scheduled Cabinet Brief** every Monday 09:00 IST via APScheduler
- **India choropleth** map on the dashboard (physical/financial RAG by state)
- **Dashboard widgets:** MoM RAG delta, component×HC heatmap, Pareto red flags, DPR milestones on trend, drag-and-drop layouts
- **Public transparency page** at `/` and `/public` (no login) — national KPIs, India choropleth, HC bar chart, top/bottom High Courts

Run dashboard tests: `docker compose exec backend pytest tests/test_dashboard_viz.py -q`

### Workflow & notifications (29-feature upgrade)
- **Approved-only dashboards:** national KPIs include only `(HC, period)` pairs with `submissions.status == Approved` (baseline periods exempt). Toggle via `DASHBOARD_REQUIRE_APPROVAL` or Master Data → Workflow.
- **Period locks:** auto-lock after `submission_grace_days` (default 7); CPC edits blocked when Submitted/Approved unless Admin override or re-open window.
- **Notifications:** period-open (1st of month), overdue (daily after SLA day), RED alerts on physical/financial/outcome with optional email (`also_email=True` when SMTP configured).
- **Cabinet Brief:** scheduled PDF emailed with attachment; uses approved data only.
- **API tokens:** Admin → Account Settings → generate read-only tokens; use `Authorization: Bearer <token>` on `/api/public/*`, `/api/dashboard/*`, tracker GET. Rate limit: `API_TOKEN_RATE_LIMIT` (default 120) requests per `API_TOKEN_RATE_WINDOW` seconds (default 60).
- **PPT export:** `GET /api/export/dashboard?reporting_period=` — 4 slides: KPI summary, trend chart, state RAG grid, top/bottom HC rankings.
- **Webhooks, SLA, re-open, saved report views, comments, anomalies:** see OpenAPI at `/docs`. Weekly anomaly digest email (Fri 11:00 IST).
- **Redis cache (optional):** set `REDIS_URL` for dashboard/public progress caching.
- **PWA:** `frontend/public/sw.js` caches `/api/public/*` for offline public progress viewing.
- **Executive narrative:** `GET /api/dashboard/narrative` + Dashboard widget with **Admin review/approve** gate (`NARRATIVE_REQUIRES_REVIEW`, default true); optional LLM via `NARRATIVE_ENABLED`.
- **i18n:** EN + **HI full PMIS UI** (trackers, dashboard, submissions, master data, schedules, admin pages, reports); 8 regional locales + UR (RTL) with nav/public stubs and native Task Management strings.
- **Accessible RAG charts:** pie, bar, trend, Pareto, heatmap, and public progress charts use symbols/stroke patterns when accessible mode is enabled (Account Settings).
- **Accessibility:** **18** axe-playwright specs in `e2e/a11y.spec.js` (public, login, dashboards, trackers, reports, submissions, master data, schedules, task management pages); skip link; `ScrollRegion` on scrollable tables.

### Iteration 5 — Data entry & bulk operations
- **Master data CRUD:** `PUT` for outcome subjects and districts; inactive districts visible to Admin (`include_inactive=true`)
- **District granularity:** district in unique compound indexes; HC rollup in dashboard/reports; district filter + column on Physical/Financial trackers
- **Rollup coverage:** heatmap, Pareto, trend, public progress, cabinet brief, and MoM RAG delta roll district rows before aggregating
- **Bulk Excel:** Physical, Financial, and Outcome bulk upload with shared parser; dry-run preview before commit (`BulkUploadPanel`); preview cached server-side (`preview_token`, 30 min) so confirm does not re-upload the file
- **Outcome district:** district field on District-granularity KPIs (form, table, bulk template, unique index)
- **Physical init prompt:** banner when HC + period have zero rows, linking to `Initialize indicator rows`
- **Inline editing:** click-to-edit cells in tracker tables (reuses POST upsert endpoints)
- **Form drafts:** debounced `localStorage` restore banner on all three tracker forms
- **Indicator templates:** `POST /api/physical/init-period` — initialize placeholder rows from master indicators
- **Financial & Outcome init-period:** `POST /api/financial|outcome/init-period` with auto-prompt banners on all three trackers
- **Bulk routes module:** bulk upload, templates, and init-period endpoints live in `backend/bulk_routes.py`
- **Tracker routes module:** physical/financial/outcome CRUD in `backend/tracker_routes.py`
- **Outcome rollup:** district outcome rows roll up in dashboard summary and public progress (`outcome.kpi_count`, `outcome.reported_count`)
- **Route guard:** all protected routes match sidebar role rules (`RoleGuard` in `App.js`)
- **Route modules:** master CRUD in `backend/master_routes.py`; exports and cabinet brief in `backend/export_routes.py`; audit in `audit_routes.py`; submissions/notifications in `submissions_routes.py`; backup/restore in `admin_routes.py`; PMU/DPR in `pmu_routes.py`; iJuris in `ijuris_routes.py`; scheduler in `scheduler_routes.py`; file uploads in `file_routes.py`; startup/seeding in `backend/startup.py`
- **Outcome dashboard viz:** heatmap, Pareto (physical/financial/outcome), trend, choropleth, and **MoM RAG delta** (`metric=physical|financial|outcome`)
- **Cabinet brief:** outcome summary plus top/bottom 5 HC rankings for physical, financial, and outcome; shared builder in `backend/cabinet_brief.py`
- **Scheduled cabinet brief:** weekly job generates PDF artifact (stored on delivery record) with Admin download endpoint
- **Public progress:** full viz bundle (trend, heatmap, Pareto, **MoM RAG delta**, multi-metric choropleth) via `/public/progress` and `/public/trend|heatmap|pareto-red-flags|rag-delta`
- **Dashboard summary routes:** `/dashboard/summary`, `/by-component`, `/by-high-court`, `/trend` live in `dashboard_routes.py`
- **E2E tests:** Playwright specs in `frontend/e2e/` (route guards, CPC/Admin bulk on all trackers, bulk error preview, **public progress viz**, **scheduled cabinet brief PDF**, **task management workflows**); fixtures in `frontend/e2e/fixtures/`

### Post–Iteration 5 polish
- **SMTP email worker:** when `SMTP_HOST` + `SMTP_FROM` are set, APScheduler drains `db.email_outbox` every minute; Admin can also `POST /api/admin/email-outbox/drain`
- **Local file storage:** when `EMERGENT_LLM_KEY` is empty, uploads persist under `backend/local_storage/` (dev-friendly fallback)
- **Scheduled PDF guard:** cabinet brief deliveries skip storage when PDF exceeds 5 MB

Run data-entry tests: `docker compose exec backend pytest tests/test_master_crud.py tests/test_district_granularity.py tests/test_bulk_upload.py tests/test_rollup_aggregations.py tests/test_data_entry_integration.py -q`

Run E2E (stack must be up on :5182): `cd frontend && yarn test:e2e`

---

## 5. Test Credentials

| Email | Password | Role | Jurisdiction |
| --- | --- | --- | --- |
| `admin@pmis.gov.in` | `Admin@PMIS2026` | Admin | All HCs |
| `cpc.allahabad@pmis.gov.in` | `Cpc@PMIS2026` | CPC | Allahabad HC |
| `viewer@pmis.gov.in` | `View@PMIS2026` | Viewer | Read-only |
| `member@pmis.gov.in` | `Member@PMIS2026` | Viewer (task: team_member) | Task module only |

After login, users land on **`/app-selector`** with two tiles: **Task Management** (command centre) and **Application** (PMIS dashboard at `/dashboard`).

### Task Management module

Separate workflow app at `/task-management/*` with role-based dashboards (manager, team lead, member, auditor), task list/detail, evidence upload, approvals, SLA tracking, reports, and admin config.

| Capability | Details |
| --- | --- |
| Workflow | Assign → accept → start → evidence → submit → verify → (optional manager closure) → closed; escalate / block / rework |
| Export | CSV, Excel, PDF from list and reports (`GET /api/tasks/export?format=csv\|xlsx\|pdf`) |
| Bulk actions | Multi-select on list — bulk assign lead/member, bulk cancel (manager) |
| SLA jobs | Scheduled 50/75/90% warnings + breach notifications |
| i18n | Native `tasks.*` in **all 11 locales**; **HI full PMIS UI**; other regional PMIS sections still EN |
| Tests | 11 backend + 2 SLA pytest; 14 Playwright E2E in `e2e/task-management.spec.js` |

Demo task users: `member@pmis.gov.in` / `Member@PMIS2026` (team member); `viewer@pmis.gov.in` opens auditor overview when task role is auditor.

These are also defined in `backend/.env.example` — change them in
`backend/.env` **before going to production**.

---

## 6. Configuration

### Backend `.env`
```dotenv
MONGO_URL="mongodb://localhost:27017"
DB_NAME="pmis_ecourts"
CORS_ORIGINS="*"

JWT_SECRET="<32-byte hex secret>"          # MUST change in production

ADMIN_EMAIL="admin@pmis.gov.in"
ADMIN_PASSWORD="Admin@PMIS2026"
CPC_DEMO_EMAIL="cpc.allahabad@pmis.gov.in"
CPC_DEMO_PASSWORD="Cpc@PMIS2026"
VIEWER_DEMO_EMAIL="viewer@pmis.gov.in"
VIEWER_DEMO_PASSWORD="View@PMIS2026"

EMERGENT_LLM_KEY="<optional — Emergent object storage; leave empty for local disk uploads>"

# Optional — SMTP email delivery (drains db.email_outbox when set)
# SMTP_HOST="smtp.gov.in"
# SMTP_PORT="587"
# SMTP_USER=""
# SMTP_PASSWORD=""
# SMTP_FROM="pmis-noreply@doj.gov.in"
# SMTP_USE_TLS="true"
APP_NAME="ecourts-pmis"

LOCKOUT_MAX_FAILS="5"
LOCKOUT_DURATION_MIN="15"
LOCKOUT_CAPTCHA_AFTER="3"
PASSWORD_MIN_LENGTH="12"
PASSWORD_HISTORY_COUNT="5"
PASSWORD_MAX_AGE_DAYS="90"
ADMIN_IP_ALLOWLIST_ENABLED="false"
ADMIN_IP_ALLOWLIST=""

# Optional — when iJuris API access is provisioned
# IJURIS_BASE_URL="https://ijuris.api.gov.in"
# IJURIS_TOKEN=""

# Optional — extra Cabinet Brief recipients (admins are auto-included)
# CABINET_BRIEF_RECIPIENTS="secretary@doj.gov.in,nodal@pmu.gov.in"
```

### Frontend `.env`
```dotenv
REACT_APP_BACKEND_URL=http://localhost:5182
WDS_SOCKET_PORT=443
```

For local dev you can usually leave `REACT_APP_BACKEND_URL` pointing at
`http://localhost:8001`. The frontend uses cookies, so the protocol+host pair
must match the URL you actually open in the browser.

---

## 7. Important rules

- **Never use `npm install`** — always `yarn`. Mixing them breaks lockfiles.
- All backend API routes are under `/api/...`.
- The backend serves cookies as `httpOnly`; the React app talks to it with
  `withCredentials: true`.
- The default MongoDB connection has no auth — for production, switch
  `MONGO_URL` to a properly secured cluster URI.
- The **email outbox** queues mail in `db.email_outbox`. Without SMTP env vars, delivery is logged only. Set `SMTP_HOST` and `SMTP_FROM` to enable the built-in drain worker.

---

## 8. Running tests

```bash
cd backend
source .venv/bin/activate
pytest tests/ -q                    # full backend suite (99 tests)

# Or inside Docker:
docker compose exec backend pytest tests/ -q

# Playwright E2E (stack on :5182):
cd frontend && yarn test:e2e

# axe accessibility (stack on :5182):
cd frontend && PMIS_BASE_URL=http://localhost:5182 yarn test:e2e a11y.spec.js
```

### Manual security smoke (live stack)

With `docker compose up` running on port **5182**:

```bash
chmod +x scripts/security_qa_smoke.sh
./scripts/security_qa_smoke.sh http://localhost:5182
```

Checks health, CAPTCHA, login lockout path, session API, and Admin 2FA gate.

---

## 9. Security deployment notes

| Control | Configuration |
|---|---|
| Admin IP allowlist | Master Data → **Security** tab, or `ADMIN_IP_ALLOWLIST_*` env vars (default **off**) |
| Password policy | `PASSWORD_MIN_LENGTH`, `PASSWORD_HISTORY_COUNT`, `PASSWORD_MAX_AGE_DAYS` |
| Login lockout / CAPTCHA | `LOCKOUT_MAX_FAILS`, `LOCKOUT_DURATION_MIN`, `LOCKOUT_CAPTCHA_AFTER` |
| Session invalidation | JWT `sid` in MongoDB `sessions`; old tokens without `sid` are rejected after deploy |

**Behind nginx (Docker `web` service):** `frontend/nginx.conf` sets `X-Forwarded-For` on `/api/` proxy
pass-through. The backend reads the **first hop** of that header for Admin IP allowlist checks.
Only trust this header from your internal reverse proxy — do not expose the backend directly on the
public internet without re-validating client IP at the edge.

After deploy, all users must **sign in once** (session store migration).

---

## 10. Useful Endpoints (Admin)

| Endpoint | Purpose |
|---|---|
| `GET  /api/admin/backup` | Download full JSON backup |
| `POST /api/admin/restore` | Merge / replace restore |
| `GET  /api/admin/scheduled-jobs` | List APScheduler jobs |
| `POST /api/admin/scheduled-deliveries/run-now` | Manually trigger Cabinet Brief |
| `GET  /api/admin/scheduled-deliveries/{id}/pdf` | Download scheduled brief PDF |
| `POST /api/admin/email-outbox/drain` | Manually drain email outbox (SMTP required) |
| `GET  /api/email-outbox` | Inspect queued emails |
| `GET  /api/ijuris/config` | iJuris live-mode status |

Full OpenAPI docs: open `http://localhost:8001/docs` while the backend is running.

---

## 11. Roadmap

See `memory/PRD.md` for the prioritised backlog (Phase 2, including live SMTP,
PFMS integration, AI narrative summaries, 2FA for non-Admin roles, full
WCAG 2.1 AA pass and Hindi + 8 regional language UIs).
