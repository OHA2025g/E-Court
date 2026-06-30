"""Export Routes."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from seed_constants import DEFAULT_RAG_THRESHOLDS
import io
from typing import Literal, Optional

from fastapi.responses import StreamingResponse
import xlsxwriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from cabinet_brief import build_cabinet_brief_pdf
from export_i18n import financial_headers, outcome_headers, physical_headers, resolve_export_lang, sla_headers
from period_policy import approved_match_filter, merge_match
from rollup import (
    apply_district_filter,
    financial_national_totals_stages,
)

def register_export_routes(
    api: APIRouter,
    db,
    require_fully_authenticated,
    require_role,
    audit_fn,
    scope_filter_fn,
    serialize_fn,
    compute_rag_fn,
    safe_div_fn,
    now_utc_fn,
    default_rag_thresholds: dict = DEFAULT_RAG_THRESHOLDS,
):
    def _enforce_export_limit(user: dict):
        from api_rate_limit import enforce_user_export_rate_limit
        enforce_user_export_rate_limit(user["id"])

    async def _export_query(user, reporting_period, high_court, component, district=None, subject=None):
        q: dict = scope_filter_fn(user)
        if high_court:
            q["high_court"] = high_court
        if component:
            q["component"] = component
        if subject:
            q["subject"] = subject
        if reporting_period:
            q["reporting_period"] = reporting_period
        apply_district_filter(q, district)
        extra = await approved_match_filter(db, reporting_period, False, user)
        return merge_match(q, extra)

    def _build_xlsx(rows: list, columns: list, headers: list) -> bytes:
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {"in_memory": True})
        ws = wb.add_worksheet("Report")
        hf = wb.add_format({"bold": True, "bg_color": "#0A1128", "font_color": "white", "border": 1})
        bf = wb.add_format({"border": 1})
        for i, h in enumerate(headers):
            ws.write(0, i, h, hf)
        for r, row in enumerate(rows, start=1):
            for c, key in enumerate(columns):
                v = row.get(key)
                if v is None: v = ""
                ws.write(r, c, v, bf)
            ws.set_column(0, len(columns) - 1, 22)
        wb.close()
        buf.seek(0)
        return buf.read()

    def _build_pdf(title: str, rows: list, columns: list, headers: list) -> bytes:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=landscape(A4), title=title)
        styles = getSampleStyleSheet()
        data = [headers] + [[str(r.get(k, "") if r.get(k) is not None else "") for k in columns] for r in rows]
        tbl = Table(data, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A1128")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#94A3B8")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        doc.build([Paragraph(f"<b>{title}</b>", styles["Title"]), Spacer(1, 12), tbl])
        buf.seek(0)
        return buf.read()

    @api.get("/export/physical")
    async def export_physical(request: Request,
                              format: Literal["xlsx", "pdf"] = "xlsx",
                              high_court: Optional[str] = None,
                              component: Optional[str] = None,
                              reporting_period: Optional[str] = None,
                              district: Optional[str] = None,
                              user: dict = Depends(require_fully_authenticated)):
        _enforce_export_limit(user)
        lang = resolve_export_lang(request.headers.get("accept-language"))
        q = await _export_query(user, reporting_period, high_court, component, district)
        items = await db.physical_entries.find(q).sort("high_court", 1).to_list(20000)
        rows = serialize_fn(items)
        cols = ["high_court", "district", "component", "indicator", "reporting_period", "target",
                "achieved", "percent", "rag", "remarks"]
        headers = physical_headers(lang)
        if format == "xlsx":
            data = _build_xlsx(rows, cols, headers)
            return StreamingResponse(io.BytesIO(data),
                                     media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                     headers={"Content-Disposition": "attachment; filename=physical_report.xlsx"})
        data = _build_pdf("Physical Tracker Report", rows, cols, headers)
        return StreamingResponse(io.BytesIO(data), media_type="application/pdf",
                                 headers={"Content-Disposition": "attachment; filename=physical_report.pdf"})

    @api.get("/export/financial")
    async def export_financial(request: Request,
                               format: Literal["xlsx", "pdf"] = "xlsx",
                               high_court: Optional[str] = None,
                               component: Optional[str] = None,
                               reporting_period: Optional[str] = None,
                               district: Optional[str] = None,
                               user: dict = Depends(require_fully_authenticated)):
        _enforce_export_limit(user)
        lang = resolve_export_lang(request.headers.get("accept-language"))
        q = await _export_query(user, reporting_period, high_court, component, district)
        items = await db.financial_entries.find(q).sort("high_court", 1).to_list(20000)
        rows = serialize_fn(items)
        cols = ["high_court", "district", "component", "reporting_period", "fund_target",
                "fund_allocated", "fund_released", "fund_utilized",
                "utilisation_percent", "variance", "rag", "remarks"]
        headers = financial_headers(lang)
        if format == "xlsx":
            data = _build_xlsx(rows, cols, headers)
            return StreamingResponse(io.BytesIO(data),
                                     media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                     headers={"Content-Disposition": "attachment; filename=financial_report.xlsx"})
        data = _build_pdf("Financial Tracker Report", rows, cols, headers)
        return StreamingResponse(io.BytesIO(data), media_type="application/pdf",
                                 headers={"Content-Disposition": "attachment; filename=financial_report.pdf"})

    @api.get("/export/outcome")
    async def export_outcome(request: Request,
                             format: Literal["xlsx", "pdf"] = "xlsx",
                             high_court: Optional[str] = None,
                             subject: Optional[str] = None,
                             reporting_period: Optional[str] = None,
                             user: dict = Depends(require_fully_authenticated)):
        _enforce_export_limit(user)
        lang = resolve_export_lang(request.headers.get("accept-language"))
        q = await _export_query(user, reporting_period, high_court, None, None, subject)
        items = await db.outcome_entries.find(q).sort([("high_court", 1), ("subject", 1), ("kpi_id", 1)]).to_list(20000)
        rows = serialize_fn(items)
        cols = ["high_court", "component", "sub_component", "granularity", "district", "subject", "kpi_id", "kpi",
                "outcome_type", "periodicity", "baseline", "value",
                "computed_percent", "reporting_period", "remarks"]
        headers = outcome_headers(lang)
        if format == "xlsx":
            data = _build_xlsx(rows, cols, headers)
            return StreamingResponse(io.BytesIO(data),
                                     media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                     headers={"Content-Disposition": "attachment; filename=outcome_report.xlsx"})
        data = _build_pdf("Outcome Tracker Report", rows, cols, headers)
        return StreamingResponse(io.BytesIO(data), media_type="application/pdf",
                                 headers={"Content-Disposition": "attachment; filename=outcome_report.pdf"})

    # -------------------------------------------------------------------- CABINET BRIEF
    @api.get("/export/cabinet-brief")
    async def export_cabinet_brief(reporting_period: Optional[str] = None,
                                    user: dict = Depends(require_role("Admin", "Viewer"))):
        """Single-page Cabinet/Ministry brief: KPI summary + RAG distribution + top/bottom HCs."""
        _enforce_export_limit(user)
        extra = await approved_match_filter(db, reporting_period, False, user)
        pdf_bytes = await build_cabinet_brief_pdf(
            db, reporting_period, user["email"],
            compute_rag_fn, safe_div_fn, now_utc_fn, default_rag_thresholds, extra,
        )
        return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
                                 headers={"Content-Disposition": "attachment; filename=cabinet_brief.pdf"})

    @api.get("/export/dashboard")
    async def export_dashboard_pptx(
        reporting_period: Optional[str] = None,
        user: dict = Depends(require_role("Admin", "Viewer")),
    ):
        """PowerPoint export: KPI summary, trend, state RAG grid, top/bottom HC slides."""
        _enforce_export_limit(user)
        from ppt_export import build_dashboard_pptx
        from server import STATE_TO_HC

        extra = await approved_match_filter(db, reporting_period, False, user)
        ppt_bytes = await build_dashboard_pptx(
            db, scope_filter_fn, compute_rag_fn, safe_div_fn, user, reporting_period, extra, STATE_TO_HC,
        )
        return StreamingResponse(
            io.BytesIO(ppt_bytes),
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={"Content-Disposition": "attachment; filename=dashboard_brief.pptx"},
        )

    @api.get("/export/sla")
    async def export_sla(request: Request, format: Literal["xlsx"] = "xlsx", user: dict = Depends(require_fully_authenticated)):
        _enforce_export_limit(user)
        lang = resolve_export_lang(request.headers.get("accept-language"))
        from datetime import timedelta
        from period_policy import get_workflow_settings

        settings = await get_workflow_settings(db)
        sla_day = int(settings.get("sla_due_day", 10))
        today = now_utc_fn()
        period = today.strftime("%Y-%m")
        pers = await db.reporting_periods.find({"is_baseline": False}).sort("period", -1).to_list(50)
        target_period = next((p["period"] for p in pers if p["period"] <= period), period)
        due = today.replace(day=min(sla_day, 28), hour=0, minute=0, second=0, microsecond=0)
        if today.day > sla_day:
            nxt = today.replace(day=1) + timedelta(days=32)
            due = nxt.replace(day=min(sla_day, 28), hour=0, minute=0, second=0, microsecond=0)
        subs = await db.submissions.find({"reporting_period": target_period}).to_list(100)
        sub_map = {s["high_court"]: s for s in subs}
        hcs = [h["name"] for h in await db.high_courts.find({"active": True}).to_list(100)]
        rows = []
        for hc in hcs:
            sub = sub_map.get(hc)
            status = sub.get("status") if sub else "NotSubmitted"
            rows.append({
                "high_court": hc,
                "reporting_period": target_period,
                "status": status,
                "days_remaining": (due - today).days,
                "delinquent": status not in ("Submitted", "Approved") and today > due,
            })
        cols = ["high_court", "reporting_period", "status", "days_remaining", "delinquent"]
        headers = sla_headers(lang)
        data = _build_xlsx(rows, cols, headers)
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=sla_delinquency.xlsx"},
        )
