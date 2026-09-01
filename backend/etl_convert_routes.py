"""ETL convert → 1:1 mapping preview → approve & push for Physical / Financial / Outcome."""
from typing import Callable, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from bulk_preview import consume_bulk_preview, save_bulk_preview
from bulk_upload import process_financial_bulk, process_outcome_bulk, process_physical_bulk
from cache_layer import cache_invalidate_prefix
from etl_convert_service import convert_tracker, public_convert_payload
from period_policy import assert_editable
from tracker_routes import ADMIN_ONLY_CREATE_DETAIL

MAX_FILE_BYTES = 10 * 1024 * 1024
VALID_TRACKERS = ("physical", "financial", "outcome")


def register_etl_convert_routes(
    api: APIRouter,
    db,
    require_fully_authenticated,
    audit_fn: Callable,
    compute_rag_fn: Callable,
    safe_div_fn: Callable,
    serialize_fn: Callable,
    now_utc_fn: Callable,
    default_rag_thresholds: dict,
):
    async def _assert_admin(user: dict, reporting_period: Optional[str] = None) -> None:
        if user.get("role") != "Admin":
            raise HTTPException(status_code=403, detail=ADMIN_ONLY_CREATE_DETAIL)
        if reporting_period:
            today = now_utc_fn().strftime("%Y-%m")
            if reporting_period > today:
                raise HTTPException(status_code=400, detail="Reporting month cannot be in the future")
            hc = user.get("high_court")
            if hc:
                await assert_editable(db, hc, reporting_period, user, now_utc_fn)

    def _assert_xlsx(name: str) -> None:
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if ext not in ("xlsx", "xls"):
            raise HTTPException(status_code=400, detail="Requires an Excel file (.xlsx or .xls)")

    @api.post("/etl/convert")
    async def etl_convert(
        tracker: str = Query(..., description="physical | financial | outcome"),
        reporting_period: str = Query(...),
        mode: str = Query("auto", description="financial only: auto | released | utilised"),
        sheet: Optional[str] = Query(None),
        file: UploadFile = File(...),
        user: dict = Depends(require_fully_authenticated),
    ):
        """Convert input Excel to PMIS long format and return 1:1 column/row mappings (no DB write)."""
        await _assert_admin(user, reporting_period)
        tracker = tracker.strip().lower()
        if tracker not in VALID_TRACKERS:
            raise HTTPException(status_code=400, detail="tracker must be physical, financial, or outcome")
        if not file.filename:
            raise HTTPException(status_code=400, detail="Excel file required")
        _assert_xlsx(file.filename)
        raw = await file.read()
        if len(raw) > MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")
        if not raw:
            raise HTTPException(status_code=400, detail="Empty file")

        try:
            result = convert_tracker(tracker, raw, mode=mode, sheet=sheet)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Convert failed: {e}") from e

        bulk_bytes = result["bulk_bytes"]
        bulk_name = result.get("bulk_filename") or f"{tracker}_converted.xlsx"

        thresholds = (await db.settings.find_one({"key": "rag_thresholds"}) or {}).get(
            "value", default_rag_thresholds
        )
        if tracker == "physical":
            validation = await process_physical_bulk(
                db, bulk_bytes, bulk_name, reporting_period, user, thresholds,
                compute_rag_fn, safe_div_fn, audit_fn, serialize_fn, now_utc_fn, dry_run=True,
            )
        elif tracker == "financial":
            validation = await process_financial_bulk(
                db, bulk_bytes, bulk_name, reporting_period, user, thresholds,
                compute_rag_fn, safe_div_fn, audit_fn, serialize_fn, now_utc_fn, dry_run=True,
            )
        else:
            validation = await process_outcome_bulk(
                db, bulk_bytes, bulk_name, reporting_period, user,
                safe_div_fn, audit_fn, serialize_fn, now_utc_fn, dry_run=True,
            )

        preview_token = await save_bulk_preview(
            db, user["id"], tracker, reporting_period, bulk_name, bulk_bytes,
        )

        payload = public_convert_payload(result)
        payload["preview_token"] = preview_token
        payload["reporting_period"] = reporting_period
        payload["validation"] = {
            "summary": validation.get("summary"),
            "inserted": validation.get("inserted"),
            "updated": validation.get("updated"),
            "skipped": validation.get("skipped"),
            "errors": (validation.get("errors") or [])[:50],
            "rows": (validation.get("rows") or [])[:100],
        }
        valid = int((validation.get("summary") or {}).get("valid") or 0)
        payload["can_commit"] = bool(preview_token) and valid > 0
        return payload

    @api.post("/etl/commit")
    async def etl_commit(
        tracker: str = Query(...),
        reporting_period: str = Query(...),
        preview_token: str = Form(...),
        user: dict = Depends(require_fully_authenticated),
    ):
        """Approve mapping and push converted rows into the selected tracker."""
        await _assert_admin(user, reporting_period)
        tracker = tracker.strip().lower()
        if tracker not in VALID_TRACKERS:
            raise HTTPException(status_code=400, detail="tracker must be physical, financial, or outcome")
        if not preview_token:
            raise HTTPException(status_code=400, detail="preview_token required")

        raw, name = await consume_bulk_preview(
            db, preview_token, user["id"], tracker, reporting_period,
        )
        thresholds = (await db.settings.find_one({"key": "rag_thresholds"}) or {}).get(
            "value", default_rag_thresholds
        )
        if tracker == "physical":
            result = await process_physical_bulk(
                db, raw, name, reporting_period, user, thresholds,
                compute_rag_fn, safe_div_fn, audit_fn, serialize_fn, now_utc_fn, dry_run=False,
            )
        elif tracker == "financial":
            result = await process_financial_bulk(
                db, raw, name, reporting_period, user, thresholds,
                compute_rag_fn, safe_div_fn, audit_fn, serialize_fn, now_utc_fn, dry_run=False,
            )
        else:
            result = await process_outcome_bulk(
                db, raw, name, reporting_period, user,
                safe_div_fn, audit_fn, serialize_fn, now_utc_fn, dry_run=False,
            )

        await audit_fn(
            user, tracker, "etl_convert_commit", reporting_period,
            [
                {"field": "inserted", "old": None, "new": result.get("inserted")},
                {"field": "updated", "old": None, "new": result.get("updated")},
            ],
            None, reporting_period,
        )
        cache_invalidate_prefix("public:progress")
        cache_invalidate_prefix("dashboard:")
        return result
