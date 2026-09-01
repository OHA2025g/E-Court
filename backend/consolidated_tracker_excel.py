"""ETL: consolidated Physical + Financial long Excel (Sr. No. first) → PMIS bulk rows.

Source shape (2 sheets, 1-row header):
  Physical Tracker:
    Sr. No. | Court | Component | Description | Start Period | End Period |
    Target | Achieved | Physical Tracker Remarks
  Financial Tracker:
    Sr. No. | Court | Component | Description | Start Period | End Period |
    Funds Released (₹) | Funds Utilised (₹) | Financial Tracker Remarks

Target shapes match Admin bulk templates (amounts in ₹ Cr for financial;
e-Sewa uses DPR/CPC columns).
"""
from __future__ import annotations

import re
from typing import Any, Optional

from financial_excel import (
    BULK_HEADERS as FIN_BULK_HEADERS,
    COMPONENT_ALIASES,
    map_high_court,
    rupees_to_crore,
)
from physical_excel import BULK_HEADERS as PHYS_BULK_HEADERS
from seed_constants import (
    COMPONENT_INDICATORS,
    NSC_COMPONENT,
    NSC_FINANCIAL_COMPLEX,
    NSC_FINANCIAL_ROOMS,
)

DEFAULT_REMARKS_PHYSICAL = "ETL: Consolidated Physical Tracker (DoJ long format)"
DEFAULT_REMARKS_FINANCIAL = "ETL: Consolidated Financial Tracker (DoJ long format)"

# Extra aliases for this consolidated workbook (typos / slash variants / CPC brackets).
CONSOLIDATED_COMPONENT_ALIASES: dict[str, str] = {
    **COMPONENT_ALIASES,
    "expansion of virtual courts/ online courts": "Expansion of Virtual Courts",
    "expansion of virtual courts / online courts": "Expansion of Virtual Courts",
    "additional hardware (phase i & ii replacement)": "Additional Hardware — Phase I & II",
    "ict in newly steup court rooms [set up after 31.12.2019]": "ICT for Newly Set-Up Courts",
    "ict in newly setup court rooms [set up after 31.12.2019]": "ICT for Newly Set-Up Courts",
    "ict in newly steup court complex [set up after 31.12.2019]": "ICT for Newly Set-Up Courts",
    "ict in newly setup court complex [set up after 31.12.2019]": "ICT for Newly Set-Up Courts",
    "software development [cpc office - technical manpower]": "Software Development",
    "software development [cpc office – technical manpower]": "Software Development",
    # Not in BRD master list — preserved as-is so funds/counts are not dropped.
    "ict in high courts": "ICT in High Courts",
}

# Description (Excel) → preferred Sub-Component / indicator per canonical component.
DESCRIPTION_INDICATOR_ALIASES: dict[str, dict[str, str]] = {
    "e-Sewa Kendras": {
        "number of e-sewa kendras in court complexes (in absolute count)": (
            "No of e-sewa kendras in court complexes (in Absolute Count)"
        ),
    },
    "Paperless Courts": {
        "number of paperless courts (in absolute count)": (
            "No of paperless courts (in Absolute Count)"
        ),
    },
    "Expansion of Virtual Courts": {
        "number of virtual courts (in absolute count)": (
            "No of virtual courts operational (in Absolute Count)"
        ),
    },
    "Live Streaming": {
        "number of courts (in absolute count)": (
            "No of court rooms enabled for live streaming (in Absolute Count)"
        ),
    },
    "Digitisation of Court Records": {
        "number of pages digitized (in cr.)": "No of pages digitized (in Cr.)",
    },
    "Video Conferencing Upgrade": {
        "number of video conference (in absolute count)": (
            "No of video conference units installed (in Absolute Count)"
        ),
    },
    "Solar Power for ICT": {
        "total units of power generated (kwh)": (
            "No of solar panels installed (in Absolute Count)"
        ),
        "number of solar panels installed (in absolute count)": (
            "No of solar panels installed (in Absolute Count)"
        ),
    },
    "Additional Hardware — Phase I & II": {
        "number of courts (in absolute count)": (
            "No of Courts upgraded with new infrastructure (in Absolute Count)"
        ),
    },
    "ICT for Newly Set-Up Courts": {
        "number of courts (in absolute count)": "No of new Court Rooms covered (in Absolute Count)",
        "number of court complex (in absolute count)": "No of new Court Complexes covered (in Absolute Count)",
        "number of court complexes (in absolute count)": "No of new Court Complexes covered (in Absolute Count)",
    },
    "ICT Training / Change Management": {
        "number of training programmes (in absolute count)": (
            "No of training programmes conducted (in Absolute Count)"
        ),
    },
    "NSTEP Expansion": {
        "number of court establishments. (in absolute count)": (
            "No of Court Establishments covered (in Absolute Count)"
        ),
        "number of court establishments (in absolute count)": (
            "No of Court Establishments covered (in Absolute Count)"
        ),
    },
    "Software Development": {
        "number of technical personal engaged": (
            "No of technical support team members recruited (in Absolute Count)"
        ),
        "number of technical personnel engaged": (
            "No of technical support team members recruited (in Absolute Count)"
        ),
    },
    "e-Office for HCs & District Courts": {
        "number of e-office installation. (in absolute count)": (
            "No of Courts implemented e-Office (in Absolute Count)"
        ),
        "number of e-office installation (in absolute count)": (
            "No of Courts implemented e-Office (in Absolute Count)"
        ),
    },
    "ICT in High Courts": {
        "high court bench": "High Court Bench (in Absolute Count)",
    },
}

