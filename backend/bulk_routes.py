"""Bulk upload, init-period, and Excel template routes."""
import io
from typing import Callable, Optional

import xlsxwriter
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from bulk_preview import consume_bulk_preview, save_bulk_preview
from bulk_upload import process_financial_bulk, process_outcome_bulk, process_physical_bulk
from tracker_init import init_financial_period, init_outcome_period, init_physical_period
from tracker_routes import ADMIN_ONLY_CREATE_DETAIL
from period_policy import assert_editable

MAX_FILE_BYTES = 10 * 1024 * 1024


class InitPeriodIn(BaseModel):
    high_court: str
    reporting_period: str
    component: Optional[str] = None


class OutcomeInitPeriodIn(BaseModel):
    high_court: str
    reporting_period: str
    subject: Optional[str] = None


def register_bulk_routes(
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
    async def _assert_bulk_allowed(user: dict, reporting_period: str, high_court: Optional[str] = None) -> None:
        if user["role"] == "Viewer":
            raise HTTPException(status_code=403, detail="Read-only role")
        if user.get("role") != "Admin":
            raise HTTPException(status_code=403, detail=ADMIN_ONLY_CREATE_DETAIL)
        today = now_utc_fn().strftime("%Y-%m")
        if reporting_period > today:
            raise HTTPException(status_code=400, detail="Reporting month cannot be in the future")
        hc = high_court or user.get("high_court")
        if user["role"] == "CPC" and hc and hc != user.get("high_court"):
            raise HTTPException(status_code=403, detail="CPC limited to own High Court")
        if hc:
            await assert_editable(db, hc, reporting_period, user, now_utc_fn)

    def _assert_bulk_ext(name: str) -> None:
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else "xlsx"
        if ext not in ("xlsx", "xls"):
            raise HTTPException(status_code=400, detail="Bulk upload requires an Excel file (.xlsx or .xls)")

    async def _resolve_bulk_bytes(
        tracker: str,
        reporting_period: str,
        dry_run: bool,
        preview_token: Optional[str],
        file: Optional[UploadFile],
        user: dict,
    ) -> tuple[bytes, str]:
        if dry_run:
            if not file or not file.filename:
                raise HTTPException(status_code=400, detail="Excel file required for preview")
            raw = await file.read()
            if len(raw) > MAX_FILE_BYTES:
                raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")
            name = file.filename or "upload.xlsx"
            _assert_bulk_ext(name)
            return raw, name
        if preview_token:
            raw, name = await consume_bulk_preview(db, preview_token, user["id"], tracker, reporting_period)
            _assert_bulk_ext(name)
            return raw, name
        if file and file.filename:
            raw = await file.read()
            if len(raw) > MAX_FILE_BYTES:
                raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")
            name = file.filename or "upload.xlsx"
            _assert_bulk_ext(name)
            return raw, name
        raise HTTPException(status_code=400, detail="Provide preview_token or re-upload the Excel file")

    async def _init_guard(user: dict, reporting_period: str) -> dict:
        if user["role"] == "Viewer":
            raise HTTPException(status_code=403, detail="Read-only role")
        if user.get("role") != "Admin":
            raise HTTPException(status_code=403, detail=ADMIN_ONLY_CREATE_DETAIL)
        today = now_utc_fn().strftime("%Y-%m")
        if reporting_period > today:
            raise HTTPException(status_code=400, detail="Reporting month cannot be in the future")
        return (await db.settings.find_one({"key": "rag_thresholds"}) or {}).get("value", default_rag_thresholds)

    @api.post("/physical/init-period")
    async def physical_init_period(body: InitPeriodIn, user: dict = Depends(require_fully_authenticated)):
        thresholds = await _init_guard(user, body.reporting_period)
        try:
            result = await init_physical_period(
                db, body.high_court, body.reporting_period, user,
                compute_rag_fn, thresholds, now_utc_fn, body.component,
            )
        except ValueError as e:
            raise HTTPException(status_code=403, detail=str(e))
        await audit_fn(user, "physical", "init_period", body.high_court,
                       [{"field": "created", "old": None, "new": result["created"]}],
                       body.high_court, body.reporting_period)
        return result

    @api.post("/financial/init-period")
    async def financial_init_period(body: InitPeriodIn, user: dict = Depends(require_fully_authenticated)):
        thresholds = await _init_guard(user, body.reporting_period)
        try:
            result = await init_financial_period(
                db, body.high_court, body.reporting_period, user,
                compute_rag_fn, thresholds, now_utc_fn, body.component,
            )
        except ValueError as e:
            raise HTTPException(status_code=403, detail=str(e))
        await audit_fn(user, "financial", "init_period", body.high_court,
                       [{"field": "created", "old": None, "new": result["created"]}],
                       body.high_court, body.reporting_period)
        return result

    @api.post("/outcome/init-period")
    async def outcome_init_period(body: OutcomeInitPeriodIn, user: dict = Depends(require_fully_authenticated)):
        await _init_guard(user, body.reporting_period)
        try:
            result = await init_outcome_period(
                db, body.high_court, body.reporting_period, user,
                safe_div_fn, now_utc_fn, body.subject,
            )
        except ValueError as e:
            raise HTTPException(status_code=403, detail=str(e))
        await audit_fn(user, "outcome", "init_period", body.high_court,
                       [{"field": "created", "old": None, "new": result["created"]}],
                       body.high_court, body.reporting_period)
        return result

    @api.post("/physical/bulk")
    async def physical_bulk(
        reporting_period: str = Query(...),
        dry_run: bool = Query(False),
        preview_token: Optional[str] = Query(None),
        file: Optional[UploadFile] = File(None),
        user: dict = Depends(require_fully_authenticated),
    ):
        await _assert_bulk_allowed(user, reporting_period, user.get("high_court") if user["role"] == "CPC" else None)
        raw, name = await _resolve_bulk_bytes("physical", reporting_period, dry_run, preview_token, file, user)
        thresholds = (await db.settings.find_one({"key": "rag_thresholds"}) or {}).get("value", default_rag_thresholds)
        result = await process_physical_bulk(
            db, raw, name, reporting_period, user, thresholds,
            compute_rag_fn, safe_div_fn, audit_fn, serialize_fn, now_utc_fn, dry_run=dry_run,
        )
        if dry_run:
            result["preview_token"] = await save_bulk_preview(
                db, user["id"], "physical", reporting_period, name, raw,
            )
        return result

    @api.post("/financial/bulk")
    async def financial_bulk(
        reporting_period: str = Query(...),
        dry_run: bool = Query(False),
        preview_token: Optional[str] = Query(None),
        file: Optional[UploadFile] = File(None),
        user: dict = Depends(require_fully_authenticated),
    ):
        await _assert_bulk_allowed(user, reporting_period, user.get("high_court") if user["role"] == "CPC" else None)
        raw, name = await _resolve_bulk_bytes("financial", reporting_period, dry_run, preview_token, file, user)
        thresholds = (await db.settings.find_one({"key": "rag_thresholds"}) or {}).get("value", default_rag_thresholds)
        result = await process_financial_bulk(
            db, raw, name, reporting_period, user, thresholds,
            compute_rag_fn, safe_div_fn, audit_fn, serialize_fn, now_utc_fn, dry_run=dry_run,
        )
        if dry_run:
            result["preview_token"] = await save_bulk_preview(
                db, user["id"], "financial", reporting_period, name, raw,
            )
        return result

    @api.post("/outcome/bulk")
    async def outcome_bulk(
        reporting_period: str = Query(...),
        dry_run: bool = Query(False),
        preview_token: Optional[str] = Query(None),
        file: Optional[UploadFile] = File(None),
        user: dict = Depends(require_fully_authenticated),
    ):
        await _assert_bulk_allowed(user, reporting_period, user.get("high_court") if user["role"] == "CPC" else None)
        raw, name = await _resolve_bulk_bytes("outcome", reporting_period, dry_run, preview_token, file, user)
        result = await process_outcome_bulk(
            db, raw, name, reporting_period, user, safe_div_fn, audit_fn, serialize_fn, now_utc_fn, dry_run=dry_run,
        )
        if dry_run:
            result["preview_token"] = await save_bulk_preview(
                db, user["id"], "outcome", reporting_period, name, raw,
            )
        return result

    @api.get("/physical/bulk-template")
    async def physical_bulk_template(_: dict = Depends(require_fully_authenticated)):
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {"in_memory": True})
        ws = wb.add_worksheet("PhysicalBulk")
        hf = wb.add_format({"bold": True, "bg_color": "#0A1128", "font_color": "white", "border": 1})
        headers = ["High Court", "Component", "Sub-Component", "District", "Target", "Achieved", "Remarks"]
        for i, h in enumerate(headers):
            ws.write(0, i, h, hf)
        sample = [
            ["Allahabad", "e-Sewa Kendras", "No of sites prepared (in Absolute Count)", "", 400, 250, "Sample row"],
        ]
        for r, row in enumerate(sample, start=1):
            for c, v in enumerate(row):
                ws.write(r, c, v)
        ws.set_column(0, len(headers) - 1, 28)
        wb.close()
        buf.seek(0)
        return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                 headers={"Content-Disposition": "attachment; filename=physical_bulk_template.xlsx"})

    @api.get("/financial/bulk-template")
    async def financial_bulk_template(_: dict = Depends(require_fully_authenticated)):
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {"in_memory": True})
        ws = wb.add_worksheet("FinancialBulk")
        hf = wb.add_format({"bold": True, "bg_color": "#0A1128", "font_color": "white", "border": 1})
        headers = ["High Court", "Component", "District", "Fund Released", "Fund Utilized", "Remarks"]
        for i, h in enumerate(headers):
            ws.write(0, i, h, hf)
        ws.write(1, 0, "Allahabad")
        ws.write(1, 1, "e-Sewa Kendras")
        ws.write(1, 2, "")
        ws.write(1, 3, 10.5)
        ws.write(1, 4, 8.2)
        ws.set_column(0, len(headers) - 1, 28)
        wb.close()
        buf.seek(0)
        return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                 headers={"Content-Disposition": "attachment; filename=financial_bulk_template.xlsx"})

    @api.get("/outcome/bulk-template")
    async def outcome_bulk_template(_: dict = Depends(require_fully_authenticated)):
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {"in_memory": True})
        ws = wb.add_worksheet("OutcomeBulk")
        hf = wb.add_format({"bold": True, "bg_color": "#0A1128", "font_color": "white", "border": 1})
        headers = ["High Court", "Component", "Sub-Component", "Subject", "KPI ID", "Granularity", "District", "Value", "Baseline", "Remarks"]
        for i, h in enumerate(headers):
            ws.write(0, i, h, hf)
        ws.set_column(0, len(headers) - 1, 28)
        wb.close()
        buf.seek(0)
        return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                 headers={"Content-Disposition": "attachment; filename=outcome_bulk_template.xlsx"})
