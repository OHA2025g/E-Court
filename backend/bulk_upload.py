"""Shared Excel bulk upload parsing and validation for tracker modules."""
import io
from typing import Any, Callable, Optional

import openpyxl
from fastapi import HTTPException

from rollup import entry_query_key_financial, entry_query_key_physical
from security import validate_upload_bytes
from outcome_excel import parse_outcome_excel_rows


def parse_excel_rows(raw: bytes, filename: str, ext: str) -> tuple[list, list[str]]:
    validate_upload_bytes(raw, ext)
    try:
        wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Excel file: {e}")
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise HTTPException(status_code=400, detail="Empty sheet")
    header_row = [str(h or "").strip().lower() for h in rows[0]]

    def col(name: str) -> int:
        try:
            return header_row.index(name)
        except ValueError:
            return -1

    return rows, header_row


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


def bulk_response(
    inserted: int,
    updated: int,
    skipped: int,
    errors: list,
    reporting_period: str,
    dry_run: bool,
    preview_rows: Optional[list] = None,
) -> dict:
    valid = (inserted + updated) if dry_run else (inserted + updated)
    return {
        "dry_run": dry_run,
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
        "rows": (preview_rows or [])[:200],
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
    rows, header_row = parse_excel_rows(raw, filename, ext)
    col_hc = col_idx(header_row, "high court")
    col_comp = col_idx(header_row, "component")
    col_ind = col_idx_any(header_row, "sub-component", "sub component", "indicator")
    col_target = col_idx(header_row, "target")
    col_ach = col_idx(header_row, "achieved")
    col_rem = col_idx(header_row, "remarks")
    col_dist = col_idx(header_row, "district")
    if min(col_hc, col_comp, col_ind, col_ach) < 0:
        raise HTTPException(
            status_code=400,
            detail="Missing required columns: High Court, Component, Sub-Component, Achieved",
        )

    inserted, updated, skipped, errors, preview_rows = 0, 0, 0, [], []
    for i, r in enumerate(rows[1:], start=2):
        if not r or all(c is None for c in r):
            continue
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
            preview_rows.append({"row": i, "status": "error", "error": "Missing HC/Component/Sub-Component"})
            continue
        if user["role"] == "CPC" and hc != user.get("high_court"):
            skipped += 1
            errors.append({"row": i, "error": f"Out of CPC scope (HC={hc})"})
            preview_rows.append({"row": i, "status": "error", "error": f"Out of CPC scope (HC={hc})"})
            continue
        try:
            ach_val = None if ach in (None, "") else float(ach)
        except (ValueError, TypeError):
            skipped += 1
            errors.append({"row": i, "error": "Achieved is not numeric"})
            preview_rows.append({"row": i, "status": "error", "error": "Achieved is not numeric"})
            continue
        if ach_val is not None and ach_val < 0:
            skipped += 1
            errors.append({"row": i, "error": "Achieved cannot be negative"})
            preview_rows.append({"row": i, "status": "error", "error": "Achieved cannot be negative"})
            continue
        target_val = None
        if col_target >= 0 and user["role"] == "Admin":
            t = r[col_target]
            try:
                target_val = None if t in (None, "") else float(t)
            except (ValueError, TypeError):
                target_val = None
        remarks_val = str(r[col_rem]).strip() if (col_rem >= 0 and r[col_rem]) else None

        q = {"high_court": hc, "component": comp, "indicator": ind,
             "reporting_period": reporting_period, "district": district}
        existing = await db.physical_entries.find_one(q)
        eff_target = target_val if (user["role"] == "Admin" and target_val is not None) else (existing.get("target") if existing else None)
        percent = safe_div_fn(ach_val, eff_target)
        rag = compute_rag_fn(percent, thresholds)
        row_data = {**q, "target": eff_target, "achieved": ach_val, "percent": percent, "rag": rag, "remarks": remarks_val}
        preview_rows.append({"row": i, "status": "ok", "data": row_data, "error": None})

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

    return bulk_response(inserted, updated, skipped, errors, reporting_period, dry_run, preview_rows)


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
    rows, header_row = parse_excel_rows(raw, filename, ext)
    col_hc = col_idx(header_row, "high court")
    col_comp = col_idx(header_row, "component")
    col_rel = col_idx(header_row, "fund released")
    col_util = col_idx(header_row, "fund utilized")
    col_rem = col_idx(header_row, "remarks")
    col_dist = col_idx(header_row, "district")
    if min(col_hc, col_comp, col_rel, col_util) < 0:
        raise HTTPException(status_code=400, detail="Missing required columns: High Court, Component, Fund Released, Fund Utilized")

    inserted, updated, skipped, errors, preview_rows = 0, 0, 0, [], []
    for i, r in enumerate(rows[1:], start=2):
        if not r or all(c is None for c in r):
            continue
        hc = str(r[col_hc] or "").strip()
        comp = str(r[col_comp] or "").strip()
        district = None
        if col_dist >= 0 and r[col_dist]:
            district = str(r[col_dist]).strip() or None
        if not (hc and comp):
            skipped += 1
            errors.append({"row": i, "error": "Missing HC/Component"})
            preview_rows.append({"row": i, "status": "error", "error": "Missing HC/Component"})
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
        utilisation = safe_div_fn(utilized, released)
        variance = round(released - utilized, 2) if released is not None and utilized is not None else None
        rag = compute_rag_fn(utilisation, thresholds)
        q = entry_query_key_financial({"high_court": hc, "component": comp, "reporting_period": reporting_period, "district": district})
        existing = await db.financial_entries.find_one(q)
        row_data = {**q, "fund_released": released, "fund_utilized": utilized,
                    "utilisation_percent": utilisation, "variance": variance, "rag": rag, "remarks": remarks_val}
        preview_rows.append({"row": i, "status": "ok", "data": row_data, "error": None})

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

    return bulk_response(inserted, updated, skipped, errors, reporting_period, dry_run, preview_rows)


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
    rows, header_row = parse_excel_rows(raw, filename, ext)
    phase4 = col_idx(header_row, "kpid") >= 0 or (
        col_idx(header_row, "components") >= 0 and col_idx_any(header_row, "sub-component", "sub component") >= 0
    )

    if phase4:
        return await _process_outcome_phase4_bulk(
            db, rows, reporting_period, user, safe_div_fn, audit_fn, serialize_fn, now_utc_fn, dry_run,
        )

    col_hc = col_idx(header_row, "high court")
    col_sub = col_idx(header_row, "subject")
    col_kpi = col_idx(header_row, "kpi id")
    col_gran = col_idx(header_row, "granularity")
    col_val = col_idx(header_row, "value")
    col_base = col_idx(header_row, "baseline")
    col_rem = col_idx(header_row, "remarks")
    col_dist = col_idx(header_row, "district")
    if min(col_hc, col_sub, col_kpi, col_gran, col_val) < 0:
        raise HTTPException(status_code=400, detail="Missing required columns: High Court, Subject, KPI ID, Granularity, Value")

    inserted, updated, skipped, errors, preview_rows = 0, 0, 0, [], []
    for i, r in enumerate(rows[1:], start=2):
        if not r or all(c is None for c in r):
            continue
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
                preview_rows.append({"row": i, "status": "error", "error": "District required for District granularity"})
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
            preview_rows.append({"row": i, "status": "error", "error": f"Unknown KPI {subject}/{kpi_id}"})
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
        preview_rows.append({"row": i, "status": "ok", "data": row_data, "error": None})

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

    return bulk_response(inserted, updated, skipped, errors, reporting_period, dry_run, preview_rows)


async def _process_outcome_phase4_bulk(
    db,
    rows: list,
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

    inserted, updated, skipped, errors, preview_rows = 0, 0, 0, [], []
    for i, parsed in enumerate(parsed_rows, start=2):
        hc = parsed["high_court"]
        subject = parsed["subject"]
        kpi_id = parsed["kpi_id"]
        granularity = parsed.get("granularity") or "District"
        if user["role"] == "CPC" and hc and hc != user.get("high_court"):
            skipped += 1
            errors.append({"row": i, "error": f"Out of CPC scope (HC={hc})"})
            continue
        kpi_meta = await db.kpis.find_one({"subject": subject, "kpi_id": kpi_id})
        if not kpi_meta:
            skipped += 1
            errors.append({"row": i, "error": f"Unknown KPI {subject}/{kpi_id}"})
            preview_rows.append({"row": i, "status": "error", "error": f"Unknown KPI {subject}/{kpi_id}"})
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
        preview_rows.append({"row": i, "status": "ok", "data": row_data, "error": None})

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

    return bulk_response(inserted, updated, skipped, errors, reporting_period, dry_run, preview_rows)