_INDIAN_COMMA_RE = re.compile(r"(?<=\d),(?=\d)")
_EQ_RESULT_RE = re.compile(r"=\s*([-+]?\d+(?:\.\d+)?)")
_LEADING_NUM_RE = re.compile(
    r"(?i)(?:^|(?<=\s)|(?<=\())([-+]?\d+(?:\.\d+)?)\s*(cr\.?|crore|lakh|lac|pages?|sites?)?\b"
)
_PURE_NUM_RE = re.compile(r"^[-+]?\d+(?:\.\d+)?$")
_NA_TOKENS = {"", "-", "--", "—", "–", "na", "n/a", "nil", "none", "tbd", "yes", "no"}


def _norm(s: Any) -> str:
    return " ".join(str(s or "").strip().lower().split())


def map_consolidated_component(raw: Any) -> Optional[str]:
    key = _norm(raw)
    if not key:
        return None
    return CONSOLIDATED_COMPONENT_ALIASES.get(key)


def is_consolidated_physical_header(header: list[str]) -> bool:
    h = set(header)
    has_court = "court" in h or "high court" in h or "high courts" in h
    return (
        has_court
        and "component" in h
        and "description" in h
        and "target" in h
        and "achieved" in h
        and ("sr. no." in h or "sr no." in h or "sr. no" in h or "s.no." in h)
    )


def is_consolidated_financial_header(header: list[str]) -> bool:
    h = set(header)
    has_court = "court" in h or "high court" in h or "high courts" in h
    has_rel = any("fund" in x and "releas" in x for x in h)
    has_util = any("fund" in x and ("utilis" in x or "utiliz" in x) for x in h)
    return (
        has_court
        and "component" in h
        and has_rel
        and has_util
        and ("sr. no." in h or "sr no." in h or "sr. no" in h or "s.no." in h)
    )


def _header_index_map(header_row: tuple | list) -> dict[str, int]:
    out: dict[str, int] = {}
    for i, cell in enumerate(header_row):
        key = _norm(cell)
        if key and key not in out:
            out[key] = i
    return out


def _cell(row: tuple | list, idx: Optional[int]) -> Any:
    if idx is None or idx < 0:
        return None
    return row[idx] if idx < len(row) else None


def _find_col(imap: dict[str, int], *candidates: str) -> Optional[int]:
    for c in candidates:
        if c in imap:
            return imap[c]
    for key, idx in imap.items():
        for c in candidates:
            if c in key:
                return idx
    return None


def normalize_crore_pages_number(num: float, *, prefer_crore_pages: bool = False) -> float:
    """Convert bare page counts (≥100k) to crore pages when indicator UOM is Cr."""
    if prefer_crore_pages and num >= 100_000:
        return round(num / 10_000_000, 4)
    return num


