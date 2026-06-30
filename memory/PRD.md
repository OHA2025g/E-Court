# eCourts Phase III — Project Monitoring Information System (PMIS / PM Tracker)

## Original Problem Statement (summary)
Government of India web-based PMIS for monitoring eCourts Phase III progress across DoJ, PMU, e-Committee and 28 High Courts — replacing PDF/Excel monthly returns with a structured digital system.

## User Personas
| Persona | Role | Access |
| --- | --- | --- |
| DoJ Nodal / PMU Admin | `Admin` | Full CRUD, master data, all trackers, users, iJuris, audit, schedules, backup, 2FA |
| High Court CPC Officer | `CPC` | Edit own HC, submit for approval, view dashboards/reports |
| e-Committee Reviewer | `Viewer` | Read-only across all data, Cabinet Brief access |
| Task Team Member | `Viewer` + `task_role: team_member` | Task Management module only |

## What's Been Implemented (cumulative through Jun 2026)

### Core platform (Iterations 1–4)
- FastAPI + React + MongoDB; JWT auth, brute-force lockout, Admin TOTP 2FA
- Master Data CRUD, Physical/Financial/Outcome Trackers, Dashboard, Reports, Audit, PMU Tasks, DPR Deliverables
- Submit & approval workflow (CPC → Admin approve/return), period lockdown, re-open requests
- India choropleth (dashboard + public transparency page), component × HC heatmap, MoM RAG delta widget
- Excel/PDF exports, Cabinet Brief PDF, scheduled brief (Mon 09:00 IST), overdue HC tracker
- Comments & @mentions on tracker entries; bulk Excel upload; backup/restore
- iJuris stub (live binding via `IJURIS_BASE_URL` + `IJURIS_TOKEN` env)

### 29-feature upgrade plan (2026)
| # | Feature | Status |
| --- | --- | --- |
| 1–7 | Workflow, webhooks, Redis cache, anomalies, alerts, PFMS mock, API tokens | **Done** (Redis optional via `REDIS_URL`) |
| 8 | iJuris live API | **Partial** — env-gated; default stub |
| 9 | PFMS live | **Blocked** (external credentials) |
| 10 | SSO / Parichay | **Partial** — login button + redirect; callback **501** |
| 11–12 | Public progress page, citizen API | **Done** |
| 13 | eSign | **Stub** (backend only; no UI) |
| 14–18 | PPT export, narrative AI, narrative admin review, weekly anomaly digest, saved report views | **Done** |
| 19 | i18n (11 langs) | **Partial** — EN + **HI full PMIS UI**; all 11 locales native `tasks.*`; BN/TA/TE/GU/KN/ML/PA/UR still EN for admin/PMIS sections |
| 20 | WCAG 2.1 AA | **Done (scoped)** — **18** axe E2E specs including Task Management pages |
| 21 | Accessible RAG charts/maps | **Done** |
| 22 | RTL (Urdu) | **Partial** — `dir=rtl`; native Urdu `tasks.*` strings |
| 23–26 | PWA service worker, API rate limiting, CI build + E2E, modular route files | **Done** |
| 27 | PWA install prompt | **Done** |
| 28–29 | Onboarding tour, anomaly badges on trackers | **Done** |

Also done: export i18n (Excel/PDF headers), SSO login button when env configured.

### Task Management module (Jun 2026 — feature-complete)
- Post-login **App Selector** (`/app-selector`) — Task Management vs Application tiles
- Role-based command centre: manager / team lead / member / **auditor** dashboards, task list, detail, reports, admin config
- Full workflow API under `/api/tasks/*` — assign, accept, start, evidence, submit, verify, manager closure, escalate, block, comments, audit
- **Export CSV / Excel / PDF** with list filters (`task_export.py`)
- **Bulk actions** on task list — assign lead, assign member, cancel (up to 100 tasks)
- **SLA scheduled jobs** — 50/75/90% warnings + breach (`task_sla_jobs.py`, every 30 min)
- User `task_role` and `team_lead_id` configurable in User Management (Admin)
- **Optional TOTP 2FA** for CPC/Viewer (mandatory for Admin; extend via `REQUIRE_2FA_ROLES`)
- **Scope Charter** electronic sign-off at `/scope-charter` (4 role slots, audit trail)
- Task members (`Viewer` + `team_member`) can upload evidence files (file route allows non-auditor viewers)
- i18n: native `tasks.*` in **all 11 locales** (EN, HI, MR, BN, TA, TE, GU, KN, ML, PA, UR); PMIS admin sections still EN outside EN/HI
- **14** Playwright E2E specs in `frontend/e2e/task-management.spec.js` (incl. evidence-required, manager closure, escalate/block, bulk, export links)
- **11** backend pytest + **2** SLA job tests in `test_task_management.py` / `test_task_sla_jobs.py`

### Test coverage (Jun 2026)
- **103** backend pytest
- **47** Playwright E2E + **18** axe a11y specs (CI runs build + E2E when stack available on `:5182`)

### Architecture notes
- `server.py` delegates to modular route modules: `auth`, `tracker_routes`, `task_routes`, `export_routes`, `narrative_routes`, `webhook_routes`, etc.
- Redis optional for dashboard summary caching (`REDIS_URL`)
- Narrative: draft → admin approve (`NARRATIVE_REQUIRES_REVIEW` env); used in dashboard widget and Cabinet Brief

## Open Items / Backlog (Prioritised)

### P1 — polish (no external deps)
- Extend axe scans to Users, Audit, Account pages (optional)
- Replace MOCKED email outbox with real SMTP (Resend / GoI relay)
- PDF attached to scheduled Cabinet Brief email

### P2 — blocked on external integration
- Live iJuris API (e-Committee credentials)
- Live PFMS / Bharatkosh sync
- Parichay / SSO token exchange (callback handler)
- eSign on submission approval (backend stub exists; no UI)

### P3 — future
- Formal Scope Charter counter-signatures from field stakeholders (electronic register live; complete remaining slots)

## BRD / SoW Coverage (approx.)
- **~97%** combined functional coverage; remaining gaps are integration stubs and deep PMIS UI i18n outside Task Management
