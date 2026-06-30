# eCourts Phase III PMIS — BRD & SoW Implementation Status

**Documents reviewed**

| Document | Version / date | Location |
|----------|----------------|----------|
| Business Requirements Document (BRD) | v3, 24 Jun 2026 | `eCourts_PMIS_BRD_v3 (1).pdf` (repo root) |
| Statement of Work (SoW) | — | `eCourts_PMIS_SoW.pdf` (repo root) |
| Scope Charter | Feb 2026 | `docs/SCOPE_CHARTER.md` |
| Product backlog | Jun 2026 | `memory/PRD.md` |

**Codebase:** `ecourts-pmis` (FastAPI + React + MongoDB)

**Last verified:** June 2026

---

## Executive summary

| Document | Stated scope | Build status |
|----------|--------------|--------------|
| **BRD v3** | 13 in-scope PMIS capabilities (§2.1) + NFRs (§10) | **~95% implemented** for core PMIS; a few reporting/NFR items are partial |
| **SoW** | 7 tracking modules + audit + role/jurisdiction model | **~90% implemented**; integrations and some delivery items remain partial |
| **Combined (README claim)** | ~97% | **Reasonable** — gaps are mostly external integrations, i18n depth, and formal sign-offs |

The build **exceeds** the BRD in several areas (submit/approval workflow, public transparency, advanced dashboard widgets, full Task Management workflow app). It **deliberately stays on 17 components** (BRD) rather than 24 (SoW), per Scope Charter Decision 1.

---

## BRD §2.1 — In scope (13 capabilities)

| # | BRD requirement | Status | Evidence / notes |
|---|-----------------|--------|------------------|
| 1 | **Physical Tracker** — 17 components, indicator-level | ✅ Implemented | `frontend/src/pages/PhysicalTracker.jsx`, `backend/tracker_routes.py`, 17 components in `backend/seed_constants.py`, bulk upload, district rows, init-period |
| 2 | **Financial Tracker** — released & utilised, ₹ Cr | ✅ Implemented | `frontend/src/pages/FinancialTracker.jsx`, util %, variance, RAG, district |
| 3 | **Outcome Tracker** — Subject→KPI, Abs/Rel, State/District/National | ✅ Implemented | 19 subjects, granularity, baseline, computed %; Component/Sub-Component aligned with Phase-4 Excel |
| 4 | **Data-entry forms** (replace offline returns) | ✅ Implemented | All three trackers + bulk Excel + inline edit |
| 5 | **Master data** (HCs, components, indicators, KPIs, UoM) | ✅ Implemented | `frontend/src/pages/MasterData.jsx`, `backend/master_routes.py` — Admin CRUD |
| 6 | **Validation & duplicate prevention** | ✅ Implemented | Future-month block, negatives, unique indexes, utilisation warning, CPC target lock (`tracker_routes.py`) |
| 7 | **User creation, RBAC** | ✅ Implemented | `frontend/src/pages/UserManagement.jsx`, Admin/CPC/Viewer, `task_role` for Task module |
| 8 | **HC scoping for CPC** | ✅ Implemented | Server-side 403 on wrong HC; report/export scope enforcement |
| 9 | **Reporting** — filter, drill-down, Excel/PDF | ✅ Implemented | `frontend/src/pages/Reports.jsx` sort/search/export; saved views (beyond BRD) |
| 10 | **Audit trail** on every edit | ✅ Implemented | Field-level `{field, old, new}` in `backend/server.py` `audit()`; `frontend/src/pages/AuditLogs.jsx` |
| 11 | **Global Dashboard** | ✅ Implemented | KPI cards, trends, choropleth, heatmap, Pareto, MoM RAG delta, Cabinet Brief PDF |
| 12 | **KPI cards & charts / RAG visuals** | ✅ Implemented | Dashboard + public page |
| 13 | **PMU Task + DPR trackers** (“added later” in BRD) | ✅ Implemented | `PmuTasks.jsx` (Kanban) + `task-management/*` (full workflow) + `DprDeliverables.jsx` |
| 14 | **District extensibility** (future onboarding) | ⚠️ Partial | District master + district rows on trackers; no separate district-court tenant/onboarding flow |

---

## SoW §3 — Seven tracking modules

| SoW module | Status | Notes |
|------------|--------|-------|
| 1. Physical (24 components in SoW text) | ⚠️ Partial vs SoW wording | **17 BRD components implemented**; 7 extra SoW streams routed to **DPR Deliverables** (Scope Charter A-001) |
| 2. Financial | ✅ Implemented | Includes PFMS reconcile column (mock API) |
| 3. Outcome (DPR KPIs) | ✅ Implemented | 19 subjects seeded |
| 4. Global Dashboard | ✅ Implemented | Exceeds SoW (choropleth, heatmap, narrative widget, PPT export) |
| 5. PMU Task Tracker | ✅ Implemented | Simple Kanban **+** separate Task Management app (assign/SLA/evidence/approvals) |
| 6. DPR Deliverables | ✅ Implemented | Milestones + attachments |
| 7. Audit trail (platform-wide) | ✅ Implemented | Trackers + tasks + admin actions |

