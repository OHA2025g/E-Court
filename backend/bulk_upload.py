"""Shared Excel bulk upload parsing and validation for tracker modules."""
import io
from typing import Any, Callable, Optional

import openpyxl
from fastapi import HTTPException

from rollup import entry_query_key_financial, entry_query_key_physical, resolve_storage_type
from security import validate_upload_bytes
from outcome_excel import parse_outcome_excel_rows
from seed_constants import CLOUD_COMPUTING_COMPONENT, DEFAULT_STORAGE_TYPE

PHYSICAL_TEMPLATE_HEADERS = [
    "High Court", "Component", "Sub-Component", "Type of Storage", "District", "Target", "Achieved", "Remarks",
]
FINANCIAL_TEMPLATE_HEADERS = [
    "High Court", "Component", "District", "Fund Released", "Fund Utilized", "Remarks",
]
OUTCOME_TEMPLATE_HEADERS = [
    "High Court", "Component", "Sub-Component", "Subject", "KPI ID",
    "Granularity", "District", "Value", "Baseline", "Remarks",
]
PREVIEW_ROW_LIMIT = 500

PHYSICAL_TEMPLATE_HEADERS = [
    "High Court", "Component", "Sub-Component", "District", "Target", "Achieved", "Remarks",
]
FINANCIAL_TEMPLATE_HEADERS = [
    "High Court", "Component", "District", "Fund Released", "Fund Utilized", "Remarks",
]
OUTCOME_TEMPLATE_HEADERS = [
    "High Court", "Component", "Sub-Component", "Subject", "KPI ID",
    "Granularity", "District", "Value", "Baseline", "Remarks",
]
PREVIEW_ROW_LIMIT = 500

def parse_excel_rows(raw: bytes, filename: str, ext: str) -> tuple[list, list[str], list[str]]:
    validate_upload_bytes(raw, ext)
    try:
        wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Excel file: {e}")
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise HTTPException(status_code=400, detail="Empty sheet")
    display_headers = [str(h or "").strip() for h in rows[0]]
    header_row = [h.lower() for h in display_headers]
    return rows, header_row, display_headers


def col_idx(header_row: list, name: str) -> int:
    try:
        return header_row.index(name)
    except ValueError:
        return -1


def col_idx_any(header_row: list, *names: str) -> int:
    for name in names:
        idx = col_idx(header_row, name)
        if idx >= 0:
            return idx
    return -1


def _excel_snapshot(row, display_headers: list[str], indices: list[int]) -> dict:
    out = {}
    for idx in indices:
        if idx < 0 or idx >= len(display_headers):
            continue
        label = display_headers[idx] or f"Col{idx + 1}"
        val = row[idx] if idx < len(row) else None
        if val is None or (isinstance(val, str) and not str(val).strip()):
            continue
        out[label] = val
    return out


def _db_snapshot(existing, fields: list[str]):
    if not existing:
        return None
    return {f: existing.get(f) for f in fields}


def _column_mappings(pairs: list[tuple[str, str, str]]) -> list[dict]:
    return [{"source": s, "target": t, "transform": x} for s, t, x in pairs]


def bulk_response(
    inserted: int,
    updated: int,
    skipped: int,
    errors: list,
    reporting_period: str,
    dry_run: bool,
    preview_rows: Optional[list] = None,
    *,
    tracker: Optional[str] = None,
    template_headers: Optional[list] = None,
    column_mappings: Optional[list] = None,
) -> dict:
    valid = (inserted + updated) if dry_run else (inserted + updated)
    return {
        "dry_run": dry_run,
        "tracker": tracker,
        "reporting_period": reporting_period,
        "inserted": inserted if not dry_run else 0,
        "updated": updated if not dry_run else 0,
        "skipped": skipped,
        "errors": errors[:100],
        "summary": {
            "valid": valid,
            "invalid": skipped,
            "would_insert": inserted if dry_run else inserted,
            "would_update": updated if dry_run else updated,
        },
        "template_headers": template_headers or [],
        "column_mappings": column_mappings or [],
        "rows": (preview_rows or [])[:PREVIEW_ROW_LIMIT],
        "rows_total": len(preview_rows or []),
    }