def parse_messy_quantity(value: Any, *, prefer_crore_pages: bool = False) -> tuple[Optional[float], str]:
    """Parse Target/Achieved cells that mix numbers, units, and prose.

    Returns (numeric_or_None, residual_note). Residual is empty when fully numeric.
    """
    if value is None:
        return None, ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return normalize_crore_pages_number(float(value), prefer_crore_pages=prefer_crore_pages), ""

    raw = str(value).strip()
    if not raw:
        return None, ""
    note = raw
    low = _norm(raw)
    if low in _NA_TOKENS:
        return None, raw if low not in {"", "-"} else ""

    # Collapse Indian grouping commas: 1,36,98,953 → 13698953
    cleaned = _INDIAN_COMMA_RE.sub("", raw)
    cleaned = cleaned.replace(",", "")  # western thousands if any remain oddly
    cleaned_ws = " ".join(cleaned.split())

    # Prefer explicit result after '=' (e.g. 47+35=82)
    m_eq = _EQ_RESULT_RE.search(cleaned_ws.replace(" ", ""))
    if m_eq:
        try:
            return normalize_crore_pages_number(
                float(m_eq.group(1)), prefer_crore_pages=prefer_crore_pages,
            ), note
        except ValueError:
            pass

    # Absolute pages → Cr when labelled
    pages_m = re.search(r"(?i)(\d+(?:\.\d+)?)\s*pages?", cleaned_ws)
    if pages_m and ("page" in low or prefer_crore_pages):
        pages = float(pages_m.group(1))
        return round(pages / 10_000_000, 4), note

    # Crore / Cr
    cr_m = re.search(r"(?i)(\d+(?:\.\d+)?)\s*(?:cr\.?|crore)\b", cleaned_ws)
    if cr_m:
        return float(cr_m.group(1)), note

    # Lakh → Cr pages (1 Lakh pages = 0.01 Cr)
    lakh_m = re.search(r"(?i)(\d+(?:\.\d+)?)\s*(?:lakh|lac)\b", cleaned_ws)
    if lakh_m:
        return round(float(lakh_m.group(1)) / 100.0, 4), note

    # Sites
    sites_m = re.search(r"(?i)(\d+(?:\.\d+)?)\s*sites?\b", cleaned_ws)
    if sites_m:
        return float(sites_m.group(1)), note

    # Pure number after stripping units/prose wrappers
    pure = cleaned_ws.strip()
    if _PURE_NUM_RE.match(pure):
        return normalize_crore_pages_number(
            float(pure), prefer_crore_pages=prefer_crore_pages,
        ), ""

    # Leading number + optional unit token
    m = _LEADING_NUM_RE.search(" " + cleaned_ws)
    if m:
        num = float(m.group(1))
        unit = (m.group(2) or "").lower()
        if unit.startswith("cr") or unit.startswith("crore"):
            return num, note
        if unit in {"lakh", "lac"}:
            return round(num / 100.0, 4), note
        if unit.startswith("page"):
            return round(num / 10_000_000, 4), note
        if unit.startswith("site"):
            return num, note
        # Digitization often stores bare page totals without "pages"
        if prefer_crore_pages:
            return normalize_crore_pages_number(num, prefer_crore_pages=True), note
        # Huge kWH-like solar values: keep as number (caller may blank via policy)
        return num, note

    # Madras-style multi-block page dump: sum all large integers
    if prefer_crore_pages:
        ints = [int(x) for x in re.findall(r"\d{6,}", cleaned_ws)]
        if ints:
            # Prefer unique large blocks; if duplicates from formatting, take unique sum of halves carefully
            total = sum(ints)
            # Heuristic: if text lists HC + District legacy/fresh (4 numbers), sum all
            return round(total / 10_000_000, 4), note

    return None, note


def map_indicator(
    component: str,
    description: Any,
    *,
    source_kind: str = "standard",
) -> Optional[str]:
    if component == NSC_COMPONENT:
        if source_kind == "rooms":
            return "No of new Court Rooms covered (in Absolute Count)"
        if source_kind == "complex":
            return "No of new Court Complexes covered (in Absolute Count)"
    desc_key = _norm(description)
    by_comp = DESCRIPTION_INDICATOR_ALIASES.get(component) or {}
    if desc_key in by_comp:
        return by_comp[desc_key]
    # Fuzzy: first indicator for component if description empty
    inds = COMPONENT_INDICATORS.get(component) or []
    if not desc_key and inds:
        return inds[0]
    # Partial contains
    for k, v in by_comp.items():
        if k in desc_key or desc_key in k:
            return v
    if component == "ICT in High Courts":
        return "High Court Bench (in Absolute Count)"
    if inds:
        return inds[0]
    return None


def _source_kind_from_component_raw(raw_comp: Any) -> str:
    key = _norm(raw_comp)
    if "court rooms" in key or "court room" in key:
        return "rooms"
    if "court complex" in key:
        return "complex"
    if "ict in high courts" in key:
        return "ict_hc"
    return "standard"


