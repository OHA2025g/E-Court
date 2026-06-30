"""Scheduled job admin routes and weekly cabinet brief delivery."""
import base64
import logging
from typing import Callable, List

from fastapi import APIRouter, Depends, HTTPException, Response

from seed_constants import DEFAULT_RAG_THRESHOLDS

logger = logging.getLogger("pmis")

MAX_SCHEDULED_PDF_BYTES = 5 * 1024 * 1024  # 5 MB cap for stored delivery artifacts


def register_scheduler_routes(
    api: APIRouter,
    db,
    scheduler,
    require_role,
    serialize_fn,
    now_utc_fn,
    notify_fn: Callable,
    admin_emails_fn: Callable,
    cabinet_brief_recipients: List[str],
    build_cabinet_brief_pdf_fn: Callable,
    compute_rag_fn: Callable,
    safe_div_fn: Callable,
    default_rag_thresholds: dict = DEFAULT_RAG_THRESHOLDS,
):
    async def run_weekly_cabinet_brief():
        """Generate Cabinet Brief PDF, persist artifact, and notify admins."""
        today = now_utc_fn().strftime("%Y-%m")
        pers = await db.reporting_periods.find({"is_baseline": False}).sort("period", -1).to_list(50)
        period = next((p["period"] for p in pers if p["period"] <= today), None)
        label = next((p["label"] for p in pers if p["period"] == period), period)

        admin_emails = await admin_emails_fn()
        recipients = sorted(set((cabinet_brief_recipients or []) + admin_emails))

        from period_policy import approved_match_filter
        extra = await approved_match_filter(db, period, False, None)
        pdf_bytes = await build_cabinet_brief_pdf_fn(
            db, period, "system@scheduler",
            compute_rag_fn, safe_div_fn, now_utc_fn, default_rag_thresholds, extra,
        )
        if len(pdf_bytes) > MAX_SCHEDULED_PDF_BYTES:
            logger.error(
                "Cabinet brief PDF too large (%d bytes > %d); delivery skipped",
                len(pdf_bytes), MAX_SCHEDULED_PDF_BYTES,
            )
            await notify_fn(
                admin_emails,
                f"Weekly Cabinet Brief failed · {label}",
                f"Generated PDF exceeded size limit ({len(pdf_bytes) // 1024} KB).",
                kind="error", link="/schedules",
            )
            return

        delivery = {
            "job": "weekly_cabinet_brief",
            "ts": now_utc_fn(),
            "period": period,
            "period_label": label,
            "recipients": recipients,
            "status": "generated",
            "pdf_size_bytes": len(pdf_bytes),
            "pdf_base64": base64.b64encode(pdf_bytes).decode("ascii"),
        }
        result = await db.scheduled_deliveries.insert_one(delivery)
        delivery_id = str(result.inserted_id)

        from dashboard_agg import compute_dashboard_summary
        from narrative import narrative_for_export

        summary = await compute_dashboard_summary(
            db, lambda u: {}, compute_rag_fn, safe_div_fn,
            {"role": "Viewer"}, period, extra,
        )
        narrative_text = await narrative_for_export(db, summary, period)
        email_body = (
            f"The scheduled weekly brief for {label} has been generated ({len(pdf_bytes) // 1024} KB). "
            f"PDF attached. Also available from Admin → Scheduled deliveries.\n\n"
            f"Executive summary:\n{narrative_text}"
        )

        await notify_fn(
            admin_emails,
            f"Weekly Cabinet Brief generated · {label}",
            email_body,
            kind="info", link="/schedules",
            meta={"period": period, "scheduled": True, "delivery_id": delivery_id},
            also_email=True,
            email_attachment_base64=delivery["pdf_base64"],
            email_attachment_filename=f"cabinet_brief_{label.replace(' ', '_')}.pdf",
        )
        for extra in recipients:
            if extra not in admin_emails:
                await notify_fn(
                    [extra],
                    f"Weekly Cabinet Brief · {label}",
                    f"Attached: Cabinet Brief for {label}.",
                    kind="info", link="/public",
                    also_email=True,
                    email_attachment_base64=delivery["pdf_base64"],
                    email_attachment_filename=f"cabinet_brief_{label.replace(' ', '_')}.pdf",
                )
        logger.info(
            "Weekly Cabinet Brief job ran for period=%s recipients=%d pdf_bytes=%d delivery_id=%s",
            period, len(recipients), len(pdf_bytes), delivery_id,
        )

    @api.get("/admin/scheduled-jobs")
    async def list_scheduled_jobs(user: dict = Depends(require_role("Admin"))):
        jobs = [{"id": j.id, "name": j.name,
                 "next_run_time": j.next_run_time.isoformat() if j.next_run_time else None,
                 "trigger": str(j.trigger)} for j in scheduler.get_jobs()]
        return jobs

    @api.get("/admin/scheduled-deliveries")
    async def list_scheduled_deliveries(user: dict = Depends(require_role("Admin"))):
        items = await db.scheduled_deliveries.find(
            {}, {"pdf_base64": 0}
        ).sort("ts", -1).limit(50).to_list(50)
        return serialize_fn(items)

    @api.get("/admin/scheduled-deliveries/{delivery_id}/pdf")
    async def download_scheduled_brief(delivery_id: str, user: dict = Depends(require_role("Admin"))):
        from bson import ObjectId
        doc = await db.scheduled_deliveries.find_one({"_id": ObjectId(delivery_id)}, {"pdf_base64": 1, "period_label": 1})
        if not doc or not doc.get("pdf_base64"):
            raise HTTPException(status_code=404, detail="Brief PDF not found")
        pdf_bytes = base64.b64decode(doc["pdf_base64"])
        label = (doc.get("period_label") or "brief").replace(" ", "_")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename=cabinet_brief_{label}.pdf'},
        )

    @api.post("/admin/scheduled-deliveries/run-now")
    async def run_now(user: dict = Depends(require_role("Admin"))):
        """Trigger the Monday Cabinet Brief job manually (for verification)."""
        await run_weekly_cabinet_brief()
        return {"ok": True}

    return run_weekly_cabinet_brief