async def process_physical_bulk(
    db,
    raw: bytes,
    filename: str,
    reporting_period: str,
    user: dict,
    thresholds: dict,
    compute_rag_fn: Callable,
    safe_div_fn: Callable,
    audit_fn: Callable,
    serialize_fn: Callable,
    now_utc_fn: Callable,
    dry_run: bool = False,
) -> dict:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "xlsx"
    rows, header_row, display_headers = parse_excel_rows(raw, filename, ext)
    col_hc = col_idx(header_row, "high court")
    col_comp = col_idx(header_row, "component")
    col_ind = col_idx_any(header_row, "sub-component", "sub component", "indicator")
    col_target = col_idx(header_row, "target")
    col_ach = col_idx(header_row, "achieved")
    col_rem = col_idx(header_row, "remarks")
    col_dist = col_idx(header_row, "district")
    col_storage = col_idx_any(header_row, "type of storage", "storage type", "storage_type")
    col_target_dpr = col_idx_any(header_row, "target as per dpr", "target_dpr")
    col_ach_ec = col_idx_any(header_row, "achieved as per e-committee", "achieved as per ecommittee", "achieved_ecommittee")
    col_target_cpc = col_idx_any(header_row, "target as per cpc", "target_cpc")
    col_ach_cpc = col_idx_any(header_row, "achieved as per cpc", "achieved_cpc")
    if min(col_hc, col_comp, col_ind, col_ach) < 0:
        raise HTTPException(
            status_code=400,
            detail="Missing required columns: High Court, Component, Sub-Component, Achieved",
        )

    col_maps = _column_mappings([
        (display_headers[col_hc] if col_hc >= 0 else "High Court", "High Court", "identity"),
        (display_headers[col_comp] if col_comp >= 0 else "Component", "Component", "identity"),
        (display_headers[col_ind] if col_ind >= 0 else "Sub-Component", "Sub-Component", "alias: indicator"),
        (display_headers[col_storage] if col_storage >= 0 else "Type of Storage", "Type of Storage", "Cloud Computing only"),
        (display_headers[col_dist] if col_dist >= 0 else "District", "District", "optional"),
        (display_headers[col_target] if col_target >= 0 else "Target", "Target", "Admin-only write"),
        (display_headers[col_ach] if col_ach >= 0 else "Achieved", "Achieved", "numeric"),
        (display_headers[col_rem] if col_rem >= 0 else "Remarks", "Remarks", "optional"),
    ])
    interest = [c for c in (col_hc, col_comp, col_ind, col_storage, col_dist, col_target, col_ach, col_rem) if c >= 0]
    db_fields = ["high_court", "component", "indicator", "storage_type", "district", "target", "achieved", "remarks", "percent", "rag"]

    inserted, updated, skipped, errors, preview_rows = 0, 0, 0, [], []
    for i, r in enumerate(rows[1:], start=2):
        if not r or all(c is None for c in r):
            continue
        excel = _excel_snapshot(r, display_headers, interest)
        hc = str(r[col_hc] or "").strip()
        comp = str(r[col_comp] or "").strip()
        ind = str(r[col_ind] or "").strip()
        ach = r[col_ach]
        district = None
        if col_dist >= 0 and r[col_dist]:
            district = str(r[col_dist]).strip() or None
        if not (hc and comp and ind):
            skipped += 1
            errors.append({"row": i, "error": "Missing HC/Component/Sub-Component"})
            preview_rows.append({"row": i, "status": "error", "action": None, "error": "Missing HC/Component/Sub-Component", "excel": excel, "template": None, "database": None, "data": None})
            continue
        if user["role"] == "CPC" and hc != user.get("high_court"):
            skipped += 1
            errors.append({"row": i, "error": f"Out of CPC scope (HC={hc})"})
            preview_rows.append({"row": i, "status": "error", "action": None, "error": f"Out of CPC scope (HC={hc})", "excel": excel, "template": None, "database": None, "data": None})
            continue
        try:
            ach_val = None if ach in (None, "") else float(ach)
        except (ValueError, TypeError):
            skipped += 1
            errors.append({"row": i, "error": "Achieved is not numeric"})
            preview_rows.append({"row": i, "status": "error", "action": None, "error": "Achieved is not numeric", "excel": excel, "template": None, "database": None, "data": None})
            continue
        if ach_val is not None and ach_val < 0:
            skipped += 1
            errors.append({"row": i, "error": "Achieved cannot be negative"})
            preview_rows.append({"row": i, "status": "error", "action": None, "error": "Achieved cannot be negative", "excel": excel, "template": None, "database": None, "data": None})
            continue
        target_val = None
        if col_target >= 0 and user["role"] == "Admin":
            t = r[col_target]
            try:
                target_val = None if t in (None, "") else float(t)
            except (ValueError, TypeError):
                target_val = None
        remarks_val = str(r[col_rem]).strip() if (col_rem >= 0 and r[col_rem]) else None
        raw_storage = None
        if col_storage >= 0 and r[col_storage] not in (None, ""):
            raw_storage = str(r[col_storage]).strip()
        try:
            storage_type = resolve_storage_type(comp, raw_storage)
        except ValueError as e:
            skipped += 1
            errors.append({"row": i, "error": str(e)})
            preview_rows.append({"row": i, "status": "error", "action": None, "error": str(e), "excel": excel, "template": None, "database": None, "data": None})
            continue
        if comp == CLOUD_COMPUTING_COMPONENT and not storage_type:
            storage_type = DEFAULT_STORAGE_TYPE

        def _opt_float(col):
            if col < 0:
                return None
            v = r[col]
            try:
                return None if v in (None, "") else float(v)
            except (ValueError, TypeError):
                return None

        is_esewa = comp == "e-Sewa Kendras"
        target_dpr = _opt_float(col_target_dpr) if is_esewa else None
        achieved_ecommittee = _opt_float(col_ach_ec) if is_esewa else None
        target_cpc = _opt_float(col_target_cpc) if is_esewa else None
        achieved_cpc = _opt_float(col_ach_cpc) if is_esewa else None

        q = entry_query_key_physical({
            "high_court": hc, "component": comp, "indicator": ind,
            "reporting_period": reporting_period, "district": district,
            "storage_type": storage_type,
        })
        existing = await db.physical_entries.find_one(q)
        if user["role"] == "CPC" and existing and is_esewa:
            target_dpr = existing.get("target_dpr")
        eff_target = target_val if (user["role"] == "Admin" and target_val is not None) else (existing.get("target") if existing else None)
        percent = safe_div_fn(ach_val, eff_target)
        rag = compute_rag_fn(percent, thresholds)
        percent_ecommittee = safe_div_fn(achieved_ecommittee, target_dpr) if is_esewa else None
        percent_cpc = safe_div_fn(achieved_cpc, target_cpc) if is_esewa else None
        row_data = {
            **q, "target": eff_target, "achieved": ach_val, "percent": percent, "rag": rag, "remarks": remarks_val,
            "target_dpr": target_dpr, "achieved_ecommittee": achieved_ecommittee,
            "target_cpc": target_cpc, "achieved_cpc": achieved_cpc,
            "percent_ecommittee": percent_ecommittee, "percent_cpc": percent_cpc,
        }
        template = {
            "High Court": hc, "Component": comp, "Sub-Component": ind,
            "Type of Storage": storage_type or "",
            "District": district or "", "Target": eff_target, "Achieved": ach_val,
            "Remarks": remarks_val or "",
        }
        preview_rows.append({
            "row": i, "status": "ok", "action": "update" if existing else "insert",
            "data": row_data, "excel": excel, "template": template,
            "database": _db_snapshot(existing, db_fields), "error": None,
        })

        if dry_run:
            if existing:
                updated += 1
            else:
                inserted += 1
            continue

        doc = {**row_data, "updated_by": user["email"], "updated_at": now_utc_fn(), "source": "bulk_excel"}
        if existing:
            await db.physical_entries.update_one({"_id": existing["_id"]}, {"$set": doc})
            updated += 1
            await audit_fn(user, "physical", "bulk_update", str(existing["_id"]),
                           [{"field": "achieved", "old": existing.get("achieved"), "new": ach_val}], hc, reporting_period)
        else:
            doc["created_by"] = user["email"]
            doc["created_at"] = now_utc_fn()
            res = await db.physical_entries.insert_one(doc)
            inserted += 1
            await audit_fn(user, "physical", "bulk_create", str(res.inserted_id),
                           [{"field": "entry", "old": None, "new": serialize_fn(doc)}], hc, reporting_period)

    return bulk_response(
        inserted, updated, skipped, errors, reporting_period, dry_run, preview_rows,
        tracker="physical", template_headers=PHYSICAL_TEMPLATE_HEADERS, column_mappings=col_maps,
    )