def financial_component_for_source(canonical_component: str, source_kind: str) -> str:
    """Financial tracker stores Rooms and Complex as distinct component rows."""
    if canonical_component == NSC_COMPONENT:
        if source_kind == "rooms":
            return NSC_FINANCIAL_ROOMS
        if source_kind == "complex":
            return NSC_FINANCIAL_COMPLEX
    return canonical_component


def transform_consolidated_physical_rows(
    rows: list[tuple | list],
    *,
    remarks_default: str = DEFAULT_REMARKS_PHYSICAL,
) -> dict[str, Any]:
    if not rows:
        raise ValueError("Empty Physical Tracker sheet")
    imap = _header_index_map(rows[0])
    col_court = _find_col(imap, "court", "high court", "high courts")
    col_comp = _find_col(imap, "component")
    col_desc = _find_col(imap, "description")
    col_target = _find_col(imap, "target")
    col_ach = _find_col(imap, "achieved")
    col_rem = _find_col(imap, "physical tracker remarks", "remarks")
    if col_court is None or col_comp is None or col_ach is None:
        raise ValueError(
            "Physical consolidated sheet needs Court, Component, Achieved columns"
        )

    records: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    skipped_blank = 0
    unknown_hc = 0
    unknown_comp = 0
    non_numeric = 0

    for r_i, row in enumerate(rows[1:], start=2):
        if not row or all(c is None or str(c).strip() == "" for c in row):
            skipped_blank += 1
            continue
        raw_hc = _cell(row, col_court)
        raw_comp = _cell(row, col_comp)
        if not raw_hc and not raw_comp:
            skipped_blank += 1
            continue
        hc = map_high_court(raw_hc)
        if not hc:
            unknown_hc += 1
            issues.append({"row": r_i, "error": f"Unmapped High Court: {raw_hc!r}"})
            continue
        comp = map_consolidated_component(raw_comp)
        if not comp:
            unknown_comp += 1
            issues.append({"row": r_i, "error": f"Unmapped Component: {raw_comp!r}"})
            continue
        kind = _source_kind_from_component_raw(raw_comp)

        desc = _cell(row, col_desc)
        indicator = map_indicator(comp, desc, source_kind=kind)
        if not indicator:
            issues.append({
                "row": r_i,
                "error": f"No indicator mapping for {comp!r} / {desc!r}",
            })
            continue

        prefer_cr = comp == "Digitisation of Court Records"
        target_val, target_note = parse_messy_quantity(
            _cell(row, col_target), prefer_crore_pages=prefer_cr
        )
        ach_val, ach_note = parse_messy_quantity(
            _cell(row, col_ach), prefer_crore_pages=prefer_cr
        )

        # Solar: values that look like kWH (very large) are not panel counts — blank numeric
        if comp == "Solar Power for ICT":
            for label, num in (("target", target_val), ("achieved", ach_val)):
                if num is not None and num >= 10_000:
                    if label == "target":
                        target_val = None
                        target_note = target_note or str(_cell(row, col_target) or "")
                    else:
                        ach_val = None
                        ach_note = ach_note or str(_cell(row, col_ach) or "")

        src_remarks = str(_cell(row, col_rem) or "").strip()
        extra_notes = []
        if ach_val is not None and ach_val < 0:
            extra_notes.append(f"Achieved negative in source ({ach_val}); blanked")
            ach_val = None
        if target_val is not None and target_val < 0:
            extra_notes.append(f"Target negative in source ({target_val}); blanked")
            target_val = None
        if target_note and target_val is not None and not str(target_note).replace(".", "").isdigit():
            if not _PURE_NUM_RE.match(_INDIAN_COMMA_RE.sub("", str(target_note)).replace(",", "").strip()):
                extra_notes.append(f"Target raw: {target_note}")
        if ach_note and ach_val is not None and not _PURE_NUM_RE.match(
            _INDIAN_COMMA_RE.sub("", str(ach_note)).replace(",", "").strip()
        ):
            extra_notes.append(f"Achieved raw: {ach_note}")
        if target_val is None and target_note:
            extra_notes.append(f"Target (non-numeric): {target_note}")
        if ach_val is None and ach_note:
            extra_notes.append(f"Achieved (non-numeric): {ach_note}")
        if kind == "rooms":
            extra_notes.append("Source line: newly set-up Court Rooms")
        elif kind == "complex":
            extra_notes.append("Source line: newly set-up Court Complex")

        remarks_parts = [p for p in (src_remarks, *extra_notes, remarks_default) if p]
        remarks = " | ".join(dict.fromkeys(remarks_parts))  # dedupe, keep order

        if ach_val is None and target_val is None and not src_remarks:
            non_numeric += 1
            # Still allow e-Sewa / blank rows with remarks only
            if not remarks:
                issues.append({"row": r_i, "error": "No numeric Target/Achieved", "court": hc, "component": comp})
                continue

        is_esewa = comp == "e-Sewa Kendras"
        rec = {
            "source_row": r_i,
            "high_court": hc,
            "component": comp,
            "indicator": indicator,
            "district": "",
            "target": None if is_esewa else target_val,
            "achieved": None if is_esewa else ach_val,
            "target_dpr": target_val if is_esewa else None,
            "achieved_ecommittee": ach_val if is_esewa else None,
            "target_cpc": target_val if is_esewa else None,
            "achieved_cpc": ach_val if is_esewa else None,
            "remarks": remarks,
            "source_kind": kind,
            "raw_component": str(raw_comp or "").strip(),
        }

        records.append(rec)
    return {
        "records": records,
        "stats": {
            "records": len(records),
            "source_data_rows": max(0, len(rows) - 1),
            "skipped_blank": skipped_blank,
            "unknown_high_courts": unknown_hc,
            "unknown_components": unknown_comp,
            "non_numeric_soft": non_numeric,
            "unique_high_courts": len({r["high_court"] for r in records}),
            "unique_components": len({r["component"] for r in records}),
        },
        "issues": issues,
    }


