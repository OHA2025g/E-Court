"""ETL helpers: wide DoJ Physical Tracker Excel → PMIS long-format physical rows.

Source shape (sheet Physical_Tracker, 2-row header):
  Sr. No. | High Courts | Digitization (Target/Achieved Pgs) | eSewa Kendras (DPR/eCommittee/CPC) …

Target shape (PMIS physical_entries / bulk template):
  High Court | Component | Sub-Component | District | Target | Achieved | Remarks

Digitization pages are absolute page counts → convert to Crore Pages (/ 1e7).
eSewa counts stay Absolute Count.
"""
from __future__ import annotations

from typing import Any, Optional

from financial_excel import HC_ALIASES, map_high_court, rupees_to_crore

PAGES_PER_CRORE = 10_000_000  # same scale as ₹→Cr for page counts in Cr.

BULK_HEADERS = [
    "High Court",
    "Component",
    "Sub-Component",
    "District",
    "Target",
    "Achieved",
    "Remarks",
]

DEFAULT_REMARKS = "ETL: Physical Achieved till Sep 2025 (DoJ source)"

# Canonical indicators matching production physical_entries
INDICATOR_PAGES_DIGITIZED = "No of pages digitized (in Cr.)"
INDICATOR_ESEWA_IN_COMPLEXES = "No of e-sewa kendras in court complexes (in Absolute Count)"

COMPONENT_DIGITISATION = "Digitisation of Court Records"
COMPONENT_ESEWA = "e-Sewa Kendras"


def _norm(s: Any) -> str:
    return " ".join(str(s or "").strip().lower().split())


def pages_to_crore(value: Any, decimals: int = 4) -> Optional[float]:
    """Absolute page count → Crore Pages."""
    return rupees_to_crore(value, decimals=decimals)


def _num(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def transform_physical_achieved_sep2025_rows(
    rows: list[tuple | list],
    *,
    remarks: str = DEFAULT_REMARKS,
    include_zero_achieved: bool = True,
) -> dict[str, Any]:
    """
    Parse 2-row-header Physical_Tracker sheet into long PMIS records.

    Column layout (0-based, after inspecting source Excel):
      0 Sr.No | 1 High Courts
      2 Digitization Target Pgs | 3 Achieved Pgs | 4 %
      5 eSewa Target DPR | 6 Achieved eCommittee | 7 %
      8 eSewa Target CPC | 9 Achieved CPC | 10 %
    """
    if not rows or len(rows) < 3:
        raise ValueError("Physical sheet needs header rows + data")

    # Data starts at row index 2 (Excel row 3)
    records: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    skipped_blank = 0
    unknown_hc = 0

    for r_i, row in enumerate(rows[2:], start=3):
        if not row or all(c is None or str(c).strip() == "" for c in row):
            skipped_blank += 1
            continue
        raw_hc = row[1] if len(row) > 1 else None
        hc_key = _norm(raw_hc)
        if not hc_key or hc_key.startswith("total"):
            skipped_blank += 1
            continue
        hc = map_high_court(raw_hc)
        if not hc:
            unknown_hc += 1
            issues.append({"row": r_i, "error": f"Unmapped High Court: {raw_hc!r}"})
            continue

        # --- Digitization / Scanning → pages digitized (Cr.) ---
        dig_target = pages_to_crore(row[2] if len(row) > 2 else None)
        dig_ach = pages_to_crore(row[3] if len(row) > 3 else None)
        if dig_ach is not None or dig_target is not None:
            if dig_ach is None:
                dig_ach = 0.0
            if include_zero_achieved or dig_ach != 0:
                records.append({
                    "high_court": hc,
                    "component": COMPONENT_DIGITISATION,
                    "indicator": INDICATOR_PAGES_DIGITIZED,
                    "district": None,
                    "target": dig_target,
                    "achieved": dig_ach,
                    "remarks": remarks,
                    "source_row": r_i,
                    "measure": "digitization_pages",
                })

        # --- eSewa Kendras aggregate → kendras in court complexes ---
        # Prefer DPR target + CPC achieved; fall back to eCommittee achieved.
        esk_target = _num(row[5] if len(row) > 5 else None)
        if esk_target is None:
            esk_target = _num(row[8] if len(row) > 8 else None)
        esk_ach = _num(row[9] if len(row) > 9 else None)
        if esk_ach is None:
            esk_ach = _num(row[6] if len(row) > 6 else None)

        if esk_ach is not None or esk_target is not None:
            if esk_ach is None:
                esk_ach = 0.0
            if include_zero_achieved or esk_ach != 0:
                records.append({
                    "high_court": hc,
                    "component": COMPONENT_ESEWA,
                    "indicator": INDICATOR_ESEWA_IN_COMPLEXES,
                    "district": None,
                    "target": esk_target,
                    "achieved": esk_ach,
                    "remarks": remarks,
                    "source_row": r_i,
                    "measure": "esewa_kendras",
                })

    return {
        "records": records,
        "stats": {
            "source_data_rows": max(0, len(rows) - 2),
            "records": len(records),
            "digitization_rows": sum(1 for r in records if r["measure"] == "digitization_pages"),
            "esewa_rows": sum(1 for r in records if r["measure"] == "esewa_kendras"),
            "skipped_blank": skipped_blank,
            "unknown_high_courts": unknown_hc,
            "unique_high_courts": len({r["high_court"] for r in records}),
            "total_achieved_digitization_cr": round(
                sum(r["achieved"] for r in records if r["measure"] == "digitization_pages"), 4
            ),
            "total_achieved_esewa": round(
                sum(r["achieved"] for r in records if r["measure"] == "esewa_kendras"), 4
            ),
        },
        "issues": issues,
    }


def records_to_bulk_rows(records: list[dict[str, Any]]) -> list[list[Any]]:
    out = [list(BULK_HEADERS)]
    for r in records:
        out.append([
            r["high_court"],
            r["component"],
            r["indicator"],
            r.get("district") or "",
            "" if r.get("target") is None else r["target"],
            "" if r.get("achieved") is None else r["achieved"],
            r.get("remarks") or "",
        ])
    return out


def merge_into_physical_baseline(
    baseline: list[dict[str, Any]],
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Update target/achieved on matching (HC, component, indicator) seed rows."""
    by_key = {
        (r["high_court"], r["component"], r["indicator"]): dict(r)
        for r in baseline
    }
    updated = inserted = unchanged = 0
    for rec in records:
        key = (rec["high_court"], rec["component"], rec["indicator"])
        if key in by_key:
            existing = by_key[key]
            changed = False
            if rec.get("target") is not None and existing.get("target") != rec["target"]:
                existing["target"] = rec["target"]
                changed = True
            if rec.get("achieved") is not None and existing.get("achieved") != rec["achieved"]:
                existing["achieved"] = rec["achieved"]
                changed = True
            if changed:
                updated += 1
            else:
                unchanged += 1
        else:
            by_key[key] = {
                "high_court": rec["high_court"],
                "component": rec["component"],
                "indicator": rec["indicator"],
                "target": rec.get("target"),
                "achieved": rec.get("achieved"),
            }
            inserted += 1
    return list(by_key.values()), {"updated": updated, "inserted": inserted, "unchanged": unchanged}


# Re-export for scripts that only import physical_excel
__all__ = [
    "BULK_HEADERS",
    "DEFAULT_REMARKS",
    "HC_ALIASES",
    "map_high_court",
    "pages_to_crore",
    "transform_physical_achieved_sep2025_rows",
    "records_to_bulk_rows",
    "merge_into_physical_baseline",
]