async def process_financial_bulk(
    db,
    raw: bytes,
    filename: str,
    reporting_period: str,
    user: dict,
    thresholds: dict,
    compute_rag_fn: Callable,
    safe_div_fn: Callable,
    audit_fn: Callable,
    serialize_fn: Callable,
    now_utc_fn: Callable,
    dry_run: bool = False,
) -> dict:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "xlsx"
    rows, header_row, display_headers = parse_excel_rows(raw, filename, ext)
    col_hc = col_idx(header_row, "high court")
    col_comp = col_idx(header_row, "component")
    col_rel = col_idx(header_row, "fund released")
    col_util = col_idx(header_row, "fund utilized")
    col_rem = col_idx(header_row, "remarks")
    col_dist = col_idx(header_row, "district")
    if min(col_hc, col_comp, col_rel, col_util) < 0:
        raise HTTPException(status_code=400, detail="Missing required columns: High Court, Component, Fund Released, Fund Utilized")

    col_maps = _column_mappings([
        (display_headers[col_hc] if col_hc >= 0 else "High Court", "High Court", "identity"),
        (display_headers[col_comp] if col_comp >= 0 else "Component", "Component", "identity"),
        (display_headers[col_dist] if col_dist >= 0 else "District", "District", "optional"),
        (display_headers[col_rel] if col_rel >= 0 else "Fund Released", "Fund Released", "₹ Cr; blank preserves DB"),
        (display_headers[col_util] if col_util >= 0 else "Fund Utilized", "Fund Utilized", "₹ Cr; blank preserves DB"),
        (display_headers[col_rem] if col_rem >= 0 else "Remarks", "Remarks", "optional"),
    ])
    interest = [c for c in (col_hc, col_comp, col_dist, col_rel, col_util, col_rem) if c >= 0]
    db_fields = ["high_court", "component", "district", "fund_released", "fund_utilized", "remarks", "utilisation_percent", "rag"]

    inserted, updated, skipped, errors, preview_rows = 0, 0, 0, [], []
    for i, r in enumerate(rows[1:], start=2):
        if not r or all(c is None for c in r):
            continue
        excel = _excel_snapshot(r, display_headers, interest)
        hc = str(r[col_hc] or "").strip()
        comp = str(r[col_comp] or "").strip()
        district = None
        if col_dist >= 0 and r[col_dist]:
            district = str(r[col_dist]).strip() or None
        if not (hc and comp):
            skipped += 1
            errors.append({"row": i, "error": "Missing HC/Component"})
            preview_rows.append({"row": i, "status": "error", "action": None, "error": "Missing HC/Component", "excel": excel, "template": None, "database": None, "data": None})
            continue
        if user["role"] == "CPC" and hc != user.get("high_court"):
            skipped += 1
            errors.append({"row": i, "error": f"Out of CPC scope (HC={hc})"})
            continue
        try:
            released = None if r[col_rel] in (None, "") else float(r[col_rel])
            utilized = None if r[col_util] in (None, "") else float(r[col_util])
        except (ValueError, TypeError):
            skipped += 1
            errors.append({"row": i, "error": "Fund values must be numeric"})
            continue
        remarks_val = str(r[col_rem]).strip() if (col_rem >= 0 and r[col_rem]) else None
        q = entry_query_key_financial({"high_court": hc, "component": comp, "reporting_period": reporting_period, "district": district})
        existing = await db.financial_entries.find_one(q)
        # Partial ETL: blank cells preserve existing fund values on update
        if existing:
            if released is None:
                released = existing.get("fund_released")
            if utilized is None:
                utilized = existing.get("fund_utilized")
            if not remarks_val:
                remarks_val = existing.get("remarks")
        utilisation = safe_div_fn(utilized, released)
        variance = round(released - utilized, 2) if released is not None and utilized is not None else None
        rag = compute_rag_fn(utilisation, thresholds)
        row_data = {**q, "fund_released": released, "fund_utilized": utilized,
                    "utilisation_percent": utilisation, "variance": variance, "rag": rag, "remarks": remarks_val}
        template = {
            "High Court": hc, "Component": comp, "District": district or "",
            "Fund Released": released, "Fund Utilized": utilized, "Remarks": remarks_val or "",
        }
        preview_rows.append({
            "row": i, "status": "ok", "action": "update" if existing else "insert",
            "data": row_data, "excel": excel, "template": template,
            "database": _db_snapshot(existing, db_fields), "error": None,
        })

        if dry_run:
            if existing:
                updated += 1
            else:
                inserted += 1
            continue

        doc = {**row_data, "updated_by": user["email"], "updated_at": now_utc_fn(), "source": "bulk_excel"}
        if existing:
            await db.financial_entries.update_one({"_id": existing["_id"]}, {"$set": doc})
            updated += 1
            await audit_fn(user, "financial", "bulk_update", str(existing["_id"]), [], hc, reporting_period)
        else:
            doc["created_by"] = user["email"]
            doc["created_at"] = now_utc_fn()
            res = await db.financial_entries.insert_one(doc)
            inserted += 1
            await audit_fn(user, "financial", "bulk_create", str(res.inserted_id),
                           [{"field": "entry", "old": None, "new": serialize_fn(doc)}], hc, reporting_period)

    return bulk_response(
        inserted, updated, skipped, errors, reporting_period, dry_run, preview_rows,
        tracker="financial", template_headers=FINANCIAL_TEMPLATE_HEADERS, column_mappings=col_maps,
    )


