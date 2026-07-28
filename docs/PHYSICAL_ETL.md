# Physical Tracker ETL — Achieved till Sep 2025

Reusable pipeline to load DoJ wide-format Physical Excel into PMIS `physical_entries`.

## Source

| Item | Value |
|------|--------|
| File | `Physicial_Tracker_Data_for_Achieved_till_Sep-2025.xlsx` |
| Sheet | `Physical_Tracker` (2-row header) |
| Coverage | Digitization + eSewa Kendras only (28 High Courts) |
| Units | Digitization = absolute pages; eSewa = Absolute Count |

## Target

| Item | Value |
|------|--------|
| Collection | `physical_entries` |
| Period | `2025-09` (also merge into baseline `2026-05` / current months) |
| Channel | Admin `POST /api/physical/bulk` |

### Field mapping

| Excel block | PMIS Component | Sub-Component (indicator) | Target | Achieved |
|-------------|----------------|---------------------------|--------|----------|
| Digitization Target/Achieved Pgs | Digitisation of Court Records | No of pages digitized (in Cr.) | pages ÷ 1e7 | pages ÷ 1e7 |
| eSewa Target DPR / Achieved CPC | e-Sewa Kendras | No of e-sewa kendras in court complexes (in Absolute Count) | Target as per DPR (fallback CPC) | Achieved as per CPC (fallback eCommittee) |

Other BRD components/indicators are **not** in this file and remain unchanged.

## Pipeline stages

```
┌─────────────┐    ┌──────────────┐    ┌─────────────────────────────┐
│ 1. EXTRACT  │ →  │ 2. TRANSFORM │ →  │ 3. LOAD                     │
│ openpyxl    │    │ HC aliases,  │    │ • bulk .xlsx                │
│ 2-row hdr   │    │ pages→Cr,    │    │ • seed physical_baseline    │
│             │    │ unpivot      │    │ • Admin /api/physical/bulk  │
└─────────────┘    └──────────────┘    └─────────────────────────────┘
```

### 1. Extract
- Read `Physical_Tracker` with `data_only=True`.
- Skip blank / total rows.
- Code: `backend/scripts/import_physical_excel.py`.

### 2. Transform
- Map High Courts via shared `financial_excel.HC_ALIASES`.
- Digitization: absolute pages → Crore Pages.
- eSewa: prefer DPR target + CPC achieved.
- Emit long rows matching bulk headers:  
  `High Court | Component | Sub-Component | District | Target | Achieved | Remarks`
- Code: `backend/physical_excel.py`.

### 3. Load
| Sink | Flag |
|------|------|
| Long-format Excel | `--write-bulk-xlsx` |
| Seed baseline | `--update-seed` |
| Live API | `--load-api` |

## Commands

```bash
cd backend

python scripts/import_physical_excel.py --dry-run

python scripts/import_physical_excel.py --write-bulk-xlsx --update-seed --load-api \
  --api-url https://ecourt.demoapi.agrayianailabs.com \
  --admin-email admin@pmis.gov.in --admin-password 'Admin@PMIS2026' \
  --period 2025-09

# Also populate baseline / current months for overall app views
python scripts/import_physical_excel.py --load-api ... --period 2026-05
python scripts/import_physical_excel.py --load-api ... --period 2026-07
```

## Reuse

1. Drop a new wide physical Excel (or `--source`).
2. Extend column mapping in `transform_physical_achieved_sep2025_rows` (or add a new transform) for extra components.
3. `--dry-run` until `unknown_high_courts == 0`.
4. `--write-bulk-xlsx --update-seed --load-api --period YYYY-MM`.

## Last run snapshot

| Metric | Value |
|--------|--------|
| Records | **53** (28 digitization + 25 eSewa; 3 NE eSewa blanks skipped) |
| Digitization achieved | **579.5381 Cr pages** |
| eSewa achieved | **2,236** kendras |
| Periods loaded | `2025-09` (53 insert), `2026-05` (53 update), `2026-07` (53 insert) |
| Bulk artefact | `etl_output/physical_achieved_till_sep_2025_bulk.xlsx` |
| Verify | https://ecourt.demo.agrayianailabs.com → Physical Tracker → period **Physical Achieved till Sep 2025** |