---

## SoW §4 — Usage model & delivery

| Requirement | Status | Gap |
|-------------|--------|-----|
| CPC form-based entry, HC-scoped | ✅ | — |
| **API ingestion from iJuris** | ⚠️ Partial | `backend/ijuris_routes.py` stub; live = `IJURIS_BASE_URL` + token (A-004 pending) |
| Admin config, override any HC | ✅ | Admin role + period overrides |
| Viewer read-only | ✅ | Viewer + auditor (tasks) |
| Dynamic filterable exportable reports | ✅ | Excel/PDF + PPT dashboard export |
| **Month-over-month comparison** | ⚠️ Partial | MoM RAG delta on dashboard/public; not dedicated MoM columns on Reports page (BRD §9.2) |
| Server-side scope on every query | ✅ | `scope_filter`, CPC checks |
| Baseline Sep 2023–May 2026 + monthly from Jun 2026 | ✅ | Baseline period `2026-05`, monthly periods seeded |
| Extensible data model (district, new trackers) | ✅ | MongoDB master-driven design |
| One-time config, minimal upgrades | ✅ | Aligns with current delivery model |

---

## BRD detailed requirements — spot checks

| BRD section | Requirement | Status |
|-------------|-------------|--------|
| §4 Physical | Target Admin-only; CPC edits Achieved | ✅ CPC target preserved on upsert |
| §4 Financial | CPC enters released & utilised; Admin override | ✅ |
| §4 Outcome | Periodicity, baseline, computed % | ✅ |
| §6 | RAG thresholds configurable (80/65 default) | ✅ Master → RAG thresholds UI |
| §6 | Utilised > released → warning, not block | ✅ |
| §8.1 | Admin, CPC, Viewer roles | ✅ + Task roles |
| §8.2 | Role/jurisdiction change audit-logged with effective date | ⚠️ Partial — audit exists; no explicit effective-date field |
| §9.2 | MoM comparison on reports | ⚠️ Partial — dashboard delta widget, not full report MoM |
| §9.3 | CPC export scoped server-side | ✅ |
| §10 NFR | Data refresh in minutes | ✅ |
| §10 NFR | Full report loads within 5 seconds | ⚠️ Not formally verified in repo |
| §10 NFR | Security, RBAC, TLS | ✅ JWT, lockout, 2FA (Admin), IP allowlist |
| §10 NFR | Audit retained full scheme duration | ✅ Stored in MongoDB; retention policy not documented |
| §10 NFR | Chrome/Edge/Firefox, tablet | ⚠️ Assumed; responsive UI exists, no formal matrix |
| §10 NFR | 28 HCs concurrent monthly window | ⚠️ Designed for; no load-test evidence in repo |
| §10 NFR | WCAG / accessibility | ⚠️ Partial — 18 axe E2E specs; scoped, not full AA sign-off |

---

## Explicitly out of BRD §2.2

| Out of scope | Status |
|--------------|--------|
| Procuring a **new platform** (configure within existing infra) | ✅ Met — custom app on existing stack |

---

## Implemented beyond BRD/SoW

Delivered extras (not missing BRD items):

- Submit / **approval workflow** (CPC → Admin approve/return), period locks, re-open
- **Public transparency** page (`/public`) with full viz bundle
- **Cabinet Brief** scheduled PDF + email outbox
- **Comments / @mentions** on tracker rows
- **Webhooks**, API tokens, anomaly digest, executive **AI narrative** (optional LLM)
- **Redis** cache, **PWA**, backup/restore, Scope Charter e-sign register
- **Task Management** full workflow (export, bulk, SLA jobs, Zoho-style detail UI)
- **11-language i18n framework** (depth varies — see below)

---

## Pending / partial

### P1 — External dependencies (SoW assumptions)

| Item | Status | Blocker |
|------|--------|---------|
| **Live iJuris API** | ⚠️ Stub | e-Committee API access (Scope Charter A-004) |
| **Live PFMS / Bharatkosh** | ⚠️ Mock reconcile | `PFMS_BASE_URL` / credentials (`backend/pfms_routes.py`) |
| **SSO / Parichay** | ⚠️ Partial | OIDC redirect works; callback returns 501 (`backend/sso_routes.py`) |
| **eSign on approval** | ⚠️ Backend stub only | No UI; not wired to submissions (`backend/esign_routes.py`) |

### P2 — BRD fidelity gaps (can be closed in-product)

