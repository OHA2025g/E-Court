# eCourts Phase III PMIS — Scope Charter

**Document type:** Decision charter
**Owner:** Department of Justice (DoJ) / PMU
**Status:** Electronic sign-off available in PMIS — pending completion of all Section 9 slots
**Last updated:** February 2026

---

## 1. Purpose

This charter records the **scope decisions** taken during PMIS MVP design (Feb 2026) and flags the open items that need formal sign-off before further onboarding. It is meant to live alongside the BRD and SoW as the *single decisional* document for the platform.

---

## 2. Decision 1 — Component scope: **17 BRD components**

| Source     | Component count | Selected? |
| ---------- | --------------- | --------- |
| **BRD v3** | 17              | **YES ✅** |
| SoW        | 24              | No        |

### Decided
The MVP and current production seed track the **17 BRD-canonical components**:

1. e-Sewa Kendras
2. Paperless Courts
3. Expansion of Virtual Courts
4. Live Streaming
5. Digitisation of Court Records
6. Video Conferencing Upgrade
7. Solar Power for ICT
8. Additional Hardware — Phase I & II
9. ICT for Newly Set-Up Courts
10. HC & DC Website Migration — S3WaaS
11. Cloud Computing & Storage
12. ICT Training / Change Management
13. NSTEP Expansion
14. Software Development
15. PMU in e-Committee & DoJ
16. Connectivity — Primary + Redundancy
17. e-Office for HCs & District Courts

### Rationale
- The BRD is the **business-authoritative** document signed off by DoJ and the High Courts' CPCs. The SoW is the procurement/RFP document and references a broader sanctioned umbrella (24 components, including ancillary work-streams not yet broken into indicators).
- All 28 High Courts' baseline progress is already submitted against the 17 BRD components — staying on 17 preserves data continuity from Sep 2023 onwards.
- The data model (`components` collection in MongoDB) is **table-driven**; expanding from 17 → 24 is a configuration change, not a code change. New components can be added at any future master-data freeze.

### Open Question / Action Item — A-001 *(RESOLVED — Iteration 3)*
~~Confirm in writing with the e-Committee whether the additional 7 SoW components (e.g., DPR-specific work-streams beyond the 17) should be brought under the same PMIS umbrella as new indicators, OR tracked as **DPR Deliverables** in the existing DPR module.~~

> **Decision (Iteration 3, Feb 2026):** Route the additional 7 SoW work-streams through the **DPR Deliverables tracker**. The 17 BRD components remain the canonical Physical-Tracker scope. *Rationale:* the SoW extras are milestone-driven (not indicator-driven monthly numerics) and the DPR module is purpose-built for that grain. **Admin can now also extend the 17 to 24 via the new Master-Data CRUD UI** (Master Data → Components → Add) without code changes if business changes its mind. Pending only a written counter-sign from the e-Committee Secretariat (file note attached separately).

---

## 3. Decision 2 — Outcome subjects: **19** (BRD)

The BRD's 19 outcome subjects (eFiling, ICJS, NSTEP, etc.) have been seeded as the canonical KPI master. KPI IDs from the Excel dummy data have been retained.

### Open Question / Action Item — A-002
Some Excel KPI IDs are repeated across subjects (e.g., `5.1` appears under both NSTEP and Virtual Courts). Master data should be re-published with **globally unique KPI IDs** before any High Court is asked to submit outcome data via PMIS in production. The current import skipped duplicate-ID rows.

---

## 4. Decision 3 — Module phasing: **All 12 MVP modules in scope**

| #  | Module                                    | Status (Feb 2026)               |
| -- | ----------------------------------------- | ------------------------------- |
| 1  | Login + RBAC + jurisdiction scoping       | ✅ Live (with brute-force lock) |
| 2  | Master Data Management                    | ✅ Live (read-only UI)          |
| 3  | Physical Tracker                          | ✅ Live + Bulk Excel upload     |
| 4  | Financial Tracker                         | ✅ Live                         |
| 5  | Outcome Tracker                           | ✅ Live                         |
| 6  | Global Dashboard                          | ✅ Live + Cabinet PDF brief     |
| 7  | Reports & Export (Excel + PDF)            | ✅ Live                         |
| 8  | Audit Trail                               | ✅ Live                         |
| 9  | PMU Task Tracker                          | ✅ Live + evidence attachments  |
| 10 | DPR Deliverables                          | ✅ Live + evidence attachments  |
| 11 | iJuris API Ingestion **(STUB / MOCKED)**  | ⚠ Pending live API access      |
| 12 | Baseline + Monthly period management      | ✅ Live (baseline 2026-05)      |

