# Financial Tracker ETL — Released & Utilised

Reusable pipeline to load DoJ wide-format Excel into PMIS `financial_entries`.

## Sources

| Mode | File | Sheet | PMIS field |
|------|------|-------|------------|
| `released` | `Financial_Tracker_Data_for_Released_Fund_2024-2027.xlsx` | `Funds_Released` | `fund_released` |
| `utilised` | `Financial_Tracker_Data_for_Utilised_Fund_2023-2024.xlsx` | `Funds_Utilised` | `fund_utilized` |

Both are wide: High Court × component columns, amounts in absolute Indian Rupees.

### Phase-III utilised component mapping

| Excel header | Canonical BRD component |
|--------------|-------------------------|
| Digitization / Scanning (High Courts + Distt. Courts) | Digitisation of Court Records |
| eSewa Kendras (Porta Cabins+LAN Points) | e-Sewa Kendras |
| Addl. Hardware Components | Additional Hardware — Phase I & II |
| Solar Power | Solar Power for ICT |
| Handheld Devices/ NSTEP | NSTEP Expansion |
| Capacity Building /Training | ICT Training / Change Management |
| Additional requirement (For North Eastern States) | ICT for Newly Set-Up Courts |
| Software Development/ Technical Manpower | Software Development |

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
- Read the mode’s sheet with `data_only=True`.
- Skip total rows (e.g. `Total (In Cr.)`).
- Code: `backend/scripts/import_financial_excel.py` → `extract_sheet_rows()`.

### 2. Transform
- Map High Court aliases (`Orissa` → `Odisha`, Gauhati variants, etc.).
- Map component headers to BRD-canonical names (`COMPONENT_ALIASES`).
- Unpivot to long rows: `(high_court, component, fund_released|fund_utilized)`.
- Convert ₹ → ₹ Cr (4 decimal places).
- Leave the *other* fund column blank; CLI enriches it from seed before load so existing values are preserved.
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

# --- Funds Released 2024–2027 ---
python scripts/import_financial_excel.py --mode released --dry-run
python scripts/import_financial_excel.py --mode released \
  --write-bulk-xlsx --update-seed --load-api \
  --api-url https://ecourt.demoapi.agrayianailabs.com \
  --admin-email admin@pmis.gov.in --admin-password 'Admin@PMIS2026' \
  --period 2026-05

# --- Funds Utilised 2023–2024 ---
python scripts/import_financial_excel.py --mode utilised --dry-run
python scripts/import_financial_excel.py --mode utilised \
  --write-bulk-xlsx --update-seed --load-api \
  --api-url https://ecourt.demoapi.agrayianailabs.com \
  --admin-email admin@pmis.gov.in --admin-password 'Admin@PMIS2026' \
  --period 2026-05
```

## Reuse for future Excels

1. Drop a new wide file (or pass `--source` / `--sheet`).
2. Add any new HC / component spellings to `HC_ALIASES` / `COMPONENT_ALIASES`.
3. Run `--dry-run` until `unknown_high_courts == 0`.
4. Run `--write-bulk-xlsx --update-seed --load-api --period YYYY-MM`.
5. Choose `--mode released` or `--mode utilised` for the target field.

## Last run snapshots

### Released 2024–2027
| Metric | Value |
|--------|--------|
| Records | 364 |
| Components | 13 |
| Total released | ₹ 2,372.4434 Cr |
| Periods | `2026-05`, `2026-07` |

### Utilised 2023–2024
| Metric | Value |
|--------|--------|
| Records | 223 |
| Components | 8 |
| Total utilised | ₹ 611.8843 Cr |
| Periods | `2026-05`, `2026-07` |
| Bulk artefact | `etl_output/financial_funds_utilised_2023_2024_bulk.xlsx` |