async def process_outcome_bulk(
    db,
    raw: bytes,
    filename: str,
    reporting_period: str,
    user: dict,
    safe_div_fn: Callable,
    audit_fn: Callable,
    serialize_fn: Callable,
    now_utc_fn: Callable,
    dry_run: bool = False,
) -> dict:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "xlsx"
    rows, header_row, display_headers = parse_excel_rows(raw, filename, ext)
    phase4 = col_idx(header_row, "kpid") >= 0 or (
        col_idx(header_row, "components") >= 0 and col_idx_any(header_row, "sub-component", "sub component") >= 0
    )

    if phase4:
        return await _process_outcome_phase4_bulk(
            db, rows, display_headers, reporting_period, user, safe_div_fn, audit_fn, serialize_fn, now_utc_fn, dry_run,
        )

    col_hc = col_idx(header_row, "high court")
    col_sub = col_idx(header_row, "subject")
    col_kpi = col_idx(header_row, "kpi id")
    col_gran = col_idx(header_row, "granularity")
    col_val = col_idx(header_row, "value")
    col_base = col_idx(header_row, "baseline")
    col_rem = col_idx(header_row, "remarks")
    col_dist = col_idx(header_row, "district")
    col_comp = col_idx(header_row, "component")
    col_subc = col_idx_any(header_row, "sub-component", "sub component")
    if min(col_hc, col_sub, col_kpi, col_gran, col_val) < 0:
        raise HTTPException(status_code=400, detail="Missing required columns: High Court, Subject, KPI ID, Granularity, Value")

    col_maps = _column_mappings([
        (display_headers[col_hc] if col_hc >= 0 else "High Court", "High Court", "identity"),
        (display_headers[col_comp] if col_comp >= 0 else "Component", "Component", "from KPI master if blank"),
        (display_headers[col_subc] if col_subc >= 0 else "Sub-Component", "Sub-Component", "from KPI master if blank"),
        (display_headers[col_sub] if col_sub >= 0 else "Subject", "Subject", "identity"),
        (display_headers[col_kpi] if col_kpi >= 0 else "KPI ID", "KPI ID", "identity"),
        (display_headers[col_gran] if col_gran >= 0 else "Granularity", "Granularity", "identity"),
        (display_headers[col_dist] if col_dist >= 0 else "District", "District", "required if District gran."),
        (display_headers[col_val] if col_val >= 0 else "Value", "Value", "numeric"),
        (display_headers[col_base] if col_base >= 0 else "Baseline", "Baseline", "optional"),
        (display_headers[col_rem] if col_rem >= 0 else "Remarks", "Remarks", "optional"),
    ])
    interest = [c for c in (col_hc, col_comp, col_subc, col_sub, col_kpi, col_gran, col_dist, col_val, col_base, col_rem) if c >= 0]
    db_fields = [
        "high_court", "component", "sub_component", "subject", "kpi_id",
        "granularity", "district", "value", "baseline", "remarks",
    ]

    inserted, updated, skipped, errors, preview_rows = 0, 0, 0, [], []
    for i, r in enumerate(rows[1:], start=2):
        if not r or all(c is None for c in r):
            continue
        excel = _excel_snapshot(r, display_headers, interest)
        hc = str(r[col_hc] or "").strip()
        subject = str(r[col_sub] or "").strip()
        kpi_id = str(r[col_kpi] or "").strip()
        granularity = str(r[col_gran] or "").strip()
        district = None
        if granularity == "District":
            if col_dist >= 0 and r[col_dist]:
                district = str(r[col_dist]).strip() or None
            if not district:
                skipped += 1
                errors.append({"row": i, "error": "District required for District granularity"})
                preview_rows.append({"row": i, "status": "error", "action": None, "error": "District required for District granularity", "excel": excel, "template": None, "database": None, "data": None})
                continue
        if not (subject and kpi_id and granularity):
            skipped += 1
            errors.append({"row": i, "error": "Missing Subject/KPI ID/Granularity"})
            continue
        if user["role"] == "CPC" and hc and hc != user.get("high_court"):
            skipped += 1
            errors.append({"row": i, "error": f"Out of CPC scope (HC={hc})"})
            continue
        kpi_meta = await db.kpis.find_one({"subject": subject, "kpi_id": kpi_id})
        if not kpi_meta:
            skipped += 1
            errors.append({"row": i, "error": f"Unknown KPI {subject}/{kpi_id}"})
            preview_rows.append({"row": i, "status": "error", "action": None, "error": f"Unknown KPI {subject}/{kpi_id}", "excel": excel, "template": None, "database": None, "data": None})
            continue
        try:
            value = None if r[col_val] in (None, "") else float(r[col_val])
            baseline = None
            if col_base >= 0 and r[col_base] not in (None, ""):
                baseline = float(r[col_base])
        except (ValueError, TypeError):
            skipped += 1
            errors.append({"row": i, "error": "Value/Baseline must be numeric"})
            continue
        outcome_type = kpi_meta.get("outcome_type", "Absolute")
        computed = safe_div_fn(value, baseline) if outcome_type == "Relative" and baseline else None
        remarks_val = str(r[col_rem]).strip() if (col_rem >= 0 and r[col_rem]) else None
        q = {"high_court": hc or None, "subject": subject, "kpi_id": kpi_id,
             "reporting_period": reporting_period, "granularity": granularity,
             "district": district if granularity == "District" else None}
        existing = await db.outcome_entries.find_one(q)
        row_data = {
            **q,
            "component": kpi_meta.get("component"),
            "sub_component": kpi_meta.get("sub_component"),
            "kpi": kpi_meta.get("kpi"),
            "description": kpi_meta.get("description"),
            "periodicity": kpi_meta.get("periodicity"),
            "outcome_type": outcome_type,
            "value_type": kpi_meta.get("value_type"),
            "baseline": baseline,
            "value": value,
            "computed_percent": computed,
            "remarks": remarks_val,
        }
        template = {
            "High Court": hc,
            "Component": kpi_meta.get("component") or "",
            "Sub-Component": kpi_meta.get("sub_component") or "",
            "Subject": subject,
            "KPI ID": kpi_id,
            "Granularity": granularity,
            "District": district or "",
            "Value": value,
            "Baseline": baseline if baseline is not None else "",
            "Remarks": remarks_val or "",
        }
        preview_rows.append({
            "row": i, "status": "ok", "action": "update" if existing else "insert",
            "data": row_data, "excel": excel, "template": template,
            "database": _db_snapshot(existing, db_fields), "error": None,
        })

        if dry_run:
            if existing:
                updated += 1
            else:
                inserted += 1
            continue

        doc = {**row_data, "updated_by": user["email"], "updated_at": now_utc_fn(), "source": "bulk_excel"}
        if existing:
            await db.outcome_entries.update_one({"_id": existing["_id"]}, {"$set": doc})
            updated += 1
            await audit_fn(user, "outcome", "bulk_update", str(existing["_id"]), [], hc, reporting_period)
        else:
            doc["created_by"] = user["email"]
            doc["created_at"] = now_utc_fn()
            res = await db.outcome_entries.insert_one(doc)
            inserted += 1
            await audit_fn(user, "outcome", "bulk_create", str(res.inserted_id),
                           [{"field": "entry", "old": None, "new": serialize_fn(doc)}], hc, reporting_period)

    return bulk_response(
        inserted, updated, skipped, errors, reporting_period, dry_run, preview_rows,
        tracker="outcome", template_headers=OUTCOME_TEMPLATE_HEADERS, column_mappings=col_maps,
    )