def transform_consolidated_financial_rows(
    rows: list[tuple | list],
    *,
    remarks_default: str = DEFAULT_REMARKS_FINANCIAL,
) -> dict[str, Any]:
    if not rows:
        raise ValueError("Empty Financial Tracker sheet")
    imap = _header_index_map(rows[0])
    col_court = _find_col(imap, "court", "high court", "high courts")
    col_comp = _find_col(imap, "component")
    col_rel = _find_col(imap, "funds released (₹)", "funds released (rs)", "funds released", "fund released")
    col_util = _find_col(
        imap,
        "funds utilised (₹)",
        "funds utilized (₹)",
        "funds utilised",
        "funds utilized",
        "fund utilised",
        "fund utilized",
    )
    col_rem = _find_col(imap, "financial tracker remarks", "remarks")
    if col_court is None or col_comp is None or col_rel is None or col_util is None:
        raise ValueError(
            "Financial consolidated sheet needs Court, Component, Funds Released, Funds Utilised"
        )

    # Aggregate by (HC, financial component): NSC Rooms and Complex stay separate rows.
    agg: dict[tuple[str, str], dict[str, Any]] = {}
    issues: list[dict[str, Any]] = []
    skipped_blank = 0
    unknown_hc = 0
    unknown_comp = 0

    for r_i, row in enumerate(rows[1:], start=2):
        if not row or all(c is None or str(c).strip() == "" for c in row):
            skipped_blank += 1
            continue
        raw_hc = _cell(row, col_court)
        raw_comp = _cell(row, col_comp)
        if not raw_hc and not raw_comp:
            skipped_blank += 1
            continue
        hc = map_high_court(raw_hc)
        if not hc:
            unknown_hc += 1
            issues.append({"row": r_i, "error": f"Unmapped High Court: {raw_hc!r}"})
            continue
        comp = map_consolidated_component(raw_comp)
        if not comp:
            unknown_comp += 1
            issues.append({"row": r_i, "error": f"Unmapped Component: {raw_comp!r}"})
            continue

        rel_raw = _cell(row, col_rel)
        util_raw = _cell(row, col_util)
        rel_rupees, rel_note = parse_messy_quantity(rel_raw)
        util_rupees, util_note = parse_messy_quantity(util_raw)
        # Dash / NA placeholders → blank (preserve the other fund column).
        rel_na = _norm(rel_raw) in _NA_TOKENS or rel_raw in (None, "")
        util_na = _norm(util_raw) in _NA_TOKENS or util_raw in (None, "")
        if rel_rupees is None and not rel_na:
            issues.append({"row": r_i, "error": f"Non-numeric Funds Released: {rel_raw!r}"})
            continue
        if util_rupees is None and not util_na:
            issues.append({"row": r_i, "error": f"Non-numeric Funds Utilised: {util_raw!r}"})
            continue
        if rel_rupees is None and util_rupees is None:
            skipped_blank += 1
            continue

        src_remarks = str(_cell(row, col_rem) or "").strip()
        kind = _source_kind_from_component_raw(raw_comp)
        fin_comp = financial_component_for_source(comp, kind)
        key = (hc, fin_comp)
        bucket = agg.get(key)
        if bucket is None:
            bucket = {
                "source_row": r_i,
                "high_court": hc,
                "component": fin_comp,
                "district": "",
                "fund_released_rupees": 0.0,
                "fund_utilized_rupees": 0.0,
                "remarks_parts": [],
                "kinds": [],
            }
            agg[key] = bucket
        if rel_rupees is not None:
            bucket["fund_released_rupees"] += float(rel_rupees)
        if util_rupees is not None:
            bucket["fund_utilized_rupees"] += float(util_rupees)
        if src_remarks:
            bucket["remarks_parts"].append(src_remarks)
        if kind in {"rooms", "complex"}:
            bucket["kinds"].append(kind)
        if rel_note and not isinstance(_cell(row, col_rel), (int, float)):
            bucket["remarks_parts"].append(f"Released raw: {rel_note}")
        if util_note and not isinstance(_cell(row, col_util), (int, float)):
            bucket["remarks_parts"].append(f"Utilised raw: {util_note}")

    records: list[dict[str, Any]] = []
    for bucket in agg.values():
        kinds = set(bucket["kinds"])
        parts = list(dict.fromkeys(bucket["remarks_parts"]))
        if "rooms" in kinds:
            parts.insert(0, "Source: newly set-up Court Rooms")
        elif "complex" in kinds:
            parts.insert(0, "Source: newly set-up Court Complex")
        parts.append(remarks_default)
        records.append({
            "source_row": bucket["source_row"],
            "high_court": bucket["high_court"],
            "component": bucket["component"],
            "district": "",
            "fund_released": rupees_to_crore(bucket["fund_released_rupees"], decimals=None),
            "fund_utilized": rupees_to_crore(bucket["fund_utilized_rupees"], decimals=None),
            "fund_released_rupees": bucket["fund_released_rupees"],
            "fund_utilized_rupees": bucket["fund_utilized_rupees"],
            "source_rupees_released": bucket["fund_released_rupees"],
            "source_rupees_utilized": bucket["fund_utilized_rupees"],
            "remarks": " | ".join(p for p in parts if p),
        })

    return {
        "records": records,
        "stats": {
            "records": len(records),
            "source_data_rows": max(0, len(rows) - 1),
            "skipped_blank": skipped_blank,
            "unknown_high_courts": unknown_hc,
            "unknown_components": unknown_comp,
            "unique_high_courts": len({r["high_court"] for r in records}),
            "unique_components": len({r["component"] for r in records}),
            "total_released_cr": round(sum(r["fund_released"] or 0 for r in records), 4),
            "total_utilized_cr": round(sum(r["fund_utilized"] or 0 for r in records), 4),
        },
        "issues": issues,
    }


