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
    "gauhati (nagaland)": "Gauhati - Nagaland",
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
COMPONENT_ALIASES: dict[str, str] = {
    "e-sewa kendras": "e-Sewa Kendras",
    "paperless courts": "Paperless Courts",
    "expansion of virtual courts": "Expansion of Virtual Courts",
    "live streaming": "Live Streaming",
    "digitization of entire court records": "Digitisation of Court Records",
    "digitisation of entire court records": "Digitisation of Court Records",
    "digitisation of court records": "Digitisation of Court Records",
    "video conferencing upgrade": "Video Conferencing Upgrade",
    "solar power for ict infrastructure": "Solar Power for ICT",
    "solar power for ict": "Solar Power for ICT",
    "additional hardware (phase i & ii replacement)": "Additional Hardware — Phase I & II",
    "additional hardware — phase i & ii": "Additional Hardware — Phase I & II",
    "ict infrastructure for newly set-up courts": "ICT for Newly Set-Up Courts",
    "ict for newly set-up courts": "ICT for Newly Set-Up Courts",
    "ict training / change management": "ICT Training / Change Management",
    "nstep expansion across states/uts": "NSTEP Expansion",
    "nstep expansion": "NSTEP Expansion",
    "software development": "Software Development",
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

DEFAULT_REMARKS = "ETL: Funds Released 2024-2027 (DoJ source)"


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


def transform_funds_released_rows(
    rows: list[tuple | list],
    *,
    remarks: str = DEFAULT_REMARKS,
    include_zero: bool = True,
) -> dict[str, Any]:
    """
    Extract + Transform wide Funds_Released sheet rows into long PMIS records.

    Returns dict with:
      records: list[{high_court, component, fund_released, remarks, ...}]
      stats / issues for audit
    """
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
        # Skip total / non-data rows
        if _norm(raw_hc) in {"", "total", "grand total"}:
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
            records.append({
                "high_court": hc,
                "component": component,
                "district": None,
                "fund_released": crore,
                "fund_utilized": None,  # preserve existing on load
                "remarks": remarks,
                "source_row": r_i,
                "source_rupees": float(raw_val) if raw_val not in (None, "") else 0.0,
            })

    return {
        "records": records,
        "stats": {
            "source_data_rows": len(rows) - 1,
            "records": len(records),
            "components_mapped": len(comp_cols),
            "skipped_blank": skipped_blank,
            "unknown_high_courts": unknown_hc,
            "unique_high_courts": len({r["high_court"] for r in records}),
            "unique_components": len({r["component"] for r in records}),
            "total_released_crore": round(sum(r["fund_released"] for r in records), 4),
        },
        "issues": issues,
        "component_columns": list(comp_cols.values()),
    }


def records_to_bulk_rows(records: list[dict[str, Any]]) -> list[list[Any]]:
    """Long-format rows for openpyxl / xlsxwriter bulk template."""
    out = [list(BULK_HEADERS)]
    for r in records:
        util = r.get("fund_utilized")
        out.append([
            r["high_court"],
            r["component"],
            r.get("district") or "",
            r.get("fund_released"),
            "" if util is None else util,
            r.get("remarks") or "",
        ])
    return out


def merge_released_into_seed_baseline(
    baseline: list[dict[str, Any]],
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Update fund_released on matching (HC, component) seed rows; append missing."""
    by_key = {(r["high_court"], r["component"]): dict(r) for r in baseline}
    updated = inserted = unchanged = 0
    for rec in records:
        key = (rec["high_court"], rec["component"])
        released = rec["fund_released"]
        if key in by_key:
            existing = by_key[key]
            if existing.get("fund_released") == released:
                unchanged += 1
            else:
                existing["fund_released"] = released
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
                "fund_released": released,
                "fund_utilized": rec.get("fund_utilized"),
                "remarks": rec.get("remarks"),
            }
            inserted += 1
    # Stable order: original HC order then component
    merged = list(by_key.values())
    return merged, {"updated": updated, "inserted": inserted, "unchanged": unchanged}