---

## 5. Decision 4 — Authentication: JWT custom auth (Admin-seeded)

- Bcrypt-hashed passwords, httpOnly cookies + body token, 8-hour access / 7-day refresh.
- **Brute-force lockout:** 5 failures within 15 minutes → 15-minute lock. Self-hosted CAPTCHA required after 3 failures. Lock auto-clears on Admin password reset.
- **Password reset:** Admin-driven (BRD requirement). Generates a 12-char temporary password to share via secure channel. Users are forced to `/change-password` on next login.
- **Admin 2FA (A-003):** TOTP via authenticator app is **mandatory** for Admin accounts; cannot be disabled.
- **Optional 2FA (P3):** CPC and Viewer accounts may **optionally** enable TOTP under Account / 2FA; configurable mandatory roles via `REQUIRE_2FA_ROLES` env (default `Admin` only).
- **Session management:** Server-side sessions with list/revoke in Account settings.
- **Password policy:** Min 12 chars, complexity rules, no reuse of last 5 passwords, 90-day rotation.
- **Admin IP allowlist:** Configurable under Master Data → Security (disabled by default).
- **Upload validation:** Magic-byte checking on evidence and bulk Excel uploads.
- No self-service registration. Admin provisions users via `User Management`.

### Resolved — A-003 (Admin 2FA)
Mandatory TOTP 2FA for Admin accounts is **implemented and enforced** in PMIS (Charter A-003). CPC and Viewer roles may optionally enroll via Account settings; set `REQUIRE_2FA_ROLES=Admin,CPC` to mandate additional roles.

### Electronic sign-off (P3)
Section 9 sign-off slots are recorded in PMIS at **Scope Charter** (`/scope-charter`) with audit trail. When all four roles sign, document status becomes **SIGNED**.

---

## 6. Decision 5 — iJuris integration: **dependency-driven**

- The `/api/ijuris/ingest` endpoint is a **STUB** that mirrors the manual-entry validation pipeline (HC scope, future-month block, duplicates, audit).
- The day iJuris API access is granted, the integration becomes a *config* change (endpoint base URL + token); the validation layer does not move.

### Open Question / Action Item — A-004
e-Committee to confirm API access timeline. Until then, manual entry + bulk Excel upload remain the primary data-capture modes.

---

## 7. Decision 6 — Data granularity

- **Current grain:** High Court level (28 HCs) with optional **district-level rows** on Physical and Financial trackers (`district` field; `null` = HC-level entry).
- **Dashboard and reports** roll district rows up to HC totals (sum target/achieved/released/utilized before computing % and RAG) so national and HC views are not double-counted when CPCs enter by district.
- **Outcome tracker** retains `granularity` enum (State / District / National); district is not a separate column on outcome entries in this iteration.
- District master data is Admin-managed (create/edit/deactivate via Master Data UI; inactive districts listed with `include_inactive=true`).

---

## 8. Decisions Pending (consolidated)

| ID    | Decision needed                                                                 | Owner             | Target date | Status |
| ----- | ------------------------------------------------------------------------------- | ----------------- | ----------- | ------ |
| A-001 | 17 vs 24 components — where to slot the 7 extra SoW work-streams                | DoJ + e-Committee | 2026-03-15  | ✅ RESOLVED (route to DPR; Admin can extend via Master-Data CRUD) |
| A-002 | Globally unique KPI IDs — clean Excel KPI master before production go-live      | PMU Tech Lead     | 2026-03-31  | ✅ RESOLVED (dedup logic added in iteration 3 seed) |
| A-003 | 2FA for Admin accounts                                                          | DoJ Nodal Officer | 2026-04-15  | ✅ ENFORCED (mandatory TOTP for Admin; Charter A-003) |
| A-004 | iJuris API access timeline                                                      | e-Committee       | 2026-04-30  | ⏳ Pending external (live-binding code is config-only switch) |
| A-005 | RAG thresholds final sign-off (default Green ≥80, Amber 65–79, Red <65)         | DoJ Secretary     | 2026-03-30  | ⏳ Pending sign-off (thresholds editable via UI) |

---

## 9. Sign-off

| Role                          | Name | Date | Signature |
| ----------------------------- | ---- | ---- | --------- |
| DoJ Nodal Officer             |      |      |           |
| PMU Director                  |      |      |           |
| e-Committee Secretariat Rep.  |      |      |           |
| HC CPC Coordinators (rep.)    |      |      |           |
