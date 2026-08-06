"""ETL helpers: wide DoJ Funds-Released Excel → PMIS long-format financial rows.

Source shape (sheet Funds_Released):
  Sr. No. | High Courts | <component columns...>
  Amounts are absolute Indian Rupees.

Target shape (PMIS financial_entries / bulk template):
  High Court | Component | District | Fund Released | Fund Utilized | Remarks
  Amounts are ₹ crore (value / 1e7).
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

# Absolute ₹ → ₹ crore (1 crore = 10,000,000)
RUPEES_PER_CRORE = 10_000_000

# Excel High Court label → canonical HIGH_COURTS name
HC_ALIASES: dict[str, str] = {
    "allahabad": "Allahabad",
    "andhra pradesh": "Andhra Pradesh",
    "bombay": "Bombay",
    "calcutta": "Calcutta",
    "chhattisgarh": "Chhattisgarh",
    "delhi": "Delhi",
    "gauhati (arunachal pradesh)": "Gauhati – Arunachal Pradesh",
    "gauhati (assam)": "Gauhati – Assam",
    "gauhati (mizoram)": "Gauhati – Mizoram",
    "gauhati (nagaland)": "Gauhati – Nagaland",
    "gujarat": "Gujarat",
    "himachal pradesh": "Himachal Pradesh",
    "jammu & kashmir": "Jammu & Kashmir",
    "jammu and kashmir": "Jammu & Kashmir",
    "jharkhand": "Jharkhand",
    "karnataka": "Karnataka",
    "kerala": "Kerala",
    "madhya pradesh": "Madhya Pradesh",
    "madras": "Madras",
    "manipur": "Manipur",
    "meghalaya": "Meghalaya",
    "orissa": "Odisha",
    "odisha": "Odisha",
    "patna": "Patna",
    "punjab & haryana": "Punjab & Haryana",
    "punjab and haryana": "Punjab & Haryana",
    "rajasthan": "Rajasthan",
    "sikkim": "Sikkim",
    "telangana": "Telangana",
    "tripura": "Tripura",
    "uttarakhand": "Uttarakhand",
}

# Excel component header → canonical COMPONENTS[].name
# Includes Phase-III utilised-fund labels and Phase-IV released-fund labels.
COMPONENT_ALIASES: dict[str, str] = {
    "e-sewa kendras": "e-Sewa Kendras",
    "esewa kendras (porta cabins+lan points)": "e-Sewa Kendras",
    "esewa kendras": "e-Sewa Kendras",
    "paperless courts": "Paperless Courts",
    "expansion of virtual courts": "Expansion of Virtual Courts",
    "live streaming": "Live Streaming",
    "digitization of entire court records": "Digitisation of Court Records",
    "digitisation of entire court records": "Digitisation of Court Records",
    "digitisation of court records": "Digitisation of Court Records",
    "digitization / scanning (high courts + distt. courts)": "Digitisation of Court Records",
    "digitization / scanning": "Digitisation of Court Records",
    "video conferencing upgrade": "Video Conferencing Upgrade",
    "solar power for ict infrastructure": "Solar Power for ICT",
    "solar power for ict": "Solar Power for ICT",
    "solar power": "Solar Power for ICT",
    "additional hardware (phase i & ii replacement)": "Additional Hardware — Phase I & II",
    "additional hardware — phase i & ii": "Additional Hardware — Phase I & II",
    "addl. hardware components": "Additional Hardware — Phase I & II",
    "additional hardware components": "Additional Hardware — Phase I & II",
    "ict infrastructure for newly set-up courts": "ICT for Newly Set-Up Courts",
    "ict for newly set-up courts": "ICT for Newly Set-Up Courts",
    # Phase-III NE add-on line → closest BRD component
    "additional requirement (for north eastern states)": "ICT for Newly Set-Up Courts",
    "ict training / change management": "ICT Training / Change Management",
    "capacity building /training": "ICT Training / Change Management",
    "capacity building / training": "ICT Training / Change Management",
    "capacity building": "ICT Training / Change Management",
    "nstep expansion across states/uts": "NSTEP Expansion",
    "nstep expansion": "NSTEP Expansion",
    "handheld devices/ nstep": "NSTEP Expansion",
    "handheld devices / nstep": "NSTEP Expansion",
    "handheld devices/nstep": "NSTEP Expansion",
    "software development": "Software Development",
    "software development/ technical manpower": "Software Development",
    "software development / technical manpower": "Software Development",
    "e-office for high courts & district courts": "e-Office for HCs & District Courts",
    "e-office for hcs & district courts": "e-Office for HCs & District Courts",
}

SKIP_HEADER_KEYS = {"sr. no.", "sr no.", "s.no.", "high courts", "high court", "total"}

BULK_HEADERS = [
    "High Court",
    "Component",
    "District",
    "Fund Released",
    "Fund Utilized",
    "Remarks",
]

DEFAULT_REMARKS_RELEASED = "ETL: Funds Released 2024-2027 (DoJ source)"
DEFAULT_REMARKS_UTILISED = "ETL: Funds Utilised 2023-2024 (DoJ source)"
# Back-compat alias
DEFAULT_REMARKS = DEFAULT_REMARKS_RELEASED

FUND_FIELD_RELEASED = "fund_released"
FUND_FIELD_UTILIZED = "fund_utilized"


def _norm(s: Any) -> str:
    return " ".join(str(s or "").strip().lower().split())


def map_high_court(raw: Any) -> Optional[str]:
    key = _norm(raw)
    if not key:
        return None
    return HC_ALIASES.get(key)


def map_component(raw: Any) -> Optional[str]:
    key = _norm(raw)
    if not key or key in SKIP_HEADER_KEYS:
        return None
    return COMPONENT_ALIASES.get(key)


def rupees_to_crore(value: Any, decimals: int = 4) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        amt = float(value)
    except (TypeError, ValueError):
        return None
    return round(amt / RUPEES_PER_CRORE, decimals)


def extract_wide_header_map(header_row: Iterable[Any]) -> dict[int, str]:
    """Return {column_index: canonical_component_name} for component columns."""
    mapped: dict[int, str] = {}
    unmapped: list[str] = []
    for idx, cell in enumerate(header_row):
        if cell is None:
            continue
        key = _norm(cell)
        if key in SKIP_HEADER_KEYS:
            continue
        canon = map_component(cell)
        if canon:
            mapped[idx] = canon
        else:
            unmapped.append(str(cell).strip())
    if unmapped:
        raise ValueError(
            "Unmapped component column(s): " + ", ".join(unmapped)
            + ". Add aliases in financial_excel.COMPONENT_ALIASES."
        )
    return mapped


def find_hc_column(header_row: Iterable[Any]) -> int:
    for idx, cell in enumerate(header_row):
        if _norm(cell) in {"high courts", "high court"}:
            return idx
    raise ValueError("Header row must include 'High Courts'")


def transform_wide_financial_rows(
    rows: list[tuple | list],
    *,
    fund_field: str = FUND_FIELD_RELEASED,
    remarks: Optional[str] = None,
    include_zero: bool = True,
) -> dict[str, Any]:
    """
    Extract + Transform wide DoJ financial sheet rows into long PMIS records.

    fund_field: 'fund_released' or 'fund_utilized'
    The other fund column is left None so bulk load can preserve existing values.
    """
    if fund_field not in (FUND_FIELD_RELEASED, FUND_FIELD_UTILIZED):
        raise ValueError(f"fund_field must be {FUND_FIELD_RELEASED!r} or {FUND_FIELD_UTILIZED!r}")
    if remarks is None:
        remarks = (
            DEFAULT_REMARKS_RELEASED
            if fund_field == FUND_FIELD_RELEASED
            else DEFAULT_REMARKS_UTILISED
        )
    if not rows:
        raise ValueError("Excel sheet is empty")

    header = list(rows[0])
    hc_col = find_hc_column(header)
    comp_cols = extract_wide_header_map(header)

    records: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    skipped_blank = 0
    unknown_hc = 0

    for r_i, row in enumerate(rows[1:], start=2):
        if not row or all(c is None or str(c).strip() == "" for c in row):
            skipped_blank += 1
            continue
        raw_hc = row[hc_col] if hc_col < len(row) else None
        hc_key = _norm(raw_hc)
        # Skip total / non-data rows (e.g. "Total (In Cr.)")
        if not hc_key or hc_key in {"total", "grand total"} or hc_key.startswith("total"):
            skipped_blank += 1
            continue
        hc = map_high_court(raw_hc)
        if not hc:
            unknown_hc += 1
            issues.append({"row": r_i, "error": f"Unmapped High Court: {raw_hc!r}"})
            continue

        for col_idx, component in comp_cols.items():
            raw_val = row[col_idx] if col_idx < len(row) else None
            crore = rupees_to_crore(raw_val)
            if crore is None:
                continue
            if crore == 0 and not include_zero:
                continue
            rec = {
                "high_court": hc,
                "component": component,
                "district": None,
                "fund_released": None,
                "fund_utilized": None,
                "remarks": remarks,
                "source_row": r_i,
                "source_rupees": float(raw_val) if raw_val not in (None, "") else 0.0,
            }
            rec[fund_field] = crore
            records.append(rec)

    total_key = f"total_{fund_field.replace('fund_', '')}_crore"
    return {
        "records": records,
        "stats": {
            "source_data_rows": len(rows) - 1,
            "records": len(records),
            "fund_field": fund_field,
            "components_mapped": len(comp_cols),
            "skipped_blank": skipped_blank,
            "unknown_high_courts": unknown_hc,
            "unique_high_courts": len({r["high_court"] for r in records}),
            "unique_components": len({r["component"] for r in records}),
            total_key: round(sum((r[fund_field] or 0) for r in records), 4),
        },
        "issues": issues,
        "component_columns": list(comp_cols.values()),
    }


def transform_funds_released_rows(
    rows: list[tuple | list],
    *,
    remarks: str = DEFAULT_REMARKS_RELEASED,
    include_zero: bool = True,
) -> dict[str, Any]:
    """Back-compat wrapper for released-fund ETL."""
    return transform_wide_financial_rows(
        rows,
        fund_field=FUND_FIELD_RELEASED,
        remarks=remarks,
        include_zero=include_zero,
    )


def transform_funds_utilised_rows(
    rows: list[tuple | list],
    *,
    remarks: str = DEFAULT_REMARKS_UTILISED,
    include_zero: bool = True,
) -> dict[str, Any]:
    """Transform wide Funds_Utilised sheet into long PMIS records."""
    return transform_wide_financial_rows(
        rows,
        fund_field=FUND_FIELD_UTILIZED,
        remarks=remarks,
        include_zero=include_zero,
    )


def records_to_bulk_rows(records: list[dict[str, Any]]) -> list[list[Any]]:
    """Long-format rows for openpyxl / xlsxwriter bulk template."""
    out = [list(BULK_HEADERS)]
    for r in records:
        released = r.get("fund_released")
        util = r.get("fund_utilized")
        out.append([
            r["high_court"],
            r["component"],
            r.get("district") or "",
            "" if released is None else released,
            "" if util is None else util,
            r.get("remarks") or "",
        ])
    return out


def merge_fund_field_into_seed_baseline(
    baseline: list[dict[str, Any]],
    records: list[dict[str, Any]],
    fund_field: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Update one fund field on matching (HC, component) seed rows; append missing."""
    if fund_field not in (FUND_FIELD_RELEASED, FUND_FIELD_UTILIZED):
        raise ValueError(f"Unsupported fund_field: {fund_field}")
    by_key = {(r["high_court"], r["component"]): dict(r) for r in baseline}
    updated = inserted = unchanged = 0
    for rec in records:
        key = (rec["high_court"], rec["component"])
        value = rec.get(fund_field)
        if key in by_key:
            existing = by_key[key]
            if existing.get(fund_field) == value:
                unchanged += 1
            else:
                existing[fund_field] = value
                if rec.get("remarks"):
                    existing["remarks"] = rec["remarks"]
                updated += 1
        else:
            by_key[key] = {
                "high_court": rec["high_court"],
                "component": rec["component"],
                "description": None,
                "fund_target": None,
                "fund_allocated": None,
                "fund_released": rec.get("fund_released"),
                "fund_utilized": rec.get("fund_utilized"),
                "remarks": rec.get("remarks"),
            }
            inserted += 1
    return list(by_key.values()), {"updated": updated, "inserted": inserted, "unchanged": unchanged}


def merge_released_into_seed_baseline(
    baseline: list[dict[str, Any]],
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    return merge_fund_field_into_seed_baseline(baseline, records, FUND_FIELD_RELEASED)


def merge_utilised_into_seed_baseline(
    baseline: list[dict[str, Any]],
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    return merge_fund_field_into_seed_baseline(baseline, records, FUND_FIELD_UTILIZED)