| Item | BRD ref | Current gap |
|------|---------|-------------|
| **MoM comparison in Reports** | §9.2 | MoM on dashboard only |
| **Role change effective date** | §8.2 | Audit exists; no effective-date field |
| **24 vs 17 components in Physical/Financial** | SoW §3 vs BRD §7 | Decision: stay at 17; extend via Master Data or DPR for 7 extras |
| **Globally unique KPI IDs** | A-002 | Charter marks resolved; verify production master before go-live |
| **RAG threshold formal sign-off** | A-005 | Editable in UI; DoJ signature pending on Scope Charter |
| **Log hours / time tracking** (Task detail UI) | Recent UI work | Placeholder tab only |
| **Task fund fields ↔ Financial Tracker** | Task detail fields | UI fields exist; not synced from Financial Tracker |

### P3 — i18n & accessibility

| Item | Status |
|------|--------|
| **Hindi** full PMIS UI | ✅ |
| **Marathi + 8 regional** full PMIS UI | ⚠️ Partial — native `tasks.*`; PMIS pages mostly EN |
| **Urdu RTL** | ⚠️ Partial |
| **WCAG 2.1 AA** formal compliance | ⚠️ Scoped axe tests; not full certification |

### P4 — Operational / governance

| Item | Status |
|------|--------|
| Scope Charter **electronic sign-off** (4 roles) | ⏳ Register live at `/scope-charter`; slots unfilled |
| **SMTP** production email | ⏳ Outbox mocked unless `SMTP_*` env set |
| Formal **performance / load** NFR evidence | ⏳ Not in repository |

---

## Scope decision: 17 (BRD) vs 24 (SoW) components

| Source | Count | PMIS decision |
|--------|-------|---------------|
| **BRD v3** | **17** | ✅ **Canonical** for Physical/Financial trackers |
| **SoW** | **24** | 7 additional work-streams → **DPR Deliverables** module (A-001); Admin can add components via Master Data without code change |

See `docs/SCOPE_CHARTER.md` Decision 1.

---

## Scope Charter open actions

| ID | Decision | Owner | Status |
|----|----------|-------|--------|
| A-001 | 17 vs 24 components — route 7 SoW extras to DPR | DoJ + e-Committee | ✅ Resolved (counter-sign pending) |
| A-002 | Globally unique KPI IDs | PMU Tech Lead | ✅ Resolved in seed (verify before go-live) |
| A-003 | 2FA for Admin | DoJ Nodal Officer | ✅ Enforced |
| A-004 | iJuris API access timeline | e-Committee | ⏳ Pending external |
| A-005 | RAG thresholds final sign-off | DoJ Secretary | ⏳ Pending sign-off |

---

## Key file references

| Area | Paths |
|------|-------|
| Trackers | `backend/tracker_routes.py`, `backend/bulk_routes.py`, `frontend/src/pages/*Tracker.jsx` |
| Master data | `backend/master_routes.py`, `frontend/src/pages/MasterData.jsx` |
| Dashboard / public | `backend/dashboard_routes.py`, `frontend/src/pages/Dashboard.jsx`, `frontend/src/pages/PublicProgress.jsx` |
| Reports / export | `backend/export_routes.py`, `frontend/src/pages/Reports.jsx` |
| Workflow | `backend/submissions_routes.py`, `frontend/src/pages/Submissions.jsx` |
| Audit | `backend/server.py`, `frontend/src/pages/AuditLogs.jsx` |
| PMU / DPR | `backend/pmu_routes.py`, `frontend/src/pages/PmuTasks.jsx`, `frontend/src/pages/DprDeliverables.jsx` |
| Task Management | `backend/task_routes.py`, `backend/task_service.py`, `frontend/src/pages/task-management/` |
| Integrations | `backend/ijuris_routes.py`, `backend/pfms_routes.py`, `backend/sso_routes.py`, `backend/esign_routes.py` |
| Seed / master constants | `backend/seed_constants.py`, `backend/seed_data.json` |
| Tests | `backend/tests/` (103 pytest), `frontend/e2e/` (47 E2E + 18 axe) |

---

## Pre-production checklist

1. Sign Scope Charter — A-004 (iJuris), A-005 (RAG thresholds), remaining signature slots  
2. Publish clean KPI master — globally unique IDs (A-002)  
3. Confirm 17 vs 24 with e-Committee in writing (A-001 counter-sign)  
4. Wire or defer iJuris, PFMS, Parichay, eSign with explicit stub vs live dates  
5. Add Reports MoM view if BRD §9.2 strict compliance is required  
6. Complete HI + priority regional locales if stakeholder access requires it  
7. Run performance test on full Physical report (28 HC × 17 components) against 5 s NFR  

---

## Bottom line

**Core PMIS** (three trackers, master data, RBAC, dashboard, reports, audit, PMU/DPR modules, baseline/periods, approval workflow) is **implemented** and aligns with both **BRD v3** and **SoW**.

**Pending work** clusters into: **(1)** external integrations (iJuris, PFMS, Parichay, eSign), **(2)** BRD polish (report MoM, effective dates, formal NFR evidence), and **(3)** governance/i18n/accessibility sign-offs — not missing core tracker functionality.
