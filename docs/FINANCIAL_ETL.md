# Financial Tracker ETL — Funds Released 2024–2027

Reusable pipeline to load DoJ wide-format Excel into PMIS `financial_entries`.

## Source

| Item | Value |
|------|--------|
| File | `Financial_Tracker_Data_for_Released_Fund_2024-2027.xlsx` |
| Sheet | `Funds_Released` |
| Shape | Wide: High Court × component columns |
| Units | Absolute Indian Rupees |
| Coverage | 28 High Courts × 13 components (364 cells) |

Components **not** in this source (remain unchanged in PMIS):  
S3WaaS, Cloud Computing & Storage, PMU, Connectivity.

## Target

| Item | Value |
|------|--------|
| Collection | `financial_entries` |
| Units | ₹ crore (`rupees / 10_000_000`) |
| Period key | `YYYY-MM` (default baseline `2026-05`) |
| Channel | Admin `POST /api/financial/bulk` (same as UI Bulk Upload) |

## Pipeline stages

```
┌─────────────┐    ┌──────────────┐    ┌─────────────────────────────┐
│ 1. EXTRACT  │ →  │ 2. TRANSFORM │ →  │ 3. LOAD (one or more sinks) │
│ openpyxl    │    │ aliases,     │    │ • bulk .xlsx                │
│ wide sheet  │    │ unpivot,     │    │ • seed_data.json            │
│             │    │ ₹ → ₹ Cr     │    │ • Admin bulk API            │
└─────────────┘    └──────────────┘    └─────────────────────────────┘
```

### 1. Extract
- Read sheet `Funds_Released` with `data_only=True`.
- Code: `backend/scripts/import_financial_excel.py` → `extract_sheet_rows()`.

### 2. Transform
- Map High Court aliases (`Orissa` → `Odisha`, Gauhati variants, etc.).
- Map component headers to BRD-canonical names.
- Unpivot to long rows: `(high_court, component, fund_released)`.
- Convert ₹ → ₹ Cr (4 decimal places).
- Leave `fund_utilized` blank so load **preserves** existing utilised / target / allocated.
- Code: `backend/financial_excel.py`.

### 3. Load
| Sink | Flag | Purpose |
|------|------|---------|
| Long-format Excel | `--write-bulk-xlsx` | Admin UI / API bulk template |
| Seed baseline | `--update-seed` | Persist for fresh deploys / empty DB |
| Live API | `--load-api` | Dry-run preview → confirm upsert |

Bulk API is Admin-only and writes `source: bulk_excel`, recalculates utilisation % / variance / RAG, and audits each row.

## Commands

```bash
cd backend

# Inspect only
python scripts/import_financial_excel.py --dry-run

# Local artefacts + seed
python scripts/import_financial_excel.py --write-bulk-xlsx --update-seed

# Production load (baseline period)
python scripts/import_financial_excel.py --load-api \
  --api-url https://ecourt.demoapi.agrayianailabs.com \
  --admin-email admin@pmis.gov.in \
  --admin-password 'Admin@PMIS2026' \
  --period 2026-05

# Preview only against API
python scripts/import_financial_excel.py --load-api --api-dry-run-only \
  --api-url https://ecourt.demoapi.agrayianailabs.com \
  --admin-email admin@pmis.gov.in \
  --admin-password '...' \
  --period 2026-05
```

## Reuse for future Excels

1. Drop new wide file beside the repo (or pass `--source`).
2. Add any new HC / component spellings to `HC_ALIASES` / `COMPONENT_ALIASES` in `financial_excel.py`.
3. Run `--dry-run` until `unknown_high_courts == 0`.
4. Run `--write-bulk-xlsx --update-seed --load-api --period YYYY-MM`.

To load **utilised** from a separate wide file later, extend transform to merge on `(HC, component)` into the `Fund Utilized` column of the same bulk template.

## Last run snapshot

| Metric | Value |
|--------|--------|
| Records | 364 |
| High Courts | 28 |
| Components | 13 |
| Total released | ₹ 2,372.4434 Cr |
| Period | `2026-05` (baseline) |
| Bulk artefact | `etl_output/financial_funds_released_2024_2027_bulk.xlsx` |
