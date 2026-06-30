"""Parse Phase-4 Outcome Tracker Excel rows into normalized outcome records."""
from __future__ import annotations

import re
from typing import Any, Callable, Optional

from seed_constants import OUTCOME_SUBJECT_MAP


def fmt_kpi_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, (int, float)):
        return format(float(value), "g")
    return str(value).strip() or None


def normalize_cell(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value).replace("\n", " ")).strip()
    return text or None


def map_outcome_subject(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return raw
    return OUTCOME_SUBJECT_MAP.get(raw.strip(), raw.strip())


def parse_outcome_excel_rows(rows: list[tuple]) -> list[dict]:
    """Parse Sheet1 rows (including header) from Phase-4 Outcome Tracker Excel."""
    if not rows:
        return []

    header = [normalize_cell(c) or "" for c in rows[0]]
    col_hc = _col_idx(header, "high court")
    col_comp = _col_idx(header, "components")
    col_sub = _col_idx(header, "sub-component", "sub component")
    col_kpi = _col_idx(header, "kpid", "kpi id")
    col_kpi_name = _col_idx(header, "kpi", exact=True)
    col_desc = _col_idx(header, "description")
    col_periodicity = _col_idx(header, "periodicity")
    col_gran = _col_idx(header, "granularity")
    col_value = _col_idx_outcome_value(header)

    if min(col_hc, col_kpi, col_gran, col_value) < 0:
        raise ValueError(
            "Missing required columns: High Court, KPID/KPI ID, Granularity, and an OUTCOME value column"
        )

    parsed: list[dict] = []
    current_hc = current_comp = current_sub = None

    for row in rows[1:]:
        if not row or all(c is None for c in row):
            continue
        hc = normalize_cell(row[col_hc]) if col_hc < len(row) else None
        comp = normalize_cell(row[col_comp]) if col_comp >= 0 and col_comp < len(row) else None
        sub = normalize_cell(row[col_sub]) if col_sub >= 0 and col_sub < len(row) else None
        if hc:
            current_hc = hc
        if comp:
            current_comp = comp
        if sub:
            current_sub = sub

        component = map_outcome_subject(current_comp) if current_comp else None
        sub_component = map_outcome_subject(current_sub) if current_sub else component
        subject = sub_component or component
        kpi_id = fmt_kpi_id(row[col_kpi] if col_kpi < len(row) else None)
        if not (current_hc and subject and kpi_id):
            continue

        gran_cell = row[col_gran] if col_gran < len(row) else None
        granularity = normalize_cell(gran_cell) or "District"
        value_cell = row[col_value] if col_value < len(row) else None
        value = None if value_cell in (None, "") else float(value_cell)

        parsed.append({
            "high_court": current_hc,
            "component": component,
            "sub_component": sub_component,
            "subject": subject,
            "kpi_id": kpi_id,
            "kpi": normalize_cell(row[col_kpi_name]) if col_kpi_name >= 0 and col_kpi_name < len(row) else None,
            "description": normalize_cell(row[col_desc]) if col_desc >= 0 and col_desc < len(row) else None,
            "periodicity": normalize_cell(row[col_periodicity]) if col_periodicity >= 0 and col_periodicity < len(row) else None,
            "granularity": granularity,
            "value": value,
        })

    return parsed


def build_kpi_master(outcome_rows: list[dict]) -> dict[tuple[str, str], dict]:
    master: dict[tuple[str, str], dict] = {}
    for row in outcome_rows:
        key = (row["subject"], row["kpi_id"])
        if key in master:
            continue
        master[key] = {
            "subject": row["subject"],
            "kpi_id": row["kpi_id"],
            "component": row.get("component"),
            "sub_component": row.get("sub_component"),
            "kpi": row.get("kpi"),
            "description": row.get("description"),
            "periodicity": row.get("periodicity"),
            "granularity": row.get("granularity") or "District",
            "outcome_type": "Absolute",
            "value_type": "Count",
        }
    return master


def outcome_seed_docs(
    outcome_rows: list[dict],
    reporting_period: str,
    now_utc_fn: Callable,
) -> list[dict]:
    docs = []
    for row in outcome_rows:
        docs.append({
            "high_court": row["high_court"],
            "component": row.get("component"),
            "sub_component": row.get("sub_component"),
            "subject": row["subject"],
            "kpi_id": row["kpi_id"],
            "kpi": row.get("kpi"),
            "description": row.get("description"),
            "granularity": row.get("granularity") or "District",
            "periodicity": row.get("periodicity"),
            "outcome_type": "Absolute",
            "value_type": "Count",
            "baseline": None,
            "value": row.get("value"),
            "computed_percent": None,
            "reporting_period": reporting_period,
            "district": None,
            "remarks": None,
            "created_by": "system",
            "created_at": now_utc_fn(),
        })
    return docs


def _col_idx(header: list[str], *names: str, exact: bool = False) -> int:
    lowered = [h.lower() for h in header]
    for name in names:
        target = name.lower()
        for i, cell in enumerate(lowered):
            if cell == target:
                return i
        if not exact:
            for i, cell in enumerate(lowered):
                if target in cell:
                    return i
    return -1


def _col_idx_outcome_value(header: list[str]) -> int:
    for i, cell in enumerate(header):
        lowered = cell.lower()
        if lowered == "value":
            return i
        if "outcome" in lowered and "going forward" not in lowered:
            return i
    return -1