def physical_records_to_bulk_rows(records: list[dict[str, Any]]) -> list[list[Any]]:
    out = [list(PHYS_BULK_HEADERS)]
    for r in records:
        out.append([
            r["high_court"],
            r["component"],
            r["indicator"],
            r.get("district") or "",
            "" if r.get("target") is None else r["target"],
            "" if r.get("achieved") is None else r["achieved"],
            "" if r.get("target_dpr") is None else r["target_dpr"],
            "" if r.get("achieved_ecommittee") is None else r["achieved_ecommittee"],
            "" if r.get("target_cpc") is None else r["target_cpc"],
            "" if r.get("achieved_cpc") is None else r["achieved_cpc"],
            r.get("remarks") or "",
        ])
    return out


def financial_records_to_bulk_rows(
    records: list[dict[str, Any]],
    *,
    amounts_as_rupees: bool = False,
) -> list[list[Any]]:
    out = [list(FIN_BULK_HEADERS)]
    for r in records:
        released = r.get("fund_released")
        utilized = r.get("fund_utilized")
        if amounts_as_rupees:
            released = r.get("source_rupees_released", r.get("fund_released_rupees"))
            utilized = r.get("source_rupees_utilized", r.get("fund_utilized_rupees"))
        out.append([
            r["high_court"],
            r["component"],
            r.get("district") or "",
            "" if released is None else released,
            "" if utilized is None else utilized,
            r.get("remarks") or "",
        ])
    return out
