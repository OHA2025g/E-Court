# Consolidated Physical + Financial Tracker ETL

Reusable pipeline for the **2-sheet Sr. No.–first** DoJ long workbook.

## Source

| Item | Value |
|------|--------|
| File | `Physical_Financial_Tracker_Consolidated_2_Sheets_SrNo_First.xlsx` |
| Sheets | `Physical Tracker`, `Financial Tracker` |
| Shape | Long rows: Court × Component × Description |
| Coverage | 28 High Courts × ~15 component lines (Rooms + Complex for newly set-up courts) |

### Physical columns

`Sr. No. | Court | Component | Description | Start Period | End Period | Target | Achieved | Physical Tracker Remarks`

### Financial columns

`Sr. No. | Court | Component | Description | Start Period | End Period | Funds Released (₹) | Funds Utilised (₹) | Financial Tracker Remarks`

## Target

| Tracker | Collection | Units | Channel |
|---------|------------|-------|---------|
| Physical | `physical_entries` | Count / Crore Pages | `POST /api/physical/bulk` |
| Financial | `financial_entries` | ₹ crore (`₹ / 1e7`) | `POST /api/financial/bulk` |

Default reporting period for this workbook’s End Period (2026-06-30): **`2026-06`**.

## Transform rules

- **High Courts** — shared `HC_ALIASES` (`Orissa`→`Odisha`, Gauhati variants, …).
- **Components** — `CONSOLIDATED_COMPONENT_ALIASES` (typos like `Steup`, slash variants, CPC bracket labels).
- **Indicators** — Description → BRD Sub-Component (`DESCRIPTION_INDICATOR_ALIASES`).
- **Messy Target/Achieved** — strips “at the time of demand…”, parses `Cr.` / pages / Lakh / `47+35=82` / `90 Sites`; `NA` → blank.
- **e-Sewa** — Target→`Target as per DPR`, Achieved→`Achieved as per CPC` (bulk clears cumulative Target/Achieved).
- **ICT newly set-up** — Physical keeps separate **Court Rooms** and **Court Complex** rows (distinct indicators). Financial stores separate fund rows per line; dashboards roll both up to the BRD component.
- **ICT in High Courts** — registered in master data as component `ICT in High Courts` (DoJ consolidated tracker extension beyond BRD-17).
- **Solar** — panel-like counts loaded; huge kWH figures stored in Remarks only.

## Pipeline

```
┌─────────────┐    ┌──────────────────────────────┐    ┌─────────────────────┐
│ 1. EXTRACT  │ →  │ 2. TRANSFORM                 │ →  │ 3. LOAD             │
│ openpyxl    │    │ aliases, parse_messy_quantity│    │ bulk .xlsx + API    │
│ 2 sheets    │    │ ₹→Cr, NSC Rooms/Complex split│    │                     │
└─────────────┘    └──────────────────────────────┘    └─────────────────────┘
```

| Stage | Code |
|-------|------|
| Transform | `backend/consolidated_tracker_excel.py` |
| Convert API | `POST /api/etl/convert?tracker=physical\|financial` (auto-detects this format) |
| CLI | `backend/scripts/import_consolidated_tracker_excel.py` |

## Commands

```bash
cd backend

python scripts/import_consolidated_tracker_excel.py --dry-run

python scripts/import_consolidated_tracker_excel.py --write-bulk-xlsx --load-api \
  --api-url http://localhost:8003 \
  --admin-email admin@pmis.gov.in --admin-password 'Admin@PMIS2026' \
  --period 2026-06

# Production
python scripts/import_consolidated_tracker_excel.py --write-bulk-xlsx --load-api \
  --api-url https://ecourt.demoapi.agrayianailabs.com \
  --admin-email admin@pmis.gov.in --admin-password '…' \
  --period 2026-06
```

## Reuse

1. Drop a new file with the same two sheet names / headers (or `--source`).
2. Add any new Court / Component spellings to `CONSOLIDATED_COMPONENT_ALIASES`.
3. `--dry-run` until `unknown_high_courts == 0` and `unknown_components == 0`.
4. `--write-bulk-xlsx --load-api --period YYYY-MM`.