async def _process_outcome_phase4_bulk(
    db,
    rows: list,
    display_headers: list,
    reporting_period: str,
    user: dict,
    safe_div_fn: Callable,
    audit_fn: Callable,
    serialize_fn: Callable,
    now_utc_fn: Callable,
    dry_run: bool,
) -> dict:
    try:
        parsed_rows = parse_outcome_excel_rows(rows)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    col_maps = _column_mappings([
        ("High Court", "High Court", "forward-fill"),
        ("Components / Sub-Component", "Subject / Component / Sub-Component", "OUTCOME_SUBJECT_MAP"),
        ("KPID / KPI ID", "KPI ID", "normalize"),
        ("Granularity", "Granularity", "default District"),
        ("Value / OUTCOME*", "Value", "numeric"),
    ])
    db_fields = [
        "high_court", "component", "sub_component", "subject", "kpi_id",
        "granularity", "district", "value", "baseline", "remarks",
    ]

    inserted, updated, skipped, errors, preview_rows = 0, 0, 0, [], []
    for i, parsed in enumerate(parsed_rows, start=2):
        hc = parsed["high_court"]
        subject = parsed["subject"]
        kpi_id = parsed["kpi_id"]
        granularity = parsed.get("granularity") or "District"
        excel = {
            "High Court": hc,
            "Components": parsed.get("component"),
            "Sub-Component": parsed.get("sub_component"),
            "Subject": subject,
            "KPI ID": kpi_id,
            "KPI": parsed.get("kpi"),
            "Granularity": granularity,
            "Value": parsed.get("value"),
        }
        if user["role"] == "CPC" and hc and hc != user.get("high_court"):
            skipped += 1
            errors.append({"row": i, "error": f"Out of CPC scope (HC={hc})"})
            continue
        kpi_meta = await db.kpis.find_one({"subject": subject, "kpi_id": kpi_id})
        if not kpi_meta:
            skipped += 1
            errors.append({"row": i, "error": f"Unknown KPI {subject}/{kpi_id}"})
            preview_rows.append({"row": i, "status": "error", "action": None, "error": f"Unknown KPI {subject}/{kpi_id}", "excel": excel, "template": None, "database": None, "data": None})
            continue
        value = parsed.get("value")
        outcome_type = kpi_meta.get("outcome_type", "Absolute")
        q = {
            "high_court": hc or None,
            "subject": subject,
            "kpi_id": kpi_id,
            "reporting_period": reporting_period,
            "granularity": granularity,
            "district": None,
        }
        existing = await db.outcome_entries.find_one(q)
        row_data = {
            **q,
            "component": parsed.get("component") or kpi_meta.get("component"),
            "sub_component": parsed.get("sub_component") or kpi_meta.get("sub_component"),
            "kpi": kpi_meta.get("kpi") or parsed.get("kpi"),
            "description": kpi_meta.get("description") or parsed.get("description"),
            "periodicity": kpi_meta.get("periodicity") or parsed.get("periodicity"),
            "outcome_type": outcome_type,
            "value_type": kpi_meta.get("value_type"),
            "baseline": None,
            "value": value,
            "computed_percent": None,
            "remarks": None,
        }
        template = {
            "High Court": hc,
            "Component": row_data.get("component") or "",
            "Sub-Component": row_data.get("sub_component") or "",
            "Subject": subject,
            "KPI ID": kpi_id,
            "Granularity": granularity,
            "District": "",
            "Value": value,
            "Baseline": "",
            "Remarks": "",
        }
        preview_rows.append({
            "row": i, "status": "ok", "action": "update" if existing else "insert",
            "data": row_data, "excel": excel, "template": template,
            "database": _db_snapshot(existing, db_fields), "error": None,
        })

        if dry_run:
            if existing:
                updated += 1
            else:
                inserted += 1
            continue

        doc = {**row_data, "updated_by": user["email"], "updated_at": now_utc_fn(), "source": "bulk_excel"}
        if existing:
            await db.outcome_entries.update_one({"_id": existing["_id"]}, {"$set": doc})
            updated += 1
            await audit_fn(user, "outcome", "bulk_update", str(existing["_id"]), [], hc, reporting_period)
        else:
            doc["created_by"] = user["email"]
            doc["created_at"] = now_utc_fn()
            res = await db.outcome_entries.insert_one(doc)
            inserted += 1
            await audit_fn(user, "outcome", "bulk_create", str(res.inserted_id),
                           [{"field": "entry", "old": None, "new": serialize_fn(doc)}], hc, reporting_period)

    return bulk_response(
        inserted, updated, skipped, errors, reporting_period, dry_run, preview_rows,
        tracker="outcome", template_headers=OUTCOME_TEMPLATE_HEADERS, column_mappings=col_maps,
    )
